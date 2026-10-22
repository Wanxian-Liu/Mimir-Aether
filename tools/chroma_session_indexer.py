"""Backfill Chroma session_messages collection from sessions_search.db (SEM-02)."""

from __future__ import annotations

import errno
import fcntl
import hashlib
import itertools
import json
import logging
import math
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

# --- RL-20261020-094: cross-process write mutex ---------------------------------
# F5 single-flight (gateway/session.py) only serialises writers *inside* one
# process. The gateway incremental path (sync_message_to_chroma) and a backfill
# script are two OS processes upserting the same HNSW segment files; nothing
# serialised them, and the 2026-10-18/19 incident pattern = two writers on one
# HNSW = index written bad, not recoverable.
#
# Semantics (deliberate):
#   * Granularity: per write operation (one batch upsert / one delete), NOT the
#     whole backfill run -- a full rebuild must not starve the gateway writer
#     for hours (bounded lock budget, not an ever-held lock).
#   * Wait: poll LOCK_EX|LOCK_NB every 50ms up to
#     MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S (default 60s). On expiry raise
#     ChromaWriteLockTimeout; callers keep their existing fail-open behaviour
#     and record it via note_index_failure() -> "skip, never wait forever".
#   * Release: flock is released when the fd closes (normal exit, SIGKILL,
#     explicit unlock) -- the kernel does it, so there is no stale-lock reaper
#     and no on-disk "locked" state to clean up after a crash.
#   * Lock file: ~/.mimiraether/data/chroma_write.lock -- a sidecar, deliberately
#     NOT inside the chroma dir: that dir gets copied/rebuilt/replaced, the lock
#     must outlive it.
#   * Re-entrancy: same-thread re-entry is free (depth counter); different
#     threads in one process serialise on an RLock before touching flock.
#   * Lock file deleted while a holder runs: each acquire re-checks that the
#     path still resolves to the held inode and re-opens if it does not.
DEFAULT_WRITE_LOCK_TIMEOUT_S = 60.0
_WRITE_LOCK_POLL_S = 0.05


class ChromaWriteLockTimeout(RuntimeError):
    """Raised when the cross-process chroma write lock cannot be taken in time."""


def chroma_write_lock_path() -> Path:
    from mimir_constants import get_mimir_home

    return Path(get_mimir_home()) / "data" / "chroma_write.lock"


def _write_lock_timeout_s() -> float:
    raw = os.getenv("MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S", "").strip()
    if not raw:
        return DEFAULT_WRITE_LOCK_TIMEOUT_S
    try:
        return max(0.0, float(raw))
    except ValueError:
        logger.warning(
            "bad MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S=%r, using %.1fs",
            raw,
            DEFAULT_WRITE_LOCK_TIMEOUT_S,
        )
        return DEFAULT_WRITE_LOCK_TIMEOUT_S


_WRITE_LOCK_RLOCK = threading.RLock()


# --- D2 (RL-20261020-094): cross-process write event ledger ---------------------
# 为什么要有账本：锁「有效」不能靠过程序员的自我陈述，也不能靠等 24h。
# 只有 begin/end 成对出现、且不同 pid 的区间不重叠，才是「互斥真的生效」的证据。
# 纪律：
#   * 只记录，不参与控制流；任何异常都吞掉（写账本失败绝不能让写入失败）。
#   * 只在 depth 0->1 时记 begin（同线程重入不算一次跨进程临界区）。
#   * 取锁失败记 phase=acquire_failed + result=timeout/error，**不记 begin**，
#     这样「unpaired」永远等于「真崩溃」，不会被超时污染（D13 判据）。
#   * role 由 MIMIR_CHROMA_LOCK_ROLE 指定（writer/probe/backfill），默认 writer。
def _events_path() -> Path:
    from mimir_constants import get_mimir_home

    return Path(get_mimir_home()) / "data" / "chroma_write_events.jsonl"


def _events_enabled() -> bool:
    return os.getenv("MIMIR_CHROMA_EVENTS", "1").strip() not in ("0", "false", "no")


_EVENT_SEQ = itertools.count(1)
_EVENT_SEQ_LOCK = threading.Lock()
_NONCE_SEQ = itertools.count(1)


def _emit_event(rec: Dict[str, Any]) -> None:
    """追加一行事件（fail-open：账本坏了也不能阻断写入）。

    第 2 批：每条事件带**进程内单调 seq**，且「取号 + 写入」在同一把线程锁内完成
    —— 这样文件里的行序与 seq 序在同一进程内一致。丢行会留下 seq 空洞，审计器
    据此能指出「证据缺了几条」，而不是只看到「剩下的都对」。
    """
    if not _events_enabled():
        return
    try:
        path = _events_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        rec.setdefault("ts", time.time())
        rec.setdefault("role", os.getenv("MIMIR_CHROMA_LOCK_ROLE", "writer"))
        rec.setdefault("pid", os.getpid())
        rec.setdefault("ppid", os.getppid())
        rec.setdefault("tid", threading.get_ident())
        with _EVENT_SEQ_LOCK:
            rec.setdefault("seq", next(_EVENT_SEQ))
            line = json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n"
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line)
    except Exception:  # noqa: BLE001 - 观测面永远不许反噬主流程
        logger.debug("chroma write event emit failed", exc_info=True)


class _WriteLockState:
    def __init__(self) -> None:
        self.depth = 0
        self.fd: Optional[int] = None
        # 094c: in-band nonce identifies the locked inode (inode numbers are
        # reused on this filesystem, so st_ino alone cannot prove ownership).
        self.nonce: Optional[str] = None


_WRITE_LOCK_STATE = _WriteLockState()


def _open_lock_fd() -> int:
    path = chroma_write_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    return os.open(str(path), os.O_CREAT | os.O_RDWR, 0o644)


def _write_lock_nonce() -> str:
    """S3（第 2 批）：**每次真正的取锁**都给一个新 nonce。

    B12b 之前 nonce 只在 fd 首次打开时生成一次（fd 终生不关），于是同一进程的
    所有临界区共用同一个配对键 —— 账本里 71 条 begin 只有 7 个 nonce，配对实质
    退化成「按 pid 排队」。丢一行就会让该 pid 之后整段错配（hold_ms 失真、
    甚至造出假 overlaps）。

    末尾序号保证「同一纳秒内两次取锁」也不撞键；nonce 同时还承担「我锁住的 fd
    就是路径上那个文件」的带内证明，所以唯一性是它的语义前提，不是锦上添花。
    """
    return f"{os.getpid()}:{time.time_ns()}:{next(_NONCE_SEQ)}"


def _read_lock_file_token(path: Path) -> Optional[str]:
    """Token currently visible at *path* (None when the path is gone)."""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read(200).strip()
    except (FileNotFoundError, PermissionError):
        return None


def _lock_holder_desc() -> str:
    """B4 (RL-20261020-094): name the *holder* of the write lock.

    Diagnostics only -- this function feeds the timeout message, never control
    flow. Every path returns a string; nothing here raises. When the token
    cannot be read we say ``unknown``: an unclear message is acceptable, masking
    the original ChromaWriteLockTimeout is not.

    Format: ``pid=<pid> (<alive|gone|unknown>) token=<pid>:<ns>``.
    """
    try:
        token = _read_lock_file_token(chroma_write_lock_path())
        if not token:
            return "unknown"
        if ":" not in token:
            # Printed before the separator landed (truncated write) or a legacy
            # shape: we cannot tell pid from noise -- do not invent a holder.
            return f"unknown token={token[:64]}"
        head = token.split(":", 1)[0].strip()
        try:
            pid = int(head)
        except (TypeError, ValueError):
            # Half-written or legacy token (truncated write, pre-B1 format):
            # report what we saw, never die on a parse.
            return f"unknown token={token[:64]}"
        if pid <= 0:
            return f"unknown token={token[:64]}"
        # /proc is the cheap liveness probe. os.path.exists() cannot tell
        # "pid gone" from "procfs not mounted / not readable" (both False), so
        # probe procfs itself: if it is unusable we say "unknown", never "gone"
        # -- a false "gone" sends the responder hunting a live holder.
        try:
            procfs_usable = os.path.exists("/proc/self") or os.path.exists("/proc/1")
        except OSError:  # pragma: no cover - exists() swallows errors
            procfs_usable = False
        if not procfs_usable:
            return f"pid={pid} (unknown) token={token[:64]}"
        try:
            alive = os.path.exists(f"/proc/{pid}")
        except OSError:  # pragma: no cover - exists() swallows errors
            return f"pid={pid} (unknown) token={token[:64]}"
        return f"pid={pid} ({'alive' if alive else 'gone'}) token={token[:64]}"
    except Exception:  # noqa: BLE001 - diagnostics must never mask the real error
        logger.debug("chroma lock holder description failed", exc_info=True)
        return "unknown"


def _acquire_flock(deadline: float) -> None:
    """Take the cross-process lock, proving our fd is the *visible* lock file."""
    state = _WRITE_LOCK_STATE
    while True:
        if state.fd is None:
            state.fd = _open_lock_fd()
            state.nonce = _write_lock_nonce()
        try:
            fcntl.flock(state.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            if time.monotonic() >= deadline:
                raise ChromaWriteLockTimeout(
                    "chroma write lock not acquired within "
                    f"{_write_lock_timeout_s():.1f}s (another process holds "
                    f"{chroma_write_lock_path()}) "
                    f"holder={_lock_holder_desc()}"
                ) from exc
            time.sleep(_WRITE_LOCK_POLL_S)
            continue

        # We own this fd's flock. Prove the fd is still the file at the path:
        # if the path was unlinked/replaced, we locked an inode nobody else can
        # see and the mutex would be void. Stamp our nonce and read it back.
        #
        # S3：每次真正的取锁都换新 nonce（B12b 之前每进程只有一个）。
        state.nonce = _write_lock_nonce()
        try:
            os.ftruncate(state.fd, 0)
            os.lseek(state.fd, 0, os.SEEK_SET)
            os.write(state.fd, state.nonce.encode("utf-8"))
        except OSError:  # pragma: no cover - stamping is best-effort
            logger.debug("chroma write lock nonce write failed", exc_info=True)
        if _read_lock_file_token(chroma_write_lock_path()) == state.nonce:
            return

        logger.warning(
            "chroma write lock file at %s is not the inode we locked "
            "(deleted/replaced under us); re-opening",
            chroma_write_lock_path(),
        )
        try:
            fcntl.flock(state.fd, fcntl.LOCK_UN)
        finally:
            try:
                os.close(state.fd)
            finally:
                state.fd = None
                state.nonce = None
        if time.monotonic() >= deadline:
            raise ChromaWriteLockTimeout(
                "chroma write lock file kept being replaced under us: "
                f"{chroma_write_lock_path()} holder={_lock_holder_desc()}"
            )


class _WriteLockGuard:
    """Re-entrant, thread-safe, process-exclusive guard for chroma writes."""

    __slots__ = ("_entered", "_t0", "_hold_t0", "_emitted_begin", "_nonce_seen")

    def __init__(self) -> None:
        self._entered = False
        self._t0: Optional[float] = None
        self._hold_t0: Optional[float] = None
        self._emitted_begin = False
        self._nonce_seen: Optional[str] = None

    def __enter__(self) -> "_WriteLockGuard":
        # RL-20261020-094 B3: the in-process wait needs a deadline too. A bare
        # acquire() blocks as long as another thread holds the RLock, silently
        # overrunning MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S (measured 1.80s against a
        # 0.3s budget) -- the caller then fails open past its own deadline with
        # nothing logged. Same-thread re-entry is unaffected: RLock.acquire
        # returns True immediately when the current thread already owns it.
        self._t0 = time.monotonic()
        _budget_s = _write_lock_timeout_s()
        if not _WRITE_LOCK_RLOCK.acquire(timeout=_budget_s):
            # We never took the lock, so there is nothing to release here.
            _emit_event({
                "phase": "acquire_failed",
                "result": "timeout",
                "scope": "thread",
                "budget_s": round(_budget_s, 3),
                "waited_ms": round((time.monotonic() - self._t0) * 1000.0, 3),
            })
            raise ChromaWriteLockTimeout(
                "chroma write lock not acquired within "
                f"{_budget_s:.1f}s (another thread in this "
                "process holds it; same-process contention) "
                "holder=thread:"
                f"{threading.current_thread().name} (same process)"
            )
        try:
            state = _WRITE_LOCK_STATE
            real = state.depth == 0
            if real:
                _acquire_flock(time.monotonic() + _write_lock_timeout_s())
            state.depth += 1
        except BaseException as exc:
            _WRITE_LOCK_RLOCK.release()
            _emit_event({
                "phase": "acquire_failed",
                "result": "timeout" if isinstance(exc, ChromaWriteLockTimeout) else "error",
                "scope": "process",
                "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                "waited_ms": round((time.monotonic() - (self._t0 or time.monotonic())) * 1000.0, 3),
            })
            raise
        self._entered = True
        if real:
            # 只有真正拿到跨进程 flock 才记 begin（重入不重复记账）
            self._emitted_begin = True
            self._nonce_seen = state.nonce
            self._hold_t0 = time.monotonic()
            _emit_event({"phase": "begin", "nonce": state.nonce,
                         "wait_ms": round((self._hold_t0 - self._t0) * 1000.0, 3)})
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        # S4：区间右端必须取在**解锁之前**。B12b 之前 end.ts 由 _emit_event 在
        # 「unlock + 释放 RLock + 组 JSON + open/write」之后才取 ⇒ 区间里混进了
        # 收尾开销（实测 +2.93ms），hold_ms 与 ts 两者同时偏移、互相自洽，
        # 所以「ts 与 hold_ms 一致」这条断言抓不到它。先取时刻再解锁。
        end_ts = time.time()
        hold_ms = round(
            (time.monotonic() - (self._hold_t0 or self._t0 or time.monotonic())) * 1000.0, 3
        )
        try:
            state = _WRITE_LOCK_STATE
            state.depth -= 1
            if state.depth == 0 and state.fd is not None:
                try:
                    fcntl.flock(state.fd, fcntl.LOCK_UN)
                except OSError:  # never mask the body's exception
                    logger.debug("chroma write lock release failed", exc_info=True)
        finally:
            if self._entered:
                _WRITE_LOCK_RLOCK.release()
                self._entered = False
            if self._emitted_begin:
                _emit_event({
                    "phase": "end",
                    "nonce": self._nonce_seen,
                    "result": "error" if exc_type else "ok",
                    "ts": end_ts,
                    "hold_ms": hold_ms,
                })
                self._emitted_begin = False
        return False


def chroma_write_lock() -> _WriteLockGuard:
    """Exclusive write guard shared by every writer (thread and process)."""
    return _WriteLockGuard()



# --- Loki 四条 fallback 加固 (议题六真根因修复) ---
# 维度不匹配 (hash 384 vs bge-m3 1024) 曾导致 semantic_hit_rate 静默假 0.0。
# 规则: 告警升级 error 级 + 写 audit_log + 连续失败熔断 + 启动 fail-fast。
_EMBED_RESOLVE_FAILURES = 0
EMBED_RESOLVE_CIRCUIT_LIMIT = 3  # 连续失败达此数 -> 熔断 (后续直接 raise)


def _embedding_audit(event: str, detail: str, level: str = "error") -> None:
    """追加一行 embedding fallback 审计日志 (fail-open: 审计失败不阻断主流程)。"""
    try:
        import json
        import time as _time

        from mimir_constants import get_mimir_home

        log_path = Path(get_mimir_home()) / "data" / "audit_log.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"ts": _time.time(), "level": level, "event": event, "detail": detail},
                    ensure_ascii=False,
                )
                + "\n"
            )
    except Exception as exc:  # noqa: BLE001 - audit must never mask the real error
        logger.debug("embedding audit log write failed: %s", exc)


_INDEX_FAILURE_COUNTS: Dict[str, int] = {}


def _index_failure_path() -> Path:
    from mimir_constants import get_mimir_home

    return Path(get_mimir_home()) / "data" / "index_failure_counts.json"


def index_failure_counts() -> Dict[str, Any]:
    """Read the on-disk index-failure counter (monitor-facing read path)."""
    try:
        with open(_index_failure_path(), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001 - missing/corrupt counter reads as empty
        return {}


def note_index_failure(stage: str, exc: BaseException, *, sink: str = "") -> None:
    """Index-side failure must be audible + counted, never debug-only.

    P0 diagnosis 2026-10-05 (S8-2): three fail-open paths logged at debug only,
    so a session that lost 91% of its index left no trace on disk.
    """
    count = _INDEX_FAILURE_COUNTS.get(stage, 0) + 1
    _INDEX_FAILURE_COUNTS[stage] = count
    detail = f"{type(exc).__name__}: {exc}"
    logger.warning(
        "[INDEX-FAIL] stage=%s count=%d sink=%s %s", stage, count, sink or "-", detail
    )
    _embedding_audit("index_failure", f"stage={stage} count={count} {detail}", level="warning")
    try:
        path = _index_failure_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = index_failure_counts()
        rec = dict(data.get(stage) or {})
        rec.update(
            {
                "count": int(rec.get("count", 0)) + 1,
                "last_ts": time.time(),
                "last_error": detail,
                "sink": sink or "-",
            }
        )
        data[stage] = rec
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as audit_exc:  # noqa: BLE001 - counter must not mask the real error
        logger.debug("index failure counter write failed: %s", audit_exc)


def _embed_resolve_failed(reason: str) -> None:
    """连续失败计数 + 告警升级 error + audit_log + 熔断判定 (fail-fast)。"""
    global _EMBED_RESOLVE_FAILURES
    _EMBED_RESOLVE_FAILURES += 1
    _embedding_audit(
        "embedding_resolve_failed",
        f"{reason} (failure {_EMBED_RESOLVE_FAILURES}/{EMBED_RESOLVE_CIRCUIT_LIMIT})",
    )
    logger.error(
        "embedding resolve FAILED (%d/%d): %s",
        _EMBED_RESOLVE_FAILURES,
        EMBED_RESOLVE_CIRCUIT_LIMIT,
        reason,
    )
    if _EMBED_RESOLVE_FAILURES >= EMBED_RESOLVE_CIRCUIT_LIMIT:
        _embedding_audit(
            "embedding_circuit_open",
            f"after {_EMBED_RESOLVE_FAILURES} consecutive failures",
        )
        logger.error(
            "embedding resolve circuit OPEN after %d failures - fail-fast",
            _EMBED_RESOLVE_FAILURES,
        )
        raise RuntimeError(
            f"embedding resolve circuit breaker OPEN after {_EMBED_RESOLVE_FAILURES} consecutive "
            f"failures: {reason}. Fix MIMIR_EMBED_MODEL / venv deps, then restart."
        )

COLLECTION_NAME = "session_messages"
DEFAULT_EMBED_DIM = 384
DEFAULT_BATCH_SIZE = 128


@dataclass
class ChromaBackfillStats:
    messages_indexed: int = 0
    messages_skipped: int = 0
    batches: int = 0


@dataclass(frozen=True)
class IndexedMessage:
    message_id: int
    session_id: str
    role: str
    content: str
    source: str
    timestamp: float
    tool_name: Optional[str] = None


def chroma_available() -> bool:
    """Return True when chromadb is importable."""
    try:
        import chromadb  # noqa: F401

        return True
    except ImportError:
        return False


def message_doc_id(session_id: str, message_id: int) -> str:
    """Stable Chroma document id for idempotent upsert."""
    return f"{session_id}:{message_id}"


def hash_embed_text(text: str, *, dim: int = DEFAULT_EMBED_DIM) -> List[float]:
    """Deterministic offline embedding (tier0 / dev without ML deps)."""
    vec = [0.0] * dim
    if not text:
        return vec
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    for i in range(dim):
        byte = digest[i % len(digest)]
        vec[i] = (byte / 255.0) * 2.0 - 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def hash_embed_batch(texts: Sequence[str], *, dim: int = DEFAULT_EMBED_DIM) -> List[List[float]]:
    return [hash_embed_text(t, dim=dim) for t in texts]


class HashEmbeddingFunction:
    """Chroma-compatible embedding function using hash_embed_batch."""

    def __init__(self, dim: int = DEFAULT_EMBED_DIM) -> None:
        self._dim = dim

    def __call__(self, input: Sequence[str]) -> List[List[float]]:
        return hash_embed_batch(list(input), dim=self._dim)

    def embed_query(self, input: Sequence[str]) -> List[List[float]]:
        return self.__call__(input)

    def name(self) -> str:
        return "hash_embedding"

    def get_config(self) -> Dict[str, Any]:
        return {"dim": self._dim}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "HashEmbeddingFunction":
        return HashEmbeddingFunction(dim=int(config.get("dim", DEFAULT_EMBED_DIM)))


def get_mimir_chroma_dir() -> Path:
    from mimir_constants import get_mimir_chroma_dir as _path

    return _path()


class LocalSentenceTransformerEmbeddingFunction:
    """Chroma-compatible embedding function backed by a local sentence-transformers
    model (e.g. ~/models/bge-m3). Retrieval-optimized:
    max_seq_length=512 truncation, 16 threads, L2-normalized vectors (cosine).

    P0 (2026-08-11): real bge-m3 replaces the deterministic hash placeholder.
    """

    DEFAULT_MAX_SEQ_LENGTH = 512
    # 2026-10-21 P0: 16 -> 4。实测（同机真实负载，load≈8.6，另有三进程占 9GB）：
    #   threads=16 median 10.20s  |  8 median 0.60s  |  4 median 0.19s  |  2 median 0.16s
    # 单条短查询在 16 线程下比 4 线程慢 53.8x —— 16 核机器上再向 torch 要 16 线程
    # 属线程超订，是「语义延迟 10s > semantic_timeout_s=5.0 ⇒ 每条查询必降级」的真因。
    # 可用 MIMIR_EMBED_NUM_THREADS 覆写（批式回填若确需更多线程再调，须带前后读数）。
    DEFAULT_NUM_THREADS = 4

    def __init__(
        self,
        model_path: str,
        max_seq_length: int = DEFAULT_MAX_SEQ_LENGTH,
        num_threads: int = DEFAULT_NUM_THREADS,
    ) -> None:
        self._model_path = model_path
        self._max_seq_length = max_seq_length
        _env_threads = os.getenv("MIMIR_EMBED_NUM_THREADS", "").strip()
        if _env_threads.isdigit():
            num_threads = max(1, int(_env_threads))
        try:
            import torch
            import sentence_transformers

            torch.set_num_threads(num_threads)
            self._model = sentence_transformers.SentenceTransformer(
                model_path, device="cpu"
            )
            self._model.max_seq_length = max_seq_length
        except Exception as exc:  # noqa: BLE001 - re-raise with context
            raise ImportError(
                f"local ST model {model_path} failed to load: {exc}"
            ) from exc

    def __call__(self, input: Sequence[str]) -> List[List[float]]:
        import numpy as np

        vecs = self._model.encode(
            list(input),
            normalize_embeddings=True,
            batch_size=64,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        if isinstance(vecs, np.ndarray):
            return [v.tolist() for v in vecs]
        return [v.tolist() for v in vecs]

    def embed_query(self, input: Sequence[str]) -> List[List[float]]:
        return self.__call__(input)

    def name(self) -> str:
        return "local_sentence_transformer"

    def get_config(self) -> Dict[str, Any]:
        return {
            "model_path": self._model_path,
            "max_seq_length": self._max_seq_length,
        }

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "LocalSentenceTransformerEmbeddingFunction":
        return LocalSentenceTransformerEmbeddingFunction(
            model_path=str(config.get("model_path", "")),
            max_seq_length=int(config.get("max_seq_length", LocalSentenceTransformerEmbeddingFunction.DEFAULT_MAX_SEQ_LENGTH)),
        )


def _build_embedding_function(model: Optional[str] = None):
    """Pick embedding backend: local ST model (e.g. bge-m3) when configured, else
    chromadb ST by name, else deterministic hash (tier0 / no ML deps)."""
    global _EMBED_RESOLVE_FAILURES
    model = (model or os.getenv("MIMIR_EMBED_MODEL", "")).strip()
    if model:
        # 1) local path on disk -> retrieval-optimized local embedding (P0: bge-m3)
        model_path = Path(model).expanduser()
        if model_path.is_dir():
            try:
                ef = LocalSentenceTransformerEmbeddingFunction(str(model_path))
                _EMBED_RESOLVE_FAILURES = 0  # 成功 -> 复位熔断计数
                return ef
            except Exception as exc:  # noqa: BLE001 - fail-fast per Loki
                _embed_resolve_failed(
                    f"MIMIR_EMBED_MODEL={model} local ST load failed: {exc}"
                )
                # 熔断未开且未达上限 -> 继续尝试 chromadb ST by name
        # 2) model name resolvable via chromadb sentence-transformers extras
        try:
            from chromadb.utils import embedding_functions

            ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model)
            _EMBED_RESOLVE_FAILURES = 0  # 成功 -> 复位熔断计数
            return ef
        except (ImportError, ValueError):  # chromadb 缺 ST 时抛 ValueError 而非 ImportError
            _embed_resolve_failed(
                f"MIMIR_EMBED_MODEL={model} but sentence-transformers/chromadb extras unavailable"
            )
        # 3) 配置了模型但两条路都失败 -> 绝不静默降级 hash (维度不匹配 -> 假 0.0)
        raise RuntimeError(
            f"MIMIR_EMBED_MODEL={model} configured but unresolvable; refusing hash fallback "
            f"(dimension mismatch would fake semantic_hit_rate=0.0). "
            f"Run under .venv with torch+sentence-transformers, or unset MIMIR_EMBED_MODEL "
            f"to allow tier0 hash embeddings."
        )
    return HashEmbeddingFunction()


# 2026-10-21 P0: 模型加载缓存。实测证据（受控实验，单查询孤立运行）：
#   COLD 17.63s / WARM 13.92s，两次都打 "Loading weights" ⇒ 每次 resolve 都从盘重载
#   bge-m3（RSS 2450→2779MB）。真实语义延迟 ≈13.9s 而 semantic_timeout_s=5.0
#   ⇒ 生产每条查询必然降级为关键字（semantic_hits 逐行等于 like_hits 的成因）。
# 修法：以 model 标识为键做进程内单例；负控（不同 model_path 不得串味）见
#   tests/tools/test_embedding_function_cache.py
_EF_CACHE: Dict[str, Any] = {}
_EF_CACHE_LOCK = None


def resolve_embedding_function(model: Optional[str] = None):
    """Cached front-end for :func:`_build_embedding_function`.

    Loading bge-m3 costs ~14s and ~2.2GB; a fresh instance per query makes the
    semantic arm structurally unable to meet its own timeout budget.
    """
    global _EF_CACHE_LOCK
    key = (model or os.getenv("MIMIR_EMBED_MODEL", "")).strip() or "__hash__"
    cached = _EF_CACHE.get(key)
    if cached is not None:
        return cached

    if _EF_CACHE_LOCK is None:
        import threading as _threading

        _EF_CACHE_LOCK = _threading.Lock()
    with _EF_CACHE_LOCK:
        cached = _EF_CACHE.get(key)
        if cached is not None:
            return cached
        ef = _build_embedding_function(model)
        _EF_CACHE[key] = ef
        return ef


def clear_embedding_function_cache() -> None:
    """Test/ops hook: drop cached models (e.g. after swapping MIMIR_EMBED_MODEL)."""
    _EF_CACHE.clear()


# Garbage / non-retrieval content prefixes (P0 audit 2026-08-11: system error
# boilerplate and placeholder text was polluting the semantic index — e.g. 39x
# "抱歉,任务迭代次数已达上限" occupied HippoRAG2 query top-5 slots).
# NOTE: prefix match only — substring match would kill legitimate conversation
# that merely *mentions* these strings (e.g. a user asking what
# "[Old tool output cleared ...]" means).
_GARBAGE_PREFIXES: Tuple[str, ...] = (
    "抱歉,任务迭代次数已达上限",
    "抱歉,模型调用失败,请稍后重试",
    "(No response generated)",
    "[Old tool output cleared",
    "[CONTEXT COMPACTION",
)


def is_garbage_content(content: Optional[str]) -> bool:
    """True when content has no retrieval value (system errors / placeholders).

    Conservative prefix rules: never substring-match, so real conversation that
    quotes a placeholder stays indexable.
    """
    stripped = (content or "").strip()
    if not stripped:
        return True
    return stripped.startswith(_GARBAGE_PREFIXES)


def iter_indexable_messages(db_path: Path) -> Iterator[IndexedMessage]:
    """Yield searchable rows from sessions_search.db (garbage-filtered)."""
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.execute(
            """
            SELECT m.id, m.session_id, m.role, m.content, m.tool_name, m.timestamp,
                   COALESCE(s.source, 'unknown')
            FROM messages m
            LEFT JOIN sessions s ON m.session_id = s.session_id
            WHERE m.content IS NOT NULL AND TRIM(m.content) != ''
            ORDER BY m.id
            """
        )
        for row in cursor:
            message_id, session_id, role, content, tool_name, timestamp, source = row
            if is_garbage_content(content):
                continue
            yield IndexedMessage(
                message_id=int(message_id),
                session_id=str(session_id),
                role=str(role or "unknown"),
                content=str(content),
                source=str(source or "unknown"),
                timestamp=float(timestamp or 0.0),
                tool_name=str(tool_name) if tool_name else None,
            )
    finally:
        conn.close()


def _message_metadata(msg: IndexedMessage) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "session_id": msg.session_id,
        "message_id": msg.message_id,
        "role": msg.role,
        "source": msg.source,
        "timestamp": msg.timestamp,
    }
    if msg.tool_name:
        meta["tool_name"] = msg.tool_name
    return meta


# 094b: embedding computed OUTSIDE the write lock (RL-20261020-094 B2).
# chroma resolves documents -> vectors lazily *inside* collection.upsert when it
# is called with documents=, so the cross-process lock was held for the whole
# bge-m3 pass (measured 2026-10-21: 128-doc batch held 35.1s / 35.2s, single
# message 0.343s) and every other writer starved meanwhile. Budget: the lock
# covers the write only. Embedding is a pure function of (EF, documents) and the
# upsert stays idempotent by doc id, so computing it before the lock cannot
# change what lands.
# Two fallbacks keep behaviour identical, never "recompute inside the lock":
#   * no usable EF (missing / not callable) -> legacy documents= path, in lock;
#   * EF returned something that is not an embedding matrix (mock protheses,
#     ragged rows) -> same legacy path, logged at warning.
# A raising EF is NOT swallowed: it propagates to the caller's existing
# fail-open + note_index_failure() path, tagged with batch size (L79).
_EMBED_OUTSIDE_LOCK_CHUNK = 32


def _coerce_embeddings(raw: Any, expected: int) -> Optional[List[Any]]:
    """Return ``raw`` only if it is a well-formed embedding matrix.

    Well-formed = exactly ``expected`` rows, every row a non-empty sequence of
    numbers, all rows the same width. Rows are returned *as produced* so the
    vectors reach chroma bit-identical. Anything else -> None (caller falls back
    to the legacy path instead of writing a shape chroma would reject).
    """
    try:
        rows = list(raw)
    except Exception:  # noqa: BLE001 - unusable iterable == not an embedding matrix
        return None
    if expected == 0 or len(rows) != expected:
        return None
    dim = None
    for row in rows:
        try:
            values = [float(v) for v in row]
        except Exception:  # noqa: BLE001 - non-numeric row
            return None
        if not values:
            return None
        if dim is None:
            dim = len(values)
        elif len(values) != dim:
            return None
    return rows


def _embed_outside_lock(collection: Any, documents: Sequence[str]) -> Optional[List[Any]]:
    """Pre-compute embeddings before taking the write lock.

    Returns None when the legacy in-lock path must be used (no usable EF, or EF
    produced something we cannot prove is an embedding matrix). Raises only when
    the EF itself raises -- deliberately no "retry inside the lock": a retry
    would re-hold the lock for the same cost and would hide the failure from the
    caller's existing fail-open + note_index_failure() path.
    """
    if not documents:
        return None
    ef = getattr(collection, "_embedding_function", None)
    if ef is None or not callable(ef):
        logger.debug(
            "embed_outside_lock=unavailable batch_size=%d docs=%d ef=%s",
            len(documents),
            len(documents),
            type(ef).__name__ if ef is not None else "None",
        )
        return None
    raw: List[Any] = []
    try:
        for start in range(0, len(documents), _EMBED_OUTSIDE_LOCK_CHUNK):
            chunk = list(documents[start : start + _EMBED_OUTSIDE_LOCK_CHUNK])
            raw.extend(ef(chunk))
    except Exception as exc:
        raise RuntimeError(
            f"embed_outside_lock failed batch_size={len(documents)} docs={len(documents)} "
            f"ef={type(ef).__name__} chunk={_EMBED_OUTSIDE_LOCK_CHUNK}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc
    rows = _coerce_embeddings(raw, len(documents))
    if rows is None:
        logger.warning(
            "embed_outside_lock=invalid_shape batch_size=%d docs=%d ef=%s "
            "-> legacy in-lock path",
            len(documents),
            len(documents),
            type(ef).__name__,
        )
        return None
    return rows


def _upsert_batch(collection: Any, batch: Sequence[IndexedMessage]) -> int:
    ids = [message_doc_id(m.session_id, m.message_id) for m in batch]
    documents = [m.content for m in batch]
    metadatas = [_message_metadata(m) for m in batch]
    # Embedding (the expensive part) happens before the lock; only the write
    # itself is serialised across processes. Single call site on purpose: the
    # coverage gate counts guarded write sites, and two branches would count as
    # two writers.
    embeddings = _embed_outside_lock(collection, documents)
    write = {"ids": ids, "documents": documents, "metadatas": metadatas}
    if embeddings is not None:
        write["embeddings"] = embeddings
    with chroma_write_lock():
        collection.upsert(**write)
    return len(batch)


def get_chroma_collection(
    chroma_dir: Optional[Path] = None,
    *,
    embedding_function: Any = None,
):
    """Open or create the session_messages collection."""
    if not chroma_available():
        raise ImportError(
            "chromadb is not installed; pip install chromadb to use semantic index"
        )
    import chromadb

    root = chroma_dir or get_mimir_chroma_dir()
    root.mkdir(parents=True, exist_ok=True)
    ef = embedding_function if embedding_function is not None else resolve_embedding_function()
    # 094d: schema bootstrap is a write -- inside the lock.
    # PersistentClient() itself bootstraps the SQLite schema; two processes
    # doing that on one dir die with "table collections already exists"
    # (measured 2026-10-21, RL-094 concurrency probe). bge-m3 resolution stays
    # outside the lock so a 14s model load never blocks another writer.
    with chroma_write_lock():
        client = chromadb.PersistentClient(path=str(root))
        return client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )


def chroma_incremental_enabled() -> bool:
    """Gateway/indexer incremental upsert when chromadb is available (IQ-EVO-11)."""
    if not chroma_available():
        return False
    try:
        from tools.chroma_guard import chroma_usable

        if not chroma_usable():
            return False
    except Exception:  # 守卫自身不得拖垮索引路径
        pass
    return os.environ.get("MIMIR_CHROMA_INCREMENTAL", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


_cached_chroma_collection: Any = None


def _get_incremental_collection() -> Any:
    global _cached_chroma_collection
    if _cached_chroma_collection is None:
        _cached_chroma_collection = get_chroma_collection()
    return _cached_chroma_collection


def reset_chroma_collection_cache() -> None:
    """Test helper: drop lazy collection cache."""
    global _cached_chroma_collection
    _cached_chroma_collection = None


def upsert_indexed_messages(
    messages: Sequence[IndexedMessage],
    *,
    collection: Any = None,
) -> int:
    """Upsert one or more messages into Chroma (idempotent by doc id)."""
    if not messages:
        return 0
    if collection is None:
        collection = _get_incremental_collection()
    batch_size = DEFAULT_BATCH_SIZE
    indexed = 0
    batch: List[IndexedMessage] = []
    for msg in messages:
        batch.append(msg)
        if len(batch) >= batch_size:
            indexed += _upsert_batch(collection, batch)
            batch = []
    if batch:
        indexed += _upsert_batch(collection, batch)
    return indexed


def sync_message_to_chroma(msg: IndexedMessage) -> bool:
    """Incremental upsert for a single message row (fail-open).

    Garbage guard (P0 audit 2026-08-11): incremental path bypasses
    iter_indexable_messages() filtering, so system-error boilerplate would
    re-pollute the index after backfill purge. Skip garbage at the entry.
    """
    if not chroma_incremental_enabled():
        return False
    if is_garbage_content(msg.content):
        return False
    try:
        upsert_indexed_messages([msg])
        return True
    except Exception as exc:
        note_index_failure("incremental_upsert", exc, sink="chroma_session_indexer")
        return False


def delete_session_chroma_documents(session_id: str, *, collection: Any = None) -> bool:
    """Remove all Chroma docs for a session (before full re-sync).

    B12b：返回 bool 而不是 None。原来它吞掉一切异常并返回 None，于是 d11/d14 的
    finally 只能证明「函数被调用了」，不能证明「残行真的删掉了」。现在：
      True  = 删除完成（含本来就无残留）
      False = 无法确认删除（chroma 不可用 / 取集合失败 / 删除抛错，均已记 note_index_failure）
    调用方若不关心返回值可继续忽略（向后兼容）。
    """
    if not chroma_available():
        return False
    if collection is None:
        try:
            collection = _get_incremental_collection()
        except Exception as exc:
            note_index_failure("delete_session_docs_handle", exc, sink="chroma_session_indexer")
            logger.debug("chroma get collection for delete failed: %s", exc)
            return False
    try:
        with chroma_write_lock():
            collection.delete(where={"session_id": session_id})
        return True
    except Exception as exc:
        note_index_failure("delete_session_docs", exc, sink="chroma_session_indexer")
        logger.debug("chroma delete session %s failed: %s", session_id, exc)
        return False


def prune_session_chroma_orphans(
    session_id: str,
    like_db_path: Path | str,
    *,
    collection: Any = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Drop Chroma docs for one session whose SQLite source row no longer exists.

    Incremental transcript rewrites (``reindex_session_transcript`` with a warm
    watermark) DELETE the changed tail rows and re-INSERT them, so the new rows
    carry *new* row ids and the pre-rewrite ``{session}:{id}`` docs are stranded.
    The full-resync branch (delete + re-embed the whole session) never runs on
    that path -- deliberately, because re-embedding is what the 2026-10-05 P0
    truncated at the 30s off-loop budget -- so nothing pruned them
    (2026-10-12 measurement: 1454 orphans, 1421 from a single rewrite).

    This deletes **stale ids only**: no embedding is computed, and docs whose
    source row still exists are never touched (kept prefix stays intact).

    Returns a reading dict: ``chroma_docs`` / ``wanted`` / ``orphans`` / ``deleted``.
    """
    out: Dict[str, Any] = {
        "session_id": session_id,
        "chroma_docs": 0,
        "wanted": 0,
        "orphans": 0,
        "deleted": 0,
    }
    if not chroma_incremental_enabled():
        # Pairing invariant: only clean up on the path that also writes. With the
        # incremental writer off the tail was never (re)upserted either, so
        # deleting here would trade stale docs for missing ones.
        return out
    like_db_path = Path(like_db_path)
    if not like_db_path.is_file():
        return out
    try:
        if collection is None:
            collection = _get_incremental_collection()
        have: set = set()
        offset = 0
        while True:
            got = collection.get(
                where={"session_id": session_id}, include=[], limit=1000, offset=offset
            ).get("ids") or []
            if not got:
                break
            have |= set(got)
            offset += len(got)
            if len(got) < 1000:
                break
        wanted = {
            message_doc_id(session_id, msg.message_id)
            for msg in iter_indexable_messages(like_db_path)
            if msg.session_id == session_id
        }
        stale = sorted(have - wanted)
        out["chroma_docs"] = len(have)
        out["wanted"] = len(wanted)
        out["orphans"] = len(stale)
        if stale and not dry_run:
            with chroma_write_lock():
                collection.delete(ids=stale)
            out["deleted"] = len(stale)
        return out
    except Exception as exc:
        note_index_failure("prune_session_orphans", exc, sink="chroma_session_indexer")
        return out


def sync_session_chroma_from_db(
    session_id: str,
    like_db_path: Path | str,
    *,
    replace_existing: bool = True,
) -> int:
    """Re-sync one session from sessions_search.db into Chroma."""
    if not chroma_incremental_enabled():
        return 0
    like_db_path = Path(like_db_path)
    if not like_db_path.is_file():
        return 0
    try:
        collection = _get_incremental_collection()
        if replace_existing:
            delete_session_chroma_documents(session_id, collection=collection)
        batch: List[IndexedMessage] = []
        count = 0
        for msg in iter_indexable_messages(like_db_path):
            if msg.session_id != session_id:
                continue
            batch.append(msg)
            if len(batch) >= DEFAULT_BATCH_SIZE:
                count += upsert_indexed_messages(batch, collection=collection)
                batch = []
        if batch:
            count += upsert_indexed_messages(batch, collection=collection)
        return count
    except Exception as exc:
        note_index_failure("session_resync", exc, sink="chroma_session_indexer")
        return 0


def backfill_chroma_sessions(
    like_db_path: Path | str,
    *,
    chroma_dir: Optional[Path] = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    collection: Any = None,
    skip_existing: bool = True,
) -> ChromaBackfillStats:
    """Index sessions_search.db rows into Chroma (idempotent upsert).

    2026-10-20（刘哥批准）：默认 **只补缺口** —— 先取集合已有 doc id，已存在的整条跳过。
    历史教训：本函数此前的实现对每条都重算嵌入（86,081 条 ≈33 小时），而缺口只有 2,399 条，
    照运维手册「Backfill Chroma（一次性或修复）」补缺口时会变成全量重嵌。
    全量重建请显式传 ``skip_existing=False``（脚本对应 ``--full-rebuild``）。
    """
    like_db_path = Path(like_db_path)
    stats = ChromaBackfillStats()
    if not like_db_path.is_file():
        logger.warning("sessions_search.db missing: %s", like_db_path)
        return stats

    if collection is None:
        collection = get_chroma_collection(chroma_dir)

    have: set[str] = set()
    if skip_existing:
        try:
            have = set(collection.get(include=[])["ids"] or [])
        except Exception:  # noqa: BLE001 - 读不到已有 id 时宁可全量，不静默丢数据
            logger.warning("skip_existing: 读取已有 doc id 失败，退回全量嵌入")
            have = set()

    batch: List[IndexedMessage] = []
    for msg in iter_indexable_messages(like_db_path):
        if have and message_doc_id(msg.session_id, msg.message_id) in have:
            stats.messages_skipped += 1
            continue
        batch.append(msg)
        if len(batch) >= batch_size:
            stats.messages_indexed += _upsert_batch(collection, batch)
            stats.batches += 1
            batch = []

    if batch:
        stats.messages_indexed += _upsert_batch(collection, batch)
        stats.batches += 1

    return stats


def query_session_messages(
    query: str,
    *,
    limit: int = 5,
    chroma_dir: Optional[Path] = None,
    collection: Any = None,
) -> List[Dict[str, Any]]:
    """Semantic query against session_messages (requires chromadb index)."""
    if collection is None:
        collection = get_chroma_collection(chroma_dir)
    result = collection.query(query_texts=[query], n_results=limit)
    hits: List[Dict[str, Any]] = []
    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    for doc_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
        hits.append(
            {
                "id": doc_id,
                "content": doc,
                "metadata": meta or {},
                "distance": dist,
            }
        )
    return hits

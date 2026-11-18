# =============================================================================
# Cron job storage and scheduling (JSON file backend)
# =============================================================================
from __future__ import annotations

import json
import os
import re
import shlex
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional, Tuple

from mimir_constants import get_cron_jobs_lock_path, get_mimir_home

MIMIR_HOME = get_mimir_home()
JOBS_FILE = MIMIR_HOME / "cron" / "jobs.json"
OUTPUT_DIR = MIMIR_HOME / "cron" / "output"

try:  # pragma: no cover - 非 POSIX 平台无 fcntl
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


# =============================================================================
# P0 写路径加固（T91 · B3-R1/R2/R3）—— 跨进程单写窗口 + 原子替换 + 损坏隔离
# -----------------------------------------------------------------------------
# 病灶（2026-11-18 全面审计 B3）：多写方 load→modify→save 全量回写同一份
# jobs.json，无锁无原子替换 —— 丢更新 + 撕裂写双竞态；且「一次损坏 + 一次
# 标记回写 = 全部 cron 任务静默清零」。修法照抄仓内已验证先例：
#   * 旁车锁   = agent/persistent_store.py（ADR-001 方案 C）：flock 锁**旁车
#     文件**、不锁目标件 —— 与 tmp→replace 原子写兼容（rename 后 fd 失效的
#     顾虑只对锁目标件成立）。锁路径真源 = mimir_constants.
#     get_cron_jobs_lock_path()，flock 随 fd 关闭由内核释放，无 stale 锁清尸。
#   * 原子写   = scripts/state_engine.py::_atomic_write_text
#     （tmp→flush→fsync→os.replace，读者永不见半份，崩溃只丢 tmp 件）。
#   * 损坏隔离 = load 失败先改名 .corrupt-<ts> 留盘可恢复再返 []，切断
#     「损坏→清零」链；OSError **出声上抛**（存储不可用不许静默当空）。
# 互指：scheduler/jobs.py 是同一运行时文件的第二套实现（字段语义不同，
# 保形不保合未合一），靠**同一把旁车锁文件**与本模块互斥。
# =============================================================================
_WRITE_LOCK_FILE = get_cron_jobs_lock_path()
_write_lock = RLock()
_write_depth = 0


@contextmanager
def write_window():
    """跨进程单写窗口：同线程可重入 · 同进程跨线程串行 · 跨进程 flock。

    load→modify→save 必须整体持窗（只锁 save 挡不住丢更新）。阻塞式 flock：
    写入均为毫秒级；持有者崩溃内核自动释放，无死锁遗留。
    ⚠ 勿与本模块窗口嵌套 ``scheduler/jobs.write_window``（同线程双 fd flock
    同一锁文件会自锁）——现仓无此调用路径，新增调用前先核对。
    """
    global _write_depth
    with _write_lock:
        lock_fh = None
        if _write_depth == 0:
            _WRITE_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
            fh = open(_WRITE_LOCK_FILE, "a+")
            try:
                if fcntl is not None:
                    fcntl.flock(fh, fcntl.LOCK_EX)
            except BaseException:
                fh.close()
                raise
            lock_fh = fh
            _write_depth = 1
        else:
            _write_depth += 1
        try:
            yield
        finally:
            _write_depth -= 1
            if _write_depth == 0 and lock_fh is not None:
                try:
                    if fcntl is not None:
                        fcntl.flock(lock_fh, fcntl.LOCK_UN)
                finally:
                    lock_fh.close()


def _atomic_write_json(path: Path, text: str) -> None:
    """tmp→flush→fsync→os.replace（先例 scripts/state_engine.py::_atomic_write_text）。

    读者永不见半份；中途崩溃只丢 tmp 件（顺手清走），旧数据原地完好。
    """
    d = path.parent
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{path.name}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


def _quarantine_corrupt(path: Path) -> Optional[Path]:
    """损坏件隔离改名 ``.corrupt-<ts>``（留盘可恢复，绝不就地清零）。"""
    ts = now().strftime("%Y%m%dT%H%M%S%f")
    target = path.with_name(f"{path.name}.corrupt-{ts}")
    try:
        os.replace(path, target)
    except OSError:
        return None
    return target


def now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_dirs() -> None:
    JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_jobs() -> List[Dict[str, Any]]:
    """读取任务表（写窗口内读 ⇒ 与写者一致的全量快照）。

    - JSONDecodeError / UnicodeDecodeError ⇒ 损坏件先改名 ``.corrupt-<ts>``
      留盘可恢复，再返 ``[]``（T91/B3-R3：损坏≠没有任务，但旧字节必须留盘，
      切断「损坏→下次保存清零」链）。
    - OSError ⇒ **出声上抛**：存储不可用不许静默当空（审计 C 节修法 4）。
    """
    with write_window():
        ensure_dirs()
        if not JOBS_FILE.exists():
            return []
        try:
            text = JOBS_FILE.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            _quarantine_corrupt(JOBS_FILE)
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            _quarantine_corrupt(JOBS_FILE)
            return []
        jobs = data.get("jobs", data) if isinstance(data, dict) else data
        if isinstance(jobs, list):
            return jobs
        return []


def save_jobs(jobs: List[Dict[str, Any]]) -> None:
    """全量回写任务表（原子替换；调用方 RMW 须整体持 ``write_window``）。"""
    with write_window():
        ensure_dirs()
        payload = {"jobs": jobs, "updated_at": now().isoformat()}
        _atomic_write_json(
            JOBS_FILE, json.dumps(payload, indent=2, ensure_ascii=False)
        )


# =============================================================================
# Cron script dispatch (2026-09-15 / RS20 follow-up Q23+Q24)
# -----------------------------------------------------------------------------
# The gateway used to launch every cron `script` as `["/bin/bash", path]` --
# i.e. it ignored the shebang.  A `.py` job script was therefore parsed by
# bash: the first syntax error aborted, but a backtick inside the docstring was
# executed as a command substitution and spawned util-linux `script`, which
# waits forever on a pty.  The job then burned the whole 300s cap and reported
# only `timeout` -- a silent misconfiguration, not a slow script.
#
# Resolution order: shebang > suffix map > refuse (fail fast, never hang).
# =============================================================================

SHELL_SUFFIXES = (".sh", ".bash")

#: suffix -> interpreter prefix.  Evaluated at import: `sys.executable` is the
#: gateway's own interpreter (the project venv), which is what repo scripts
#: need -- a bare `python3` may lack project deps.
_SUFFIX_INTERPRETERS: Dict[str, List[str]] = {
    ".sh": ["/bin/bash"],
    ".bash": ["/bin/bash"],
    ".py": [sys.executable or "python3"],
    ".js": ["node"],
}


def resolve_script_argv(script_path: Any) -> Tuple[Optional[List[str]], Optional[str]]:
    """Return ``(argv, None)`` or ``(None, reason)`` for a cron script path.

    ``argv`` is the full command line (interpreter + script) to exec directly,
    without a shell.
    """
    path = Path(script_path)
    try:
        with open(path, "rb") as fh:
            first = fh.readline(200).decode("utf-8", "replace").strip()
    except OSError as exc:
        return None, f"script unreadable: {exc}"

    # 1) An explicit shebang always wins.
    if first.startswith("#!"):
        try:
            parts = shlex.split(first[2:].strip())
        except ValueError:
            parts = []
        if parts:
            return parts + [str(path)], None
        return None, "malformed shebang"

    # 2) Fall back to the file suffix.
    interp = _SUFFIX_INTERPRETERS.get(path.suffix.lower())
    if interp:
        return list(interp) + [str(path)], None

    # 3) Refuse -- do not let bash guess.
    return None, (
        f"unsupported cron script type: {path.suffix or '<no extension>'} "
        f"(allowed: {_allowed_suffixes()}; or add a shebang)"
    )


def _allowed_suffixes() -> str:
    return ", ".join(sorted(_SUFFIX_INTERPRETERS, key=len))


def validate_script_config(script_rel: str) -> Optional[str]:
    """Q24: reject an unrunnable ``script`` config at creation time.

    Static check only (no filesystem access, no path-root assumptions) -- path
    safety and existence are still enforced by the gateway at run time.  Returns
    a human-readable reason, or ``None`` when the config is dispatchable.
    """
    suffix = Path(str(script_rel)).suffix.lower()
    if suffix in _SUFFIX_INTERPRETERS:
        return None
    return (
        f"unsupported cron script type: {suffix or '<no extension>'} "
        f"(allowed: {_allowed_suffixes()})"
    )


def _job_match(job: Dict[str, Any], job_id: str) -> bool:
    jid = str(job.get("id", ""))
    return jid == job_id or jid.startswith(job_id)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    for job in load_jobs():
        if _job_match(job, job_id):
            return job
    return None


def list_jobs(include_disabled: bool = True) -> List[Dict[str, Any]]:
    jobs = load_jobs()
    if include_disabled:
        return list(jobs)
    return [j for j in jobs if j.get("enabled", True)]


def remove_job(job_id: str) -> bool:
    with write_window():  # RMW 整体持窗（T91/B3-R1：防并发丢更新）
        jobs = load_jobs()
        new_jobs = [j for j in jobs if not _job_match(j, job_id)]
        if len(new_jobs) == len(jobs):
            return False
        save_jobs(new_jobs)
        return True


def update_job(job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with write_window():  # RMW 整体持窗（T91/B3-R1：防并发丢更新）
        jobs = load_jobs()
        for i, job in enumerate(jobs):
            if not _job_match(job, job_id):
                continue
            merged: Dict[str, Any] = dict(job)
            schedule_touched = False
            for k, v in updates.items():
                if k == "repeat.completed":
                    r = dict(merged.get("repeat") or {})
                    r["completed"] = v
                    merged["repeat"] = r
                elif k == "schedule":
                    merged["schedule"] = v
                    schedule_touched = True
                else:
                    merged[k] = v
            if schedule_touched and merged.get("state") != "paused":
                sch = merged.get("schedule") or {}
                nr = compute_next_run(sch, now().isoformat())
                merged["next_run_at"] = nr
            jobs[i] = merged
            save_jobs(jobs)
            return merged
        return None


def parse_schedule(schedule: str) -> Dict[str, Any]:
    s = (schedule or "").strip()
    if not s:
        raise ValueError("empty schedule")

    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}T", s):
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return {"type": "once", "value": dt.isoformat(), "display": s}
    except ValueError:
        pass

    m = re.match(
        r"^every\s+(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\s*$",
        s,
        re.I,
    )
    if m:
        n, u = int(m.group(1)), m.group(2).lower()
        unit = "minutes" if u.startswith("m") else "hours" if u.startswith("h") else "days"
        return {"type": "interval", "value": {"n": n, "unit": unit}, "display": s}

    m = re.match(r"^(\d+)\s*(m|min|mins|h|hr|hrs|d|day|days)\s*$", s, re.I)
    if m:
        n, u = int(m.group(1)), m.group(2).lower()
        unit = "minutes" if u.startswith("m") else "hours" if u.startswith("h") else "days"
        return {"type": "interval", "value": {"n": n, "unit": unit}, "display": s}

    parts = s.split()
    if len(parts) == 5:
        return {"type": "cron", "value": s, "display": s}

    raise ValueError(f"unrecognized schedule: {schedule!r}")


def compute_next_run(schedule: Dict[str, Any], after_iso: Optional[str] = None) -> Optional[str]:
    base = now()
    if after_iso:
        try:
            base = datetime.fromisoformat(after_iso.replace("Z", "+00:00"))
            if base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            base = now()

    st = schedule.get("type")
    if st == "once":
        ts = schedule.get("value")
        if not ts:
            return None
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None
        return dt.isoformat() if dt > base else None

    if st == "interval":
        v = schedule.get("value") or {}
        try:
            n = int(v.get("n", 1))
        except (TypeError, ValueError):
            n = 1
        unit = str(v.get("unit", "minutes"))
        delta = {
            "minutes": timedelta(minutes=n),
            "hours": timedelta(hours=n),
            "days": timedelta(days=n),
        }.get(unit, timedelta(minutes=n))
        return (base + delta).isoformat()

    if st == "cron":
        expr = schedule.get("value")
        if not expr:
            return None
        try:
            from croniter import croniter  # type: ignore
        except ImportError:
            return None
        it = croniter(str(expr), base)
        nxt = it.get_next(datetime)
        if nxt.tzinfo is None:
            nxt = nxt.replace(tzinfo=timezone.utc)
        return nxt.isoformat()

    return None


def create_job(
    prompt: str = "",
    schedule: str = "",
    name: Optional[str] = None,
    repeat: Optional[int] = None,
    deliver: Optional[str] = None,
    origin: Optional[Dict[str, Any]] = None,
    skills: Optional[List[str]] = None,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    base_url: Optional[str] = None,
    script: Optional[str] = None,
) -> Dict[str, Any]:
    parsed = parse_schedule(schedule)
    jid = uuid.uuid4().hex[:12]
    schedule_display = str(parsed.get("display", schedule))
    now_s = now().isoformat()
    repeat_o: Dict[str, Any] = {}
    if repeat is not None and repeat > 0:
        repeat_o["times"] = repeat
        repeat_o["completed"] = 0
    next_run = compute_next_run(parsed, now_s)
    job: Dict[str, Any] = {
        "id": jid,
        "name": name or f"job-{jid}",
        "prompt": prompt,
        "schedule": parsed,
        "schedule_display": schedule_display,
        "enabled": True,
        "state": "scheduled",
        "next_run_at": next_run,
        "created_at": now_s,
        "deliver": deliver or "local",
    }
    if origin:
        job["origin"] = origin
    if repeat_o:
        job["repeat"] = repeat_o
    if skills:
        job["skills"] = skills
        job["skill"] = skills[0]
    if model:
        job["model"] = model
    if provider:
        job["provider"] = provider
    if base_url:
        job["base_url"] = base_url
    if script:
        _script_reason = validate_script_config(script)
        if _script_reason:
            raise ValueError(f"invalid cron script config: {_script_reason}")
        job["script"] = script

    with write_window():  # RMW 整体持窗（T91/B3-R1：防并发丢更新）
        jobs = load_jobs()
        jobs.append(job)
        save_jobs(jobs)
    return job


def pause_job(job_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    updates: Dict[str, Any] = {
        "enabled": False,
        "state": "paused",
        "paused_at": now().isoformat(),
    }
    if reason:
        updates["paused_reason"] = reason
    out = update_job(job_id, updates)
    if not out:
        raise ValueError(f"job not found: {job_id}")
    return out


def resume_job(job_id: str) -> Dict[str, Any]:
    job = get_job(job_id)
    if not job:
        raise ValueError(f"job not found: {job_id}")
    sch = job.get("schedule") or {}
    nr = compute_next_run(sch, now().isoformat())
    out = update_job(
        job_id,
        {
            "enabled": True,
            "state": "scheduled",
            "next_run_at": nr,
            "paused_at": None,
            "paused_reason": None,
        },
    )
    if not out:
        raise ValueError(f"job not found: {job_id}")
    return out


def trigger_job(job_id: str) -> Dict[str, Any]:
    out = update_job(
        job_id,
        {
            "next_run_at": now().isoformat(),
            "enabled": True,
            "state": "scheduled",
        },
    )
    if not out:
        raise ValueError(f"job not found: {job_id}")
    return out


# =============================================================================
# Job execution support
# =============================================================================


def get_due_jobs() -> List[Dict[str, Any]]:
    jobs = load_jobs()
    now_dt = now()
    due: List[Dict[str, Any]] = []

    for job in jobs:
        if not job.get("enabled", True):
            continue
        next_run = job.get("next_run_at")
        if not next_run:
            continue
        try:
            next_dt = datetime.fromisoformat(next_run.replace("Z", "+00:00"))
            if next_dt.tzinfo is None:
                next_dt = next_dt.replace(tzinfo=timezone.utc)
            if next_dt <= now_dt:
                due.append(job)
        except (ValueError, TypeError):
            continue

    return due


def mark_job_run(job_id: str, status: str, error: Optional[str] = None):
    # 读（completed 计数）→算→写 必须整体持窗，否则并发双 mark 各读同一基线
    # ⇒ repeat.completed 少计（T91/B3-R1）。
    with write_window():
        job = get_job(job_id)
        if not job:
            return

        repeat = job.get("repeat", {})
        completed = int(repeat.get("completed", 0)) + 1
        max_times = repeat.get("times")

        disable = False
        if max_times is not None and completed >= int(max_times):
            disable = True

        schedule = job.get("schedule", {})
        next_run = None
        if not disable:
            next_run = compute_next_run(schedule, now().isoformat())

        update_job(
            job_id,
            {
                "last_run_at": now().isoformat(),
                "last_status": status,
                "last_error": error,
                "repeat.completed": completed,
                "enabled": not disable,
                "next_run_at": next_run,
                "state": "scheduled" if next_run else "completed",
            },
        )


def mark_job_delivery(
    job_id: str,
    ok: bool,
    error: Optional[str] = None,
    control_only: Optional[List[str]] = None,
):
    """N8 (2026-09-18): record a cron job's DELIVERY outcome.

    Deliberately does **not** touch `repeat.completed` / `next_run_at` — those
    belong to `mark_job_run`, and calling that a second time would double-count
    the run (`repeat.completed` drives `repeat.times`, so a `1/1` job would be
    disabled one run early). This only makes delivery failures visible:
    `last_delivery_error` (surfaced by `mimir cron list`) + `last_status`.

    O-11 (2026-10-09): `control_only` = the targets that failed **by design**
    (the positive-control arm). Such a failure verifies the alarm path; it is
    NOT an incident. The caller therefore passes `ok` computed from
    *unexpected* failures only, and the control evidence is kept in its own
    field: `last_delivery_control` non-empty => the control arm really ran.
    Old shape (`ok=not failures`) pinned `last_status="delivery_failed"` for
    ever => a real outage and a designed failure were indistinguishable (it
    fooled the coordinator once).

    Returns the updated job (or None if the job is unknown).
    """
    detail = error or "delivery failed"
    updates: Dict[str, Any] = {
        "last_delivery_error": None if ok else detail,
        "last_delivery_ok": bool(ok),
        "last_delivery_control": "; ".join(control_only) if control_only else None,
    }
    if not ok:
        # Loud in BOTH surfaces a human/script reads: `last_status` (summary) and
        # `last_error` (the value `mimir cron list` prints next to a non-ok
        # status). `last_delivery_error` carries the same detail for the
        # dedicated "⚠ Delivery failed" line.
        updates["last_status"] = "delivery_failed"
        updates["last_error"] = detail
    return update_job(job_id, updates)


def save_job_output(job_id: str, output: str, metadata: Optional[Dict] = None):
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    timestamp = now().strftime("%Y%m%d_%H%M%S")
    output_file = job_dir / f"{timestamp}.md"
    content = f"""# Cron Job Output

**Job ID:** {job_id}
**Timestamp:** {timestamp}
**Metadata:** {json.dumps(metadata or {}, indent=2)}

---

{output}
"""
    output_file.write_text(content, encoding="utf-8")
    return str(output_file)


def advance_next_run(job_id: str):
    with write_window():  # 读→算→写 整体持窗（T91/B3-R1）
        job = get_job(job_id)
        if not job or not job.get("schedule"):
            return
        last_run = job.get("last_run_at") or now().isoformat()
        next_run = compute_next_run(job["schedule"], last_run)
        if next_run:
            update_job(job_id, {"next_run_at": next_run})

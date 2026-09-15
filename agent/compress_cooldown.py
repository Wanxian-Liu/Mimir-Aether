"""T16 — 压缩重试冷却闸（盘上持久化 + 指数退避）。

根因（T18 定案，2026-09-14 · 取证 notes/2026-09-14-T18-压缩热环根因定案.md）
----------------------------------------------------------------------
触发门只有一句：``core_loop.py:907 needs_compression()``
    ``tokens = last_prompt_tokens; return tokens >= threshold_tokens``
实体闸门回滚时 ``compress()`` 返回**原始 messages** ⇒ token 数不变 ⇒
**下一个 turn 必然再次触发**。不是概率问题，是确定性热环。

三处历史冷却全部不可达（盘上实测）：
  ① ``should_compress_info`` 的 ``_last_compress_time`` —— 全库零调用者（死代码）
  ② ``should_trigger_compression`` 的 ``cooldown_until`` —— 零调用者 **且**时钟域错
     （写 ``monotonic``=54918、读 ``time.time()``=1.79e9 ⇒ 恒 False）
  ③ ``_generate_summary`` 的 ``_summary_failure_cooldown_until`` —— 唯一活着的，
     但只在 LLM **抛异常**时武装；LLM 成功时主动清零（:698）⇒ 闸门回滚
     （发生在 LLM 成功之后）**永不武装**

再加一条 H4b（已证）：``api_server.py:1538`` 在 ``_run_agent()`` 体内 ``_create_agent()``，
网关不按 session 缓存 ⇒ **每 run 新建 compressor，实例内状态跨 run 归零**。
⇒ 「只加实例内冷却」被否证：**必须落在盘上**。

实测规模：台账 410 行 = 387 rollback；19 个连续回滚串；间隔 p50 20.2s；
最长两串 ≈ 84 次真 LLM 摘要、1209s 全丢。

设计
----
· 状态文件：``<mimir_home>/data/ops/compress_cooldown.json``（原子写：tmp + replace）
· 退避：``delay = min(BASE * 2**(n-1), MAX)``，n = 连续失败次数
· ``attempt_id`` 去重 ⇒ 同一次 compress() 内的多条失败只计 1（否则摘要降级 +
  闸门回滚会双计，退避跳级）
· 成功应用 ⇒ 立即清零
· **跨进程互斥**（D3 并发裁决 · 2026-09-15）：``_read_raw() → 改 → _write()`` 是**复合**
  非原子操作；``tmp + replace`` 只保证「不读到半截文件」，**不保证「不丢更新」**
  （两个进程各读到 n、各写 n+1 ⇒ 净增 1）。⇒ 临界区外挂 ``fcntl.flock(LOCK_EX)``。
  锁文件 = 状态文件同目录 ``compress_cooldown.json.lock``；等待上限 ``_LOCK_WAIT_S``，
  超时**fail-open 继续无锁执行**并打 WARNING（冷却是省 token 的优化，不是安全闸——
  宁可丢一次计数，不可让压缩路径被锁挂住）。非 POSIX 无 ``fcntl`` ⇒ 同样退化为无锁。
· **fail-open**：状态文件读不出时退回「无冷却」，并打 WARNING。
  理由：冷却是**省 token** 的优化，不是安全闸；读盘失败若 fail-closed 会让压缩
  长期停摆（比热环更糟）。此选择显式记录，便于四方复核。

env 开关（回滚用）
----------------
· ``MIMIR_COMPRESS_COOLDOWN=0``        整体关闭（回到 T16 之前的行为）
· ``MIMIR_COMPRESS_COOLDOWN_BASE=600`` 基础延迟秒
· ``MIMIR_COMPRESS_COOLDOWN_MAX=3600`` 延迟上限秒
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:  # POSIX 锁（非 POSIX 平台退化为无锁，见 _locked 的 fail-open 说明）
    import fcntl as _fcntl
except Exception:  # pragma: no cover - 非 POSIX
    _fcntl = None

logger = logging.getLogger(__name__)

STATE_VERSION = 1
BASE_DELAY_S_DEFAULT = 600.0
MAX_DELAY_S_DEFAULT = 3600.0
# 连续失败达到该值 ⇒ 打一条「长期失败」告警行（RS19「失败必须可见」的最小落点）
ALERT_AFTER_FAILURES = 5
_STATE_REL = Path("data") / "ops" / "compress_cooldown.json"


def enabled() -> bool:
    """env 关闸（回滚用）。默认开。"""
    return os.environ.get("MIMIR_COMPRESS_COOLDOWN", "1").strip().lower() not in (
        "0", "false", "no", "off",
    )


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw:
        try:
            v = float(raw)
            if v > 0:
                return v
        except Exception:
            pass
    return default


def base_delay_s() -> float:
    return _float_env("MIMIR_COMPRESS_COOLDOWN_BASE", BASE_DELAY_S_DEFAULT)


def max_delay_s() -> float:
    cap = _float_env("MIMIR_COMPRESS_COOLDOWN_MAX", MAX_DELAY_S_DEFAULT)
    return max(cap, base_delay_s())


def state_path() -> Path:
    try:
        from mimir_constants import get_mimir_home
        home = Path(get_mimir_home())
    except Exception:  # pragma: no cover - 独立导入时
        home = Path(os.environ.get("MIMIR_HOME") or (Path.home() / ".mimiraether"))
    return home / _STATE_REL


def delay_for(failures: int) -> float:
    """指数退避：600 → 1200 → 2400 → 3600（上限）。"""
    n = max(1, int(failures or 1))
    return min(base_delay_s() * (2 ** (n - 1)), max_delay_s())


def _empty() -> Dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "consecutive_failures": 0,
        "total_failures": 0,
        "total_successes": 0,
        "last_reason": None,
        "first_failure_epoch": None,
        "last_failure_epoch": None,
        "cooldown_until_epoch": 0.0,
        "cooldown_delay_s": 0.0,
        "last_applied_epoch": None,
        "last_attempt_id": None,
        "alert_emitted_for": None,
        "updated_epoch": None,
        "updated_pid": None,
    }


def _read_raw() -> Tuple[Dict[str, Any], Optional[str]]:
    """返回 (state, error)。永不抛。"""
    p = state_path()
    if not p.exists():
        return _empty(), None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return _empty(), "state_not_object"
        st = _empty()
        st.update(raw)
        return st, None
    except Exception as exc:
        return _empty(), "%s: %s" % (type(exc).__name__, exc)


_LOCK_WAIT_S = 5.0


def lock_path() -> Path:
    """锁文件路径（与状态文件同目录 ⇒ 同文件系统，flock 语义可靠）。"""
    return state_path().with_suffix(".json.lock")


@contextmanager
def _locked():
    """把「读-改-写」变成**跨进程临界区**。yield 是否真正持锁（True/False）。

    为什么必须有（D3 并发实测）：``_read_raw() → 改 → _write()`` 是复合操作，
    ``tmp.replace(p)`` 只保证读到的是**完整**文件，不保证**不丢更新**：
    两进程各自读到 n ⇒ 各自写 n+1 ⇒ 净增 1（丢一次）。
    ⇒ 判据只能写成**不变量**（不丢条 / 不倒退），不能写成「原子写所以安全」。

    fail-open 的两处（与模块既有哲学一致：冷却是省 token 的优化，不是安全闸）：
      ① 无 ``fcntl``（非 POSIX）⇒ 直接无锁执行；
      ② 等锁超过 ``_LOCK_WAIT_S`` ⇒ 打 WARNING 后无锁执行（宁可丢一次计数，
         也不能让压缩路径被锁挂住）。
    ⚠️ 不可重入：``_write()`` 必须在**已持锁**的调用栈内调用（它自己不加锁）。
    """
    if _fcntl is None:  # pragma: no cover - 非 POSIX
        yield False
        return
    p = lock_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(p), os.O_CREAT | os.O_RDWR, 0o600)
    except Exception as exc:
        logger.warning("[COMPRESS] cooldown lock unavailable (%s) — fail-open (unlocked)", exc)
        yield False
        return
    got = False
    try:
        deadline = time.monotonic() + _LOCK_WAIT_S
        while True:
            try:
                _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                got = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    logger.warning(
                        "[COMPRESS] cooldown lock wait > %.1fs — fail-open (unlocked)", _LOCK_WAIT_S
                    )
                    break
                time.sleep(0.02)
        yield got
    finally:
        try:
            if got:
                _fcntl.flock(fd, _fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _write(st: Dict[str, Any]) -> Optional[str]:
    """原子写。返回错误串（None = 成功）。

    ⚠️ 必须在 ``_locked()`` 临界区内调用（本函数不自取锁）：单独调用只保证
    「不写半截文件」，不保证「不丢更新」。
    """
    p = state_path()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        st["updated_epoch"] = round(time.time(), 3)
        st["updated_pid"] = os.getpid()
        st["version"] = STATE_VERSION
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)
        return None
    except Exception as exc:
        return "%s: %s" % (type(exc).__name__, exc)


def state(now: Optional[float] = None) -> Dict[str, Any]:
    """读当前状态（附派生的 ``cooling`` / ``remaining_s``）。永不抛。"""
    _now = time.time() if now is None else now
    st, err = _read_raw()
    st["read_error"] = err
    until = float(st.get("cooldown_until_epoch") or 0.0)
    st["cooling"] = bool(_now < until)
    st["remaining_s"] = round(max(0.0, until - _now), 1) if st["cooling"] else 0.0
    st["enabled"] = enabled()
    return st


def is_cooling(now: Optional[float] = None) -> Tuple[bool, Dict[str, Any]]:
    """是否处于冷却窗口。返回 (cooling, state)。"""
    st = state(now=now)
    if not st.get("enabled"):
        return False, st
    return bool(st.get("cooling")), st


def record_failure(reason: str, *, attempt_id: Optional[str] = None,
                   now: Optional[float] = None) -> Dict[str, Any]:
    """记一次**未应用**的压缩尝试 ⇒ 武装/加长冷却。

    ``attempt_id`` 相同 ⇒ 同一次 compress() 内的重复上报只计一次。
    """
    _now = time.time() if now is None else now
    with _locked():                       # 读-改-写整段在跨进程临界区内（D3）
        st, err = _read_raw()
        if err:
            logger.warning("[COMPRESS] cooldown state unreadable (%s) — fail-open", err)
            st = _empty()
        if attempt_id and st.get("last_attempt_id") == attempt_id:
            st["dedup"] = True
            return st
        n = int(st.get("consecutive_failures") or 0) + 1
        delay = delay_for(n)
        st.update({
            "consecutive_failures": n,
            "total_failures": int(st.get("total_failures") or 0) + 1,
            "last_reason": reason,
            "first_failure_epoch": st.get("first_failure_epoch") or round(_now, 3),
            "last_failure_epoch": round(_now, 3),
            "cooldown_delay_s": delay,
            "cooldown_until_epoch": round(_now + delay, 3),
            "last_attempt_id": attempt_id,
            "dedup": False,
        })
        werr = _write(st)
        if werr:
            logger.warning("[COMPRESS] cooldown state write failed (%s) — fail-open", werr)
        _alert = n >= ALERT_AFTER_FAILURES and st.get("alert_emitted_for") != n
        if _alert:
            st["alert_emitted_for"] = n
            _write(st)
    if _alert:
        logger.warning(
            "[COMPRESS][COOLDOWN-ALERT] 连续 %d 次压缩未通过（reason=%s）——"
            "热环已被冷却闸挡住，最近一次冷却 %.0fs（上限 %.0fs）。"
            "在此窗口内不再发起摘要 LLM 调用。请查根因，勿只等自愈。",
            n, reason, delay, max_delay_s(),
        )
    logger.warning(
        "[COMPRESS] cooldown armed failures=%d delay=%.0fs until=%s reason=%s pid=%d",
        n, delay, time.strftime("%H:%M:%S", time.localtime(_now + delay)),
        reason, os.getpid(),
    )
    return st


def record_success(*, attempt_id: Optional[str] = None,
                   now: Optional[float] = None) -> Dict[str, Any]:
    """压缩**已应用** ⇒ 清零冷却。"""
    _now = time.time() if now is None else now
    with _locked():                       # 读-改-写整段在跨进程临界区内（D3）
        st, err = _read_raw()
        if err:
            st = _empty()
        prev = int(st.get("consecutive_failures") or 0)
        st.update({
            "consecutive_failures": 0,
            "cooldown_until_epoch": 0.0,
            "cooldown_delay_s": 0.0,
            "alert_emitted_for": None,
            "last_applied_epoch": round(_now, 3),
            "last_attempt_id": attempt_id,
            "total_successes": int(st.get("total_successes") or 0) + 1,
            "dedup": False,
        })
        _write(st)
    if prev:
        logger.info(
            "[COMPRESS] cooldown cleared (was %d consecutive failure(s)) pid=%d",
            prev, os.getpid(),
        )
    return st


def reset(now: Optional[float] = None) -> Dict[str, Any]:
    """手动清空（运维 / 测试）。"""
    st = _empty()
    with _locked():
        _write(st)
    return st


def describe(st: Dict[str, Any]) -> str:
    """一行摘要（供 /health、日志、汇报用）。"""
    return (
        "cooldown cooling=%s remaining_s=%s consecutive_failures=%s "
        "last_reason=%s total_failures=%s total_successes=%s"
        % (
            st.get("cooling"), st.get("remaining_s"),
            st.get("consecutive_failures"), st.get("last_reason"),
            st.get("total_failures"), st.get("total_successes"),
        )
    )


def _main(argv=None) -> int:  # pragma: no cover - CLI 便于取证
    import argparse
    ap = argparse.ArgumentParser(description="压缩冷却闸状态 / 手动控制")
    ap.add_argument("--reset", action="store_true", help="清空冷却状态")
    ap.add_argument("--fail", metavar="REASON", help="手动记一次失败（测试用）")
    args = ap.parse_args(argv)

    if args.reset:
        reset()
    elif args.fail:
        record_failure(args.fail)
    st = state()
    print(describe(st))
    print("state_file: %s" % state_path())
    print("base=%ss max=%ss enabled=%s" % (base_delay_s(), max_delay_s(), enabled()))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())

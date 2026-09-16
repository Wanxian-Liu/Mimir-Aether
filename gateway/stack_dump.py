"""通路 A · 进程内 faulthandler 现场直取（E3 / F2-d）。

问题：停机/冻结类事故（F2 家族）需要「卡死现场的 Python 帧栈」作硬证据。
外部工具在本进程关系下结构性不可用（RS17 已自证 py-spy attach 被 ptrace_scope 挡死），
`/proc/<pid>/stack` 只给内核态栈。

解法（两条互补通道，全进程内、零外部依赖）：
  ① 信号通道：`faulthandler.register(SIGUSR2, all_threads=True, chain=True)` ——
     C 级处理器，主线程阻塞在 C 调用（epoll / join）里也能出栈。
     ⚠ SIGUSR1 已被 restart 占用（`gateway/run.py` 的 `restart_signal_handler`），故本模块默认 SIGUSR2。
  ② 停滞通道：看门狗线程按「事件循环心跳」判停滞，超时自动 dump 全线程栈 ——
     不需要外部触发，事故自己把证据落盘（每轮停滞只 dump 一次，防刷屏）。

产物：`<home>/logs/stack-dumps/stack-<UTC ts>-<tag>-<pid>.txt`（信号通道用固定 append 文件）。

关断：`MIMIR_STACKDUMP=0` 完全不装；`MIMIR_STACKDUMP_STALL_S=0` 只留信号通道。
纪律：`install_stack_dump()` 永不抛异常 —— 观测设施不得拖垮 gateway 启动。
"""

from __future__ import annotations

import faulthandler
import json
import os
import signal
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SIGNAL_NAME = "SIGUSR2"
DEFAULT_STALL_S = 30.0
DUMP_DIRNAME = "stack-dumps"

_ENV_ENABLE = "MIMIR_STACKDUMP"
_ENV_STALL = "MIMIR_STACKDUMP_STALL_S"
_ENV_SIGNAL = "MIMIR_STACKDUMP_SIGNAL"

_lock = threading.Lock()
_state: dict = {
    "enabled": False,
    "signal": None,
    "signal_path": None,
    "stall_s": None,
    "watchdog": False,
    "dumps": 0,
    "last_dump": None,
}
_armed_fh = None          # 信号通道持有：faulthandler 要求 file 对象常驻
_watchdog: "StallWatchdog | None" = None


def resolve_dump_dir(hermes_home: object = None) -> Path:
    """dump 落盘目录：`<home>/logs/stack-dumps/`（home 缺省走 mimir_constants）。"""
    if hermes_home is None:
        try:
            from mimir_constants import get_hermes_home

            hermes_home = get_hermes_home()
        except Exception:
            hermes_home = Path.home() / ".mimiraether"
    return Path(hermes_home) / "logs" / DUMP_DIRNAME


def _resolve_signum(raw: object) -> int | None:
    name = str(raw or DEFAULT_SIGNAL_NAME).strip().upper()
    if not name or name in {"0", "NONE", "OFF"}:
        return None
    sig = getattr(signal, name, None)
    if not isinstance(sig, int):
        return None
    return sig


def write_dump(tag: str = "manual", hermes_home: object = None, extra: str = "") -> Path:
    """把**当前全线程** Python 帧栈写进一个新文件，返回路径。

    独立于信号通道（信号通道是 C 级注册、写固定 append 文件）；本函数可被测试/看门狗/
    自检直接调用。
    """
    d = resolve_dump_dir(hermes_home)
    d.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    path = d / f"stack-{ts}-{tag}-{os.getpid()}.txt"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"# stack dump · tag={tag} · pid={os.getpid()}\n")
        fh.write(f"# utc={ts} · monotonic={time.monotonic():.3f} · threads={threading.active_count()}\n")
        if extra:
            fh.write(f"# {extra}\n")
        fh.write("# faulthandler.dump_traceback(all_threads=True) — 各线程栈按原始顺序\n")
        faulthandler.dump_traceback(file=fh, all_threads=True)
        fh.flush()
    with _lock:
        _state["dumps"] = int(_state.get("dumps") or 0) + 1
        _state["last_dump"] = str(path)
    return path


def arm_signal_channel(hermes_home: object = None, signum: int | None = None) -> Path | None:
    """装信号通道：`kill -SIGUSR2 <gateway pid>` ⇒ 全线程栈落到固定 append 文件。"""
    global _armed_fh
    if signum is None:
        signum = _resolve_signum(os.getenv(_ENV_SIGNAL))
    if signum is None:
        return None
    d = resolve_dump_dir(hermes_home)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"stack-signal-{os.getpid()}.log"
    fh = open(path, "a", encoding="utf-8", buffering=1)
    fh.write(
        f"\n# === armed signal channel at {datetime.now(timezone.utc).isoformat()} "
        f"pid={os.getpid()} signum={signum} ===\n"
    )
    # ⚠ chain 必须为 False：实测（2026-09-16，pytest exit=140=128+SIGUSR2）——
    # chain=True 时 dump 之后会把信号交还给「上一个处理器」，而缺省就是 SIG_DFL ⇒
    # **发一次 dump 信号就把进程杀掉**（gateway 会直接死）。chain=False = 只 dump、继续跑。
    faulthandler.register(signum, all_threads=True, chain=False, file=fh)
    _armed_fh = fh  # 常驻引用：被 GC 即失去信号通道
    with _lock:
        _state["signal"] = signal.Signals(signum).name
        _state["signal_path"] = str(path)
    return path


def disarm_signal_channel(signum: int | None = None) -> bool:
    """卸掉信号通道（测试清理用）。"""
    global _armed_fh
    if signum is None:
        signum = _resolve_signum(os.getenv(_ENV_SIGNAL))
    if signum is None:
        return False
    try:
        faulthandler.unregister(signum)
    except Exception:
        return False
    fh, _armed_fh = _armed_fh, None
    if fh is not None:
        try:
            fh.close()
        except Exception:
            pass
    with _lock:
        _state["signal"] = None
    return True


# --------------------------------------------------------------------------- 停滞看门狗


class StallWatchdog(threading.Thread):
    """心跳看门狗：`stall_s` 秒没有 beat ⇒ dump 全线程栈（每轮停滞只 dump 一次）。

    判据是**事件循环心跳**（`heartbeat_ticker` 每 `interval` 秒喂一次）：
    循环被阻塞（`join(timeout=5)` / 阻塞 `_select()` 等）⇒ 心跳停 ⇒ 判定停滞。
    """

    def __init__(self, stall_s: float, hermes_home: object = None, logger=None, interval: float = 1.0):
        super().__init__(name="stack-dump-watchdog", daemon=True)
        self.stall_s = max(0.1, float(stall_s))
        self.hermes_home = hermes_home
        self.logger = logger
        self.interval = max(0.05, float(interval))
        self._stop_evt = threading.Event()
        self._last_beat = time.monotonic()
        self._dumped_this_episode = False
        self.stalls = 0
        self.beats = 0

    def beat(self) -> None:
        with self._lock_state():
            self.beats += 1
            self._last_beat = time.monotonic()
            if self._dumped_this_episode:
                self._dumped_this_episode = False

    def _lock_state(self) -> threading.Lock:
        lock = getattr(self, "_beat_lock", None)
        if lock is None:
            lock = threading.Lock()
            self._beat_lock = lock
        return lock

    def stalled_for(self) -> float:
        with self._lock_state():
            return time.monotonic() - self._last_beat

    def run(self) -> None:
        while not self._stop_evt.wait(self.interval):
            if self.stalled_for() < self.stall_s:
                continue
            with self._lock_state():
                if self._dumped_this_episode:
                    continue
                self._dumped_this_episode = True
                self.stalls += 1
            try:
                path = write_dump(
                    tag="stall",
                    hermes_home=self.hermes_home,
                    extra=f"watchdog: no loop heartbeat for >= {self.stall_s:.2f}s",
                )
                if self.logger is not None:
                    self.logger.warning("stack_dump: stall detected, dumped all threads -> %s", path)
            except Exception as exc:  # 观测设施自身失败不得反噬
                if self.logger is not None:
                    self.logger.warning("stack_dump: stall dump failed: %s", exc)

    def stop(self) -> None:
        self._stop_evt.set()


async def heartbeat_ticker(interval: float = 1.0) -> None:
    """事件循环心跳生产者（asyncio 任务）。循环阻塞 ⇒ 本协程不再推进 ⇒ 看门狗判停滞。"""
    import asyncio

    while True:
        heartbeat()
        await asyncio.sleep(interval)


def heartbeat() -> None:
    """喂心跳（无看门狗时静默）。"""
    wd = _watchdog
    if wd is not None:
        wd.beat()


# --------------------------------------------------------------------------- 装配入口


def install_stack_dump(
    hermes_home: object = None,
    logger=None,
    *,
    enabled: object = None,
    stall_s: object = None,
    signum: object = None,
    start_watchdog: bool = True,
) -> dict:
    """装通路 A。**永不抛异常**（返回状态 dict）。幂等：重复调用只填缺项。"""
    try:
        on = str(os.getenv(_ENV_ENABLE, "1")).strip().lower() not in {"0", "false", "off", "no", ""}
        if enabled is not None:
            on = bool(enabled)
        with _lock:
            if _state["enabled"]:
                return dict(status())
            _state["enabled"] = on
            _state["pid"] = os.getpid()
        if not on:
            return dict(status())

        sig_raw = os.getenv(_ENV_SIGNAL) if signum is None else signum
        arm_signal_channel(hermes_home=hermes_home, signum=_resolve_signum(sig_raw))

        raw_stall = os.getenv(_ENV_STALL) if stall_s is None else stall_s
        try:
            stall_val = DEFAULT_STALL_S if raw_stall is None or str(raw_stall).strip() == "" else float(raw_stall)
        except (TypeError, ValueError):
            stall_val = DEFAULT_STALL_S
        with _lock:
            _state["stall_s"] = stall_val
        if stall_val > 0 and start_watchdog:
            global _watchdog
            _watchdog = StallWatchdog(stall_val, hermes_home=hermes_home, logger=logger)
            _watchdog.start()
            with _lock:
                _state["watchdog"] = True
        return dict(status())
    except Exception as exc:  # pragma: no cover - 防御：永不拖垮调用方
        if logger is not None:
            try:
                logger.warning("stack_dump: install failed: %s", exc)
            except Exception:
                pass
        with _lock:
            _state["enabled"] = False
            _state["error"] = str(exc)
        return dict(status())


def status() -> dict:
    """当前装配快照（JSON 可序列化）。"""
    with _lock:
        snap = dict(_state)
    wd = _watchdog
    if wd is not None:
        snap["watchdog_beats"] = wd.beats
        snap["watchdog_stalls"] = wd.stalls
        snap["stalled_for_s"] = round(wd.stalled_for(), 3)
    return snap


def _reset_for_tests() -> None:
    """仅测试用：卸信号通道 + 停看门狗 + 清状态。"""
    global _watchdog
    disarm_signal_channel()
    if _watchdog is not None:
        _watchdog.stop()
        _watchdog = None
    with _lock:
        _state.update(
            {"enabled": False, "signal": None, "signal_path": None, "stall_s": None,
             "watchdog": False, "dumps": 0, "last_dump": None}
        )


def _main(argv: list[str]) -> int:
    """自检/证据入口：`python -m gateway.stack_dump --dump --tag e3-selftest`。"""
    args = list(argv)
    tag = "selftest"
    if "--tag" in args:
        tag = args[args.index("--tag") + 1]
    home = os.getenv("MIMIR_STACKDUMP_HOME") or None
    st = install_stack_dump(hermes_home=home)
    path = write_dump(tag=tag, hermes_home=home, extra="selftest: fresh-process in-process dump")
    print(json.dumps({"status": st, "dump": str(path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(_main(sys.argv[1:]))

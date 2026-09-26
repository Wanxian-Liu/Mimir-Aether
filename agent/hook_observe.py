"""Hook observability — 记录两条运行时钩子的门控原因（触发与未触发都记）。

背景（2026-09-26 实测 · RS17 探针 VERIFIED）：
  `parallel-read nudge`（conversation_nudges.maybe_parallel_read_nudge，agent_loop.py 接线）
  与 `PI auto-delegate`（pi_trigger.maybe_pi_delegate_execute，agent_loop.py turn 0 接线）
  自 2026-08-19 上线以来，生产日志中 **0 次触发、0 行原因** ⇒ 无法区分
  「代码没跑到」「门没过」「门过了但模型不响应」三态。
  本模块补的正是这一层：每条钩子每次被调用 → 落一行 JSONL + 一行 INFO 日志。

设计约束（纯增量 · 不改运行逻辑）：
  * 只观测，**不改变任何返回值**；调用方把 observe 放在 return 之前。
  * 自身异常一律吞掉（观测失败不得影响主流程）。
  * 日志标记固定 `[HOOK-OBS]`，便于 grep 与 SLO 看板聚合。
  * env 开关 `MIMIR_HOOK_OBSERVE`（默认 1 开；=0 关闭 ⇒ 零写盘）。
  * env `MIMIR_HOOK_OBS_PATH` 可覆盖落盘路径（供测试隔离，勿在生产设置）。
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

OBS_MARKER = "[HOOK-OBS]"
OBS_ENV_ENABLE = "MIMIR_HOOK_OBSERVE"
OBS_ENV_PATH = "MIMIR_HOOK_OBS_PATH"
OBS_DEFAULT_REL = os.path.join("data", "ops", "hook_observations.jsonl")

# 已解析过的落盘路径缓存（None 表示解析失败——静默降级为「只打日志」）
_resolved_path: Optional[Path] = None
_path_resolved: bool = False


def _enabled() -> bool:
    return os.environ.get(OBS_ENV_ENABLE, "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def obs_path() -> Optional[Path]:
    """落盘路径：env 覆盖 > Mimir home 下 data/ops/。解析失败返回 None（不抛）。"""
    global _resolved_path, _path_resolved
    if _path_resolved:
        return _resolved_path
    try:
        override = os.environ.get(OBS_ENV_PATH, "").strip()
        if override:
            _resolved_path = Path(override)
        else:
            from mimir_constants import get_mimir_home  # type: ignore

            _resolved_path = Path(get_mimir_home()) / OBS_DEFAULT_REL
    except Exception:
        _resolved_path = None
    _path_resolved = True
    return _resolved_path


def observe(hook: str, decision: str, reason: str, **fields: Any) -> None:
    """记录一次钩子决策。

    hook     : `parallel_read_nudge` / `pi_delegate_nudge` / `pi_delegate_execute`
    decision : `triggered`（门全过） / `blocked`（某道门拦下）
    reason   : 门名（`env_disabled` / `turn_lt_3` / `tools_lt_2` / `injected` / ...）
    fields   : 附加标量（turn / tools / est / min_turns / subtasks / error_len ...）
    """
    if not _enabled():
        return
    try:
        extra = " ".join(
            "%s=%s" % (k, fields[k]) for k in sorted(fields) if fields[k] is not None
        )
        logger.info(
            "%s hook=%s decision=%s reason=%s %s",
            OBS_MARKER, hook, decision, reason, extra,
        )
    except Exception:
        pass
    try:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "hook": hook,
            "decision": decision,
            "reason": reason,
            "pid": os.getpid(),
        }
        for k, v in fields.items():
            if isinstance(v, (int, float, str, bool)) and v is not None:
                rec[k] = v
        path = obs_path()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def reset_path_cache() -> None:
    """清空落盘路径缓存（测试用；生产无需调用）。"""
    global _resolved_path, _path_resolved
    _resolved_path = None
    _path_resolved = False


__all__ = ["OBS_MARKER", "OBS_ENV_ENABLE", "OBS_ENV_PATH", "obs_path", "observe",
           "reset_path_cache"]

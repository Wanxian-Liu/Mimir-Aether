"""Persist last-known LLM context token usage for ops tools (AUTO-04).

B10（2026-09-13）遥测双口径 —— 唯一化 + 标注真源/旁路
----------------------------------------------------
根因：单槽 ``last_context_usage.json`` 是 last-writer-wins。主会话
（``model == config.yaml model.default``，ctx=1M 的 deepseek-flash 口径）与旁路实例
（如 delegate/subagent 用 deepseek-chat，ctx=163840）**互相覆盖**，读端无法分辨
一个数字属于哪个口径——「上下文 146807 / 阈值 120000」这类读数因此不可归因。

本模块的三条不变量：

1. **口径自证**：payload 增 ``pid`` / ``writer_kind`` / ``caliber``
   （``<model>@<ctx>/thr=<threshold>``），任何一条记录都能自报来路。
2. **唯一化**：``writer_kind == "aux"`` 时**不得覆盖未过期 main 记录**
   （TTL :data:`AUX_TTL_SECONDS` = 1800s）——改写到旁路文件
   ``last_context_usage_aux.json``；main 缺失 / 已 stale / 主槽本身是 aux 时才接管主槽。
   main 始终可覆盖（并回收 stale 的旁路文件）。
3. **读端标注**：:func:`read_context_usage_snapshot` 仍只读主槽（向后兼容），
   旁路口径由 :func:`read_aux_context_usage_snapshot` 单独提供，由调用方
   （mimir_ops / prompt hint）标注「真源 vs 旁路」。
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from mimir_constants import get_mimir_home

logger = logging.getLogger(__name__)

# main 记录的「未过期」窗口：aux 在此时长内不得覆盖 main（B10 §2）。
AUX_TTL_SECONDS = 1800
MAIN_SNAPSHOT_FILENAME = "last_context_usage.json"
AUX_SNAPSHOT_FILENAME = "last_context_usage_aux.json"


def _ops_dir() -> Path:
    path = Path(get_mimir_home()) / "data" / "ops"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _snapshot_path() -> Path:
    """主槽（真源 / last-writer 主口径）。"""
    path = _ops_dir() / MAIN_SNAPSHOT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _aux_snapshot_path() -> Path:
    """旁路口径槽（B10 §2）。"""
    path = _ops_dir() / AUX_SNAPSHOT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_payload(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_payload(path: Path, payload: Dict[str, Any]) -> None:
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def make_caliber(model: str, context_length: int, threshold_tokens: int) -> str:
    """口径串：``<model>@<ctx>/thr=<threshold>``（B10 §1）。"""
    return (
        f"{(model or '').strip()}@{int(context_length or 0)}"
        f"/thr={int(threshold_tokens or 0)}"
    )


def is_fresh(
    payload: Optional[Dict[str, Any]],
    *,
    now: Optional[float] = None,
    ttl: int = AUX_TTL_SECONDS,
) -> bool:
    """payload 是否在 TTL 内（无 timestamp / 非法 / 超期 ⇒ False）。"""
    if not isinstance(payload, dict):
        return False
    try:
        ts = float(payload.get("timestamp") or 0)
    except (TypeError, ValueError):
        return False
    if ts <= 0:
        return False
    return (now if now is not None else time.time()) - ts < max(int(ttl), 1)


def _config_default_model() -> str:
    """``config.yaml`` 的 ``model.default``（与 gateway 同源：``$MIMIR_AETHER_HOME/config.yaml``）。

    读不到（文件缺失 / 解析失败 / 值为空）一律返回 ``""`` —— 由调用方 fail-open。
    """
    path = Path(get_mimir_home()) / "config.yaml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    try:
        import yaml

        data = yaml.safe_load(text) or {}
        model_cfg = data.get("model") if isinstance(data, dict) else None
        if isinstance(model_cfg, dict):
            return str(model_cfg.get("default") or "").strip()
        if isinstance(model_cfg, str):
            return model_cfg.strip()
        return ""
    except Exception:
        pass
    # yaml 不可用时的极简回退：只在顶层 ``model:`` 块内找 ``default:``。
    in_model_block = False
    for line in text.splitlines():
        if not line:
            continue
        if not line[0].isspace():
            in_model_block = line.split(":", 1)[0].strip() == "model"
            continue
        if in_model_block and line.strip().startswith("default:"):
            return line.split("default:", 1)[1].strip().strip("'\"")
    return ""


def resolve_writer_kind(model: str) -> str:
    """口径判定（B10 §3）：``main`` 若 ``model`` == config.yaml ``model.default``，否则 ``aux``。

    **fail-open**：配置读不到 / 默认值为空 / model 为空 ⇒ 判 ``main``
    （宁保留遥测也不因配置缺失而丢记录）。
    """
    default = _config_default_model()
    current = (model or "").strip()
    if not default or not current:
        return "main"
    return "main" if current.lower() == default.lower() else "aux"


def write_context_usage_snapshot(
    *,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    context_length: int = 0,
    threshold_tokens: int = 0,
    message_count: int = 0,
    session_key: str = "",
    session_id: str = "",
    model: str = "",
    writer_kind: str = "main",
    pid: Optional[int] = None,
) -> Optional[Path]:
    """Write latest usage for mimir_ops /health-style reads (best-effort).

    Returns the path **actually written**（main 主槽 / aux 旁路文件），便于取证
    「写了哪个文件、为什么」（B10 §2）。
    """
    kind = "aux" if (writer_kind or "").strip().lower() == "aux" else "main"
    model_s = (model or "").strip()
    payload: Dict[str, Any] = {
        "timestamp": time.time(),
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "total_tokens": int(total_tokens or 0),
        "context_length": int(context_length or 0),
        "threshold_tokens": int(threshold_tokens or 0),
        "message_count": int(message_count or 0),
        "session_key": (session_key or os.environ.get("HERMES_SESSION_KEY", "")).strip(),
        "session_id": (session_id or "").strip(),
        "model": model_s,
        "pid": int(pid if pid is not None else os.getpid()),
        "writer_kind": kind,
        "caliber": make_caliber(model_s, context_length, threshold_tokens),
    }
    main_path = _snapshot_path()
    aux_path = _aux_snapshot_path()

    if kind == "aux":
        main = _read_payload(main_path)
        main_kind = str((main or {}).get("writer_kind") or "main").strip().lower()
        main_blocks_aux = main is not None and main_kind != "aux" and is_fresh(main)
        if main_blocks_aux:
            # 分支 1：main 未过期 → aux 不得覆盖，改写到旁路文件。
            _write_payload(aux_path, payload)
            logger.info(
                "[TELEMETRY-AUX] 写旁路文件 %s（reason=main 记录未过期 < %ss，"
                "caliber=%s；main 保留 caliber=%s）",
                aux_path.name, AUX_TTL_SECONDS, payload["caliber"],
                (main or {}).get("caliber"),
            )
            return aux_path
        # 分支 2：main 缺失 / 已 stale / 主槽本身是 aux → aux 接管主槽。
        _write_payload(main_path, payload)
        _write_payload(aux_path, payload)
        logger.info(
            "[TELEMETRY-AUX] 写主槽 %s + 同步旁路 %s（reason=main %s，caliber=%s）",
            main_path.name, aux_path.name,
            "缺失" if main is None else ("主槽本身是 aux" if main_kind == "aux" else f"已 stale > {AUX_TTL_SECONDS}s"),
            payload["caliber"],
        )
        return main_path

    # main 分支：始终可覆盖（含回收 stale 的旁路文件；未过期的 aux 保留作旁路证据）。
    _write_payload(main_path, payload)
    aux = _read_payload(aux_path)
    if aux is not None and not is_fresh(aux):
        try:
            aux_path.unlink()
        except OSError:
            pass
        logger.info(
            "[TELEMETRY-MAIN] 写主槽 %s（caliber=%s）；回收 stale 旁路 %s（> %ss）",
            main_path.name, payload["caliber"], aux_path.name, AUX_TTL_SECONDS,
        )
    else:
        logger.info(
            "[TELEMETRY-MAIN] 写主槽 %s（caliber=%s；旁路 %s %s）",
            main_path.name, payload["caliber"], aux_path.name,
            "保留（未过期，作旁路证据）" if aux is not None else "不存在",
        )
    return main_path


def read_context_usage_snapshot() -> Optional[Dict[str, Any]]:
    """读主槽（真源口径）—— 行为与 B10 前一致。"""
    return _read_payload(_snapshot_path())


def read_aux_context_usage_snapshot() -> Optional[Dict[str, Any]]:
    """读旁路口径槽（B10 §4：存在则读端标注为**旁路**，勿与主口径混算）。"""
    return _read_payload(_aux_snapshot_path())

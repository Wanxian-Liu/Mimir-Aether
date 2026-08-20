"""task_completion.py — 任务书完成度辅助检查（2026-08-20 精简版——对齐 Hermes completed 语义）。

对照（Hermes 源码——turn_finalizer.py L193-195）：
    completed = final_response is not None and not failed and (api_call_count < max_iterations or normal_text_response)
    —— 完成判定 = 有最终交付 + 未失败——简单——无 - [ ] 清单强制、无 L1/L2/L3 渐进、无信号表。

Mimir 对齐：完成判定由 agent_loop 的 has_written（写盘产出 = final_response 语义）+ 未失败负责。
本模块降级为"可选辅助"：
- 任务书含 - [ ] 清单时——未勾项未交付 → 返回提醒文本（供 agent_loop 注入提示——**非阻断**）
- 无清单 / 无未勾项 / 已交付 → None（不打扰——完成与否交给 has_written 判定）

历史（去机制记录）：
- 2026-08-19 四方会议实施（清单强制 + L1/L2/L3 + 模糊信号 + emoji 防绕过 + _MIN_ITEM_LEN）
- 2026-08-20 刘哥判断"左加右加加多了成阻碍"——对照 Hermes 源码精简（本版）
  —— 去：清单强制依赖/L1L2L3 渐进/模糊信号表/emoji 防绕过/信号词表/_MIN_ITEM_LEN 边界
"""

import re
from typing import Any, Dict, List, Optional

_CHECKBOX_RE = re.compile(r"^-\s+\[([ xX])\]\s*(.+)$", re.MULTILINE)
_CN_TASK_MARKERS = ("【任务】", "任务书：")


def extract_task_spec(messages: List[Dict[str, Any]]) -> str:
    """从消息历史提取任务书（可选——辅助提醒用）。无任务书结构返回 ""。"""
    found = ""
    for m in messages:
        if m.get("role") != "user":
            continue
        c = m.get("content", "")
        if isinstance(c, str) and (_CHECKBOX_RE.search(c) or any(mk in c for mk in _CN_TASK_MARKERS)):
            found = c
    return found


def check_task_completion(task_spec: str, messages: List[Dict[str, Any]]) -> Optional[str]:
    """可选提醒（非阻断——对齐 Hermes：完成判定交给 has_written）。

    Returns:
        None: 无清单 / 无未勾项 / 未勾项已交付——不打扰（完成与否由 agent_loop 判定）
        str:  提醒文本（"任务书有 N 项未交付（提醒）: [...]"——注入提示——不强制阻断）
    """
    if not task_spec or not task_spec.strip():
        return None
    unchecked = [m.group(2).strip() for m in _CHECKBOX_RE.finditer(task_spec) if m.group(1).lower() != "x"]
    if not unchecked:
        return None
    texts = []
    for m in reversed(messages):
        if m.get("role") == "assistant" and m.get("content"):
            texts.append(str(m["content"]))
            if len(texts) >= 3:
                break
    joined = " ".join(texts)
    remaining = [it for it in unchecked if it not in joined]
    if not remaining:
        return None
    return f"任务书有 {len(remaining)} 项未交付（提醒——非阻断）: {remaining[:3]}"

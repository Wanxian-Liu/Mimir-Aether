"""task_completion.py — 任务书完成度检查（四方会议 2026-08-19 实施 · Loki reality-check 5 项清单）。

设计来源（盘上参照）：
- Hermes 方案（会议卡 L47-58）：natural EXIT 前加"任务完成度检查"——任务书含子步骤清单时，
  未完成禁止自然结束。
- OpenClaw 强化（会议卡 L185-208）：独立 plain function（不引入类/状态机）+ 强边界
  （无任务书结构跳过）+ env 门控回退。
- Loki reality-check（会议卡 L299-325）：
  B-L2 task_spec 来源（选项 A 外部传入 + 运行时从消息历史兜底提取——覆盖续作场景）；
  B-L4 item 匹配收紧（[x] 已勾状态优先 + 完整关键词匹配 + 首次/末次出现位置——取代子串匹配）。

边界（OpenClaw L210-215）：
- 无任务书结构 → 跳过（返回 None）
- 任务书结构但无 `- [ ]` 未勾项（全 [x]）→ 跳过
- 任务书含 `- [ ]` 但最近 assistant 已交付（勾选/完整关键词+末次出现）→ 视为完成
- 读清单失败 → 调用方回退现行为（降级安全，不阻断）
"""

import re
from typing import Any, Dict, List, Optional

# 任务书结构特征：markdown 标题（## S1 ...）或 checkbox 清单（- [ ] / - [x]）
_TASK_SPEC_HEADING_RE = re.compile(r"^#{1,3}\s+\S", re.MULTILINE)
_CHECKBOX_RE = re.compile(r"^-\s+\[([ xX])\]\s*(.+)$", re.MULTILINE)

# 未完成信号（对齐 agent_loop._UNFINISHED_SIGNALS + 补充）：item 末次出现后若含这些词 → 视为未完成
_UNFINISHED_SIGNALS = ("准备", "接下来", "将要", "即将", "待完成", "还没", "稍后", "下一步")

# item 完整关键词匹配的最小长度门槛（防 "S2" 这类泛串字面误判完成——Loki B-L4 核心关切）
_MIN_ITEM_LEN = 4


def extract_task_spec(messages: List[Dict[str, Any]]) -> str:
    """从消息历史提取任务书文本（B-L2 运行时兜底）。

    优先取"最后一条含任务书结构（markdown 标题或 checkbox）的 user 消息"：
    - 首次任务：首条 user 消息即任务书
    - 续作任务：任务书在历史更早处（core_loop._build_full_messages 含全量历史）——
      取最后一条仍含结构的 user 消息，覆盖续作场景（E1 二次失败即续作任务书失效场景）

    返回 "" = 无任务书（检查跳过）。
    """
    found = ""
    for m in messages:
        if m.get("role") != "user":
            continue
        c = m.get("content", "")
        if not isinstance(c, str) or not c.strip():
            continue
        if _TASK_SPEC_HEADING_RE.search(c) or _CHECKBOX_RE.search(c):
            found = c
    return found


def check_task_completion(task_spec: str, messages: List[Dict[str, Any]]) -> Optional[str]:
    """任务书完成度检查（OpenClaw 工程化建议签名）。

    Returns:
        None: 通过（无任务书 / 无未勾项 / 未交付项已由最近 assistant 交付）——允许自然结束
        str:  阻断理由（"任务书未完成 (N 项未交付): [...]"）——调用方必须阻止自然结束
    """
    if not task_spec or not task_spec.strip():
        return None

    unchecked = _unchecked_items(task_spec)
    if not unchecked:
        return None  # 无 `- [ ]` 未勾项（全 [x] 或清单已完成）→ 通过

    texts = _recent_assistant_texts(messages, n=3)
    remaining = [it for it in unchecked if not _item_delivered(it, texts)]
    if not remaining:
        return None

    return f"任务书未完成（{len(remaining)} 项未交付）: {remaining[:3]}"


def _unchecked_items(task_spec: str) -> List[str]:
    """收集任务书中 `- [ ]` 未勾项（`- [x]` / `- [X]` 视为已勾，不收集）。"""
    items = []
    for m in _CHECKBOX_RE.finditer(task_spec):
        mark, text = m.group(1), m.group(2).strip()
        if mark.lower() != "x":
            items.append(text)
    return items


def _recent_assistant_texts(messages: List[Dict[str, Any]], n: int = 3) -> List[str]:
    """最近 n 条 assistant 文本（B-L4：判定交付只看最近的对话，防旧消息误判）。"""
    texts = []
    for m in reversed(messages):
        if m.get("role") != "assistant":
            continue
        c = m.get("content")
        if not c:
            continue
        texts.append(c if isinstance(c, str) else str(c))
        if len(texts) >= n:
            break
    return texts


def _item_delivered(item: str, texts: List[str]) -> bool:
    """B-L4 收紧判定：item 是否已交付（Loki 三条手段组合——取代 OpenClaw 子串匹配）。

    1. [x] 已勾状态优先：模型在文本里写 `- [x] <item>` / `[x] <item>` → 直接判定完成
    2. 完整关键词匹配：item 完整出现（边界感知，非子串）且长度 ≥ _MIN_ITEM_LEN
       （防 "S2 起步" 被解释内容里的裸 "S2" 字面误判完成）
    3. 首次/末次出现位置：item 末次出现后无未完成信号 → 判定完成
       （首次出现是声明，末次出现是完成——Loki 建议 ③）

    三项全不满足 → 未完成（保守侧：宁可不放行，不可误放行）。
    """
    item = item.strip()
    if not item:
        return False
    _ITEM = re.escape(item)
    for text in texts:
        # 1) 已勾状态优先（最强信号——模型明确勾选）
        if re.search(r"\[[xX]\]\s*" + _ITEM, text):
            return True
        # 2) 完整关键词 + 边界感知（非子串）
        if len(item) >= _MIN_ITEM_LEN and re.search(
            r"(?<![\w\u4e00-\u9fff])" + _ITEM + r"(?![\w\u4e00-\u9fff])", text
        ):
            # 3) 末次出现后无未完成信号 → 完成
            _tail = text[text.rfind(item):]
            if not any(sig in _tail for sig in _UNFINISHED_SIGNALS):
                return True
    return False

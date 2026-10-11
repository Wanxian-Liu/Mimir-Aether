"""Markdown → 飞书卡片（JSON 2.0）—— 2026-10-11 Mimir 自研。

动机（实测）：
  1. 主 chat 回复此前恒为纯文本（`msg_type=text`）⇒ markdown 符号**裸露**
     （`**粗体**`、`## 标题`、`| a | b |` 全是字面），用户 2026-10-11 反馈
     "全是文本和各种符号"。
  2. 飞书卡片 markdown 组件**不支持表格语法**（官方「支持的语法」表内无「表格」，
     2026-10-11 实测 `含表格? False`）⇒ 管道表格会裸露，须单独转 `table` 组件。
  3. `table` 组件写法已实测合法（cardkit 建卡 `ok:true` + card_id）。

设计：
  - 只做「markdown 文本 ⇒ 卡片」这一件事；HTML 模板路径仍走
    `html_to_feishu_card.convert_or_fallback`（显式标记时）。
  - 任何异常都回退纯文本（绝不因美化而丢消息）。

公开接口：
  build_card(md, title=None) -> dict        # 飞书卡片 JSON（2.0）
  to_card_message(md, title=None) -> dict   # {"type": "card_json", "data": "<json str>"}
  convert_or_fallback(md, title=None) -> dict
      {"mode": "card"|"text", "payload": ..., "fallback_reason": ...}
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

# 低于此长度不包卡：极短回复包卡 = 形式主义（用户 2026-10-11 明确反对）
CARD_MIN_CHARS = 300
MAX_ELEMENTS = 50
MAX_MD_CHARS = 6000      # 单个 markdown 元素上限
MAX_TABLE_COLS = 6       # 飞书表格组件列数上限（保守取值）

# 表格分隔行：| --- | :--: | 之类
_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _is_table_sep(line: str) -> bool:
    s = line.strip()
    if "-" not in s:
        return False
    return bool(_SEP_RE.match(s))


def _split_pipe_row(line: str) -> List[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _extract_tables(md: str) -> Tuple[str, List[Dict[str, Any]]]:
    """把 markdown 里的管道表格块摘出来，返回 (剩余文本, [表格,...])。

    只在**非围栏代码块**内检测表格；代码块内原样保留。
    """
    lines = md.split("\n")
    out: List[str] = []
    tables: List[Dict[str, Any]] = []
    i = 0
    in_fence = False
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out.append(line)
            i += 1
            continue
        # 表格判定：本行含 |，且下一行是分隔行
        if (not in_fence and "|" in line and i + 1 < len(lines)
                and _is_table_sep(lines[i + 1])):
            headers = _split_pipe_row(line)
            rows: List[List[str]] = []
            j = i + 2
            while j < len(lines) and "|" in lines[j] and lines[j].strip():
                cells = _split_pipe_row(lines[j])
                if len(cells) >= 2:
                    rows.append(cells)
                j += 1
            if headers and rows:
                tables.append({"headers": headers, "rows": rows})
                out.append(f"%%MIMIR_TABLE_{len(tables) - 1}%%")
                i = j
                continue
        out.append(line)
        i += 1
    return "\n".join(out), tables


def _table_element(tbl: Dict[str, Any]) -> Dict[str, Any]:
    """管道表格 ⇒ 飞书 table 组件（写法 2026-10-11 实测合法）。"""
    headers = [str(h) for h in tbl["headers"]][:MAX_TABLE_COLS]
    rows = [[str(c) for c in r][:MAX_TABLE_COLS] for r in tbl["rows"]]

    def _name(ix: int) -> str:
        return f"c{ix}"

    def _disp(ix: int, raw: str) -> str:
        # 飞书不接受空列名（230099 / 200907）
        t = raw.strip() or "—"
        return t[:40]

    columns = [{
        "name": _name(ix),
        "display_name": _disp(ix, h),
        "data_type": "text",
        "horizontal_align": "left",
        "width": "auto",
    } for ix, h in enumerate(headers)]

    out_rows = []
    for r in rows:
        item = {_name(ix): (r[ix][:120] if ix < len(r) else "") for ix in range(len(headers))}
        out_rows.append(item)

    return {
        "tag": "table",
        "page_size": max(1, min(len(out_rows), 10)),
        "row_height": "low",
        "header_style": {
            "text_align": "left", "text_size": "normal",
            "background_style": "grey", "text_color": "default",
            "bold": True, "lines": 1,
        },
        "columns": columns,
        "rows": out_rows,
    }


def _derive_title(md: str) -> Tuple[Optional[str], str]:
    """若首行是独立标题（#/##/### 或整行加粗），拿它当卡片标题并从正文摘除。"""
    lines = md.split("\n")
    for ix, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        m = re.match(r"^#{1,3}\s+(.*)$", s)
        if m:
            title = m.group(1).strip()
            del lines[ix]
            return (title[:60] or None), "\n".join(lines)
        m = re.match(r"^\*\*(.+?)\*\*$", s)
        if m:
            title = m.group(1).strip()
            del lines[ix]
            return (title[:60] or None), "\n".join(lines)
        break
    return None, md


def build_card(md: str, title: Optional[str] = None) -> Dict[str, Any]:
    """markdown ⇒ 飞书卡片 JSON（schema 2.0）。"""
    if not isinstance(md, str) or not md.strip():
        raise ValueError("empty markdown")

    body_md, tables = _extract_tables(md)
    if title is None:
        title, body_md = _derive_title(body_md)

    elements: List[Dict[str, Any]] = []

    # 正文按表格占位切段 ⇒ markdown 元素 / table 元素 交替
    parts = re.split(r"%%MIMIR_TABLE_(\d+)%%", body_md)
    for ix in range(0, len(parts), 2):
        chunk = (parts[ix] or "").strip()
        if chunk:
            elements.append({"tag": "markdown", "content": chunk[:MAX_MD_CHARS]})
        if ix + 1 < len(parts):
            tix = int(parts[ix + 1])
            if 0 <= tix < len(tables):
                elements.append(_table_element(tables[tix]))

    if not elements:
        elements = [{"tag": "markdown", "content": md.strip()[:MAX_MD_CHARS]}]

    if len(elements) > MAX_ELEMENTS:
        elements = elements[: MAX_ELEMENTS - 1]
        elements.append({"tag": "markdown",
                         "content": "⚠️ 内容过多，已截断。"})

    card: Dict[str, Any] = {
        "schema": "2.0",
        "config": {"wide_screen_mode": True},
        "body": {"elements": elements},
    }
    if title:
        card["header"] = {
            "title": {"tag": "plain_text", "content": str(title)[:100]},
            "template": "blue",
        }
    return card


def card_content_json(md: str, title: Optional[str] = None) -> str:
    """⇒ 可直接塞进 im/v1/messages 的 interactive `content`。

    2026-10-11 实测：inline 2.0 卡片的 content 必须是**卡片 JSON 原文**；
    用 `{"type":"card_json","data":...}` 信封会报 200621 parse card json err。
    """
    return json.dumps(build_card(md, title), ensure_ascii=False)


def convert_or_fallback(md: str, title: Optional[str] = None) -> Dict[str, Any]:
    """安全转换：任何异常 ⇒ 回退纯文本（绝不丢消息）。

    返回：
      mode          "card" | "text"
      payload       card ⇒ 卡片 dict（供自测/校验）；text ⇒ 原文
      content_json  card ⇒ 可直接发送的 content 字符串
      fallback_reason  仅回退时存在
    """
    try:
        card = build_card(md, title)
        return {
            "mode": "card",
            "payload": card,
            "content_json": json.dumps(card, ensure_ascii=False),
        }
    except Exception as exc:  # noqa: BLE001 —— 兜底必须宽
        return {"mode": "text", "payload": md, "fallback_reason": str(exc)}


# ── 开关 ─────────────────────────────────────────────
# True  ⇒ 主 chat 回复默认卡片化（≥CARD_MIN_CHARS 才包卡）
# False ⇒ 全部纯文本（一键回滚）
USE_MD_CARD = True
# ─────────────────────────────────────────────────────

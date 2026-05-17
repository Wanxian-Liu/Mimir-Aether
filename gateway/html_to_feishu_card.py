"""
HTML → Feishu Card JSON 转换器

将 MimirAether HTML 输出模板的子集转换为飞书卡片消息 JSON。
支持飞书卡片支持的 HTML 语义元素，不支持的自动降级。

飞书卡片文档: https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/card-components

使用:
    from gateway.html_to_feishu_card import convert
    card_json = convert(html_content, title="报告标题")

回退策略:
    1. 飞书卡片 JSON（优先）
    2. 纯文本摘录（卡片不支持时）
    3. 原始 Markdown（任何失败时）← 跟现在一模一样
"""

from html import unescape as _unescape_html
import re
import json
from datetime import datetime
from typing import Optional


def _extract_body(html: str) -> str:
    """提取 <body> 或最外层 div 内的内容"""
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
    if body_match:
        return body_match.group(1)
    # Try the mimir wrapper
    mimir_match = re.search(
        r'<!-- MIMIR:HTML_OUTPUT[^>]*-->(.*?)<!-- /MIMIR:HTML_OUTPUT -->',
        html, re.DOTALL
    )
    if mimir_match:
        return mimir_match.group(1)
    return html


def _extract_first(html: str, tag: str) -> Optional[str]:
    """提取第一个指定标签的文本内容"""
    match = re.search(fr'<{tag}[^>]*>(.*?)</{tag}>', html, re.DOTALL)
    if match:
        return re.sub(r'<[^>]+>', '', match.group(1)).strip()
    return None


def _extract_sections(html: str) -> list[dict]:
    """从 HTML 中提取所有 section 标题和内容 (跳过 h1——已用作卡片标题)"""
    sections = []
    # 匹配 h2-h3 标题（h1 留给卡片 header）
    pattern = re.compile(r'<(h[23])[^>]*>(.*?)</\1>(.*?)(?=<h[23]|$)', re.DOTALL)
    for match in pattern.finditer(html):
        heading = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        content = match.group(3).strip()
        if heading and len(heading) < 100:
            sections.append({"heading": heading, "content": content})
    return sections


def _html_table_to_card(html: str) -> Optional[dict]:
    """将 HTML <table> 转换为飞书卡片表格元素"""
    table_match = re.search(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
    if not table_match:
        return None

    table_html = table_match.group(1)

    # 提取表头
    headers = []
    thead_match = re.search(r'<thead[^>]*>(.*?)</thead>', table_html, re.DOTALL)
    if thead_match:
        headers = [re.sub(r'<[^>]+>', '', h).strip()
                   for h in re.findall(r'<th[^>]*>(.*?)</th>', thead_match.group(1), re.DOTALL)]
    if not headers:
        headers = [re.sub(r'<[^>]+>', '', h).strip()
                   for h in re.findall(r'<th[^>]*>(.*?)</th>', table_html, re.DOTALL)]

    # 提取行
    rows = []
    tbody_match = re.search(r'<tbody[^>]*>(.*?)</tbody>', table_html, re.DOTALL)
    target = tbody_match.group(1) if tbody_match else table_html
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', target, re.DOTALL):
        cells = [re.sub(r'<[^>]+>', '', td).strip()
                 for td in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)]
        if cells:
            rows.append(cells)

    if not headers or not rows:
        return None

    # 飞书卡片表格：最多 4 列
    if len(headers) > 4:
        headers = headers[:4]
        rows = [row[:4] for row in rows]

    # 过滤空列名（飞书不允许列名为空）
    # decode HTML entities + strip 零宽字符
    valid_indices = [i for i, h in enumerate(headers) if _unescape_html(h).strip().strip('\u200b\u200c\u200d\u2060\ufeff')]
    if not valid_indices:
        return None
    headers = [headers[i] for i in valid_indices]
    rows = [[row[i] if i < len(row) else "" for i in valid_indices] for row in rows]

    # 构建
    header_row = [{"content": h, "tag": "plain_text"} for h in headers]
    cols = [{"data": [{"content": row[i] if i < len(row) else "", "tag": "plain_text"}
                       for row in rows]}
            for i in range(len(headers))]

    return {
        "tag": "table",
        "header": header_row,
        "columns": cols
    }


def _strip_html_tags(text: str) -> str:
    """去除 HTML 标签，保留文本"""
    # 处理 <br> 为换行
    text = re.sub(r'<br\s*/?>', '\n', text)
    # 去除标签
    text = re.sub(r'<[^>]+>', '', text)
    # 清理多余空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text


def _extract_notes(html: str) -> list[dict]:
    """提取 <div class="mimir-note"> 为飞书 note 元素（黄色背景块）"""
    notes = []
    pattern = r'<div[^>]*class="[^"]*mimir-note[^"]*"[^>]*>(.*?)</div>'
    for match in re.findall(pattern, html, re.DOTALL):
        text = _strip_html_tags(match)
        if text.strip():
            notes.append(text.strip()[:1000])
    return notes


def _extract_columns(html: str) -> Optional[list[str]]:
    """提取 <div class="mimir-columns"> 为多列布局"""
    import re as _re
    # 手动找 mimir-columns 的开闭标签（处理嵌套 div）
    start_marker = 'class="mimir-columns"'
    start_idx = html.find(start_marker)
    if start_idx == -1:
        # 也匹配 class="...mimir-columns..." (多类)
        m = _re.search(r'class="[^"]*mimir-columns[^"]*"', html)
        if not m:
            return None
        start_idx = m.start()

    # 从 class 所属 div 的开标签开始
    div_start = html.rfind('<div', 0, start_idx)
    if div_start == -1:
        return None
    tag_end = html.find('>', start_idx)
    if tag_end == -1:
        return None

    # 计数匹配 </div>
    depth = 1
    pos = tag_end + 1
    while depth > 0 and pos < len(html):
        next_open = html.find('<div', pos)
        next_close = html.find('</div>', pos)
        if next_close == -1:
            return None
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = next_open + 4
        else:
            depth -= 1
            if depth == 0:
                inner = html[tag_end + 1:next_close]
                # 提取每列
                columns = []
                for col_match in _re.finditer(
                    r'<div[^>]*class="[^"]*mimir-col[^"]*"[^>]*>(.*?)</div>',
                    inner, _re.DOTALL
                ):
                    text = _strip_html_tags(col_match.group(1))
                    if text.strip():
                        columns.append(text.strip()[:500])
                return columns if columns else None
            pos = next_close + 6
    return None


def _extract_actions(html: str) -> list[dict]:
    """提取 <button class="mimir-action"> 为飞书 action 按钮（支持 url 属性）"""
    actions = []
    pattern_full = r'<button([^>]*class="[^"]*mimir-action[^"]*"[^>]*)>(.*?)</button>'
    for match in re.findall(pattern_full, html, re.DOTALL):
        attrs_str, inner = match
        label = _strip_html_tags(inner).strip()
        if not label:
            continue
        # Parse url attribute from button
        url_match = re.search(r'''url\s*=\s*["']([^"']+)["']''', attrs_str)
        action_url = url_match.group(1) if url_match else None
        btn = {
            "tag": "button",
            "text": {"tag": "plain_text", "content": label[:40]},
            "type": "default",
        }
        if action_url:
            btn["multi_url"] = {
                "url": action_url, "android_url": action_url,
                "ios_url": action_url, "pc_url": action_url,
            }
        else:
            # Fallback: google/wiki search button stays non-URL (cosmetic)
            btn["type"] = "default"
        actions.append(btn)
    return actions


def _html_to_card_elements(html: str, is_feishu: bool = True) -> list[dict]:
    """
    将 HTML 内容转换为飞书卡片元素列表。

    转换规则（对齐飞书卡片能力）:
    - <h1>/<h2>/<h3> → 标题文本
    - <table> → 飞书表格组件
    - <div class="mimir-note"> → 飞书 note 元素（黄色背景块）★ 明显视觉差异
    - <div class="mimir-columns"> → 飞书 column_set（并排多列）★ 明显视觉差异
    - <button class="mimir-action"> → 飞书 action 按钮 ★ 明显视觉差异
    - <details><summary> → 折叠文本（📋 前缀标记）
    - <pre><code> → 代码块
    - <div class="mimir-progress"> → 进度条
    - <hr> → 分割线
    - <strong>/<em> → lark_md 格式
    - 普通段落 → lark_md 文本

    Args:
        html: HTML 内容
        is_feishu: True 时优化飞书格式，False 时生成通用格式

    Returns:
        飞书卡片元素列表
    """
    elements = []

    # 剥离 body
    body = _extract_body(html)

    # 0. 提取 note 元素（优先处理，在文本清洗前）
    notes = _extract_notes(body)
    for note_text in notes:
        elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": note_text}]
        })
    body = re.sub(r'<div[^>]*class="[^"]*mimir-note[^"]*"[^>]*>.*?</div>',
                  '', body, flags=re.DOTALL)

    # 0.5 提取 action 按钮（必须在 column_set 之前，按钮通常在 columns 内部）
    actions = _extract_actions(body)
    body = re.sub(r'<button[^>]*class="[^"]*mimir-action[^"]*"[^>]*>.*?</button>',
                  '', body, flags=re.DOTALL)

    # 0.6 提取 column_set
    columns = _extract_columns(body)
    body = re.sub(r'<div[^>]*class="[^"]*mimir-columns[^"]*"[^>]*>.*?</div>\s*(?=<div|</div|$)',
                  '', body, flags=re.DOTALL)

    # 1. 尝试表格转换
    table_card = _html_table_to_card(body)
    if table_card:
        elements.append(table_card)
        # 移除表格以免重复渲染
        body = re.sub(r'<table[^>]*>.*?</table>', '', body, flags=re.DOTALL)

    # 2. 提取代码块
    code_blocks = []
    for pre in re.findall(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', body, re.DOTALL):
        code_text = pre.strip()
        code_blocks.append(code_text)
        body = body.replace(pre, f'%%CODE_BLOCK_{len(code_blocks)-1}%%')

    # 3. 提取 <details> 折叠区
    details_blocks = []
    for detail in re.findall(r'<details[^>]*>(.*?)</details>', body, re.DOTALL):
        summary_match = re.search(r'<summary[^>]*>(.*?)</summary>', detail, re.DOTALL)
        summary = _strip_html_tags(summary_match.group(1)) if summary_match else "详情"
        detail_body = re.sub(r'<summary[^>]*>.*?</summary>', '', detail, flags=re.DOTALL)
        detail_text = _strip_html_tags(detail_body)
        details_blocks.append({"summary": summary, "body": detail_text})
        body = body.replace(detail, f'%%DETAILS_{len(details_blocks)-1}%%')

    # 4. 提取进度条
    progress_bars = []
    for pb in re.findall(
        r'<div[^>]*class="[^"]*mimir-progress[^"]*"[^>]*>.*?(\d+)%',
        body, re.DOTALL
    ):
        progress_bars.append(int(pb))
        body = re.sub(
            r'<div[^>]*class="[^"]*mimir-progress[^"]*"[^>]*>.*?</div>',
            f'%%PROGRESS_{len(progress_bars)-1}%%', body, flags=re.DOTALL
    )

    # 5. 按 section 分割处理
    sections = _extract_sections(body)
    if not sections:
        sections = [{"heading": "", "content": body}]

    for i, sec in enumerate(sections):
        # 标题
        if sec["heading"]:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": f"**{sec['heading']}**"
                }
            })

        # 内容
        content = sec["content"]
        # 恢复代码块
        for idx, code in enumerate(code_blocks):
            placeholder = f'%%CODE_BLOCK_{idx}%%'
            if placeholder in content:
                code_display = code[:800] + ("\n... (truncated)" if len(code) > 800 else "")
                content = content.replace(
                    placeholder,
                    f'```\n{code_display}\n```'
                )

        # 恢复 details
        for idx, detail in enumerate(details_blocks):
            placeholder = f'%%DETAILS_{idx}%%'
            if placeholder in content:
                folded = f"📋 **{detail['summary']}**\n{detail['body'][:500]}"
                content = content.replace(placeholder, folded)

        # 恢复进度条
        for idx, pct in enumerate(progress_bars):
            placeholder = f'%%PROGRESS_{idx}%%'
            if placeholder in content:
                bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
                content = content.replace(
                    placeholder,
                    f"**进度** {bar} {pct}%"
                )

        # 清理剩余 HTML
        clean = _strip_html_tags(content)
        if clean:
            elements.append({
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": clean[:3000]  # 飞书单段限制
                }
            })

        # 节间分割线
        if i < len(sections) - 1 and clean:
            elements.append({"tag": "hr"})

    # 5.5 插入 column_set（在主要内容之后）
    if columns and len(columns) >= 2:
        col_elements = []
        width_map = {2: 2, 3: 3, 4: 3}  # Feishu width: 1-4, 2=1/2, 3=1/3
        w = width_map.get(len(columns), 2)
        for col_text in columns[:4]:  # 最多4列
            col_elements.append({
                "tag": "column",
                "width": f"weighted_{w}",
                "elements": [{
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": col_text[:800]}
                }]
            })
        elements.append({"tag": "column_set", "flex_mode": "bisect", "columns": col_elements})

    # 6. 插入 action 按钮（在最后）
    if actions:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "action",
            "actions": actions[:3]  # 飞书最多3个
        })

    return elements


def convert(html: str, title: str = "MimirAether Report") -> dict:
    """
    主转换函数: HTML → 飞书卡片 JSON

    Args:
        html: MimirAether HTML 输出（含 MIMIR:HTML_OUTPUT 标记）
        title: 卡片标题

    Returns:
        飞书 interactive 消息 dict
    """
    elements = _html_to_card_elements(html)

    # 限制元素数量（飞书卡片最多50个）
    if len(elements) > 50:
        elements = elements[:49]
        elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": "⚠️ 内容过多，已截断。完整版见 wiki/raw/"}]
        })

    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {
                "tag": "plain_text",
                "content": title[:100]
            },
            "template": "blue"
        },
        "elements": elements,
        "card_link": {
            "url": "",
            "android_url": "",
            "ios_url": "",
            "pc_url": ""
        }
    }

    return {
        "msg_type": "interactive",
        "content": json.dumps(card, ensure_ascii=False)
    }


def convert_or_fallback(html: str, title: str = "MimirAether") -> dict:
    """
    安全转换：如果卡片生成失败或不确定效果，回退到纯文本。

    Returns:
        {"mode": "card"|"text", "payload": ...}
    """
    try:
        card = convert(html, title)
        return {"mode": "card", "payload": card}
    except Exception as e:
        # 任何失败 → 回退到纯文本
        plain = _strip_html_tags(html)
        return {
            "mode": "text",
            "payload": f"{title}\n\n{plain[:4000]}",
            "fallback_reason": str(e)
        }


# ── 快速开关 ──────────────────────────────────────────
# USE_HTML_OUTPUT = True   → HTML→Card 模式
# USE_HTML_OUTPUT = False  → 纯 Markdown（跟现在一样）
USE_HTML_OUTPUT = True  # 2026-05-14 飞书验证阶段开启
# ───────────────────────────────────────────────────────

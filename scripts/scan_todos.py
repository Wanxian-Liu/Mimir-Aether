#!/usr/bin/env python3
"""
TODO抽取工具 — 扫描代码库提取 TODO/FIXME/HACK/XXX/OPTIMIZE 标记

输出：
    data/todos.json     — 结构化数据（供自动化消费）
    docs/TODO_REPORT.md — 可读报告

用法：
    python scripts/scan_todos.py              # 全量扫描
    python scripts/scan_todos.py --json-only  # 仅输出JSON
    python scripts/scan_todos.py --report-only # 仅输出报告
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

# ── 配置 ────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent

# 标签必须全大写（排除自然语言中的常见词如 "optimize", "hack", "xxx"）
_RAW_TAGS = r'TODO|FIXME|HACK|XXX|OPTIMIZE'

# 匹配规则：
#   1. 标签必须在注释上下文中（行中有 # // -- /* 或无代码前缀）
#      或标签就是该行的主要内容（行首只有空白/标点）
#   2. 标签: 全大写
#   3. 标签后: 空格/冒号/括号 或 行尾
#   4. 文本: 标签后的内容（到行尾）
#
# 负向排除：标签前有字母（代码标识符中的 OPTIMIZE/TODO 不算）
TAG_PATTERN = re.compile(
    rf'(?:^|[^a-zA-Z])(?P<tag>{_RAW_TAGS})(?:$|[\s:：(])(?P<text>.*?)$',
    re.IGNORECASE
)

def _is_in_comment_context(match: re.Match, ext: str) -> bool:
    """检查标签是否在注释上下文中。

    对于代码文件（.py .sh .toml），标签必须出现在 # 注释标记之后。
    对于文档文件（.md .json .yml .yaml），可能出现在任意位置。
    """
    line = match.string
    if ext in ('.md', '.json', '.yml', '.yaml'):
        return True
    if ext in ('.py', '.sh', '.bash', '.toml'):
        # 代码文件：标签必须在 # 之后
        idx = line.find('#')
        return idx >= 0 and match.start('tag') > idx
    return True

def _is_valid_tag(match: re.Match) -> bool:
    """二次验证：排除代码标识符中的误匹配"""
    tag = match.group('tag')
    if tag != tag.upper():
        return False

    # 标签在代码标识符中（ModuleType.OPTIMIZE，_TODO_LIST 等）→ 排除
    text = match.string
    start = match.start('tag')
    if start > 0 and text[start - 1] in ('.', '_'):
        return False

    # XXX 特判：前后都必须是单词边界/非字母
    if tag == 'XXX':
        end = match.end('tag')
        if start > 0 and text[start - 1].isalpha():
            return False
        if end < len(text) and text[end].isalpha():
            return False
    return True

TAG_PRIORITY = {
    'FIXME': 0,     # 必须修复
    'XXX': 0,       # 必须修复
    'HACK': 1,      # 技术债
    'TODO': 2,      # 待办
    'OPTIMIZE': 3,  # 优化
}

TAG_EMOJI = {
    'FIXME': '🔴',
    'XXX': '🔴',
    'HACK': '🟠',
    'TODO': '🟡',
    'OPTIMIZE': '🟢',
}

SCAN_EXTENSIONS = {'.py', '.md', '.yaml', '.yml', '.sh', '.bash', '.json', '.toml'}
SKIP_DIRS = {
    '__pycache__', '.git', 'node_modules', 'venv', '.venv',
    '.backup', '.backups', 'backups', 'checkpoints',
    'cache', '.mypy_cache', '.pytest_cache', '.ruff_cache',
    'dist', 'build', 'egg-info',
}

# 输出文件（避免自指反馈回路）
SKIP_FILES = {'data/todos.json', 'docs/TODO_REPORT.md'}

# 大文件跳过（>500KB）
MAX_FILE_SIZE = 500 * 1024

# ── 数据模型 ────────────────────────────────────────────────

@dataclass
class TodoItem:
    file: str           # 相对路径
    line: int
    tag: str            # TODO/FIXME/HACK/XXX/OPTIMIZE
    text: str           # 标签后的文本
    author: str = ''    # git blame 获取
    priority: int = 3
    created_at: str = '' # ISO 日期

@dataclass
class TodoReport:
    generated_at: str
    total: int
    by_tag: dict = field(default_factory=dict)
    by_priority: dict = field(default_factory=dict)
    items: list = field(default_factory=list)

# ── 核心逻辑 ────────────────────────────────────────────────

def _should_skip_dir(dirname: str) -> bool:
    return dirname in SKIP_DIRS or dirname.startswith('.')

def _get_git_author(filepath: str, line_num: int) -> str:
    """通过 git blame 获取指定行的最后修改者"""
    try:
        result = subprocess.run(
            ['git', 'blame', '-L', f'{line_num},{line_num}', '--line-porcelain', filepath],
            capture_output=True, text=True, timeout=5,
            cwd=str(REPO_ROOT)
        )
        for line in result.stdout.split('\n'):
            if line.startswith('author '):
                return line[7:].strip()
    except Exception:
        pass
    return ''

def _get_git_date(filepath: str, line_num: int) -> str:
    """通过 git log 获取指定行首次添加的日期"""
    try:
        result = subprocess.run(
            ['git', 'log', '--follow', '--diff-filter=A', '--format=%aI',
             '-L', f'{line_num},{line_num}:{filepath}'],
            capture_output=True, text=True, timeout=10,
            cwd=str(REPO_ROOT)
        )
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line and line[0].isdigit():
                return line  # ISO 8601
    except Exception:
        pass
    return ''

def _scan_file(filepath: Path) -> List[TodoItem]:
    """扫描单个文件"""
    items = []
    try:
        size = filepath.stat().st_size
        if size > MAX_FILE_SIZE:
            return items

        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception:
        return items

    rel_path = str(filepath.relative_to(REPO_ROOT))
    ext = filepath.suffix

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # 跳过纯注释行（效率优化：标签可能在注释中，但更可能在代码内联注释）
        # 对注释行我们仍扫描，但降低优先级

        # 代码文件必须在注释上下文中
        match = TAG_PATTERN.search(stripped)
        if not match or not _is_valid_tag(match) or not _is_in_comment_context(match, ext):
            # 也检查全行模式（纯标签行，必须全大写且精确匹配）
            _upper = stripped.upper()
            _matched_tag = None
            for t in ('TODO', 'FIXME', 'HACK', 'XXX', 'OPTIMIZE'):
                if _upper.startswith(t) and (len(stripped) == len(t) or stripped[len(t)] in (' ', ':', '：', '\t', '(')):
                    # 排除代码标识符上下文（TODO_FIELD, ModuleType.OPTIMIZE 等）
                    _before_t = stripped[:stripped.upper().find(t)]
                    if _before_t and _before_t[-1] in ('.', '_'):
                        continue
                    _matched_tag = t
                    break
            if _matched_tag:
                # 验证注释上下文（代码文件中必须在 # 之后）
                tag_pos = stripped.upper().find(_matched_tag)
                if ext in ('.py', '.sh', '.bash', '.toml'):
                    hash_pos = stripped.find('#')
                    if hash_pos < 0 or tag_pos <= hash_pos:
                        _matched_tag = None  # 标签不在注释中，跳过
            if _matched_tag:
                rest = stripped[len(_matched_tag):].lstrip(' :：\t')
                items.append(TodoItem(
                    file=rel_path, line=i, tag=_matched_tag,
                    text=rest,
                    priority=TAG_PRIORITY.get(_matched_tag, 3),
                ))
            continue

        tag = match.group('tag').upper()
        text = match.group('text').strip()

        items.append(TodoItem(
            file=rel_path, line=i, tag=tag,
            text=text,
            priority=TAG_PRIORITY.get(tag, 3),
        ))

    return items

def scan_all() -> TodoReport:
    """全量扫描"""
    items = []
    total_files = 0

    for root, dirs, files in os.walk(REPO_ROOT):
        # 跳过不需要的目录
        dirs[:] = [d for d in dirs if not _should_skip_dir(d)]

        for f in files:
            _, ext = os.path.splitext(f)
            if ext not in SCAN_EXTENSIONS:
                continue

            total_files += 1
            filepath = Path(root) / f
            rel_path = str(filepath.relative_to(REPO_ROOT))
            if rel_path in SKIP_FILES:
                continue
            items.extend(_scan_file(filepath))

    # 统计
    by_tag = {}
    by_priority = {}
    for item in items:
        by_tag[item.tag] = by_tag.get(item.tag, 0) + 1
        by_priority[item.priority] = by_priority.get(item.priority, 0) + 1

    # 按优先级排序，同优先级按文件排序
    items.sort(key=lambda x: (x.priority, x.file, x.line))

    return TodoReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total=len(items),
        by_tag=by_tag,
        by_priority=by_priority,
        items=[asdict(item) for item in items],
    )

def _enrich_with_git(report: TodoReport) -> None:
    """为 TODO 项附加 git blame 信息（慢操作）"""
    for item_dict in report.items:
        filepath = str(REPO_ROOT / item_dict['file'])
        line = item_dict['line']
        item_dict['author'] = _get_git_author(filepath, line)
        item_dict['created_at'] = _get_git_date(filepath, line)

# ── 输出 ────────────────────────────────────────────────────

def _build_markdown(report: TodoReport) -> str:
    """生成 Markdown 报告"""
    lines = [
        f"# TODO 抽取报告",
        f"",
        f"**生成时间**: {report.generated_at}",
        f"**总计**: {report.total} 项",
        f"",
        f"## 按标签",
        f"",
    ]

    for tag in ['FIXME', 'XXX', 'HACK', 'TODO', 'OPTIMIZE']:
        count = report.by_tag.get(tag, 0)
        emoji = TAG_EMOJI.get(tag, '')
        if count:
            lines.append(f"- {emoji} **{tag}**: {count}")
    lines.append("")

    lines.append("## 按优先级")
    lines.append("")
    for pri in sorted(report.by_priority.keys()):
        count = report.by_priority[pri]
        label = {0: '🔴 必须修复', 1: '🟠 技术债', 2: '🟡 待办', 3: '🟢 优化'}.get(pri, f'P{pri}')
        lines.append(f"- {label}: {count}")
    lines.append("")

    lines.append("## 详细列表")
    lines.append("")

    # 按文件分组
    by_file = {}
    for item in report.items:
        f = item['file']
        if f not in by_file:
            by_file[f] = []
        by_file[f].append(item)

    for fpath in sorted(by_file.keys()):
        items = by_file[fpath]
        lines.append(f"### `{fpath}` ({len(items)} 项)")
        lines.append("")
        for item in items:
            tag = item['tag']
            emoji = TAG_EMOJI.get(tag, '')
            text = item['text'][:120]
            if len(item.get('text', '')) > 120:
                text += '...'
            author = item.get('author', '')
            date_str = item.get('created_at', '')[:10] if item.get('created_at') else ''

            extra = []
            if author:
                extra.append(f"@{author}")
            if date_str:
                extra.append(date_str)

            prefix = f"L{item['line']}"
            if extra:
                prefix += f" ({', '.join(extra)})"

            lines.append(f"- {emoji} {prefix}: {text}")
        lines.append("")

    # 统计信息
    lines.append("---")
    lines.append(f"_Generated by `scripts/scan_todos.py` — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_")
    lines.append("")

    return '\n'.join(lines)

# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='TODO抽取工具')
    parser.add_argument('--json-only', action='store_true', help='仅输出JSON（不生成报告）')
    parser.add_argument('--report-only', action='store_true', help='仅输出报告（不生成JSON）')
    parser.add_argument('--no-git', action='store_true', help='跳过git blame（更快）')
    parser.add_argument('--out-json', default=None, help='JSON输出路径（默认 data/todos.json）')
    parser.add_argument('--out-report', default=None, help='报告输出路径（默认 docs/TODO_REPORT.md）')
    args = parser.parse_args()

    print(f"🔍 扫描中...")
    report = scan_all()

    if not args.no_git:
        print(f"📋 附加 git blame 信息...")
        _enrich_with_git(report)

    # 输出
    json_path = Path(args.out_json) if args.out_json else (REPO_ROOT / 'data' / 'todos.json')
    report_path = Path(args.out_report) if args.out_report else (REPO_ROOT / 'docs' / 'TODO_REPORT.md')

    write_json = not args.report_only
    write_report = not args.json_only

    if write_json:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json.dump(asdict(report), open(json_path, 'w', encoding='utf-8'),
                  indent=2, ensure_ascii=False)
        print(f"✅ JSON → {json_path}")

    if write_report:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(_build_markdown(report), encoding='utf-8')
        print(f"✅ Report → {report_path}")

    # 摘要
    print(f"\n📊 摘要: {report.total} 项")
    for tag in ['FIXME', 'XXX', 'HACK', 'TODO', 'OPTIMIZE']:
        count = report.by_tag.get(tag, 0)
        if count:
            print(f"   {TAG_EMOJI.get(tag, '')} {tag}: {count}")

if __name__ == '__main__':
    main()

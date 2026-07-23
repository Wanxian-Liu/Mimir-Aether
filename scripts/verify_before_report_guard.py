#!/usr/bin/env python3
"""
verify_before_report_guard.py — 声称\"完成\"前必须验证的运行时守卫。

触发条件：在 Agent 输出包含声称性结论（\"已完成\"/\"已修\"/\"已验证\"等）时，
检查最近 N 条工具调用是否包含至少一次验证操作（read_file / json.load / terminal cat）。
如果没有，则阻止该输出，并返回提示消息。

OpenSpace v2 Pattern: Signal Detector (P3)
  — 扩展版支持主动扫描模式：在 Agent 开始响应前检查 verification_results.jsonl
    中是否有未处理的验证失败记录，提前发出预警而非等到 claim 出现才反应。

Env gate: MIMIR_VERIFY_BEFORE_REPORT=1 (default: enabled)

用法 (作为模块导入):
    from scripts.verify_before_report_guard import check_verification
    result = check_verification(tool_call_history)
    if result['blocked']:
        print(result['message'])

    # 主动扫描模式（OpenSpace v2 P3）:
    from scripts.verify_before_report_guard import proactive_scan
    scan_result = proactive_scan()
    if scan_result['has_unresolved_failures']:
        print(f\"警告：有 {scan_result['failure_count']} 个未处理的验证失败\")

用法 (命令行):
    python3 verify_before_report_guard.py --check \"已完成\" --calls read_file,web_search
    python3 verify_before_report_guard.py --scan   # 主动扫描模式
"""

import os
import re
import json
from pathlib import Path

# 声称性结论的触发词
CLAIM_PATTERNS = [
    r"\b已完成\b",
    r"\b已修\b",
    r"\b已修复\b",
    r"\b已验证\b",
    r"\b验证通过\b",
    r"\b成功了\b",
    r"\b成功\b(?:地|了|完成|提交)",
    r"\b完成\b(?:了|成功|提交)",
    r"\bdone\b",
    r"\bfinished\b",
    r"\bverified\b",
    r"\bfixed\b",
]

# 验证类工具调用（可信来源）
VERIFICATION_TOOL_PATTERNS = [
    "read_file",
    "json.load",
    r'terminal.*cat.*persistent',
    r'terminal.*cat.*\.json',
    r'terminal.*cat.*\.md',
    r"json\.load",
    r"json\.dumps",
    # NOTE: write_file and patch are intentionally included so the regex
    # check below matches them but then EXCLUDES them via the "skip" logic:
]


def has_claim(text: str) -> bool:
    """检查文本是否包含声称性结论"""
    if not text:
        return False
    text_lower = text.lower()
    for pattern in CLAIM_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def has_verification_call(tool_history: list, lookback: int = 5) -> bool:
    """检查最近 lookback 条工具调用中是否包含验证操作

    验证操作定义：至少一次 read_file / json.load / terminal cat 到持久化文件
    """
    if not tool_history:
        return False
    recent = tool_history[-lookback:] if len(tool_history) > lookback else tool_history
    for call in recent:
        call_str = json.dumps(call).lower() if isinstance(call, dict) else str(call).lower()
        for vpat in VERIFICATION_TOOL_PATTERNS:
            if re.search(vpat, call_str):
                # Skip patterns that are NOT real verification:
                # - terminal cat without persistent/json/md paths
                # - write_file / patch (these modify, not verify)
                if "cat" in vpat and "persistent" not in call_str and ".json" not in call_str and ".md" not in call_str:
                    continue
                if vpat in ("write_file", "patch") or re.fullmatch(r"write_file|patch", vpat):
                    continue
                return True
    return False


def check_verification(output_text: str, tool_call_history: list) -> dict:
    """主入口：检查输出是否需要阻止

    返回:
        {"blocked": bool, "message": str, "reason": str}
    """
    # 环境变量门控（默认开启）
    env_gate = os.environ.get("MIMIR_VERIFY_BEFORE_REPORT", "1")
    if env_gate != "1":
        return {"blocked": False, "message": "", "reason": "env_gate_disabled"}

    if not has_claim(output_text):
        return {"blocked": False, "message": "", "reason": "no_claim"}

    if has_verification_call(tool_call_history):
        return {"blocked": False, "message": "", "reason": "verified"}

    # 阻止：有声称性结论但无验证调用
    return {
        "blocked": True,
        "message": (
            "[BLOCKED:verify-before-report] 你输出的最后一句话包含声称性结论 "
            "（已完成/已修/已验证），但最近 5 条工具调用中没有验证操作（read_file / json.load 等）。\n\n"
            "请在声称完成之前先调 read_file 或 json.load 确认盘上数据与声称一致。\n"
            "这条消息已从对话中移除，验证通过后请重新输出你的结论。"
        ),
        "reason": "claim_without_verification",
    }


def proactive_scan(max_lookback: int = 10) -> dict:
    """主动扫描模式 — OpenSpace v2 P3: Signal Detector

    在 Agent 开始响应前检查 verification_results.jsonl 中是否有
    未处理的验证失败记录，提前发出预警而非等到 claim 出现才反应。

    返回:
        {
            "has_unresolved_failures": bool,
            "failure_count": int,
            "failures": [{"time": str, "failure_type": str, "detail": str}],
            "scan_time": str
        }
    """
    from mimir_constants import get_mimir_home
    log_path = Path(get_mimir_home()) / "data" / "verification_results.jsonl"
    if not log_path.exists():
        return {
            "has_unresolved_failures": False,
            "failure_count": 0,
            "failures": [],
            "scan_time": __import__("datetime").datetime.now().isoformat()
        }

    failures = []
    with open(log_path) as f:
        lines = f.readlines()
        # 只读最近 max_lookback 条
        for line in lines[-max_lookback:]:
            try:
                entry = json.loads(line)
                if not entry.get("passed", True):
                    failures.append({
                        "time": entry.get("timestamp", "unknown"),
                        "failure_type": entry.get("failure_type", "unknown"),
                        "detail": entry.get("message", "")
                    })
            except (json.JSONDecodeError, KeyError):
                continue

    now = __import__("datetime").datetime.now().isoformat()
    return {
        "has_unresolved_failures": len(failures) > 0,
        "failure_count": len(failures),
        "failures": failures,
        "scan_time": now
    }


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="验证守卫：检查声称前是否先验证")
    parser.add_argument("--check", help="要检查的文本")
    parser.add_argument("--calls", help="逗号分隔的工具调用列表")
    parser.add_argument("--scan", action="store_true", help="主动扫描模式（检查未处理的验证失败）")
    args = parser.parse_args()

    if args.scan:
        result = proactive_scan()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        text = args.check or "已完成"
        calls = [{"tool": c.strip()} for c in (args.calls or "").split(",") if c.strip()]
        result = check_verification(text, calls)
        print(json.dumps(result, indent=2, ensure_ascii=False))

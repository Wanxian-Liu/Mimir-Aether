#!/usr/bin/env python3
"""
能力快照 — 扫描5个最怕退化的能力，记录当前状态。

每项能力的检查维度：
1. 可用性（工具/技能是否存在）
2. 完整性（关键结构是否完整）
3. 最近使用痕迹（按每个能力的 threshold_days 检查最近调用时间）

写入：heartbeat/logs/capability_snapshot.log
"""
import sys
import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from mimir_constants import get_skills_dir

HEARTBEAT_DIR = Path(__file__).resolve().parent
LOG_FILE = HEARTBEAT_DIR / "logs" / "capability_snapshot.log"
SOFT_LOG = HEARTBEAT_DIR / "logs" / "soft_beat.log"

# Primary skills root (project tree)
SKILLS_DIR = get_skills_dir()

# ============================================================
# 5 项最怕退化的能力
# ============================================================
# 每项能力定义：
#   - name: 唯一标识
#   - why: 退化后果描述
#   - check: 检查方式简述
#   - threshold_days: 超过此天数未使用即判定为退化
#   - tool_names: 软心跳日志中用于匹配的工具/技能名（支持多个）
#   - status: 初始状态
CAPABILITIES = [
    {
        "name": "skill_view",
        "why": "技能是程序性记忆，如果skill_view不可用=失忆",
        "check": "工具存在 + 技能文件可读",
        "threshold_days": 14,
        "tool_names": ["skill_view"],
        "status": "unknown",
    },
    {
        "name": "skill_manage",
        "why": "技能管理是元认知，退化则无法学习/更新技能",
        "check": "工具存在 + 可写",
        "threshold_days": 14,
        "tool_names": ["skill_manage"],
        "status": "unknown",
    },
    {
        "name": "produce_capsule",
        "why": "胶囊系统是核心知识产出机制，退化=知识工厂停产",
        "check": "工具存在 + 可响应",
        "threshold_days": 30,
        "tool_names": ["produce_capsule"],
        "status": "unknown",
    },
    {
        "name": "session_search",
        "why": "跨会话记忆检索，退化=每次从零开始",
        "check": "工具存在",
        "threshold_days": 21,
        "tool_names": ["session_search"],
        "status": "unknown",
    },
    {
        "name": "root_cause_debugging",
        "why": "根源调试习惯（4-phase），退化=遇bug直接猜而非追根溯源",
        "check": "systematic-debugging 技能存在 + 4-phase结构完整",
        "threshold_days": 30,
        "tool_names": ["systematic-debugging", "root_cause", "debugging"],
        "status": "unknown",
    },
]


def check_tool_availability(tool_name: str) -> dict:
    """检查工具是否可用"""
    result = {"available": False, "detail": ""}

    # 1. 检查主 skills 根下是否有对应的技能目录
    candidates = list(SKILLS_DIR.glob(f"**/{tool_name}*"))
    if candidates:
        result["available"] = True
        result["detail"] = f"skill dirs: {len(candidates)}"
    else:
        # 二级检查：项目 skills/ 下
        project_skills = HEARTBEAT_DIR.parent / "skills"
        if project_skills.exists():
            proj_candidates = list(project_skills.glob(f"**/{tool_name}*"))
            if proj_candidates:
                result["available"] = True
                result["detail"] = f"found in project skills: {proj_candidates[0].name}"
            else:
                result["detail"] = "not found in any skills path"
        else:
            result["detail"] = "not found in any skills path"

    return result


def check_recent_usage(tool_names: list[str], threshold_days: int) -> dict:
    """
    检查软心跳日志中是否有指定工具的最近使用记录。
    
    退化判定依据：超过 threshold_days 未使用 → 退化风险。
    """
    result = {
        "used_recently": False,
        "last_used": "never",
        "days_since_last_use": None,
        "degraded": True,  # 默认退化，找到近期使用才标记为正常
        "detail": "",
    }

    try:
        if not SOFT_LOG.exists() or SOFT_LOG.stat().st_size == 0:
            result["detail"] = "no soft_beat log available"
            return result

        lines = SOFT_LOG.read_text().strip().split("\n")
        last_ts = None

        for line in reversed(lines):
            for tn in tool_names:
                if f"| {tn} |" in line:
                    parts = line.split(" | ")
                    ts_str = parts[0] if len(parts) > 0 else None
                    if ts_str:
                        last_ts = ts_str
                    break
            if last_ts:
                break

        if last_ts:
            try:
                last_dt = datetime.fromisoformat(last_ts)
                now = datetime.now(timezone.utc)
                delta = now - last_dt
                days_since = delta.total_seconds() / 86400.0
                result["last_used"] = last_ts
                result["days_since_last_use"] = round(days_since, 1)
                result["used_recently"] = days_since <= threshold_days
                result["degraded"] = days_since > threshold_days

                if result["degraded"]:
                    result["detail"] = (
                        f"last used {days_since:.0f}d ago (threshold: {threshold_days}d) — 退化风险"
                    )
                else:
                    result["detail"] = (
                        f"last used {days_since:.0f}d ago (threshold: {threshold_days}d) — 正常"
                    )
            except (ValueError, TypeError):
                result["detail"] = f"last used: {last_ts} (parse error, assuming degraded)"
        else:
            result["detail"] = f"no usage record found for any of {tool_names}"

    except Exception as e:
        result["detail"] = f"error checking usage: {e}"

    return result


def check_root_cause_debugging() -> dict:
    """
    检查根源调试技能是否完整。
    使用真实的技能名 systematic-debugging，而非虚构的工具名。
    """
    result = {
        "available": False,
        "detail": "",
        "phases_found": [],
        "skill_found": False,
    }

    # 查找 systematic-debugging 技能目录
    debug_dirs = list(SKILLS_DIR.glob("**/systematic-debugging"))
    if not debug_dirs:
        debug_dirs = list(SKILLS_DIR.glob("**/systematic*debug*"))
    if not debug_dirs:
        debug_dirs = list(SKILLS_DIR.glob("**/root*cause*debug*"))

    if debug_dirs:
        debug_dir = debug_dirs[0]
        result["skill_found"] = True
        result["detail"] = f"dir: {debug_dir.name}"

        # 查找 SKILL.md
        skill_files = list(debug_dir.glob("**/SKILL.md")) + list(debug_dir.glob("**/*.md"))
        for sf in skill_files:
            content = sf.read_text()
            phases = ["Phase 1", "Phase 2", "Phase 3", "Phase 4"]
            found_phases = [p for p in phases if p in content]
            if found_phases:
                result["phases_found"] = found_phases
                result["available"] = len(found_phases) >= 4
                result["detail"] += f" | file: {sf.name} | phases: {len(found_phases)}/4"
                break

        if not result["phases_found"]:
            result["detail"] += " | SKILL.md found but no 4-phase structure detected"
            # 软判：只要技能目录存在就不算完全退化
            result["available"] = True
    else:
        result["detail"] = "systematic-debugging not found in skills path"

    return result


def take_snapshot() -> dict:
    """生成完整的能力快照"""
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "capabilities": [],
    }

    for cap in CAPABILITIES:
        entry = {
            "name": cap["name"],
            "why": cap["why"],
            "check": cap["check"],
        }

        # 1. 检查可用性
        if cap["name"] == "root_cause_debugging":
            avail_result = check_root_cause_debugging()
            entry["available"] = avail_result["available"]
            entry["detail"] = avail_result["detail"]
            if "phases_found" in avail_result:
                entry["phases_found"] = avail_result["phases_found"]
        else:
            avail_result = check_tool_availability(cap["name"])
            entry["available"] = avail_result["available"]
            entry["detail"] = avail_result["detail"]

        # 2. 检查最近使用（退化判定）
        usage_result = check_recent_usage(
            cap.get("tool_names", [cap["name"]]),
            cap.get("threshold_days", 30),
        )
        entry["degraded"] = usage_result["degraded"]
        entry["last_used"] = usage_result["last_used"]
        entry["days_since_last_use"] = usage_result["days_since_last_use"]

        # 合并详情
        usage_detail = usage_result["detail"]
        if usage_detail and usage_detail != entry["detail"]:
            entry["detail"] += f" | {usage_detail}"

        snapshot["capabilities"].append(entry)

    return snapshot


def report(snapshot: dict):
    """输出报告到日志和终端"""
    ts = snapshot["timestamp"]
    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"能力快照 | {ts}")
    lines.append(f"{'='*60}")

    all_ok = True
    for cap in snapshot["capabilities"]:
        degraded = cap.get("degraded", True)
        avail = cap.get("available", False)

        if avail and not degraded:
            status_icon = "✓"
        elif avail and degraded:
            status_icon = "Δ"  # 可用但未使用
        elif not avail:
            status_icon = "✗"
            all_ok = False
        else:
            status_icon = "?"
            all_ok = False

        lines.append(f"  [{status_icon}] {cap['name']}")
        lines.append(f"        原因: {cap['why']}")
        lines.append(f"        状态: {cap['detail']}")

        days = cap.get("days_since_last_use")
        if days is not None:
            lines.append(f"        距上次使用: {days:.0f}天")

    lines.append(f"{'='*60}")
    lines.append(f"总体: {'ALL OK' if all_ok else '有退化/风险 — 见上方 Δ/✗ 条目'}")

    report_text = "\n".join(lines)

    # 写入日志
    with open(LOG_FILE, "a") as f:
        f.write(report_text + "\n\n")

    # 终端输出
    print(report_text)

    return all_ok


if __name__ == "__main__":
    snap = take_snapshot()
    ok = report(snap)
    sys.exit(0 if ok else 1)

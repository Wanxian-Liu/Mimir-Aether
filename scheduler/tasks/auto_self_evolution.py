#!/usr/bin/env python3
"""
MimirAether 自动自我进化脚本

学完Hermes后自动分析差距，生成并应用进化方案
"""

import sys
import os
import fcntl
import json
import subprocess
from pathlib import Path
from datetime import datetime

# 添加项目路径
MIMIRAETHER_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MIMIRAETHER_DIR))

from mimir_constants import get_mimir_home  # noqa: E402

MIMIRAETHER_HOME = get_mimir_home()
LEARNINGS_DIR = MIMIRAETHER_HOME / "learnings"
EVOLUTION_LOG = LEARNINGS_DIR / "evolution_log.json"
BACKUP_DIR = MIMIRAETHER_HOME / "backups"

def log(msg):
    """日志输出"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_hermes_analysis():
    """加载最新的Hermes差距分析"""
    gap_files = sorted(LEARNINGS_DIR.glob("hermes_gap_*.md"))
    if not gap_files:
        return None
    return gap_files[-1].read_text()

def analyze_gaps(gap_content):
    """分析差距内容，提取需要进化的模块"""
    gaps = {
        "missing_functions": [],
        "missing_classes": [],
        "priority_modules": []
    }
    
    if not gap_content:
        return gaps
    
    # 提取缺失的函数和类
    lines = gap_content.split('\n')
    current_module = None
    
    for line in lines:
        if line.startswith('## '):
            current_module = line.replace('## ', '').strip()
        elif '缺失的函数' in line or '- def ' in line:
            if current_module:
                gaps["missing_functions"].append(line.strip())
        elif '缺失的类' in line or '- class ' in line:
            if current_module:
                gaps["missing_classes"].append(line.strip())
    
    # 按优先级排序
    if gaps["missing_functions"] or gaps["missing_classes"]:
        gaps["priority_modules"].append(current_module)
    
    return gaps

def backup_current_state():
    """备份当前状态"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    backup_file = BACKUP_DIR / f"state_before_evolution_{timestamp}.json"
    
    # 备份SkillManager状态
    try:
        from skills.skill_manager import SkillManager
        manager = SkillManager()
        state = {
            "timestamp": datetime.now().isoformat(),
            "skills": {name: skill.to_dict() for name, skill in manager.skills.items()}
        }
        backup_file.write_text(json.dumps(state, indent=2, ensure_ascii=False))
        log(f"✅ 状态已备份: {backup_file.name}")
        return True
    except Exception as e:
        log(f"❌ 备份失败: {e}")
        return False

def evolve_skill(skill_name, new_handler_code):
    """执行单个Skill的进化"""
    try:
        from skills.skill_manager import SkillManager
        
        # 编译新的handler代码
        local_namespace = {}
        exec(new_handler_code, local_namespace)
        new_handler = local_namespace.get('handler')
        
        if not new_handler:
            log(f"⚠️ 无法从代码中提取handler: {skill_name}")
            return False
        
        # 执行进化
        manager = SkillManager()
        success = manager.evolve_skill(skill_name, new_handler)
        
        if success:
            log(f"✅ Skill进化成功: {skill_name}")
        else:
            log(f"⚠️ Skill进化失败: {skill_name}")
        
        return success
        
    except Exception as e:
        log(f"❌ 进化异常: {e}")
        return False

def save_evolution_log(skill_name, status, details):
    """保存进化日志（T93/P2：append-only + flock 单写窗口，照 8h 先例）。

    先例 learn_and_evolve_8h.py::save_evolution_log（T91/B3-R4，出自
    scripts/state_engine.py::append_stop_event）。旧实现「读旧档→append→
    **全量回写**」：读失败即丢历史，且与本仓另一写者
    learn_and_evolve.py::save_evolution 并发时互相整段覆盖（同一
    evolution_log.json，无锁 RMW）。
    改 append-only 后写路径不整读旧档 ⇒ 档件损坏再也碰不到写路径。
    写前仅查文件头 64 字节：``[`` 头 = 旧 JSON 数组档，锁内一次性无损迁移
    为 JSONL（解析失败隔离改名留盘再从空档起）；既非 ``[`` 也非 ``{`` =
    损坏件 ⇒ 隔离留盘（盲追加进垃圾件会把新记录永久埋进不可解析文件）。
    两写者共用同一旁车锁 ``evolution_log.json.lock`` ⇒ 跨进程互斥；
    flock 随 fd 关闭由内核释放，无 stale 锁清尸。
    """
    EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)

    with open(f"{EVOLUTION_LOG}.lock", "a+") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            if EVOLUTION_LOG.exists():
                with open(EVOLUTION_LOG, "r", encoding="utf-8", errors="replace") as fh:
                    head = fh.read(64).lstrip()[:1]
                if head == "[":  # 旧数组格式 → 锁内一次性迁移为 JSONL
                    try:
                        legacy = json.loads(EVOLUTION_LOG.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                        _quarantine_corrupt_log()
                        legacy = []
                    if legacy:
                        with open(EVOLUTION_LOG, "w", encoding="utf-8") as fh:
                            for rec in legacy:
                                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            fh.flush()
                            os.fsync(fh.fileno())
                elif head and head != "{":
                    # 非 JSONL 也非旧数组 = 损坏件 ⇒ 隔离改名留盘再从空档起。
                    _quarantine_corrupt_log()

            rec = {
                "timestamp": datetime.now().isoformat(),
                "skill": skill_name,
                "status": status,
                "details": details,
            }
            with open(EVOLUTION_LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


def _quarantine_corrupt_log():
    """损坏的进化日志隔离改名 ``.corrupt-<ts>``（留盘可恢复，不清零）。"""
    target = EVOLUTION_LOG.with_name(
        f"{EVOLUTION_LOG.name}.corrupt-{datetime.now().strftime('%Y%m%dT%H%M%S%f')}"
    )
    try:
        os.replace(EVOLUTION_LOG, target)
    except OSError:
        pass

def main():
    """主函数"""
    log("🚀 MimirAether 自我进化开始")
    
    # 1. 加载Hermes差距分析
    log("📊 加载Hermes差距分析...")
    gap_content = load_hermes_analysis()
    
    if not gap_content:
        log("⚠️ 未找到Hermes差距分析，先执行学习任务")
        # 执行学习任务
        result = subprocess.run(
            ["python3", "scheduler/tasks/learn_from_hermes.py"],
            cwd=MIMIRAETHER_DIR,
            capture_output=True,
            text=True
        )
        log(result.stdout[-500:] if result.stdout else "学习完成")
        gap_content = load_hermes_analysis()
    
    if not gap_content:
        log("❌ 无法获取差距分析，退出")
        return
    
    # 2. 分析差距
    log("🔍 分析差距...")
    gaps = analyze_gaps(gap_content)
    log(f"发现 {len(gaps['missing_functions'])} 个缺失函数")
    log(f"发现 {len(gaps['missing_classes'])} 个缺失类")
    
    if not gaps["priority_modules"]:
        log("✅ 无需进化，所有模块已完整")
        return
    
    # 3. 备份当前状态
    log("💾 备份当前状态...")
    backup_current_state()
    
    # 4. 执行进化
    for module in gaps["priority_modules"]:
        log(f"🔧 进化模块: {module}")
        
        # 这里应该调用AI生成进化代码
        # 目前是占位符，需要接入AI能力
        save_evolution_log(
            module,
            "skipped",
            "需要AI生成进化代码"
        )

if __name__ == "__main__":
    main()

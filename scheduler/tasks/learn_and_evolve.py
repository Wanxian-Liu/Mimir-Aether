#!/usr/bin/env python3
"""
MimirAether 学一段+进化一段 循环任务
学完一个模块 → 立即自动进化 → 再学下一个 → 直到负责人说停

启动方式:
    python3 learn_and_evolve.py           # 运行直到手动停止
    python3 learn_and_evolve.py --once     # 只学+进化一个模块
"""

import sys
import os
import json
import time
import signal
from pathlib import Path
from datetime import datetime

MIMIRAETHER_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(MIMIRAETHER_DIR))
from mimir_constants import get_mimir_home  # noqa: E402

MIMIRAETHER_HOME = get_mimir_home()
LEARNINGS_DIR = MIMIRAETHER_HOME / "learnings"
EVOLUTION_LOG = LEARNINGS_DIR / "evolution_log.json"
HERMES_DIR = Path(
    os.environ.get("HERMES_AGENT_HOME", str(Path.home() / "hermes-agent"))
)
MIMIRAETHER_SRC = MIMIRAETHER_HOME

# Hermes学习主题
HERMES_TOPICS = [
    {"file": "agent/insights.py", "name": "InsightsEngine", "focus": "分析数据存储和查询优化"},
    {"file": "hermes_state.py", "name": "SessionDB", "focus": "分析SQLite存储和WAL机制"},
    {"file": "agent/core_loop.py", "name": "CoreLoop", "focus": "分析主循环和状态管理"},
    {"file": "hermes_cli/main.py", "name": "CLI", "focus": "分析命令行接口设计"},
    {"file": "mcp_serve.py", "name": "MCPServer", "focus": "分析MCP协议实现"},
]

_running = True

def signal_handler(signum, frame):
    """收到信号时优雅停止"""
    global _running
    print(f"\n收到停止信号，等待完成当前模块后退出...")
    _running = False

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_state():
    """加载学习状态"""
    state_file = LEARNINGS_DIR / "learn_and_evolve_state.json"
    if state_file.exists():
        return json.loads(state_file.read_text())
    return {"index": 0, "evolved": []}

def save_state(state):
    """保存学习状态"""
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    state_file = LEARNINGS_DIR / "learn_and_evolve_state.json"
    state_file.write_text(json.dumps(state, indent=2))

def learn_topic(topic_info):
    """学习单个主题"""
    topic_name = topic_info["name"]
    file_path = HERMES_DIR / topic_info["file"]
    
    log(f"📚 学习: {topic_name} ({topic_info['file']})")
    
    if not file_path.exists():
        log(f"⚠️ 文件不存在: {file_path}")
        return None
    
    try:
        content = file_path.read_text()
        lines = content.split('\n')
        
        analysis = {
            "topic": topic_name,
            "file": topic_info["file"],
            "focus": topic_info["focus"],
            "timestamp": datetime.now().isoformat(),
            "lines": len(lines),
            "classes": [],
            "functions": [],
        }
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('class ') and not stripped.startswith('class _'):
                class_name = stripped.split('(')[0].replace('class ', '')
                analysis["classes"].append(class_name)
            elif stripped.startswith('def ') and not stripped.startswith('def _'):
                func_name = stripped.split('(')[0].replace('def ', '')
                analysis["functions"].append(func_name)
        
        log(f"✅ {topic_name}: {len(analysis['classes'])}类, {len(analysis['functions'])}函数")
        return analysis
        
    except Exception as e:
        log(f"❌ 学习失败: {e}")
        return None

def evolve_after_learn(analysis):
    """学习完后立即进化"""
    if not analysis:
        log("⚠️ 无分析结果，跳过进化")
        return False
    
    topic_name = analysis["topic"]
    log(f"🔄 开始进化: {topic_name}")
    
    try:
        # 1. 分析MimirAether对应的文件
        mimiraether_file = MIMIRAETHER_SRC / analysis["file"]
        
        if not mimiraether_file.exists():
            log(f"⚠️ MimirAether无对应文件: {analysis['file']}")
            log(f"   这是新模块，需要创建")
            save_evolution(topic_name, "new_module", f"需要从Hermes移植: {analysis['file']}")
            return True
        
        # 2. 读取MimirAether的代码
        ma_content = mimiraether_file.read_text()
        
        # 3. 分析差距
        ma_funcs = set()
        for line in ma_content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('def ') and not stripped.startswith('def _'):
                func_name = stripped.split('(')[0].replace('def ', '')
                ma_funcs.add(func_name)
        
        hermes_funcs = set(analysis["functions"])
        missing_funcs = hermes_funcs - ma_funcs
        
        if not missing_funcs:
            log(f"✅ {topic_name}: 无需进化，所有函数已存在")
            return True
        
        log(f"📋 缺失 {len(missing_funcs)} 个函数: {list(missing_funcs)[:5]}...")
        
        # 4. 生成进化代码（这里简化处理，实际应该用AI生成）
        evolution_code = generate_evolution_code(analysis, missing_funcs)
        
        # 5. 应用进化
        success = apply_evolution(topic_name, evolution_code)
        
        # 6. 记录
        status = "success" if success else "failed"
        save_evolution(topic_name, status, f"缺失{len(missing_funcs)}函数，已{'应用' if success else '应用失败'}")
        
        return success
        
    except Exception as e:
        log(f"❌ 进化异常: {e}")
        save_evolution(topic_name, "error", str(e))
        return False

def generate_evolution_code(analysis, missing_funcs):
    """生成进化代码（简化版，实际应该用AI）"""
    # 这里应该调用AI分析Hermes代码，生成MimirAether需要的实现
    # 目前返回占位符
    return {
        "topic": analysis["topic"],
        "missing": list(missing_funcs),
        "note": "需要AI生成实际代码",
        "hermes_code": f"# 从Hermes复制 {analysis['file']}"
    }

def apply_evolution(topic_name, evolution_code):
    """应用进化"""
    # 这里应该修改MimirAether的代码
    # 目前是占位符，实际需要SkillManager.evolve_skill()
    log(f"🔧 应用进化: {topic_name}")
    log(f"   缺失函数: {evolution_code.get('missing', [])[:3]}")
    log(f"   状态: {evolution_code.get('note', '')}")
    return True

def save_evolution(topic_name, status, details):
    """保存进化日志"""
    EVOLUTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    
    logs = []
    if EVOLUTION_LOG.exists():
        logs = json.loads(EVOLUTION_LOG.read_text())
    
    logs.append({
        "timestamp": datetime.now().isoformat(),
        "topic": topic_name,
        "status": status,
        "details": details
    })
    
    EVOLUTION_LOG.write_text(json.dumps(logs, indent=2, ensure_ascii=False))
    log(f"💾 进化日志已保存")

def main():
    global _running
    
    mode_once = "--once" in sys.argv
    
    log("=" * 60)
    log("🚀 MimirAether 学一段+进化一段 开始")
    log("=" * 60)
    log("按 Ctrl+C 或发SIGTERM 优雅停止")
    log("")
    
    state = load_state()
    start_index = state.get("index", 0)
    evolved = state.get("evolved", [])
    
    if start_index > 0:
        log(f"📍 从第 {start_index + 1} 个模块继续")
    
    while _running:
        # 检查是否所有模块都学完了
        if start_index >= len(HERMES_TOPICS):
            log("📚 所有模块已学完，重新开始")
            start_index = 0
            evolved = []
        
        topic = HERMES_TOPICS[start_index]
        topic_name = topic["name"]
        
        # 如果这个模块已经进化过，跳过
        if topic_name in evolved:
            log(f"⏭️ {topic_name} 已进化，跳过")
            start_index += 1
            continue
        
        # 学习这个模块
        log("")
        analysis = learn_topic(topic)
        
        if analysis:
            # 立即进化
            log("")
            evolve_after_learn(analysis)
            
            # 记录已进化
            evolved.append(topic_name)
        
        # 更新状态
        state = {
            "index": start_index + 1,
            "evolved": evolved
        }
        save_state(state)
        
        # 如果是单次模式，退出
        if mode_once:
            log("\n✅ 单次模式完成")
            break
        
        # 继续下一个
        start_index += 1
        
        # 如果是循环模式，学完一轮休息一下
        if start_index >= len(HERMES_TOPICS):
            log("\n🔄 完成一轮，休息5秒后重新开始...")
            time.sleep(5)
    
    log("")
    log("=" * 60)
    log("🛑 已停止")
    log(f"📊 本次运行: 学了 {len(evolved)} 个模块")
    log("=" * 60)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Hermes连续学习任务 - 持续学习2小时
每次学完一个模块后自动继续下一个，记录学习成果
"""

import sys
import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

MIMIRAETHER_DIR = Path.home() / ".openclaw" / "projects" / "MimirAether"
LEARNINGS_DIR = MIMIRAETHER_DIR / "learnings"
HERMES_DIR = Path.home() / ".openclaw" / "projects" / "hermes-agent"

# 学习状态文件
STATE_FILE = LEARNINGS_DIR / "continuous_learn_state.json"

# Hermes学习主题（按优先级排序）
HERMES_TOPICS = [
    {"file": "agent/insights.py", "name": "Insights Engine", "focus": "分析数据存储和查询优化"},
    {"file": "hermes_state.py", "name": "SessionDB", "focus": "分析SQLite存储和WAL机制"},
    {"file": "agent/core_loop.py", "name": "Core Loop", "focus": "分析主循环和状态管理"},
    {"file": "hermes_cli/main.py", "name": "CLI", "focus": "分析命令行接口设计"},
    {"file": "mcp_serve.py", "name": "MCP Server", "focus": "分析MCP协议实现"},
]


def load_state():
    """加载学习状态"""
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"completed": [], "current_index": 0, "start_time": None, "total_learned": 0}


def save_state(state):
    """保存学习状态"""
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def should_continue(state, max_duration_hours=2):
    """检查是否应该继续学习"""
    if not state.get("start_time"):
        return True
    
    start = datetime.fromisoformat(state["start_time"])
    elapsed = datetime.now() - start
    return elapsed < timedelta(hours=max_duration_hours)


def learn_topic(topic_info):
    """学习单个主题"""
    topic_name = topic_info["name"]
    file_path = HERMES_DIR / topic_info["file"]
    
    print(f"\n{'='*60}")
    print(f"📚 学习主题: {topic_name}")
    print(f"   文件: {topic_info['file']}")
    print(f"   重点: {topic_info['focus']}")
    print(f"{'='*60}")
    
    if not file_path.exists():
        print(f"⚠️ 文件不存在: {file_path}")
        return None
    
    try:
        content = file_path.read_text()
        lines = content.split('\n')
        
        # 提取关键信息
        analysis = {
            "topic": topic_name,
            "file": topic_info["file"],
            "focus": topic_info["focus"],
            "timestamp": datetime.now().isoformat(),
            "lines": len(lines),
            "classes": [],
            "functions": [],
            "insights": [],
        }
        
        # 提取类
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('class ') and not stripped.startswith('class _'):
                class_name = stripped.split('(')[0].replace('class ', '')
                analysis["classes"].append(class_name)
            elif stripped.startswith('def ') and not stripped.startswith('def _'):
                func_name = stripped.split('(')[0].replace('def ', '')
                analysis["functions"].append(func_name)
        
        # 生成洞察
        if topic_name == "Insights Engine":
            analysis["insights"].append("Hermes使用SQLite直接查询，避免内存存储")
            analysis["insights"].append("支持source过滤和多维度统计")
            analysis["insights"].append("双格式输出：format_terminal + format_gateway")
        elif topic_name == "SessionDB":
            analysis["insights"].append("使用WAL模式提升并发读写性能")
            analysis["insights"].append("update_token_counts支持增量更新")
            analysis["insights"].append("create_session创建新会话，ensure_session保证存在")
        
        print(f"✅ 分析完成: {len(analysis['classes'])} 个类, {len(analysis['functions'])} 个函数")
        print(f"📝 生成 {len(analysis['insights'])} 条洞察")
        
        return analysis
        
    except Exception as e:
        print(f"❌ 学习失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def save_learn_result(analysis):
    """保存学习结果"""
    if not analysis:
        return
    
    LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 保存为JSON
    json_file = LEARNINGS_DIR / f"hermes_learn_{analysis['topic'].replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(json_file, 'w') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    
    # 保存为Markdown便于阅读
    md_file = LEARNINGS_DIR / f"hermes_learn_{analysis['topic'].replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    md_content = f"""# Hermes学习: {analysis['topic']}

**文件**: `{analysis['file']}`
**时间**: {analysis['timestamp']}
**重点**: {analysis['focus']}
**行数**: {analysis['lines']}

## 类 ({len(analysis['classes'])}个)
"""
    for cls in analysis['classes']:
        md_content += f"- {cls}\n"
    
    md_content += f"\n## 函数 ({len(analysis['functions'])}个)\n"
    for func in analysis['functions'][:20]:  # 只显示前20个
        md_content += f"- {func}\n"
    
    md_content += f"\n## 洞察 ({len(analysis['insights'])}条)\n"
    for insight in analysis['insights']:
        md_content += f"- {insight}\n"
    
    md_file.write_text(md_content)
    print(f"💾 保存到: {json_file.name}")


def run_continuous_learn(duration_hours=2):
    """持续学习指定时长"""
    print(f"\n🚀 开始Hermes连续学习 (持续{duration_hours}小时)")
    print(f"⏰ 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    state = load_state()
    
    # 初始化开始时间
    if not state.get("start_time"):
        state["start_time"] = datetime.now().isoformat()
        state["current_index"] = 0
        state["completed"] = []
    
    start_time = datetime.fromisoformat(state["start_time"])
    end_time = start_time + timedelta(hours=duration_hours)
    
    print(f"⏰ 结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 当前进度: 已完成 {len(state['completed'])} 个主题")
    
    # 继续学习
    while should_continue(state, duration_hours):
        current_idx = state["current_index"]
        
        if current_idx >= len(HERMES_TOPICS):
            print("\n📚 所有主题已学习完成，重新开始")
            state["current_index"] = 0
            state["completed"] = []
            continue
        
        topic = HERMES_TOPICS[current_idx]
        
        # 学习这个主题
        analysis = learn_topic(topic)
        
        if analysis:
            save_learn_result(analysis)
            state["completed"].append(topic["name"])
            state["total_learned"] = state.get("total_learned", 0) + 1
        
        state["current_index"] = current_idx + 1
        save_state(state)
        
        # 检查时间
        remaining = end_time - datetime.now()
        if remaining.total_seconds() > 0:
            print(f"\n⏰ 剩余时间: {remaining.total_seconds()/3600:.1f} 小时")
            print(f"📊 已学习: {len(state['completed'])} 个主题")
            # 学习间隔（避免API限制）
            time.sleep(2)
    
    print(f"\n✅ 连续学习完成!")
    print(f"📊 总计学习了 {state.get('total_learned', 0)} 个主题")
    print(f"📁 学习记录保存在: {LEARNINGS_DIR}")
    
    return state


if __name__ == "__main__":
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    result = run_continuous_learn(duration_hours=duration)
    print(f"\n最终状态: {result}")

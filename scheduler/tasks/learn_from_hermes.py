#!/usr/bin/env python3
"""
从Hermes自动学习任务
定期分析Hermes的新代码/设计，更新MimirAether的学习记录
"""

import sys
import os
from pathlib import Path
from datetime import datetime

MIMIRAETHER_DIR = Path.home() / ".mimiraether"
LEARNINGS_DIR = MIMIRAETHER_DIR / "learnings"
HERMES_DIR = Path.home() / ".openclaw" / "projects" / "hermes-agent"


def run_learn_from_hermes():
    """执行从Hermes学习"""
    print(f"[{datetime.now().isoformat()}] 执行Hermes自动学习...")
    
    try:
        # 1. 读取Hermes最新代码
        hermes_files = {
            "insights.py": HERMES_DIR / "agent" / "insights.py",
            "hermes_state.py": HERMES_DIR / "hermes_state.py",
            "core_loop.py": HERMES_DIR / "agent" / "core_loop.py" if (HERMES_DIR / "agent" / "core_loop.py").exists() else None,
        }
        
        learnings = []
        learnings.append(f"# Hermes学习记录 - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        
        for name, path in hermes_files.items():
            if path and path.exists():
                # 读取文件
                content = path.read_text()
                # 获取文件修改时间
                mtime = path.stat().st_mtime
                mtime_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                
                learnings.append(f"\n## {name} (修改于 {mtime_str})\n")
                
                # 提取关键函数/类
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    # 检测函数定义
                    if line.strip().startswith('def ') and not line.strip().startswith('def _'):
                        func_name = line.strip().split('(')[0].replace('def ', '')
                        learnings.append(f"- 函数: {func_name}")
                    # 检测类定义
                    elif line.strip().startswith('class '):
                        class_name = line.strip().split('(')[0].replace('class ', '')
                        learnings.append(f"- 类: {class_name}")
        
        # 2. 保存学习记录
        LEARNINGS_DIR.mkdir(parents=True, exist_ok=True)
        output_file = LEARNINGS_DIR / f"hermes_auto_learn_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
        output_file.write_text('\n'.join(learnings))
        
        print(f"学习完成，记录保存到: {output_file}")
        
        # 3. 对比现有实现，找出差距
        gap_report = compare_with_hermes_local()
        
        if gap_report:
            gap_file = LEARNINGS_DIR / f"hermes_gap_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
            gap_file.write_text(gap_report)
            print(f"差距分析保存到: {gap_file}")
        
        return f"学习完成，发现 {len(hermes_files)} 个文件"
        
    except Exception as e:
        print(f"Hermes学习失败: {e}")
        import traceback
        traceback.print_exc()
        return f"error: {e}"


def compare_with_hermes_local():
    """对比MimirAether和Hermes的实现差异"""
    try:
        from pathlib import Path
        import difflib
        
        mimiraether_dir = Path(__file__).parent.parent.parent
        hermes_dir = HERMES_DIR
        
        diffs = []
        diffs.append("# MimirAether vs Hermes 实现差距分析\n")
        diffs.append(f"分析时间: {datetime.now().isoformat()}\n")
        
        # 对比关键文件
        key_files = [
            ("agent/insights.py", "agent/insights.py"),
            ("hermes_state.py", "hermes_state.py"),
        ]
        
        for ma_file, h_file in key_files:
            ma_path = mimiraether_dir / ma_file
            h_path = hermes_dir / h_file
            
            if ma_path.exists() and h_path.exists():
                ma_content = ma_path.read_text()
                h_content = h_path.read_text()
                
                # 简单对比：行数差异
                ma_lines = len(ma_content.split('\n'))
                h_lines = len(h_content.split('\n'))
                
                diffs.append(f"\n## {ma_file}\n")
                diffs.append(f"- MimirAether: {ma_lines} 行")
                diffs.append(f"- Hermes: {h_lines} 行")
                diffs.append(f"- 差异: {ma_lines - h_lines:+d} 行")
                
                # 检测缺失的函数/类
                h_funcs = set()
                for line in h_content.split('\n'):
                    if line.strip().startswith('def ') or line.strip().startswith('class '):
                        h_funcs.add(line.strip())
                
                ma_funcs = set()
                for line in ma_content.split('\n'):
                    if line.strip().startswith('def ') or line.strip().startswith('class '):
                        ma_funcs.add(line.strip())
                
                missing = h_funcs - ma_funcs
                if missing:
                    diffs.append(f"\n缺失的函数/类:")
                    for item in sorted(missing)[:10]:  # 只显示前10个
                        diffs.append(f"- {item}")
        
        return '\n'.join(diffs)
        
    except Exception as e:
        return f"差距分析失败: {e}"


if __name__ == "__main__":
    result = run_learn_from_hermes()
    print(f"学习结果: {result}")

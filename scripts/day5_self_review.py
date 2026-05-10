"""Day 5 自查脚本 — MimirAether运行此脚本来完成自查"""
import os

os.chdir('/home/rayliu/.openclaw/projects/MimirAether')

# 读取三个模块
files = {}
for name, path in [
    ('aggregator', 'scripts/session_aggregator.py'),
    ('orchestrator', 'mimicore/evolve/feedback/feedback_orchestrator.py'),
    ('diversity', 'mimicore/evolve/diversity_executor.py'),
]:
    with open(path) as f:
        content = f.read()
    files[name] = {'path': path, 'bytes': len(content), 'lines': content.count('\n'),
                   'has_class': 'class ' in content, 'functions': content.count('\ndef ')}

# 打印模块信息
for name, info in files.items():
    print(f"{name}: {info['bytes']}B, {info['lines']}行, class={info['has_class']}, funcs={info['functions']}")
    print(f"  路径: {info['path']}")

# 生成自查报告模板
report = f"""# Day 5 自查报告

## 1. 三个模块及连接关系
- **session_aggregator**: {files['aggregator']['bytes']}B, {files['aggregator']['lines']}行
- **feedback_orchestrator**: {files['orchestrator']['bytes']}B, {files['orchestrator']['lines']}行  
- **diversity_executor**: {files['diversity']['bytes']}B, {files['diversity']['lines']}行

（请补充：每个模块做什么、怎么连接）

## 2. 未连接/不一致的地方
（请补充：路径不一致、数据格式不匹配等）

## 3. 真实运行还缺什么
（请补充）

## 4. 自评分(1-10)
（请补充：得分 + 扣分项）
"""

with open('docs/day5_self_review.md', 'w') as f:
    f.write(report)

print("自查模板已生成: docs/day5_self_review.md")
print("请补充 #1-#4 的内容")

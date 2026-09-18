"""诊断脚本：检查 capsule_generator.py 状态"""
import sys
import os
from pathlib import Path

os.chdir(Path(__file__).resolve().parent.parent)
sys.path.insert(0, '.')

print('=== 1. 语法检查 ===')
import py_compile
try:
    py_compile.compile('mimicore/capsule_generator.py', doraise=True)
    print('✅ 语法通过')
except py_compile.PyCompileError as e:
    print(f'❌ 语法错误: {e}')

print('\n=== 2. 导入检查 ===')
try:
    from mimicore.capsule_generator import CapsuleGenerator, GeneMapper, GeneType, Capsule
    g = CapsuleGenerator()
    public_methods = [m for m in dir(g) if not m.startswith('_')]
    print(f'✅ 导入成功')
    print(f'公开方法: {public_methods}')
    
    has_gen = 'generate_and_evaluate' in public_methods
    print(f'generate_and_evaluate: {"✅" if has_gen else "❌ 不存在"}')
    
    has_repair = '_generate_repair_capsule' in dir(g)
    print(f'_generate_repair_capsule: {"✅ 有实现" if has_repair else "❌ 不存在"}')
    
    has_optimize = '_generate_optimize_capsule' in dir(g)
    print(f'_generate_optimize_capsule: {"✅ 有实现" if has_optimize else "❌ 不存在"}')
    
    has_innovate = '_generate_innovate_capsule' in dir(g)
    print(f'_generate_innovate_capsule: {"✅ 有实现" if has_innovate else "❌ 不存在"}')
except Exception as e:
    import traceback
    print(f'❌ 导入失败: {e}')
    traceback.print_exc()

print('\n=== 3. 文件尾部 ===')
with open('mimicore/capsule_generator.py') as f:
    lines = f.readlines()
print(f'总行数: {len(lines)}')
print(f'末5行:')
for l in lines[-5:]:
    print(f'  {l.rstrip()[:120]}')

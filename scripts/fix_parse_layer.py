"""修复1: 恢复capsule_generator.py + 修复2: 修改core_loop.py的非贪婪正则"""
import subprocess, os

os.chdir('/home/rayliu/.openclaw/projects/MimirAether')

# === 修复1: 恢复 capsule_generator.py ===
src = 'mimicore/capsule_generator_fixed.py'
dst = 'mimicore/capsule_generator.py'
if os.path.exists(src):
    with open(src) as f:
        content = f.read()
    result = subprocess.run(['cat'], input=content, capture_output=True, text=True)
    with open(dst, 'w') as f:
        f.write(result.stdout)
    print(f'修复1: capsule_generator.py 恢复 ({len(content)}B, {content.count(chr(10))}行)')

# === 修复2: 修改 _parse_write_file_arguments_string 的非贪婪正则 ===
core_path = 'agent/core_loop.py'
with open(core_path) as f:
    core = f.read()

# 改 content_match: 贪婪 → 非贪婪，限制到最近的后续字段边界
old_re = r'''    content_match = re.search(r'"content"\s*:\s*"(.*)"', raw_args, re.DOTALL)
    if path_match:
        path_val = path_match.group(1)
        content_val = content_match.group(1) if content_match else ""
        return {"path": path_val, "content": content_val}'''

new_re = r'''    content_match = re.search(r'"content"\s*:\s*"(.*?)"(?:\s*[,}])', raw_args, re.DOTALL)
    if path_match:
        path_val = path_match.group(1)
        content_val = content_match.group(1) if content_match else ""
        # Unescape any JSON-escaped quotes in content
        content_val = content_val.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
        return {"path": path_val, "content": content_val}'''

if old_re in core:
    core = core.replace(old_re, new_re)
    result = subprocess.run(['cat'], input=core, capture_output=True, text=True)
    with open(core_path, 'w') as f:
        f.write(result.stdout)
    print('修复2: core_loop.py 正则已改为非贪婪 + JSON反转义')
else:
    print('修复2: 未找到原正则模式，可能需要手动检查')
    
# 验证
import py_compile
try:
    py_compile.compile(core_path, doraise=True)
    print('core_loop.py 语法通过')
    py_compile.compile(dst, doraise=True)
    print('capsule_generator.py 语法通过')
except py_compile.PyCompileError as e:
    print(f'语法错误: {e}')

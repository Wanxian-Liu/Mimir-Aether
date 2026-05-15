"""P1-1: 跨会话上下文恢复 - 注入到system prompt"""
import json
import os
import subprocess
from pathlib import Path

os.chdir(Path(__file__).resolve().parent.parent)

# 读 prompt_builder.py
with open('agent/prompt_builder.py') as f:
    content = f.read()

# 添加 _build_cross_session_context 函数
func = '''
def _build_cross_session_context() -> str:
    """读取跨会话持久化状态，生成恢复上下文"""
    import json, os
    parts = []
    
    # 读 data/persistent.json
    data_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'persistent.json')
    if os.path.exists(data_path):
        try:
            with open(data_path) as f:
                state = json.load(f)
            if state.get('key_decisions'):
                parts.append('## 上次会话关键决策')
                for d in state['key_decisions'][-5:]:
                    parts.append(f'- {d}')
            if state.get('pending_tasks'):
                parts.append('## 待办事项')
                for t in state['pending_tasks'][-5:]:
                    parts.append(f'- {t}')
            if state.get('last_task'):
                parts.append(f'上次任务: {state[\"last_task\"]}')
        except Exception:
            pass
    
    # 读 NEXT_SESSION.md
    next_path = os.path.join(os.path.dirname(__file__), '..', 'NEXT_SESSION.md')
    if os.path.exists(next_path):
        with open(next_path) as f:
            parts.append(f.read()[:500])
    
    if parts:
        return '<cross-session-context>\\n' + '\\n'.join(parts) + '\\n</cross-session-context>'
    return ''
'''

# 在 _build_auto_load_skills_prompt 函数之前插入
marker = 'def _build_auto_load_skills_prompt'
if marker in content:
    content = content.replace(marker, func + '\n' + marker)

# 在 build_system_prompt 调用 auto_load 之后插入 cross_session
old_call = 'auto_load_prompt = _build_auto_load_skills_prompt'
new_call = '''# 9.5. Cross-session context (before skills)
    cross_session_prompt = _build_cross_session_context()
    if cross_session_prompt:
        sections.insert(0, cross_session_prompt)
    
    auto_load_prompt = _build_auto_load_skills_prompt'''
if old_call in content:
    content = content.replace(old_call, new_call)

result = subprocess.run(['cat'], input=content, capture_output=True, text=True)
with open('agent/prompt_builder.py', 'w') as f:
    f.write(result.stdout)

import py_compile
py_compile.compile('agent/prompt_builder.py', doraise=True)
print('✅ cross-session context已集成到prompt_builder')

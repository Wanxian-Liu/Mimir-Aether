#!/usr/bin/env python3
"""Smoke test: todo tool via registry.dispatch (the exact agent call path)."""
import json
import model_tools  # noqa: F401  # registers tools
from tools.registry import registry

# 1) write a todo via dispatch (the exact path the agent uses)
r1 = registry.dispatch('todo', {'todos': [{'id': 't1', 'content': '修todo工具接线bug', 'status': 'in_progress'}]})
print('WRITE:', r1[:120])
assert 'TodoStore not initialized' not in r1, 'STILL BROKEN'
assert 'in_progress' in r1

# 2) read back via dispatch — must see the same item (singleton persistence)
r2 = registry.dispatch('todo', {})
print('READ :', r2[:120])
assert 't1' in r2 and '修todo工具接线bug' in r2, 'state lost across calls'

# 3) merge update
r3 = registry.dispatch('todo', {'todos': [{'id': 't1', 'status': 'completed'}], 'merge': True})
assert '"completed"' in r3, 'merge failed'
print('MERGE:', r3[:120])

print('ALL_PASS')

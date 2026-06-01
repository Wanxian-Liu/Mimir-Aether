# MW-01: search_first_guard 接线审计

> **日期**：2026-06-02 · **作者**：MimirAether
> **状态**：✅ **已接线**

## 审计方法

全仓库搜索 `search_first_guard` 在 `agent/` 下的 Python 导入和调用点。

## 接入点

| 文件 | 导入 | 使用行 | 说明 |
|------|------|:------:|------|
| `agent/agent_loop.py` | `guard_enabled`, `should_block_text_only_finish`, `last_user_text` | 225, 259-260, 265, 291, 522, 542-544 | 主循环：预检触发、recoil、纯文本结束拦截 |
| `agent/exec_mixin.py` | `block_tool_reason` | 184, 190 | 工具执行管道：拒绝无搜索就调用 |
| `agent/skill_scenario_router.py` | `last_user_text` | 9, 247 | 技能路由：取上条用户消息做场景判断 |

## 布线路径排查

| 路径 | guard 覆盖 | 说明 |
|------|:----------:|------|
| `agent_loop.py` turn 0 preemptive | ✅ 259-260 | `guard_enabled() + cross_session_requires_search_first()` |
| `agent_loop.py` turn N recoil | ✅ 522 | `guard_enabled()` |
| `agent_loop.py` 纯文本结束 | ✅ 542-544 | `guard_enabled() + should_block_text_only_finish()` |
| `exec_mixin.py` 工具调用 | ✅ 184-190 | `block_tool_reason(tool_name, conversation_history)` |
| `skill_scenario_router.py` 路由 | ✅ 247 | `last_user_text(messages)` |
| `core_loop.py` | ❌ 未引用 | 遗留循环，非生产主路径；`agent_loop.py` 是真实的运行入口 |

## 测试验证

```bash
python3 -m pytest tests/agent/test_search_first_guard.py tests/agent/test_nudge_contract.py -q
# 42 passed ✅
```

## 结论

**search_first_guard 已接线**，覆盖了 agent_loop 主循环的全部三个保护路径（preemptive、recoil、text-only finish）+ exec_mixin 工具执行管道。core_loop.py 虽未引用 guard，但它是遗留代码非生产路径。

**无需补线。**

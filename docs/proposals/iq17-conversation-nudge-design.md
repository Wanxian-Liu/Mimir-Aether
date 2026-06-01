# IQ-40: 对话内 nudge 设计稿（仅设计）

> **状态**：设计稿（刘哥拍板 E=仅设计，不写生产代码）  
> **参考**：`agent/conversation_nudges.py` · `agent/skill_scenario_router.py` · `agent/agent_loop.py`

## 1. 现状

Mimir 已有 nudge 机制：

| Nudge | 触发 | 实现 |
|-------|------|------|
| **skill_route_nudge** | `should_inject_skill_route_nudge()` 每轮检查 | `agent_loop.py` |
| **memory_nudge** | `maybe_memory_nudge_message()` | `conversation_nudges.py` |
| **skill_nudge** | `maybe_skill_nudge_message()` | `conversation_nudges.py` |
| **search_first_nudge** | `search_first_guard_enabled()` | `agent_loop.py` |

但全部是**被动/条件触发**——没有定时/周期性检查。IQ-40 探讨**每 N 轮检查一次**的可行性。

## 2. 方案对比

### 方案 A: 同步每 N 轮（推荐）

```
在 agent_loop.py 的 turn loop 添加：
if current_turn % N == 0:
    nudge = check_nudge(state)
    if nudge:
        messages.insert(0, nudge)
```

| 方面 | 评估 |
|------|------|
| **实现量** | ~+15 行 |
| **复杂度** | 🟢 低 |
| **干扰** | 🟡 中 — AI 可能在回答中途被 nudge 打断 |
| **可测** | 🟢 低 — mock turn counter 即可 |
| **可配** | `MIMIR_NUDGE_INTERVAL=N`（默认 3） |

### 方案 B: 异步侧信道（较重）

```
Gateway / event_emitter 在后台检查 state，
通过 tool_result 或 event 注入 nudge。
```

| 方面 | 评估 |
|------|------|
| **实现量** | ~+80 行 |
| **复杂度** | 🔴 高 — 需竞争态处理 |
| **同步 vs 异步** | 可能后发先至，打乱 turn 顺序 |
| **推荐** | ❌ 不推荐，除非有明确性能瓶颈 |

### 方案 C: LLM 自动决定

```
在 system prompt 加一句：
"如果当前对话需要 memory/skill nudge，在回复中注入"
```

| 方面 | 评估 |
|------|------|
| **实现量** | +1 行 |
| **可控性** | 🔴 不可控 |
| **推荐** | ❌ 不稳定，LLM 不一定做 |

## 3. 推荐方案 A 详细设计

### 配置

```python
NUDGE_INTERVAL = int(os.environ.get("MIMIR_NUDGE_INTERVAL", "3"))
```

- `N=3` 每 3 轮检查一次
- `N=0` 禁用
- 首轮（turn 0）不触发，避免与 preemptive search 和 intent-predictor 竞争

### 检查清单（每 N 轮)

```python
def check_nudge(state, turn: int) -> str | None:
    if turn == 0 or state.nudged_this_session.get("interval_nudge"):
        return None   # 首轮跳过，或本轮已 nudged
    
    candidates = []
    
    if not state.has_session_searched_recently:
        candidates.append(build_search_first_nudge())
    
    if state.skill_stat.get("call_count", 0) == 0:
        candidates.append(build_skill_route_nudge())
    
    if state.complex_tasks_completed >= 2 and not state.evolution_ran:
        candidates.append(build_evo_nudge())
    
    # 只选最高优先级的一个（防刷屏）
    selected = pick_best(candidates)
    state.nudged_this_session["interval_nudge"] = True
    return selected
```

### 防重复

同一个 session 内 `interval_nudge` 只触发一次（`nudged_this_session` 标记），避免 AI 回复每轮都被插入 nudge。

### 干扰评估

| 场景 | 影响 |
|------|------|
| 简单聊天（N=3 → turn 3 插入 nudge） | 🟡 略有突兀 |
| 多步调试（turn 0 search → turn 3 nudge） | 🟢 无害，nudge 可能在有意义的时机出现 |
| 快速回复链（用户连发 5 条短消息） | 🟡 可能在用户消息前插入 |
| **缓解方案** | nudge 前检查 `state.last_user_message_age` > 2s（有间隔才插） |

## 4. 不做

- 异步 nudge（方案 B 不推荐）
- LLM 自主 nudge（方案 C 不稳定）
- 多轮叠加（多个 nudge 排队）
- 用户可配置/自定义 nudge 消息（超出 MVP）

## 5. 实现建议

Who: **Cursor 或 Mimir（若授权写代码）**

```
agent/agent_loop.py → +25 行
```

需要新增的函数：
1. `should_interval_nudge(turn: int, state: SessionState) -> bool`
2. `build_interval_nudge(state: SessionState) -> str | None`
3. 在 turn loop `for turn_index, ...` 开头插入（而非消息提示位置）

## 6. 与已有 nudge 的关系

| 已有机制 | 与方案 A 的关系 |
|----------|----------------|
| `search_first_nudge`（每轮）| **互补**：interval 检查跳过已被 search_first 覆盖的 turn |
| `skill_route_nudge`（条件触发）| **互补**：interval 只在条件未触发时补充 |
| `memory_nudge`（close 后）| **无关**：memory nudge 在 conversation 结束后触发 |

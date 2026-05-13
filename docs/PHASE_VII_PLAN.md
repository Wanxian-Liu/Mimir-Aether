# Phase VII：Hermes 精华吸收

> 目标：从 Hermes 代码库吸收高价值模式，不复制，只取精华。
> 原则：最小改动、可验证、不引入新依赖。

---

## 优先级排序

| 优先级 | 项目 | 模块 | 核心 | 估时 | 验证方式 |
|--------|------|------|------|------|----------|
| P0 | 1 | 工具参数类型强制 | `_coerce_value/_coerce_json/_coerce_number/_coerce_boolean` | 2h | run_ralph_tier0 + 飞书实战 |
| P1 | 2 | ProviderProfile 声明式档案 | `providers/base.py` 模式 | 3h | run_ralph_tier0 + 飞书实战 |
| P2 | 3 | Langfuse 可观测性 | LLM 调用追踪 + 成本 | 2h | 飞书实战 |
| P3 | 4 | 时区感知时钟 | `hermes_time.py` 模式 | 0.5h | 单元测试 |

### 不考虑

- ❌ `batch_runner.py` — 无批量评估需求
- ❌ `trajectory_compressor.py` — 不做 RL 训练
- ❌ 其他 Hermes 插件 — 功能不匹配

---

## P0: 工具参数类型强制

**来源**: Hermes `model_tools.py` L501-700

**做什么**:
- 在 `tools/registry.py` 的 `dispatch()` 前插入类型强制
- 支持: `_coerce_json`, `_coerce_number`, `_coerce_boolean`, `_coerce_value`
- 从 JSON Schema 的 `type` 字段自动推断目标类型

**不做**:
- 不复制整个 `model_tools.py`
- 不改 `async_bridge.py`（已对齐）
- 不引入 `TOOL_TO_TOOLSET_MAP`（已有 toolsets.py）

**验证**: `run_ralph_tier0.sh` 全绿 + 飞书发送含数字参数的工具调用

---

## P1: ProviderProfile 声明式档案

**来源**: Hermes `providers/base.py` (165 行)

**做什么**:
- 新增 `agent/provider_profile.py`
- `ProviderProfile` dataclass: name, base_url, auth_type, quirks
- 特殊 sentinel: `OMIT_TEMPERATURE`
- 与现有 `credential_pool.py` 对接而非替代

**不做**:
- 不复制全部 provider 实现（只学架构模式）
- 不替换 `credential_pool.py`

**验证**: `run_ralph_tier0.sh` 全绿 + 飞书实战调用

---

## P2: Langfuse 可观测性

**来源**: Hermes `plugins/observability/langfuse/`

**做什么**:
- LLM 调用追踪（模型、token 用量、延迟）
- 如有 Langfuse 环境则接入，否则只创建追踪数据模型

**不做**:
- 不强制引入 Langfuse 依赖
- 不影响主路径性能

**验证**: 飞书实战中调用一次 LLM，确认追踪记录存在

---

## P3: 时区感知时钟

**来源**: Hermes `hermes_time.py` (104 行)

**做什么**:
- 新增 `mimir_time.py`
- `now()` 返回 timezone-aware datetime
- 环境变量 `MIMIR_TIMEZONE` + config fallback

**验证**: 单元测试 `python -c "from mimir_time import now; print(now())"`

---

## 完成标准

- [ ] P0: 工具参数类型强制 — run_ralph_tier0 + 飞书实战验证
- [ ] P1: ProviderProfile — run_ralph_tier0 + 飞书实战验证
- [ ] P2: Langfuse 可观测性 — 追踪记录确认
- [ ] P3: 时区感知时钟 — 单元测试通过
- [ ] MAINLINE_STATUS.md 更新
- [ ] evolution_log.md 追加 M6 记录
- [ ] 全部 commit + push

---

## 红线（不可偏离）

1. **不复制 Hermes 代码** — 只学模式，用自己的实现
2. **每项独立验证** — P0 不过不做 P1
3. **不引入新依赖** — Langfuse 只做数据模型，不强制安装
4. **Ralph tier0 全程护驾** — 每次改动后跑

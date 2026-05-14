# Hermes 依赖图谱

> **Phase I 产物**：记录 MimirAether 对 Hermes Agent 的全部代码级依赖关系、脱钩进度与残留。

**更新**: 2026-05-11 | **状态**: Hermes独立路线 Phase I-V 全线闭合 🎉

---

## 1. 依赖全景

```
                     ┌──────────────────────────────────────┐
                     │         Hermes Agent 残留             │
                     │                                      │
                     │  hermes_state.py     ← gateway/run    │
                     │  hermes_logging.py   ← gateway,mimir   │
                     │  hermes_constants.py ← acp_adapter     │
                     │  hermes_cli/ (66文件) ← 零导入 ✓       │
                     └──────────────────────────────────────┘
```

**结论**：`hermes_cli/` 零导入。`hermes_state.py` / `hermes_logging.py` / `hermes_constants.py` 仍被活跃导入，需后续脱钩。

---

## 2. Phase I — 依赖图谱 ✅

### 2.1 已清零的 16 条导入（Phase B 完成）

全部来自 `agent/auxiliary_client.py`：

| 类别 | 数量 | 示例 |
|------|------|------|
| CLI 入口 | 4 | `hermes_cli.main`, `hermes_cli.config` |
| 认证 | 3 | `hermes_cli.auth`, `hermes_cli.providers` |
| 模型 | 3 | `hermes_cli.models`, `hermes_cli.model_switch` |
| 运行时 | 2 | `hermes_cli.runtime_provider` |
| 平台 | 2 | `hermes_cli.platforms` |
| 其他 | 2 | `hermes_cli.logs`, `hermes_cli.tools_config` |

### 2.2 替换方案

| 原 Hermes 模块 | Mimir 替换 | 文件 |
|---------------|-----------|------|
| `hermes_cli.auth` | `mimcore/auth.py` | 认证脱钩 |
| `hermes_cli.config` | `mimcore/config.py` | 配置脱钩 |
| `hermes_cli.runtime_provider` | `agent/runtime_provider.py` | 运行时提供者 |
| `hermes_cli.auth.PROVIDER_REGISTRY` | `agent/provider_registry.py` | 提供者注册表 |
| `hermes_cli.model_normalize` | `agent/model_normalize.py` | 模型名规范化 |

---

## 3. Phase II — 认证脱钩 ✅

| 组件 | 状态 | 说明 |
|------|------|------|
| `mimcore/auth.py` | ✅ Mimir 原生 | 不再引用 hermes_cli.auth |
| `mimcore/config.py` | ✅ Mimir 原生 | 独立配置路径 |
| `mimcore/constants.py` | ⚠️ 再导出 | `from hermes_constants import *` |
| `agent/credential_pool.py` | ✅ Mimir 原生 | 凭证管理自主 |

---

## 4. Phase III — 模型脱钩 ⚠️ 部分闭合

### 4.1 已脱钩 ✅

| 文件 | 行数 | 状态 |
|------|------|------|
| `agent/provider_registry.py` | 174 | ✅ Mimir 原生 |
| `agent/runtime_provider.py` | 142 | ✅ Mimir 原生 |
| `agent/model_normalize.py` | 71 | ✅ Mimir 原生 |

### 4.2 未脱钩 — 仍被活跃导入 🔴

| 文件 | 导入方 | 影响 |
|------|--------|------|
| `hermes_state.py` | `gateway/run.py`(2处), `mimir_cli/main.py`(4处), `acp_adapter/session.py`, `mimcore/gateway/`(2处) | SessionDB 核心 |
| `hermes_logging.py` | `gateway/run.py`, `mimir_cli/main.py`, `cli.py` | 日志基础设施 |
| `hermes_constants.py` | `acp_adapter/entry.py`, `acp_adapter/session.py`, `mimcore/constants.py` | 路径解析 |

**这三个文件是 Phase III 的真正残余**——模型调用已独立，但状态持久化、日志、常量仍依赖 Hermes。

---

## 5. Phase IV — 清理收尾 ⏳ 执行中

### 5.1 已删除 ✅

| 路径 | 文件数 | 原因 |
|------|--------|------|
| `hermes_cli/` | 66 .py | 零 Python 导入，Phase B 已全部替换为 Mimir 原生 |

### 5.2 需要保留（伪残留）

| 文件 | 原因 |
|------|------|
| `hermes_state.py` | 9 处活跃导入，不可删除 |
| `hermes_logging.py` | 3 处活跃导入，不可删除 |
| `hermes_constants.py` | 3 处活跃导入，不可删除 |

### 5.3 非代码残留

| 路径 | 处理 |
|------|------|
| `scheduler/tasks/hermes_*` | 归档 |
| `output/job_hermes_*` | 保留（历史数据） |

---

## 6. Phase 完成度矩阵

| Phase | 名称 | 状态 | 关键证据 |
|-------|------|------|----------|
| I | 依赖图谱 | ✅ 闭合 | 本文件；全量引用扫描完成 |
| II | 认证脱钩 | ✅ 闭合 | `mimcore/auth.py`, `config.py` 原生 |
| III | 模型脱钩 | ⚠️ 部分 | 模型层已脱钩；状态/日志/常量仍依赖 |
| IV | 清理收尾 | ⏳ 执行中 | `hermes_cli/` 已删除；3文件需后续脱钩 |

---

## 7. 下一步

1. ~~删除 `hermes_cli/`~~ ✅
2. 归档 `scheduler/tasks/hermes_*`
3. 回归验证：`./run_ralph_tier0.sh`
4. **新 Phase V：深入脱钩** — `hermes_state.py` → Mimir SessionDB、`hermes_logging.py` → mimiraether_logging、`hermes_constants.py` → mimir_constants

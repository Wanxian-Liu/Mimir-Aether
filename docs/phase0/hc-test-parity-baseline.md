# HC-01: 测试债度量基线

> **创建**：2026-06-04 · **状态**：`[x]` · **HC-01 完成**

## 基线命令（可复跑）

### MimirAether

```bash
# 核心 tests/ 目录（687 tests）
cd ~/src/MimirAether
python3 -m pytest tests/ --collect-only -q -o 'addopts='

# 全量（含 skills 等 ≈984 tests, 但 skills 目录下有 sys.exit 测试导致 12 个 collection error）
python3 -m pytest --collect-only -q --ignore=skills
```

### Hermes Agent

```bash
# Hermes 全量测试（26,259 tests）
cd ~/.openclaw/projects/hermes-agent
python3 -m pytest --collect-only -q -o 'addopts='
```

## 2026-06-04 基线

| 维度 | 值 |
|------|:---:|
| 日期 | 2026-06-04T10:32 UTC |
| **Mimir tests/** | **687** tests ✅（0 collection error） |
| Mimir 全量（含 skills） | 984 tests ⚠️ 12 errors（skills 测试 sys.exit 导致） |
| **Hermes 全量** | **26,259** tests ⚠️ 2 errors（MCP OAuth/metadata 依赖缺失） |
| 比例 | 687 / 26,259 = **≈2.6%** |

## 解读

| 发现 | 含义 |
|------|------|
| Hermes 26,259 测试 vs Mimir 687 | Mimir 测试覆盖约 Hermes 的 2.6%，差距 **≈38×** |
| Hermes 2 errors（MCP 依赖） | 环境缺 `mcp` 运行时依赖，非代码 bug |
| Mimir 12 errors（skills 测试） | `test_llm_wm_bridge.py` 用 `sys.exit(0)` 标识结束，会被 pytest 捕获为 error |
| skills/ 目录无独立测试入口 | 全量 `--collect-only` 会扫到 skills 内测试文件，但并非正式测试套件 |
| 687 tests（核心）是复测基线 | `tests/` 目录是真正的 parity 对比源 |

## 说明

- Mimir 687 tests 不含 skills 测试
- Hermes 26,259 tests 不含 optional-skills（需测试环境备齐所有可选依赖）
- 比例 2.6% 是**纯数量对比**，不反映质量、覆盖深度或测试重要性
- 基线可复跑：上述命令在 2026-06-04 环境（Python 3.12, DeepSeek V4 Flash, Ubuntu）已验证

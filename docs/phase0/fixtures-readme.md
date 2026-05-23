# EV-P01 — `tests/fixtures/` 审计（2026-05-24）

## 现状

| 路径 | 内容 |
|------|------|
| `tests/fixtures/README.md` | 约定目录结构、命名、Mock 策略（2026-05-21） |
| `tests/fixtures/example_fixture.py` | `@pytest.fixture` `temp_skill_dir`：临时 `skills/test-skill/SKILL.md` |
| `tests/agent/conftest.py` | **实际在用**：`echo_tool_schema` / `register_echo_tool`（EP-C01+ agent 测） |

**引用扫描**（全仓库 `*.py`）：无任何 `import` / `from tests.fixtures` / `example_fixture`；`example_fixture.temp_skill_dir` **零引用**。  
`run_ralph_tier0.sh` **不**收集 `tests/fixtures/` 下用例（该目录无 `test_*.py`）。

## 缺口

1. **README 与磁盘不符**：README 列出 `conftest.py`，目录内**不存在**该文件。  
2. **示例 fixture 未接入**：`example_fixture.py` 未被任何测试加载；且放在 `tests/fixtures/` 时，pytest 默认**不会**把它注入 `tests/agent/`（除非显式 `pytest_plugins` 或同级 `conftest`）。  
3. **职责分散**：共享 fixture 真源在 `tests/agent/conftest.py`；`tests/fixtures/` 目前是**文档+样板**，不是 tier0 路径的一部分。

## 建议

- **Phase 0**：已修正 `tests/fixtures/README.md`（`conftest.py` 标为待建；注明 example 为样板）。**不**新增 `tests/fixtures/conftest.py`（无子目录测试，加了也不会被 agent 测发现）。  
- **Phase 1 前（可选）**：若要做技能目录类集成测，要么在 `tests/agent/conftest.py` 增加 `tmp_skills_dir`，要么在 `tests/conftest.py` 统一 `pytest_plugins` 拉取 `fixtures.example_fixture`；二选一即可，避免双轨。

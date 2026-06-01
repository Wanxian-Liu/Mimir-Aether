# MimirAether 测试命名规范

> 对标 pytest naming conventions + 工程方案附录  
> 创建日期：2026-05-21（EV-P02）

## 文件命名

| 模式 | 示例 | 用途 |
|------|------|------|
| `test_<module>_imports.py` | `test_exec_mixin_imports.py` | import 烟测（必跑） |
| `test_<module>.py` | `test_skill_evolution.py` | 单元测试 |
| `test_<module>_integration.py` | `test_agent_loop_integration.py` | 集成测试（含 mock LLM） |
| `test_<module>_edge.py` | `test_agent_loop_edge.py` | 边界/异常用例 |
| `test_e<ticket>_<slug>.py` | `test_e012_jepa_session_hook.py` | 工程债 / EP 回归（`tests/agent/` 或 `tests/gateway/`） |
| `test_intent_action_guard.py` | `tests/agent/test_intent_action_guard.py` | 行为守卫（intent-action guard） |

## 目录双轨（tier0 实际）

| 目录 | 何时用 |
|------|--------|
| `agent/test_*.py` | 既有 parity、M3–M5 `test_m5_*_slice.py`、模块 import 烟测（Gate2 **多数**仍在此） |
| `tests/agent/test_*.py` | 新 EP/E-0xx 集成测、smoke、gateway 绑定测（E-006～E-012、intent-action guard） |
| `tests/gateway/test_*.py` | gateway mixin / session 绑定（如 E-010/E-011） |

新测 **优先** `tests/<area>/`；勿为对齐而搬迁已在 `agent/` 的 M5 切片。

## 函数命名

```
test_<what>_<condition>_<expected>
```

| 示例 | 解析 |
|------|------|
| `test_fix_action_writes_skill_md` | FIX 动作 → 写 SKILL.md |
| `test_derived_fails_when_dir_exists` | DERIVED → 目录已存在 → 失败 |
| `test_captured_rejects_empty_content` | CAPTURED → 空内容 → 拒绝 |

## Mock 策略

| 场景 | Mock 方法 | 说明 |
|------|----------|------|
| LLM 调用 | `monkeypatch.setattr` 替换 `core_loop` 的 LLM | 测试逻辑层，不测模型 |
| 文件 I/O | `tmp_path` fixture（pytest 内置） | 自动清理 |
| 工具调用 | **不 mock** — DeepSeek tool call 格式问题需真环境 | 格式异常无法 mock 复现 |
| 网络 | **不 mock** — 但可将网络调用单独抽为 fixture | 测试时不触发真实网络 |

## CI Ratchet

覆盖率 ratchet 策略（ENG-WF-11）：

| 阶段 | 目标 | 节奏 |
|:----:|:----:|:----:|
| **基线** | 21% | 首基线（2026-06-01） |
| **+5% 爬升** | 26% → 31% → 35% | 每季度爬 5% |
| **封顶** | 35% | 不设更高目标（覆盖价值递减） |

```
# tier0 Gate1 中使用（随阶段修改 fail-under）：
pytest --cov=agent --cov-fail-under=21 --cov-append tests/
```

## 防再发

- 新增 Python 模块 → 必须同步新增 `test_<name>_imports.py`
- Mock 不跳过写盘（EV-K05 反模式教训）
- 过夜测试用 `--timeout=60` 防止 flaky test 挂起 CI

**Phase 0 审计**（合规样本 / tier0 双轨 / 偏离例）：[`docs/phase0/test-naming-convention.md`](./phase0/test-naming-convention.md)

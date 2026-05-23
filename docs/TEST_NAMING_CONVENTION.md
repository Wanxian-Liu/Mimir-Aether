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

```
# 在 tier0 Gate1 中追加：
# 覆盖率 >= 基线（如 15% → 定期提高）
pytest --cov=agent --cov-fail-under=15 --cov-append tests/
```

## 防再发

- 新增 Python 模块 → 必须同步新增 `test_<name>_imports.py`
- Mock 不跳过写盘（EV-K05 反模式教训）
- 过夜测试用 `--timeout=60` 防止 flaky test 挂起 CI

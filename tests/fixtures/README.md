# tests/fixtures — 共享测试夹具

> 对标 pytest fixtures convention  
> 创建日期：2026-05-21（EV-P01）· 审计：2026-05-24（[docs/phase0/fixtures-readme.md](../../docs/phase0/fixtures-readme.md)）

## 目录结构（实际）

```
tests/fixtures/
├── README.md            ← 本文件
└── example_fixture.py   ← 示例 fixture（样板；当前无测试引用）
```

`conftest.py` — **待建**（Phase 1 前按需；agent 类测试现用 `tests/agent/conftest.py`）

## 命名规范

| 模式 | 用途 |
|------|------|
| `conftest.py` | pytest 自动发现 fixture（作用于**本目录及子目录**） |
| `test_*.py` | 测试文件 |
| `*_fixture.py` | 独立夹具模块（经 `pytest_plugins` 或 conftest 导入） |

## Mock 策略

- **LLM 调用**：用 `pytest.monkeypatch` 替换 `agent.core_loop` 的 LLM 调用为固定返回值
- **文件 I/O**：用 `tmp_path` fixture（pytest 内置）隔离
- **网络**：不 mock 工具层（DeepSeek tool call 格式问题只能真环境复现）

## 防再发

- 共享 fixture 不依赖 `$MIMIR_AETHER_HOME` 环境变量
- 每个 fixture 独立清理（`tmp_path` 自动清理）
- 不对 `persistent.json` 做读写（只读测试用 `tmp_path` 副本）

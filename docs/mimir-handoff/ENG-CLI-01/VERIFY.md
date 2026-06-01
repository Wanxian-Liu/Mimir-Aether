# ENG-CLI-01: 验证

## tier0

```
./run_ralph_tier0.sh
```

末行：

```
4 failed, 677 passed
```

4 项失败均为预存（L2/L3 跨会话检索测试），与本次改动无关。

## 专项测试

```
python3 -m pytest tests/tools/test_cli_one_shot.py -v
```

```
tests/tools/test_cli_one_shot.py::test_one_shot_flag_in_parser PASSED
tests/tools/test_cli_one_shot.py::test_one_shot_with_model_flag PASSED
tests/tools/test_cli_one_shot.py::test_one_shot_handler_exists PASSED
tests/tools/test_cli_one_shot.py::test_one_shot_no_args_does_not_trigger PASSED
tests/tools/test_cli_one_shot.py::test_one_shot_dispatch_in_main PASSED

5 passed in 0.19s
```

## 手动验证

```bash
# 基本：flag 可解析
mimir --one-shot "hello" 2>&1 | head -3
# 应输出纯文本响应（无 banner/装饰）

# 无 flag 时默认交互模式不受影响
echo "" | mimir 2>&1 | head -5
# 应输出 banner / 欢迎信息
```

需要 Gateway 重启后生效（与 ENG-SF-01 同批）。

## 回归

`git diff --stat`:
```
cli.py                                    |  1 +
mimir_cli/cli_subparsers_setup.py         |  8 +++++++-
mimir_cli/main.py                         | 24 ++++++++++++++++++++++++
tests/tools/test_cli_one_shot.py          | 65 ++++++++++++++++++++++++++++++++++++++++++
```

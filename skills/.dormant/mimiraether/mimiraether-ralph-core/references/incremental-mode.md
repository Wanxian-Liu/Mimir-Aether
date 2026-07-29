# `--changed-only` 增量模式参考

## 实现位置

- 入口: `~/src/MimirAether/run_ralph_tier0.sh`
- 审计日志: `logs/incremental-run.log`

## 行为

```
$ ./run_ralph_tier0.sh --changed-only
```

1. git diff HEAD --name-only 检测变更文件
2. ≤15 个 → 增量模式
   - Gate1: 只 compile/import 变更的 TARGET_FILES
   - Gate2: 只跑变更的 test_*.py 文件
   - Gate3: 永远全量跑
3. >15 个 → 退化到全量
4. 审计日志写入 logs/incremental-run.log（含 SHA256 hash）

## 验证

```bash
# 改一个 test 文件 → 只跑 6 个测试（vs 全量 708）
echo "# incr-test" >> agent/test_persistent_store_akl.py
./run_ralph_tier0.sh --changed-only
git checkout agent/test_persistent_store_akl.py  # 恢复
```

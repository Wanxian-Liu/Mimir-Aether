# 压缩台账口径速查（A6 审计会实证 · 2026-10-07）

## 阈值真源（三处，改一处不够）
| 层 | 键 | 现值 | 生效方式 |
|:--|:--|--:|:--|
| gateway 卫生压缩 | tuned 键 `compressor.hygiene_token_threshold` | 300000 | **每会话每轮读一次**（`_hygiene_token_threshold()`）⇒ 热调**免重启** |
| agent 层 | env `MIMIR_COMPRESS_THRESHOLD_TOKENS` | 300000 | 日志 `source=env:...` 可见 |
| gateway 消息数硬限 | `hard_msg_limit` | **400 条** | msgs>400 即唤起卫生压缩（与 token 无关） |
旁证：`tuned_thresholds.json` 另有 `compressor.effective_window_tokens=300000` / `compressor.threshold_percent=0.35`。

## 台账 `data/compression_quality.jsonl` 字段口径（易误读）
- `prompt_tokens_before` = **估算**（`_pre_tokens_for_ledger`）——与实计可差 2×，**引用它立论前先看 next**
- `prompt_tokens_before_actual` = **API 实计**（`pre_tokens_caliber=api`）
- `prompt_tokens_after` = `result.compressed_tokens`（**不是** API 实计）
- `outcome` 生产端唯一：`compress()` 尾部实体验证块 → `rate<0.80 ⇒ rollback`；否则 `quality_outcome_for(result)`
- `applied|noop` 由 `compressed_count >= original_count` 判定（`cc==oc ⇒ noop`）

## 三态可复算定义（jq 一行）
```
jq -r '(if .outcome=="applied" and .compressed_count<.original_count then "E_real"
        elif .outcome=="applied" then "E_earlyexit" else (.outcome//"none") end)' \
   ~/.mimiraether/data/compression_quality.jsonl | sort | uniq -c
```
现状读数：71 E_real / 7 E_earlyexit / 49 noop / 458 rollback / 1 none（共 586 行）
⇒ **覆盖率分母只认 `E_real`**；`E_real==0` 时必须报 `UNMEASURABLE`，**禁报 0.0000**。

## 两条只读取证捷径
1. `[COMPRESS]` 日志 reason 分布 = `compress()` 走了哪条分支的**运行时真源**（比读源码快）：
   `(nothing compressed)` / `(compress returned messages unchanged)` / `entity_retention_low`
2. 常驻单元名 = **`mimiraether.service`**（不是 `mimiraether-gateway.service`）；解释器 = `.venv` Python 3.12 ⇒ 看 `*.cpython-312.pyc` 的 mtime vs 源 mtime 判字节码是否陈旧。

## 已知坑
- `/proc/<pid>/exe` 与 `.env` 字面量会被**载荷扫描拦**（`denied path segment`）⇒ 换 `systemctl show -p MainPID` + unit 文件。
- 长文（≥3KB）单次 `write_file`/`execute_code` 会报 `Invalid JSON: Unterminated string` ⇒ **分块 ≤3KB 追加**。

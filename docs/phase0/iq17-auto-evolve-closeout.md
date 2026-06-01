# IQ-13: C AUTO_EVOLVE 核实 closeout

> 日期：2026-06-01 · 刘哥拍板：**只保持 .env=1，不改代码默认**

## 现状

| 项 | 值 |
|----|-----|
| `.env` 变量 | `MIMIR_AUTO_EVOLVE=1`（SELF-10 已设） |
| 代码默认 | `os.environ.get("MIMIR_AUTO_EVOLVE", "")` → 空字符串 = 关 |
| 刘哥决定 | 不改代码默认，只用 `.env` 控制 |

## 结论

**不改代码。** 新部署时须文档写明需在 `.env` 加 `MIMIR_AUTO_EVOLVE=1`。

## 验证

```bash
grep MIMIR_AUTO_EVOLVE ~/.mimiraether/.env
# → MIMIR_AUTO_EVOLVE=1
```

# Phase 1 — P1-4 工具冒烟与 tier0

| 字段 | 值 |
|------|-----|
| **日期** | 2026-05-19 |
| **数据根** | `MIMIR_AETHER_HOME=/home/rayliu/.mimiraether` |

---

## 1. 胶囊工具冒烟

| 检查 | 结果 |
|------|------|
| `list_capsules(limit=5)` | `total=230`, `shown=5` |
| `get_capsule_by_id("d4e0223cdc53")` | `file=06-06-linearize-typescript-strict.html`, preview 1000 字符 |
| `get_capsule_by_id("2f052678ed10")` | 命中带前缀文件名 |
| `pytest tests/test_mimircore_tool_capsules.py` | **5 passed** |

---

## 2. Ralph tier0

```bash
./run_ralph_tier0.sh
```

| Gate | 结果 |
|------|------|
| Gate1 Syntax/Import | PASS |
| Gate2 Parity Tests | **162 passed** |
| Gate3 Core E2E | **2 passed** |
| Advisory openclaw literals | ok (12 / threshold 60) |

**裁定**：**PASS**（2026-05-19 本机仓库根执行）。

---

## 3. 修订

| 日期 | 变更 |
|------|------|
| 2026-05-19 | 初版 |

# HERM-CTX-02 closeout — Feishu natural-language context references

**Grain:** `HERM-CTX-02` · Wave 12 Task 8  
**Backlog:** `docs/MIMIR_EXEC_BACKLOG.md` §18.2 / §19.1

## Problem

`@file` / `@url:` DSL existed but Feishu users paste doc links in plain Chinese without `@`. Preprocess only ran when `"@" in message`, so links were ignored.

## Delivered

- **`agent/context_references.py`**: `FEISHU_URL_PATTERN`, `parse_feishu_natural_references`, `message_has_context_references`, `kind=feishu` stub expansion
- **`agent/core_loop.py`** + **`gateway/router/inbound_prep_mixin.py`**: trigger on Feishu URL without `@`
- **`data/feishu_context_smoke.json`**: one documented smoke utterance
- Tests: `tests/agent/test_context_references_feishu.py`, `tests/contract/test_horizon_herm_ctx_02.py`

## Mimir smoke (1 条)

1. Gateway running (hard restart if SCR/CTX code not loaded).
2. Feishu DM one line (or use fixture text):

   `请根据飞书文档 https://<tenant>.feishu.cn/docx/<token> 总结要点`

3. Expect log: `@引用展开` with `feishu` ref; assistant prompt contains `Feishu document link` + URL (stub block, not full doc body unless lark-doc used).

Automated check:

```bash
python3 -m pytest tests/agent/test_context_references_feishu.py -q
```

## Verify

```bash
./run_ralph_tier0.sh
```

## Gateway

**Hard restart recommended** — touches `core_loop` + gateway inbound prep (Feishu path).

## Next

- **OS-REV-01** — skill description quality hook

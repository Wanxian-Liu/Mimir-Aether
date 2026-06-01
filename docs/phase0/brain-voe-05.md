# BRAIN-05: VoE Learning Evidence

> **Date**: 2026-06-01  
> **Env**: `MIMIR_WM_VOE_LEARNING=1` ✓  
> **Code path**: WM-P11 dual-write not yet implemented in Python  

## Status

- ✅ `MIMIR_WM_VOE_LEARNING=1` set in production `.env`
- ✅ `MIMIR_WM_VOE_REPLAN_CTX=1` set in production `.env`
- ✅ `world_model_spike.py` predictor functional (BRAIN-01 test + contract test)
- ❌ VoE dual-write (expected vs actual comparison → `feedback_events.jsonl`) not yet wired — env var set but no consumer code reads it

## Coverage

| Test | Status |
|------|--------|
| `test_recall_intent_needs_context` | ✅ |
| `test_code_intent_needs_source_files` | ✅ |
| `test_general_intent_no_special_needs` | ✅ |
| `test_wm_predictor_default_off` | ✅ |
| `test_wm_predictor_env_on` | ✅ |

## Next

VoE learning dual-write is a Phase 2 item (IQ-EVO / Horizon C). The env var is forward-looking — won't consume CPU until code lands.

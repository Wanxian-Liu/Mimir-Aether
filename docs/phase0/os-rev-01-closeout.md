# OS-REV-01 closeout — skill description quality reviewer

**Grain:** `OS-REV-01` · Wave 12 Task 9  
**Backlog:** `docs/MIMIR_EXEC_BACKLOG.md` §18.2 / §19.1

## Problem

`skills_qa.score_skill_quality` scores whole SKILL.md files, but curator lifecycle reports lacked a **description-only** signal for routing quality (depends on OS-TQM-02 wiring culture).

## Delivered

- **`agent/skill_description_reviewer.py`**: `score_skill_description`, env `MIMIR_SKILL_DESCRIPTION_REVIEW` (default **on**), JSON report at `$MIMIR_AETHER_HOME/data/skill_description_review.json`
- **`agent/skill_curator.run_lifecycle_pass`**: runs review when enabled; appends section to lifecycle markdown
- Tests: `tests/agent/test_skill_description_reviewer.py`, `tests/contract/test_horizon_os_rev_01.py`

## Verify

```bash
python3 -m pytest tests/agent/test_skill_description_reviewer.py tests/contract/test_horizon_os_rev_01.py -q
./run_ralph_tier0.sh
```

Manual:

```bash
MIMIR_SKILL_CURATOR_ON_CLOSE=1  # optional on-close trigger
python3 -c "from agent.skill_description_reviewer import run_description_review_pass; print(run_description_review_pass())"
```

## Gateway

**No restart required** — agent-only hook; no gateway route changes.

## Next

- **OS-TOOL-SRCH-01** — ToolRanker / tool-level search

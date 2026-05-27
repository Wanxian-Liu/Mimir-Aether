# HERM-SDH-02 closeout — subdirectory hints in system prompt

**Grain:** `HERM-SDH-02` · Wave 10 Task 3  
**Backlog:** `docs/MIMIR_EXEC_BACKLOG.md` §18.2 / §19.1

## Delivered

- `SubdirectoryHintTracker.prompt_block()` — scans immediate child dirs for AGENTS/CLAUDE/.cursorrules
- `build_subdirectory_hints_system_block(cwd)` gated by **`MIMIR_SUBDIR_HINTS_IN_SYSTEM`** (default **off**)
- Wired into `build_system_prompt()` and `build_system_prompt_parts()` **context** tier (after cwd context files)
- Tests: `tests/agent/test_subdirectory_hints_prompt.py`, `tests/contract/test_horizon_herm_sdh_02.py`

## Verify

```bash
python3 -m pytest tests/agent/test_subdirectory_hints_prompt.py tests/contract/test_horizon_herm_sdh_02.py -q
./run_ralph_tier0.sh
```

## Ops

- Enable: `MIMIR_SUBDIR_HINTS_IN_SYSTEM=1` on gateway/agent (increases context tier size; max 12 child dirs)
- Tool-result hints (HERM-SDH-01) unchanged and independent

## Wave 10 exit

- §19.1 first three rows `[x]` (CUR-02 · TGR-02 · SDH-02)

## Next

- **OS-TQM-02** (Wave 11)

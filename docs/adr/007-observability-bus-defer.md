# ADR-007: ObservabilityBus — defer (Horizon B1 · OBS-B1-01)

> **Status:** Accepted — **defer implementation** (2026-05-26)  
> **Scope:** **OBS-B1-01** · backlog §16 · D6-2  
> **Supersedes:** ADR-005 §4 open question (D6-2)  
> **Related:** ADR-005 (execution trace SoT) · IEVO-05 monitor/insights tests · GH **#22** remainder

---

## Context

D17 / wiki audits proposed an in-process **ObservabilityBus** to fan out tool/session events to monitor, SessionTracker, ExecutionRecorder, and Insights. ADR-005 (IEVO-03) left D6-2 open: synchronous fan-out in `execution_pipeline.record_tool_call()` was sufficient for the industrial-evolution MVP.

Horizon **B1** asks for an explicit **evaluate → wire or defer** decision without breaking `/health` or the execution SoT.

---

## Current wiring (2026-05-26)

Single integration point: `agent.execution_pipeline.record_tool_call()`.

| Sink | Purpose | Failure mode |
|------|---------|--------------|
| **ExecutionRecorder** | SoT JSONL trace (ADR-005) | Required when pipeline started |
| **ToolQualityManager** | Per-tool success/degradation | Best-effort via session pipeline |
| **SessionTracker** | `sessions.db` aggregates | `try/except` fail-open |
| **monitor** | Sliding-window alerts → `/health` inputs | `try/except` fail-open |

No ordering guarantees across sinks; no async queue; no cross-process bus. **This matches IEVO-03 design intent.**

---

## Evaluation

| Criterion | Assessment |
|-----------|------------|
| Fan-out complexity | **Low** — four calls, one function, no plugin registry |
| Ordering / race bugs | **None observed** in tier0 or Wave E monitor tests |
| Ops pain | **Low** — SoT path documented (ADR-005); monitor + health_check cover alerts |
| Cost of bus now | **Medium** — new abstraction + migration + dual tests for little gain |
| Benefit of bus now | **Low** — no new consumer in B1 scope |

**Conclusion:** A dedicated ObservabilityBus is **not justified** for B1. Keep `record_tool_call()` as the integration seam.

---

## Decision

1. **Defer** ObservabilityBus implementation until a **documented trigger** fires (below).
2. **Do not** add a parallel event path; new observability consumers MUST hook via `record_tool_call()` or read SoT JSONL (ADR-005).
3. **B1 observability work** continues in **OBS-B1-02** (ops runbooks / health_check) and **OBS-B1-03** (ISSUES #10), not a bus refactor.

### Reopen triggers (any one)

- A fifth sink is added to `record_tool_call()` **and** ordering/failure semantics become ambiguous.
- Production incidents tied to **lost events** because one sink threw before another ran (not currently seen).
- Product requires **async** or **cross-process** telemetry fan-out (e.g. external OTel collector as mandatory sink).

---

## Consequences

### Positive

- No risk to `/health` or evolution SoT from a large refactor during B1.
- Clear operator story: one function, one ADR chain (005 → 007).

### Negative

- `record_tool_call()` may grow if many sinks are added without a bus — revisit when reopen trigger hits.

---

## Verification

```bash
./run_ralph_tier0.sh   # includes test_horizon_obs_b1_01
```

Contract asserts ADR-007 exists, ADR-005 still names ExecutionRecorder SoT, and `record_tool_call` retains monitor + SessionTracker fan-out.

---

## References

- [`005-observability-execution-sot.md`](./005-observability-execution-sot.md)
- [`MIMIR_EXEC_BACKLOG.md`](../MIMIR_EXEC_BACKLOG.md) §16
- `agent/execution_pipeline.py` — `record_tool_call`

# ADR-004: mimicore submodule and `.openclaw` boundary

> **Status:** Accepted (2026-05-25)  
> **Scope:** Wave D **IND-04** · D7 partial  
> **Closes class:** GitHub **#13** (mimicore `.openclaw` defaults) — must not recur

---

## Context

`mimicore/` is a **git submodule** pointing at [`memory-hall`](https://github.com/Wanxian-Liu/memory-hall) (see `.gitmodules`). Capsule generation, JEPA/self-evolution hooks, and optional introspection live there. Before **PR #24** / `mimir_paths.py`, submodule code defaulted to `~/.openclaw/projects/…` paths and broke de-platformed installs (no OpenClaw tree on disk).

MimirAether **parent repo** (`agent/`, `gateway/`, `tools/`) already resolves home via `mimir_constants` (ADR-003). The submodule **cannot** import `mimir_constants` (separate package / CI checkout); it carries a **mirror** resolver in `mimicore/mimir_paths.py`.

---

## Decision

### 1. Submodule contract

| Rule | Detail |
|------|--------|
| **Init** | After clone: `git submodule update --init mimicore` ([`MIMIR_ACTIVATE.md`](../MIMIR_ACTIVATE.md)) |
| **Pointer bumps** | Only with intent: tier0 green + note in PR body; do not bump to pick up unrelated memory-hall churn |
| **Upstream** | Prefer fixes in **memory-hall** → bump submodule pointer in MimirAether; avoid long-lived fork-only path logic |
| **Package root** | `MIMICORE_ROOT` env may override checkout path (tests / alternate layout) |

### 2. Path resolution inside mimicore

**Canonical API:** `mimicore.mimir_paths.get_mimir_home()` — same precedence as ADR-003:

`MIMIR_AETHER_HOME` → `MIMIRAETHER_HOME` → `HERMES_HOME` → `~/.mimiraether`

**All new runtime defaults** under `mimicore/**/*.py` (except allowlist below) MUST use `get_mimir_home()` or helpers built on it (`memory_vault_*`, `get_mimicore_root()`, etc.).

**Do not** import `mimir_constants` from the parent repo inside submodule code (coupling / import cycles in partial checkouts).

### 3. Where `.openclaw` literals are allowed in mimicore

| Category | Allowed | Example |
|----------|---------|---------|
| **Migration scan** | Yes, explicit | `introspection_log_dirs()` may list legacy `~/.openclaw/logs` **after** canonical `$MIMIR_AETHER_HOME/logs` |
| **Permission regex** | Yes, alternation | `memory_vault_permission_pattern()` legacy `openclaw` segment in regex only |
| **Comments / docstrings** | Yes | `threshold_manager.py`, `__init__.py` |
| **Tests / plans / `library/`** | Exempt (not tier0 runtime) | `tests/integration/README.md`, `mini_agent/*.md` |
| **JSON snapshots** | Exempt until refreshed | `introspection/module_map.json` (historical paths; not import-time defaults) |
| **New runtime default** | **No** | `Path.home() / ".openclaw"` as sole data root |

### 4. Parent repo integration

| Consumer | Contract |
|----------|----------|
| `tools/mimircore_tool.py` | `MIMIR_CORE_PATH` default `{get_mimir_home()}/mimicore` or submodule path via `get_mimicore_root()` |
| `skills/…/self_evolution` | Import `mimicore.*` only after submodule init |
| Tier0 | Does **not** compile entire submodule; **contract test** `test_mimicore_openclaw_boundary_ind04.py` scans `mimicore/**/*.py` |

### 5. Advisory scope

[`scripts/warn_openclaw_literals.py`](../../scripts/warn_openclaw_literals.py) scans **`agent/`, `gateway/`, `tools/` only** — not `mimicore/`. Submodule boundary is **IND-04 contract test**, not the advisory counter.

---

## Enforcement

- **Contract:** `tests/contract/test_mimicore_openclaw_boundary_ind04.py` (tier0)
- **Human review:** PRs touching `mimicore/` pointer or `mimir_paths.py` require ADR-004 checklist in description

**Regression signal (GH #13 class):** Agent/gateway starts, `MIMIR_AETHER_HOME=~/.mimiraether`, no `~/.openclaw` on disk → capsule tool / introspection still resolves paths under mimir home.

---

## Non-goals (IND-04)

- Rewriting all historical docs under `mimicore/library/` or `mini_agent/*.md`
- Refreshing `module_map.json` (separate chore)
- Merging memory-hall and MimirAether into one repo

---

## References

- [ADR-003](./003-runtime-env-aliases.md) — env aliases (parent repo)
- [`MIMIR_OPENCLAW_BOUNDARY.md`](../MIMIR_OPENCLAW_BOUNDARY.md) §7 — audit closure #13
- [`path-contract.md`](../path-contract.md) — Runtime entry: mimicore
- [`MIMIR_CLARIFY_BASELINE.md`](../MIMIR_CLARIFY_BASELINE.md) §3 — mimicore touchpoints

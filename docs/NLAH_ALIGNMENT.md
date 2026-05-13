# NLAH Alignment — MimirAether

Natural Language Agent Harness (NLAH) formalization: mapping MimirAether
architecture to the NLAH paper's core concepts.

## Core Mapping

| NLAH Concept | MimirAether Implementation |
|:--|:--|
| **Agent Identity & Scope** | `SOUL.md` (identity) + `AGENTS.md` (scope) |
| **Tool Definitions** | `SKILL.md` frontmatter + JSON Schema via `tools/registry.py` |
| **Type Safety** | `model_tools.coerce_tool_args()` — Hermes-level type coercion |
| **Environment Constraints** | `Ralph tier0` (Gate1-3) + `_safe_path()` + strategy pre-validation |
| **Evaluation Loop** | `evaluator-optimizer` skill (Anthropic pattern) + `verification` gate |
| **Context Management** | `context_engine.py` + `context-compressor` + `cross-session` |
| **Memory & State** | `memory` tool + `cross-session` context + `persistent.json` |
| **Human-in-the-Loop** | `brainstorming` gate (design approval) + `clarify` tool |

## Harness Layers

```
┌─────────────────────────────────────┐
│  Identity (SOUL.md + AGENTS.md)     │  ← Who am I?
├─────────────────────────────────────┤
│  Knowledge (wiki/ + llms.txt)       │  ← What do I know?
├─────────────────────────────────────┤
│  Skills (75 SKILL.md files)         │  ← What can I do?
├─────────────────────────────────────┤
│  Tools (registry + model_tools)     │  ← How do I act?
├─────────────────────────────────────┤
│  Guards (strategy + tool_guard)     │  ← What stops me?
├─────────────────────────────────────┤
│  Pipeline (brainstorming → ship)    │  ← How do I flow?
└─────────────────────────────────────┘
```

## SKILL.md → NLAH Alignment

Each SKILL.md maps to NLAH's "tool card" concept:

| SKILL.md Section | NLAH Equivalent |
|:--|:--|
| `frontmatter` (name, description, triggers) | Tool identity + precondition |
| `## Steps` | Action sequence |
| `## Pitfalls` | Failure modes + recovery |
| `## Verification` | Post-condition checks |

*Created: Phase XIV (2026-05-14). Source: ai-boost/harness-engineering foundations.*

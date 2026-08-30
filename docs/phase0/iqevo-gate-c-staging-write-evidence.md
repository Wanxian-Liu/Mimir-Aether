# IQ-EVO-41 · Gate C staging 真实 SKILL 写入证据

| 字段 | 值 |
|------|-----|
| **ISO 时间 (UTC)** | `2026-05-26T16:32:09Z` |
| **方式** | **B** 受控脚本（`scripts/iqevo_41_staging_write.py`） |
| **会话** | `iqevo41-20260526T163209Z` |
| **任务名** | `iqevo-41-staging-write` |
| **运行时** | `MIMIR_AETHER_HOME=~/.mimiraether` |
| **非 pilot** | 是 — 写入路径不含 `data/ops/gate-b-pilot/` |

## 环境（步骤 1）

```text
$ grep -E 'MIMIR_AUTO_(ANALYSIS|EVOLVE)' ~/.mimiraether/.env
MIMIR_AUTO_ANALYSIS=1
MIMIR_AUTO_EVOLVE=1

$ pgrep -af 'gateway/run.py' | head -1
401777 python3 ~/src/MimirAether/gateway/run.py

$ curl -s http://127.0.0.1:18999/health | head -c 200
{"status": "ok", "platform": "MimirAether", "gateway": "ok", "agent": "ok", ...}
```

## 被改 SKILL

**绝对路径：** `~/.mimiraether/skills/iqevo-41-gate-c-staging/SKILL.md`

**mtime：** `2026-05-27 00:32:09 +0800`（`stat` 与 `find -mmin 30` 一致）

### 改前（≤10 行）

```markdown
# IQ-EVO-41 staging skill (before)

Gate C staging evidence target. Do not use in production workflows.
```

`sha256` 前缀：`0d63df59ec2d5ca9`

### 改后（≤10 行）

```markdown
# IQ-EVO-41 staging skill (after apply_evolution_from_analysis)

Written by run_post_analysis_sync → apply_evolution_from_analysis.
```

`sha256` 前缀：`a026f2692fc12dde`

## Analysis artifact

`~/.mimiraether/data/analysis_artifacts/20260527T003209_iqevo-41-staging-write.json`

- `type`: `post_task_analysis`
- `task_name`: `iqevo-41-staging-write`
- `timestamp`: `2026-05-27T00:32:09.248705`（文件内）

## agent.log 摘录

来源：`~/.mimiraether/logs/agent.log`（第二次受控运行前 `setup_logging(hermes_home=..., force=True)`）

```text
2026-05-27 00:32:09,575 INFO agent.post_close_analysis: post_analysis applied session_id=iqevo41-20260526T163209Z task=iqevo-41-staging-write
2026-05-27 00:32:09,583 INFO agent.post_close_analysis: post_analysis evolution session_id=iqevo41-20260526T163209Z applied=1 ok=1
```

## 执行链说明

1. `pipeline_result` 含 `errors` + `degraded_tools`（受控信号，非生产破坏）。
2. `run_post_analysis_sync` → `save_analysis_artifact` → `apply_analysis_to_pipeline`（mock `call_llm` 返回 fix 建议）。
3. `apply_evolution_from_analysis`（`MIMIR_AUTO_EVOLVE=1`）→ `get_skills_dir()` → `~/.mimiraether/skills/` 下 FIX 写入。

复现（需 env 已开）：

```bash
MIMIR_REPO_ROOT=~/src/MimirAether MIMIR_AETHER_HOME=~/.mimiraether \
  MIMIR_AUTO_ANALYSIS=1 MIMIR_AUTO_EVOLVE=1 \
  python3 ~/src/MimirAether/scripts/iqevo_41_staging_write.py
```

## 人工审查

**结论：OK**（staging 专用技能 `iqevo-41-gate-c-staging`，不影响既有生产技能）

**如需 revert：**

```bash
rm -rf ~/.mimiraether/skills/iqevo-41-gate-c-staging
# 可选：删除对应 artifact
# rm ~/.mimiraether/data/analysis_artifacts/20260527T003209_iqevo-41-staging-write.json
```

## 声明

- 本证据 **未** 使用 `data/ops/gate-b-pilot/` 作为写入目标。
- 未提交 `data/persistent.json`。
- Gate C 结案（§42）留待战略窗下一粒。

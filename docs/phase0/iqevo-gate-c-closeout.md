# IQ-EVO-42 · Gate C 结案

| 字段 | 值 |
|------|-----|
| **Date (UTC)** | `2026-05-26T16:52:26Z`（C2 第三次 eval 完成时刻） |
| **Home** | `MIMIR_AETHER_HOME=~//.mimiraether`（刘哥机 staging/生产同 home） |
| **前置** | IQ-EVO-41 PASS — [`iqevo-gate-c-staging-write-evidence.md`](./iqevo-gate-c-staging-write-evidence.md) |
| **§41 写入方式** | **B** 受控脚本（非 `data/ops/gate-b-pilot/`）；真实路径 `~/.mimiraether/skills/iqevo-41-gate-c-staging/SKILL.md` |

---

## C1 · 档位 B 已 [x]

| 检查 | 结果 |
|------|------|
| `iqevo-evolution-gates.md` 档位 B 表 B1–B7 | 全 **[x]** |
| 结案文档 | [`iqevo-gate-b-closeout.md`](./iqevo-gate-b-closeout.md) |
| B1 skills 基线 | `$MIMIR_AETHER_HOME/data/ops/gate-b1-skills-baseline.tar.gz` |

**C1：** [x]

---

## C2 · 生产 home 连续 3× `run_evolution_eval.sh` exit 0

**命令（每次相同）：**

```bash
MIMIR_REPO_ROOT=~/src/MimirAether MIMIR_AETHER_HOME=~/.mimiraether \
  ./scripts/run_evolution_eval.sh
```

| Run | exit | compare JSON（绝对路径） | `pass` |
|-----|:----:|--------------------------|:------:|
| 1 | 0 | `~//.mimiraether/data/evolution_eval/memory-retrieval-compare-20260526T165224Z.json` | true |
| 2 | 0 | `~//.mimiraether/data/evolution_eval/memory-retrieval-compare-20260526T165225Z.json` | true |
| 3 | 0 | `~//.mimiraether/data/evolution_eval/memory-retrieval-compare-20260526T165226Z.json` | true |

**C2：** [x]

---

## C3 · skills 审查

**7 日内 `SKILL.md` mtime 变更（节选）：**

| mtime (local) | 路径 | 判定 |
|---------------|------|------|
| 2026-05-27 00:32 | `skills/iqevo-41-gate-c-staging/SKILL.md` | §41 受控写入；**保留**（staging 专用，可 revert） |
| 2026-05-26 20:32 | `skills/mimiraether-world-model-paper-analysis/SKILL.md` | 既有业务技能；内容与 frontmatter 正常；**无改坏迹象** |
| 2026-05-24 11:35 | 若干 `software-development/`、`research/`、`mimiraether/` 等 | 批量同步/安装痕迹；未抽查全文 |

**`docs/MIMIR_ISSUES.md` Active：** 仅 #3（记忆落盘设计债，deferred）；**无**「技能改坏」类 P0。

**staging 技能处置：** `iqevo-41-gate-c-staging` **保留**供 Gate C 审计链；revert 见 [`iqevo-gate-c-staging-write-evidence.md`](./iqevo-gate-c-staging-write-evidence.md) §人工审查。

**C3：** [x]

---

## 生产 AUTO_EVOLVE 状态

```text
$ grep -E 'MIMIR_AUTO_(ANALYSIS|EVOLVE)' ~/.mimiraether/.env
MIMIR_AUTO_ANALYSIS=1
MIMIR_AUTO_EVOLVE=1
```

Gate C「生产」= 本 home 在 §41 证据后保持上述配置（见 wave7 plan §6）。

---

## Gateway（§42 重启后）

```text
$ pgrep -af 'gateway/run.py' | head -1
434462 python3 ~//src/MimirAether/gateway/run.py

$ curl -s http://127.0.0.1:18999/health
{"status": "ok", "platform": "MimirAether", "gateway": "ok", "agent": "ok", ...}
```

重启命令：

```bash
MIMIR_REPO_ROOT=~/src/MimirAether MIMIR_AETHER_HOME=~/.mimiraether \
  ./scripts/restart_gateway_hard.sh
```

---

## tier0

`./run_ralph_tier0.sh` — **456+2 PASS**（2026-05-27，Gate C 结案窗）

---

## 回滚步骤（档位 C 撤销）

1. `~/.mimiraether/.env` 设 `MIMIR_AUTO_EVOLVE=0`（可选同时关 `MIMIR_AUTO_ANALYSIS`）。
2. `MIMIR_REPO_ROOT=~/src/MimirAether MIMIR_AETHER_HOME=~/.mimiraether ./scripts/restart_gateway_hard.sh`
3. 恢复 skills：`tar -xzf ~/.mimiraether/data/ops/gate-b1-skills-baseline.tar.gz -C ~/.mimiraether/`（先备份当前 `skills/` 若需对比）
4. 可选删除 staging 证据技能：`rm -rf ~/.mimiraether/skills/iqevo-41-gate-c-staging`

---

## 声明

- 未实现 Gate D / Unified Plan 1c。
- 未改 SKILL 进化逻辑代码。
- 未提交 `data/persistent.json`。
- backlog §15 Wave 7 **IQ-EVO-42** 由战略窗标 [x]。

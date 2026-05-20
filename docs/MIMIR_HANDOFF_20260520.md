# MimirAether 离线交接 — IR-20260520 结案后（2026-05-20）

> **给刘哥**：Cursor 工程收尾已完成；**Mimir 续跑**见下文与 `docs/MIMIR_EXEC_BACKLOG.md` §2。  
> **给 Mimir**：禁止再改 mixin 架构；从 **T-02** 起冒烟（T-01 / 工具链已在 IR 中 Go）。

---

## 1. 本轮工程已交付（Cursor）

| 项 | 状态 | 证据 |
|----|------|------|
| IR-20260520 mixin 缺 import → NameError → TRUNCATE | **已修** | `44061e2`…`a612217`；`docs/MIMIR_INCIDENT_IR-20260520.md` |
| recovery 不对代码错误 TRUNCATE | **已修** | `agent/recovery_mixin.py` + `test_recovery_mixin_code_errors.py` |
| exec_mixin 分裂后 import（ToolError/registry/functools） | **已修** | `4ff3e91` + `test_exec_mixin_imports.py` |
| gateway mixin import 冒烟 | **已修** | `test_gateway_mixin_import_smoke.py` |
| tier0 | **绿** | `./run_ralph_tier0.sh` → **181 + 2 PASS** |
| TRUNCATE 基线 | **冻结 19** | `grep -c 'Level 3 TRUNCATE' ~/.mimiraether/logs/agent.log` |
| 飞书工具冒烟（read_file AGENTS.md） | **Go** | Phase 3c，见 incident 文档 |
| git push | **待刘哥** 或已授权后由 Cursor 执行 | `main` 领先 `origin/main` 约 10 commit |

**勿提交**：`data/persistent.json`、`data/cross-session-context.md`（runtime）。

---

## 2. Mimir 下一刀（按 backlog 第一条 `[ ]`）

1. **§2b EV-M*** — 小颗粒离线进化（`docs/MIMIR_EXEC_BACKLOG.md` §2b）；**每次一颗粒**  
2. **识图** — **搁置**（`EV-VISION-DEFER`）；刘哥 **DeepSeek-only**，不配 OpenRouter  
3. **T-03 / T-06～T-12** — 映射到 EV-M02～EV-M12，见 §2b 表  
4. 每轮更新：`docs/MIMIR_EXEC_BACKLOG.md` §4 + §2b 勾选；冒烟完结后发 **EV-M13** 包  
5. **自学习轨**：`docs/MIMIR_EXEC_BACKLOG.md` **§2c EV-L01～L14** → 写入 `docs/MIMIR_EV_L_INDUSTRIAL_LEARNING.md`（工业级防再发，只写文档）

**一键提示词**：`docs/MIMIR_D17_AUDIT_AND_TASKS.md` **§5**（已更新 post-IR 基线）。

**禁止**：E-004+ 工程代码；删 `role=tool`；填 d5 进化 19 存根；未经授权 `git push`。

---

## 3. 工程队列头（Cursor，刘哥在线时）

| 顺序 | ID | 说明 |
|------|-----|------|
| 1 | **E-004** | `CLI_CONFIG` 默认值，单独 PR |
| 2 | E-005～E-009 | d7→d6→d5，分 PR |
| 3 | **M-008** | `git push origin main`（授权后） |

**延后（勿与 IR 混 PR）**：Phase 4–5 session_count/jsonl 叙事恢复；d7 大删 `cli.py`。

---

## 4. 离线沟通（Mimir backlog 与 OpenClaw / 微信无关）

- **Mimir**：飞书 + 仓库 `docs/MIMIR_EXEC_BACKLOG.md` + `docs/MIMIR_LIU_CURSOR_BRIDGE.md`（留言、授权、签收）。  
- **微信**：仅 OpenClaw **琬弦** 可选用，**不**承担 Mimir 队列同步。  
- **Cursor**：你回电脑后读 bridge 即可。

---

## 5. 常用命令

```bash
cd ~/src/MimirAether
./run_ralph_tier0.sh
MIMIR_AETHER_HOME=~/.mimiraether ./scripts/restart_gateway_hard.sh
pgrep -af 'gateway/run.py'
grep -c 'Level 3 TRUNCATE' ~/.mimiraether/logs/agent.log
```

---

## 6. 文档索引

| 文档 | 用途 |
|------|------|
| `docs/MIMIR_EXEC_BACKLOG.md` | 统一队列真源 |
| `docs/MIMIR_D17_AUDIT_AND_TASKS.md` | T-01～T-11 + §5 总提示词 |
| `docs/MIMIR_INCIDENT_IR-20260520.md` | 事故全记录 |
| `docs/MAINLINE_STATUS.md` | 主线快照 |
| `docs/GATEWAY_STABILITY_BACKLOG.md` | 十条稳定性 |

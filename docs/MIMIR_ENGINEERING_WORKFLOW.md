# Mimir 工程工作流（可执行真源 · ENG-WF）

> **读者**：Mimir（主执行）· 刘哥（拍板/本机 shell）· Cursor（你和我 · 复核/大改）  
> **立案**：2026-06-01 · 承接 [`output/2026-06-01-MIMIR评估与改造方向.md`](../output/2026-06-01-MIMIR评估与改造方向.md)  
> **队列表**：[`MIMIR_TASK_QUEUE.md`](./MIMIR_TASK_QUEUE.md) **§12**（只认第一条可执行 `[ ]`）  
> **方向北星**：[`DEVELOPMENT_NORTH_STAR.md`](./DEVELOPMENT_NORTH_STAR.md) — **Parity 先于覆盖率数字游戏**

---

## 0. 何时跑本链（优先级）

```text
每轮开场执行：

  ./scripts/mimir_iq17_run_next.sh --dry-run

  若 NEXT_TASK=IQ-xx 且非 BLOCK → 先做完 §11（MIMIR_IQ17_EXECUTION_PLAN.md），再回来看 §12。
  若 NEXT_TASK=NONE → ./scripts/mimir_eng_run_next.sh --dry-run
  若仍为 NONE → ./scripts/mimir_wish_run_next.sh --dry-run   # §13 心愿单
```

| 顺序 | 真源 | 说明 |
|:----:|------|------|
| 1 | **§11 IQ-17** | 仍有 `[ ]` 且非纯 BLOCK 时 **必须先 IQ** |
| 2 | **§12 ENG-WF**（本文） | §11 仅剩 BLOCK 时 |
| 3 | **§13 MW** | [`MIMIR_WISHLIST_WORKFLOW.md`](./MIMIR_WISHLIST_WORKFLOW.md) · §12 全 [x] 后 |
| 4 | **§10 SELF-LOOP** | 每周一次 |
| 5 | **§6.1 周常** | M-WEEKLY-01～03 |

**BLOCK 粒纪律**：见 §12 表「BLOCK」列 — Mimir **不得**假装完成；bridge §4 写 `SKIP <ID> reason=…`，**立刻** `./scripts/mimir_eng_run_next.sh` 取下一粒。

---

## 1. 每轮开场（复制给 Mimir）

```text
你是 Mimir 工程轨（ENG-WF）。本轮顺序：

1) $WORKSPACE/CLAUDE.md
2) ~/src/MimirAether/AGENTS.md
3) 本文（MIMIR_ENGINEERING_WORKFLOW.md）§2 单粒循环
4) ~/src/MimirAether/docs/MIMIR_TASK_QUEUE.md §12 第一条可执行 [ ]
5) ~/src/MimirAether/docs/MIMIR_IQ_EVOLUTION_DIRECTION.md §3.3 回报模板

纪律：
- 只改当前 ID 列出的路径；禁止顺手重构
- 声称完成前必须有命令输出（verification-before-completion）
- 禁止 commit data/persistent.json
- 禁止飞书对话内 ensure_single_gateway / kill gateway
- 改 agent|gateway|tools|tests → ./run_ralph_tier0.sh + record_m6_evolution.sh
- §10 授权下可 git commit + push；hook 红则同 ID 修，最多 3 轮，仍红则 BLOCKED 停链
- 做完 [x] 后禁止问「要不要继续」→ 立刻下一粒
```

---

## 2. 单粒循环（每个 ENG-WF-xx 必做）

```text
【ENG-WF 单粒 — <ID>】
0) ./scripts/mimir_eng_run_next.sh --dry-run   # 确认当前 ID
1) git pull --rebase origin main
2) Read 本文 §4 中 <ID> 全文（做什么 / 禁止 / 验证）
3) 若 Owner=刘哥：只写证据包 + bridge 催办；不得代跑 stop/disable/飞书
4) 实现（Surgical）
5) 验证：执行 §4「验证」全部命令；贴 exit code 与关键输出摘要到 VERIFY
6) 若改 agent|gateway|tools：
     cd ~/src/MimirAether && ./run_ralph_tier0.sh
     ./scripts/record_m6_evolution.sh "ENG-WF-xx: <一句>"
7) git add <列出的文件> && git commit -m "<建议 message>"
8) git push origin main   # 禁止 --no-verify；禁止 --force main
9) 若需 Gateway 加载新 agent 代码：bridge §4 写「需刘哥 shell: ensure_single_gateway」
    （刘哥在飞书外执行，Mimir 不在会话内执行）
10) TASK_QUEUE §12 该行改 [x]
11) bridge §4 一行（§3 模板）
12) 立刻 ./scripts/mimir_eng_run_next.sh --dry-run → 下一 ID
```

**失败**：tier0 红 → 定位 → 最小修复 → 回到步骤 6（同 ID，≤3 次）→ 仍红 → bridge `ENG-WF-xx BLOCKED` + **停链**（等刘哥或 Cursor）。

---

## 3. 回报模板（bridge §4 · 必填）

```text
ENG-WF-<ID> <done|SKIP|BLOCKED> · tier0=<N PASS|n/a> · push=<sha|n/a> · 证据=<路径或命令一行>
下一粒=<下一 ID|NONE> · 需刘哥=<无|见 §4>
```

长回报（可选 `docs/phase0/eng-wf-log.md` 追加）仍须含 [`MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md) §3.3 四行：做了什么 / 证据 / 不足 / 下一粒。

---

## 4. 颗粒定义（做什么 · 谁做 · 验证）

> 状态：`[ ]` 待做 · `[~]` 进行中 · `[x]` 完成 · `BLOCK` 等刘哥

### 波次 0 — 对齐（只做一次）

#### ENG-WF-00 — 读真源 + 基线快照

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **做什么** | `git pull`；`curl -s http://127.0.0.1:18999/health \| head -c 300`；`./run_ralph_tier0.sh` 记末行 PASS 数；写 `docs/phase0/eng-wf-00-baseline.md`（health 摘要、tier0 数、日期） |
| **禁止** | 改代码 |
| **验证** | 文件存在 ≥5 行；tier0 exit 0 |
| **产出** | `docs/phase0/eng-wf-00-baseline.md` |

**提示词**

```text
任务 ENG-WF-00：只读基线。pull + health + tier0，写 eng-wf-00-baseline.md，§12 改 [x]，bridge 一行。
```

---

### 波次 1 — P0 可信（运维 + 编造）

#### ENG-WF-01 — Gateway 单 Owner（systemd 止血）

| 项 | 内容 |
|----|------|
| **Owner** | **刘哥** shell · Mimir 只出证据包 |
| **BLOCK** | 刘哥未确认前，ENG-WF-02 可准备文档但不得写「已收敛」 |
| **刘哥命令** | `systemctl --user stop mimiraether.service && systemctl --user disable mimiraether.service` |
| **Mimir 做什么** | 写 `docs/phase0/eng-wf-ops-gateway.md`：现象（restart counter）、根因（双轨启动）、验收三命令 |
| **验证（刘哥后 Mimir 跑）** | `systemctl --user is-active mimiraether.service` → inactive；`pgrep -af 'gateway/run.py'` 仅 1 条且含 `.venv`；`ss -tlnp \| grep 18999` 仅 1 listener |
| **状态** | `[x]` 2026-06-02 · [`eng-wf-ops-gateway.md`](./phase0/eng-wf-ops-gateway.md) |

**给刘哥（可转发）**

```text
ENG-WF-01：请在本机执行 stop+disable mimiraether.service（user systemd）。
完成后回飞书「ENG-WF-01 PASS」。Mimir 只读 log 写证据，不在飞书里 restart gateway。
```

---

#### ENG-WF-02 — 运维真源一句进 OPERATIONS

| 项 | 内容 |
|----|------|
| **Owner** | Mimir（docs） |
| **依赖** | ENG-WF-01 刘哥 PASS |
| **做什么** | 在 [`OPERATIONS_GATEWAY.md`](./OPERATIONS_GATEWAY.md) §5 增加 **「单 Owner」** 小节（≤15 行）：禁止 systemd + ensure_single 并行；唯一推荐 `ensure_single_gateway.sh` |
| **禁止** | 改 gateway 代码 |
| **验证** | `rg -n '单 Owner' docs/OPERATIONS_GATEWAY.md` 有命中 |
| **状态** | `[ ]` |

---

#### ENG-WF-03 — 编造问题：现状与验收标准

| 项 | 内容 |
|----|------|
| **Owner** | Mimir（docs） |
| **做什么** | 写 `docs/phase0/eng-wf-fabrication-spec.md`：定义「编造」（无 tool_result 却宣称已执行/已完成）；列 3 条可测验收（对齐 IQ-32/33 已有代码）；引用 `tests/agent/test_intent_action_guard.py` |
| **禁止** | 大改 core_loop |
| **验证** | 文件含 **Acceptance-1/2/3** 各带 `pytest` 或 `rg` 命令 |
| **状态** | `[ ]` |

---

#### ENG-WF-04 — 编造回归：契约测（M-ENG）

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **依赖** | ENG-WF-03 |
| **做什么** | 新增 `tests/agent/test_eng_wf_fabrication_guard.py`（≥3 cases）：续跑/「已完成」类 user 文本 → 须触发 guard 或要求 tool 证据；跑 tier0 |
| **允许改** | `tests/**`、`agent/intent_predictor.py`（仅 **≤30 行** 且为测绿） |
| **禁止** | 新 Verification Gate 大框架 |
| **验证** | `./run_ralph_tier0.sh` exit 0；`pytest tests/agent/test_eng_wf_fabrication_guard.py -q` exit 0 |
| **状态** | `[ ]` |

---

#### ENG-WF-05 — 跨 session 消息：tool result 不丢（M-ENG）

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **做什么** | 读 `agent/agent_loop.py` / context 裁剪；**最小**补丁：长会话中 `role=tool` 消息优先级不低于 system nudge（或文档化已有行为 + 补 2 测例） |
| **验证** | 新增或扩展 `tests/agent/test_*` ≥2；tier0 绿 |
| **状态** | `[ ]` |

---

#### ENG-WF-06 — 波次 1 收官

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **做什么** | `docs/phase0/eng-wf-wave1-closeout.md`：WF-01～05 证据链接；编造 Acceptance 是否全绿 |
| **验证** | closeout 存在；tier0 再跑 1 次贴末行 |
| **状态** | `[ ]` |

---

### 波次 2 — P0 可测（覆盖率基建）

#### ENG-WF-10 — 覆盖率口径 + 基线数字

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **做什么** | 新增 `scripts/coverage_baseline.sh`：`pytest --cov=agent --cov=gateway --cov=tools --cov-report=term-missing`（**omit** `skills/**,optional-skills/**,mimicore/**`）；写 `docs/phase0/eng-wf-coverage-baseline.md` 记录 **TOTAL %** 与日期 |
| **验证** | 脚本 exit 0；md 含 `TOTAL` 行 |
| **状态** | `[ ]` |

---

#### ENG-WF-11 — 覆盖率 ratchet（非 50% 悬崖）

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **做什么** | 在 `docs/TEST_NAMING_CONVENTION.md` CI Ratchet 写清：**首基线 +5% 封顶到 35%（季度）**；可选 `scripts/coverage_ratchet.sh` 读 baseline md 比较 |
| **禁止** | tier0 默认 `--cov-fail-under=50` |
| **验证** | 文档有 ratchet 表；`rg cov-fail-under docs/` 无 50 |
| **状态** | `[ ]` |

---

#### ENG-WF-12 — tools/registry 覆盖 ≥80%（模块级）

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **做什么** | 扩写 `tests/tools/` 或 `agent/test_tool_registry_*.py`；`pytest --cov=agent/tool_registry.py --cov-fail-under=80`（或等价路径） |
| **验证** | 上述 pytest exit 0；tier0 绿 |
| **状态** | `[ ]` |

---

#### ENG-WF-13 — credential_pool / search_first_guard 各 +3 测例

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **做什么** | 各加 ≥3 测例，覆盖失败分支；不 mock 真实网络 |
| **验证** | tier0 绿；`pytest tests/agent/test_search_first_guard.py -q` |
| **状态** | `[ ]` |

---

#### ENG-WF-14 — 波次 2 收官 + 更新 baseline

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **做什么** | 重跑 `coverage_baseline.sh`；`eng-wf-wave2-closeout.md` 写 **前后 TOTAL %** |
| **验证** | TOTAL ≥ baseline + 3% **或** 诚实写未达标原因 + 下一粒建议 |
| **状态** | `[ ]` |

---

### 波次 3 — P1 可维护（小步拆分 · 不 Monorepo）

#### ENG-WF-20 — 上下文三套清单（只读）

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **做什么** | `docs/phase0/eng-wf-context-inventory.md`：conversation_history / context_compressor / recovery 各 5 行：职责、重叠、建议收敛 **一条**（不实施） |
| **验证** | 北星 §3 阶段 1b 格式 |
| **状态** | `[ ]` |

---

#### ENG-WF-21 — turn_loop 纯函数抽 1 个 + 单测

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **做什么** | 从 `agent/turn_loop.py` 抽 **1 个** 无副作用函数到同文件或 `agent/turn_loop_utils.py`（≤80 行新文件）；`tests/agent/test_turn_loop_utils.py` |
| **禁止** | 拆 core_loop；禁止 >200 行 diff |
| **验证** | tier0 绿；新测 ≥2 |
| **状态** | `[ ]` |

---

#### ENG-WF-22 — FauxLlm 再迁 2 测（Harness）

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **做什么** | 用 `tests/conftest.py` `create_mimir_harness()` 再迁 2 个现有测（见 ENG-PI06-01 handoff） |
| **验证** | tier0 绿 |
| **状态** | `[ ]` |

---

### 波次 4 — 收官

#### ENG-WF-90 — 工程链总收官

| 项 | 内容 |
|----|------|
| **Owner** | Mimir |
| **做什么** | `docs/phase0/eng-wf-closeout.md`：WF-M1～M6 表（见 §5）；更新 `output/2026-06-01-MIMIR评估与改造方向.md` 顶部链到本文 |
| **验证** | closeout 诚实写「行覆盖仍 <35% 与否」；tier0 绿 |
| **状态** | `[ ]` |

---

## 5. 收官合格线（ENG-WF-M1～M6）

| ID | 合格条件 | 验证 |
|----|----------|------|
| **ENG-WF-M1** | systemd 不再 auto-restart 撞 18999 | ENG-WF-01 三命令 + 刘哥 PASS |
| **ENG-WF-M2** | 编造 spec + ≥3 契约测绿 | ENG-WF-03/04 |
| **ENG-WF-M3** | 覆盖率 baseline 文档化且可复跑 | `scripts/coverage_baseline.sh` |
| **ENG-WF-M4** | registry 模块 cov ≥80% | ENG-WF-12 |
| **ENG-WF-M5** | 末粒含代码 → tier0 PASS（≥681） | closeout 贴末行 |
| **ENG-WF-M6** | closeout 不夸大 pi-agent 60% 已达成 | 写清差距与下一链建议 |

---

## 6. 三角分工（本链）

| 角色 | 做 | 不做 |
|------|-----|------|
| **刘哥** | ENG-WF-01 systemd；Gateway 重启；IQ-14 飞书冒烟；`.env` 新键 | 日常改 agent |
| **Mimir** | §12 第一条 `[ ]` → 实现/文档 → 自证 → push → 下一粒 | 飞书内杀 gateway · force push |
| **Cursor（你和我）** | Mimir `BLOCKED` / handoff / >200 行重构；独立 tier0 复核 | 与 Mimir 抢同一 `[ ]` |

**Handoff 触发**：单粒 diff >200 行 · 需新 ADR · tier0 3 轮仍红 → `docs/mimir-handoff/ENG-WF-xx/` + bridge `HANDOFF ENG-WF-xx ready`。

---

## 7. 与评估文档的映射

| 评估 § | ENG-WF 粒 |
|--------|-----------|
| 编造 P0 | ENG-WF-03～06 |
| 运维双轨 | ENG-WF-01～02 |
| 覆盖 5%→ratchet | ENG-WF-10～14 |
| GOD/Monorepo | **不立项**；用 ENG-WF-20～22 小步 |
| 多平台/Provider | **ENG-WF-90 仅写 Horizon 建议**，不在本链实施 |

---

## 8. 修订日志

| 日期 | 摘要 |
|------|------|
| 2026-06-01 | 初版：§12 颗粒 ENG-WF-00～90 · 对接评估稿与 IQ §11 优先级 |

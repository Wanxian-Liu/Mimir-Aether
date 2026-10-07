---
name: mimiraether-empty-content-forensics
description: runner 层「空正文/截断」类故障取证 SOP——用受控差分（同输入唯一变量）定位是预算截断、真空、还是 gate 误判；含 reasoning_tokens 指纹与关思考修复臂。触发词：empty_content/空正文/空跑/截断/finish_reason/reasoning_tokens/模型没输出。
auto_load: false
---

# runner 层空正文取证 SOP（MimirAether）

## 何时用
判词类：`empty_content` / 「模型没输出」/ 「回答截断」/ 输出为空但 api 时延很长。

## 核心判据（先分型再动手，禁直接猜「上下文太长」）
| 形态 | 读数指纹 | 归属 |
|---|---|---|
| **预算被思考吃光** | `finish_reason="length"` ∧ `content_len=0` ∧ `completion_tokens == reasoning_tokens == max_tokens` | 输出侧参数（runner 层，我修） |
| 真·真空（provider 侧） | 秒回（<2s）· `completion_tokens≈0` · `stop` | provider/网络 |
| gate 误判 | 有正文但被后处理剥离为空（如 `strip_think_blocks` 全剥） | 判定逻辑 |
| 工具悬挂 | 无 `session_end` 记录 · tool_call 后长时间无结束 | 工具/进程 |

## 步骤（受控差分 · 唯一变量原则）
1. **取证先看盘上有什么**：`data/trajectories/<date>/<session>.jsonl`（只有 `session_start`/`tool_call`/`session_end` 三类）；
   `logs/agent.log` 找 `turn N: api=Xs, no tools (finished)` + `空正文自然结束`。
   **时延是读数**：18-19s ⇒ 生成了 ~4K tokens；<2s ⇒ 秒回真空（用饥饿臂标定：16/64/256 token → 0.8/1.2/1.7s）。
2. **复现（生产同条件）**：`python3 ~/src/MimirAether/scripts/probes/empty_content_diagnosis.py repro`
   （stream=True + `max_tokens=4096` + 长上下文 ≈29K tokens + 重推理任务 ⇒ 期望 `length/0/4096/4096`）。
   **探针条件必须与生产一致**（stream 与否、模型名、max_tokens）——否则结论不可用。
3. **参数定位**：`agent/callers_mixin.py` `_builtin_call_model_with_tokens` 里
   - **2026-10-06 更正（本技能旧文写「两臂等价」，实测不成立）**：关思考臂只有
     `thinking={"type":"disabled"}` 干净（`finish_reason=stop` · content_len 2912）；
     `reasoning_effort="none"` **不够**（有正文 7200 但 `finish_reason` 仍 `=length`）。
     选臂必跑 `bash scripts/probes/empty_content_diagnosis.py fixmode` 看 `finish_reason`，
     别只看 `content_len`（有正文 ≠ 没收顶）。
   - **修复已落地（B1/B2 · commit c3cbc23）**：唯一窄口改为 `_BuiltinLlmBackend.call_model_with_tokens`
     外包健康闸（纯函数 `classify_output_health` / `plan_output_retry`），
     原实现更名 `_builtin_call_model_with_tokens_once`（新增 `max_tokens_override` / `disable_thinking`）。
     回归 `tests/test_output_budget_retry.py`（20 例）。排障时先看 `grep OUTPUT_HEALTH agent.log`。
   `max_output_tokens = ... else 4096`（**非 claude 硬编码 4096**）；`max_tokens = min(max_output_tokens, context_length//4)`。
4. **判定点定位**：`agent/agent_loop.py` 空正文分支（`if not str(content or "").strip()`）——它**不看** `finish_reason/usage`。
5. **修复臂（同条件差分）**：
   - `reasoning_effort="none"` → 实测 content 7279 字符（`reasoning_tokens=null`）
   - `thinking={"type":"disabled"}` → 实测 content 7919 字符
   - ❌ 换 `deepseek-flash`、❌ 提示级「禁止推理」均无效（仍 4096 reasoning）
   - 注意：关思考后正文仍会撞 4096 ⇒ 必须同时放宽 `max_tokens`（建议 ≥8192）。

## 阈值型闸门（「阈值 N 但实测 M 才动」）取证三选一 · 2026-10-07 实证

遇到「闸门形同虚设 / 阈值 4 实测 15」类判词，**先分型再改**：

| 假设 | 判据（盘上读数） |
|---|---|
| ① **计数器语义错** | 计数函数的「清零条件」是否 = 闸门目标？反例：`readonly_streak()` 遇**任意 write** 清零，而目标是「没写交付物」⇒ staging/日志写**退还预算**，闸门在它自己要防的死法里自关。**受控差分可证**：同轨迹回放，旧版在 staging 写后静默 N 轮、新版 0 轮。 |
| ② **指令发出但被忽略** | 日志有 `触发` 行 + 有 `注入` 行，且 streak 单调递增 ⇒ 指令确实进了消息、模型不理。纯文字提醒在长回环里**饱和** ⇒ 修法＝接到**工具面**（超限只读调用被拒发），不是再叠一条提醒。 |
| ③ **接线不全** | `grep -c '触发'` = 0，或 streak 从不到阈值。 |

**别被尾部离群骗**：先看 streak 分布再下结论。实测 `{4:104, 5:88, 6:26, … 15:1}` ⇒
**中位数 4、max 15**——「实测 15」是离群不是常态。

**改语义后必查两件事**：
1. **旧用例可能只因 bug 才通过**。本例 arm C「已写交付物 ⇒ 不再拦」实际是靠 streak 被误清零成立 ⇒
   改语义后暴露测试里的 tmp 路径被判 staging。改语义 = 同时审「钉住旧语义的断言」。
2. **分离「先前既有失败」**：`git worktree add /tmp/head-check HEAD` → 干净树复跑同一批文件 →
   失败**逐条同名**即先前既有，不是本轮引入。**别把别人的坑算成自己的，也别把自己的坑甩出去。**

## Pitfalls
- **模型名**：API 只认 `deepseek-flash` / `deepseek-v4-pro` / `deepseek-v4-flash` 等**裸名**；带 `provider/` 前缀直接 400。
  运行期由 `model_metadata._strip_provider_prefix` 剥离（`_PROVIDER_PREFIXES` 含 `deepseek`）⇒ 探针要照抄裸名。
- **两条「空」口径不同**：`session_end.final_response_summary` 取「最后一条**非空** assistant content」（中途进度句也算），
  **不等于**判定那轮有正文——不可混读。
- **禁止跳过量具直接改行为**：先落 `finish_reason / completion_tokens / reasoning_tokens / content_len / reasoning_len`
  （现在流式路径整块丢 `delta.reasoning_content`，`finish_reason` 从不落盘 ⇒ 事后无法归因）。
- 探针走真 API：长上下文 ≈29K prompt tokens/次；跑前确认 key 在 `~/.mimiraether/.env`（勿 print 值）。
- 家路径字面量会被 pre-push A6 闸拦 ⇒ 探针里一律 `Path.home()` 运行期展开。

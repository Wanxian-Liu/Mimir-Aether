# World Model 归档目录（2026-08-03）

> WM surprise 流按四方共识停用（存废讨论：surprise 流停用，其余保留）。
> 本目录保存 WM Phase0/1.1 的代码与数据作为历史参考。
> **2026-08-03 18bug 手术**：代码已修复为正确实现（BUG-01~23 全部修复/处理），
> 若未来复活 VoE 思想，本目录代码是**正确**的起点，不会重蹈 18bug 覆辙。

## 文件清单

| 文件 | 大小 | 说明 |
|:--|:--|:--|
| `world_model_spike.py` | 9,491B | Phase0 规则预测器（BUG-01/06/07/13/14/15 已修） |
| `wm_voe_learning.py` | ~13.7KB | VoE 学习 + 自愈索引（BUG-03/04/05/08/10/11/12/16/17/21/22 已修） |
| `surprise_events.jsonl` | 1,597,468B | 历史 surprise 事件（3,394 条，供 KPI 审计） |
| `learned_surprises.json` | 147,370B | 历史自愈索引（230 条，供 KPI 审计） |

## 18bug 修复状态总表

| Bug | 级别 | 状态 | 修复位置 |
|:--|:--|:--|:--|
| BUG-01 预测工具名不存在 | P0 | ✅ 修 | world_model_spike.py `_INTENT_SKILLS`（run_terminal_cmd→terminal、grep→search_files） |
| BUG-02 VoE 整串比较 | P0 | ✅ 修 | agent/agent_loop.py VoE 段（单工具比较） |
| BUG-03 自愈映射方向反 | P0 | ✅ 修 | wm_voe_learning.py `_SELF_HEAL_TOOL_MAP`（删除，identity） |
| BUG-04 置信度门控永不触发 | P1 | ✅ 修 | wm_voe_learning.py `append_surprise_event`（normalize 后查 confidence） |
| BUG-05 置信度分母失真 | P1 | ✅ 修 | wm_voe_learning.py `auto_update_predictions`（per-tool hits） |
| BUG-06 is_collapsed 死代码 | P1 | ✅ 修 | world_model_spike.py `predict()` 接入调用点 |
| BUG-07 accuracy 死代码 | P1 | ✅ 修 | world_model_spike.py `compute_prediction_accuracy`（真实工具名 + 诚实空转 0.0） |
| BUG-08 EXCLUDE 误排 | P1 | ✅ 修 | wm_voe_learning.py `_SELF_HEAL_EXCLUDE`（移除 read_file/session_search） |
| BUG-09 归档后残留写 | P2 | ✅ 停 | env 已关（MIMIR_WM_*=0）+ 本 README 重启说明 |
| BUG-10 JSON 非原子写 | P2 | ✅ 修 | wm_voe_learning.py `_atomic_write_json`（tmp+replace） |
| BUG-11 无轮转 | P2 | ✅ 记录 | 停用后不再增长；复活时需轮转策略 |
| BUG-12 int() 无保护 | P2 | ✅ 修 | wm_voe_learning.py AUTO_UPDATE_THRESHOLD try/except |
| BUG-13 相对导入 | P2 | ✅ 修 | world_model_spike.py 防御性 import |
| BUG-14 chat 分支死代码 | P3 | ✅ 修 | world_model_spike.py `_CHAT_HINT` + `_infer_intent` |
| BUG-15 recall 误判 | P3 | ✅ 修 | world_model_spike.py `_infer_intent`（code 优先） |
| BUG-16 全局状态不持久化 | P3 | ✅ 记录 | 设计意图注明（进程内共享，测试可 reset） |
| BUG-17 单槽覆盖 | P3 | ✅ 修 | wm_voe_learning.py pending 队列化 |
| BUG-18 测试被归档破坏 | 归档遗留 | ✅ 修 | 5 个测试文件 pytest.importorskip |
| BUG-19 callers_mixin 残留 import | P2 | ✅ 修 | agent/callers_mixin.py 删除 + agent_loop.py 加注释 |
| BUG-20 raw_session_logs 增长 | P2 | ✅ 修 | agent/execution_pipeline.py `_raw_log_enabled()` 默认 OFF |
| BUG-21 learned 畸形 key | P2 | ✅ 修 | wm_voe_learning.py `normalize_pair`（拆分整串） |
| BUG-22 key shape 91.7% miss | P1 | ✅ 修 | wm_voe_learning.py `normalize_pair` + BUG-02 单工具协议 |
| BUG-23 归档 README 缺失 | P2 | ✅ 修 | 本文件 |

## 清理路径 / 重启序列（BUG-09/23 操作层）

env 开关变更**必须配进程重启才生效**（env 是进程启动快照）：
1. `~/.mimiraether/.env` 已设 `MIMIR_WM_PREDICTOR=0` / `MIMIR_WM_VOE_LEARNING=0` / `MIMIR_WM_VOE_RECALL=0` / `MIMIR_WM_VOE_REPLAN_CTX=0`
2. 重启 Gateway 后，残留目录应停止更新：
   - `~/.mimiraether/data/wm_phase0/surprise_events.jsonl`（mtime 应冻结）
   - `~/.mimiraether/data/wm_phase11/learned_surprises.json`
   - `~/.mimiraether/data/raw_session_logs.jsonl`（BUG-20 已默认停写）
3. 验证命令：
   ```bash
   stat -c '%y' ~/.mimiraether/data/wm_phase0/surprise_events.jsonl   # mtime 不再变化
   stat -c '%s' ~/.mimiraether/data/raw_session_logs.jsonl            # 大小不再增长
   ```

## 复活 VoE 的检查清单（未来）

1. env 开关置 1（4 个）+ 重启
2. `_INTENT_SKILLS` 工具名需与当前工具注册表对齐（tools/ 为准）
3. 消费方必须先接入（WM消费方定义.md：KPI 审计 / degeneration_guard）
4. 先跑 `scripts/wm-kpi-verify.sh` 用归档数据建立基线

---
*归档 + 18bug 手术：Mimir · 2026-08-03 · 刘哥拍板 · Hermes 监督*

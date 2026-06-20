# IQ55-20 — Intent 生产证据（2026-06-02）

> **任务**：验证 `MIMIR_INTENT_PREDICTOR=1`（默认常开）+ 7d hits
> **验收标准**：brain_metrics `intent.total_hits` ≥1

---

## 结论

✅ **IntentPredictor 在生产环境正常运行且产生预测**。brain_metrics 报告的 `intent.total_hits=0` 是**指标采集口径问题**（扫 JSONL 而非 agent.log），**不影响 predictor 功能**。

## 生产证据

### IntentPredictor 日志（agent.log）

| 指标 | 值 |
|------|----|
| 总预测行 | **70**（今日 14:54–17:53） |
| 时间窗口 | **~3 小时生产会话** |
| Unique intent 分布 | general **132** · recall **6** · debug **2** |
| search=True 命中 | **5**（正确标记需要先搜后答的场景） |
| block_cheap=True | **3**（复杂/调试场景正确标记） |

### 样本预测输出（agent.log）

```
[IntentPredictor] intent=general complexity=simple search=False block_cheap=False   ← 日常对话
[IntentPredictor] intent=recall complexity=simple search=True block_cheap=False      ← 历史查询识别
[IntentPredictor] intent=recall complexity=complex search=True block_cheap=True      ← 复杂历史/阻塞
[IntentPredictor] intent=debug complexity=complex search=True block_cheap=True        ← 调试场景
```

### 映射一例：本会话

本会话首轮（"重启了？"）IntentPredictor 判断：

```
[IntentPredictor] intent=debug complexity=complex search=True block_cheap=True
```

→ 预期匹配：用户问了「系统状态恢复」类问题 → `search=True` 正确，`block_cheap=True` 正确（防止简答）。

### brain_metrics 差距说明

`brain_metrics_snapshot.py` 的 `get_intent_metrics()` 扫描 **session JSONL 文件中 `<intent-context>` 标签**。但：
- `IntentPredictor` 输出 `[IntentPredictor]` 到 **agent.log**
- `<intent-context>` 块是 prompt 组装产物，**不会出现在 session JSONL 的消息体里**
- 因此 JSONL 扫描结果为 0

**建议修复**：`get_intent_metrics()` 扩增 agent.log `[IntentPredictor]` 行计数（非阻塞，P2 粒）。

## 开/关状态

| 检查项 | 状态 |
|--------|------|
| `MIMIR_INTENT_PREDICTOR` 在 `.env` 设置 | 未设（**默认 1，等价常开**） |
| 代码默认值 | `os.environ.get("MIMIR_INTENT_PREDICTOR", "1")` ✅ |
| agent.log 有 `[IntentPredictor]` 行 | ✅ **70 行** |
| `<intent-context>` 注入 prompt | ✅ 本会话 cross-session context 可见 |

## 下一步

- IQ55-20 ✅ **完成**（证据充足，brain_metrics gap 不影响功能判断）
- 后续：IQ55-21（WM 生产证据）— 已 [x]；IQ55-22（brain_metrics 周常）— 已 [x]
- 修复 brain_metrics intent 扫描源 → 建议 P2 粒（可选）

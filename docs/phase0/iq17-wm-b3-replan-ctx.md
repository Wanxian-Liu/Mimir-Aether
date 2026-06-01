# IQ-30: WM B3 REPLAN_CTX 启用登记

> 日期：2026-06-01 · 参考：[wm-production-enablement.md](../proposals/wm-production-enablement.md) 步骤 3

## 状态：⏳ 待刘哥 shell 执行

| 项 | 值 |
|----|-----|
| `.env` 变量 | `MIMIR_WM_VOE_REPLAN_CTX=1`（需刘哥手动添加） |
| 依赖 | B1 `MIMIR_WM_VOE_LEARNING=1` ✅ 已开（IQ-11） |
| 观察窗 | IQ-22 已检查 WM 日志，无异常 ✅ |

## 行为

surprise 时 `report.details["wm_learning_context"]` = 学习事件摘要。replan 函数可读此字段带额外上下文重规划。

## 刘哥执行（本机 shell）

```bash
# 1. 检查是否已存在
grep MIMIR_WM_VOE_REPLAN_CTX ~/.mimiraether/.env

# 2. 添加（若不存在）
echo 'MIMIR_WM_VOE_REPLAN_CTX=1' >> ~/.mimiraether/.env

# 3. 重启 gateway（非飞书内）
cd ~/src/MimirAether && bash scripts/ensure_single_gateway.sh
```

## 验证命令

```bash
# 确认 env 已写入
grep MIMIR_WM_VOE_REPLAN_CTX ~/.mimiraether/.env

# 确认 gateway 新 PID
curl -s http://127.0.0.1:18999/health | grep -o '"pid":[0-9]*'
```

## 风险

- 中风险：replan 上下文可能让 prompt 变长、引入噪声
- 回滚：`sed -i '/MIMIR_WM_VOE_REPLAN_CTX/d' ~/.mimiraether/.env` + 重启 gateway

## 验证（触发后）

触发 surprise 后，replan 调用 log 含 `wm_learning_context` 字段：

```bash
grep wm_learning_context ~/.mimiraether/logs/agent.log | tail -3
```

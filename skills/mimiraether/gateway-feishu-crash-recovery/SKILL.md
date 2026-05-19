---
name: gateway-feishu-crash-recovery
description: Gateway崩溃重启后飞书WebSocket僵死诊断与修复。症状：消息可收到但全部处理失败。根因：WebSocket event loop卡死在closed状态未正确恢复。修复：二次重启Gateway。
version: 1.0.0
auto_load: false
---

# Gateway 飞书崩溃恢复

## 触发条件

- Gateway 进程崩溃或非正常退出后自动/手动重启
- 飞书消息能收到（有消息类型到达），但全部处理失败
- `send_message` 或飞书相关操作报错「connection closed」「event loop」等

## 故障模式

**根因**：Gateway 崩溃重启后，飞书 WebSocket 长连接的 event loop 未正确重新初始化——卡死在 `closed` 状态。Gateway 进程存活、消息可达，但全部处理失败。

**症状链**：
1. Gateway 在某个时间点崩溃
2. 自动/手动重启 Gateway
3. 表面正常（`platform(s): api_server + feishu` 显示在线）
4. 但飞书消息全部处理失败（WebSocket event loop 已死）
5. 消息类型可达（飞书仍推送），但处理链路断裂

## 诊断步骤

1. 检查 Gateway 进程状态和启动时间：
   ```bash
   ps aux | grep gateway
   ```
2. 查看 Gateway 日志中的飞书相关错误：
   ```bash
   grep -i "feishu\|websocket\|event loop\|closed" <gateway_log>
   ```
3. 如果看到大量「closed」「connection」错误但消息仍在到达 → **确认 WebSocket 僵死**

## 修复：二次重启 + 用户验证（强制）

**关键**：崩溃后的第一次重启不可靠。必须做第二次重启。
**用户规则（2026-05-19）**：重启后必须向用户发送验证消息，确认消息处理正常——不能只凭进程状态判断。

```bash
# 1. 杀掉当前Gateway
kill <gateway_pid>

# 2. 确认已退出
ps aux | grep gateway

# 3. 重启Gateway（使用正常启动命令）
./run_gateway.sh  # 或对应的启动命令

# 4. ★ 强制：send_message 到飞书向用户验证
#    消息内容：「Gateway 已重启，验证消息——请确认你收到了这条消息」
#    用户确认收到 + 消息处理正常 → 才算恢复成功
#    用户未确认或消息发送失败 → 继续诊断，可能需要三次重启
```

## 验证

- [ ] Gateway 显示 `2 platform(s): api_server + feishu`
- [ ] ★ **向用户发送验证消息 → 用户确认收到**（只用 send_message，不等用户被动发现）
- [ ] Gateway 日志无 WebSocket closed 错误
- [ ] 进程 PID 为二次重启后的新 PID

## 反模式

- **只重启一次就认为已恢复**：崩溃后首次重启的 WebSocket 状态不可信，必须二次确认
- **只看 platform 列表**：`feishu` 在列表中不代表 event loop 健康
- **只看消息到达**：消息类型可达 ≠ 消息处理成功

## 此技能来自

2026-05-13 Gateway 在 19:55 崩溃重启后飞书 WebSocket event loop 僵死，消息全部处理失败。PID 680912 二次重启后恢复。

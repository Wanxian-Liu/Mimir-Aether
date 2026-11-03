---
name: gateway-feishu-crash-recovery
description: 飞书链路故障恢复两模式。A=WS僵死（崩溃重启后消息可达但全部处理失败→必须二次重启）；B=链路层DNS断（NameResolutionError/Temporary failure in name resolution，进程未重启、NRestarts=0→等链路恢复，切勿重启）。分不清时先跑判别命令分型。
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

## 故障模式 B：链路层 DNS 断（≠ WS 僵死，**不要急着重启**）

**症状差异**：进程存活、`NRestarts=0`、启动时间未变，但日志刷
`[Lark] ERROR connect failed ... NameResolutionError(... Failed to resolve 'open.feishu.cn' ([Errno -3] Temporary failure in name resolution))`
且 `feishu_adapter: [Feishu] Token refresh failed: Cannot connect to host open.feishu.cn:443`。

**判别（三条一分钟查完）**

```bash
# 1) 是不是我方的锅：进程有没有重启过（有重连循环就不需要重启）
systemctl --user show mimiraether.service -p MainPID -p NRestarts -p ExecMainStartTimestamp
# 2) 失败事件的真实规模（Lark 每条打两遍：行数 ÷ 2；口径必须标“去重”）
journalctl --user -u mimiraether --since today --no-pager | grep -c 'Temporary failure in name resolution'
journalctl --user -u mimiraether --since today --no-pager | grep 'Temporary failure in name resolution' | awk '{print $3}' | sort -u | wc -l
# 3) 链路层证据（真因通常在这里，不在飞书）
journalctl --since today --no-pager | grep -iE 'wlp1s0|systemd-resolved|CONNECTED_GLOBAL|wpa_supplicant' | tail -20
```

**2026-11-01 实测样本**：15:16:23 → 17:49:39，按秒去重 **113** 次解析失败（原始日志 **217** 行）；
`17:45:00 wlp1s0: Trying to authenticate (SSID='RAY1_5G')` → `17:51:03 systemd-resolved: Bus client set DNS server list to: 223.5.5.5, 223.6.6.6` →
`17:51:10 [Lark] connected to wss://msg-frontier.feishu.cn/ws/v2`（第 **103** 次重连才成）→ `17:52:31 NetworkManager state is now CONNECTED_GLOBAL`。
⇒ WiFi 关联丢失 ⇒ 系统无 DNS ⇒ 全部解析失败。**SDK 重连循环自愈，重启 gateway 不解决任何事**（反而丢上下文）。

**这一模式的真缺陷不是「坏了」而是「坏了 2h33m 没人知道」**：断连窗口内所有 cron 照跑、零告警。
修法方向：把 `connected / reconnect 次数` 打点到已有的 `mimir-slo-dashboard`，断连 >5min 告警（SLI = Feishu WS 连接态）。
另：断连窗口内的对端消息**不会补投**（恢复后要对方重发）——需要的话得在重连后调 `im/v1/messages` 回捞。

**分不清时先跑 3 条判别命令**：`NRestarts>0` 或「消息到但处理全失败」→ 模式 A（WS 僵死，二次重启）；
`NameResolutionError / Temporary failure in name resolution` → 模式 B（DNS/链路，**等链路恢复，别重启**）。

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

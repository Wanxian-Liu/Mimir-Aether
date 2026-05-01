# Gateway连接超时/断开问题分析

## 问题描述

MimirAether在运行subagent任务时，Gateway在约1分钟后断开连接：
- 错误码：`1006 abnormal closure (no close frame)`
- 发生时间：subagent启动后约1分9秒
- 影响：任务无法完成提交，进度丢失

## 根因分析

### 1. 问题定位

从日志分析，关键错误点：
```
[warn] Subagent announce give up (retry-limit) run=... retries=3 endedAgo=40s
```

**核心问题**：subagent在完成任务后，试图通过`announce`机制将结果返回给主session，但Gateway连接已断开。

### 2. 根本原因

OpenClaw的subagent系统存在以下问题：

1. **WebSocket连接保活机制缺失**
   - Gateway默认的WebSocket ping/pong间隔可能太短
   - 长时间无数据传输时，Gateway认为连接已死

2. **Subagent Session生命周期问题**
   - subagent运行在自己的session中
   - 该session的worker TTL（默认60分钟）不是问题
   - 问题在于session之间的announcement通道

3. **sessions_spawn已知问题**
   - Foundry记录显示：`sessions_spawn:gateway timeout after Nms` 已出现10次
   - `sessions_spawn:Tool sessions_spawn not found` 已出现5次

### 3. 架构层面的问题

```
Main Session (负责人对话)
    │
    │ sessions_spawn()
    ▼
Subagent Session (独立运行)
    │
    │ ⚠️ announce() 失败
    ▼
Gateway (已断开连接?)
```

## 解决方案

### 方案A：增加ACP Runtime TTL（推荐）

在配置中添加：
```json
"acp": {
  "runtime": {
    "ttlMinutes": 120
  }
}
```

**作用**：延长ACP session worker的生存时间，避免过早清理。

### 方案B：减少Subagent任务超时

在配置中降低`runTimeoutSeconds`：
```json
"agents": {
  "defaults": {
    "subagents": {
      "maxConcurrent": 8,
      "runTimeoutSeconds": 180
    }
  }
}
```

**作用**：让subagent在Gateway断开前完成任务。

### 方案C：MimirAether端实现断点续传

在MimirAether中实现进度保存机制：
1. 定期保存任务进度到文件
2. 任务开始时检查是否有未完成的任务
3. 异常恢复后继续执行

**优点**：最可靠的解决方案
**缺点**：需要较大的代码改动

### 方案D：修改subagent为非阻塞模式

不使用`announce`机制，改用结果轮询：
1. subagent将结果写入共享文件
2. 主session轮询检查结果文件
3. 避免announcement通道失败

## 推荐方案

**短期**：方案A + 方案B（配置调整，立即生效）

**长期**：方案C（代码实现断点续传）

## 实施计划

1. 修改`~/.openclaw/openclaw.json`，增加ACP runtime TTL
2. 验证Gateway重启后问题是否改善
3. 如仍有问题，实现方案C的断点续传机制

## 相关日志

```
[warn] Subagent announce give up (retry-limit) run=bacbb354... retries=3 endedAgo=40s
```

这个警告说明：
- subagent尝试announce 3次
- 每次间隔约13秒
- 总计约40秒后放弃
- Gateway在此期间关闭了连接

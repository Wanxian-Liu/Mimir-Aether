---
name: mimiraether-recovery-patterns
description: Tool-level error recovery patterns — when file/process/network operations fail, apply standard recovery before escalation
auto_load:
  triggers:
    - tool_returned_error
    - permission_denied
    - file_read_only
    - file_not_found_recovery
    - locked_file
    - parse_error
version: 1.0.0
---

# MimirAether Recovery Patterns — 工具级错误恢复

**核心理念**: 不崩溃、不放弃、不死循环。每个可恢复错误都有标准恢复路径。

---

## 触发条件

工具返回以下信号时自动加载并执行对应模式：

| 信号 | 触发 |
|------|------|
| `Permission denied` / `EACCES` / `Read-only` | 🔴 权限恢复 |
| `File exists` / `Directory not empty` / locked | 🟡 冲突恢复 |
| `Invalid JSON` / `parse error` / `corrupted` | 🟡 损坏恢复 |
| `No such file` / `not found` in write context | 🟡 缺失恢复 |
| `Connection refused` / `timeout` / `broken pipe` | 🟡 网络恢复（已有 backoff） |

---

## 恢复模式

### 模式 1: 权限恢复 (READ_ONLY)

**场景**: 文件存在但不可写（chmod 444）

```
检测: "Permission denied" + write_file / patch 操作
恢复:
  1. chmod u+w <file>          ← 加写权限
  2. 重试原操作
  3. 成功 → 可选恢复 chmod 444（保持原样）
  4. 失败 → 检查父目录权限
  5. 仍失败 → 报告用户
```

**禁止**: 直接 `sudo` / `chmod 777`（安全隐患）

### 模式 2: 文件锁定 (FILE_BUSY)

**场景**: 文件被其他进程持有

```
检测: "Text file busy" / "Device or resource busy" / "lock"
恢复:
  1. sleep 2 → 重试 (最多3次，指数退避)
  2. 仍失败 → fuser <file> 找持锁进程
  3. 非关键进程 → 询问用户是否 kill
  4. 关键进程 → 报告用户，等待
```

### 模式 3: 损坏恢复 (CORRUPTED)

**场景**: JSON/YAML/配置文件语法错误

```
检测: json.loads 抛出 / YAML parse error
恢复:
  1. 尝试宽松解析 (json.loads strict=False)
  2. 尝试自动修复（引号/逗号/trailing comma）
  3. 尝试解析为备选格式（YAML/TOML/INI fallback）
  4. 全部失败 → 备份原文件为 .bak，创建默认值
```

### 模式 4: 缺失恢复 (MISSING)

**场景**: 目标路径不存在（但操作是写入/创建）

```
检测: "No such file or directory" + write_file/patch
恢复:
  1. 检查父目录存在 → 不存在则 mkdir -p
  2. 重试原操作
  3. 仍失败 → 检查磁盘空间 df -h
  4. 磁盘满 → 报告用户
```

---

## 执行协议

```
工具调用失败
    │
    ├─→ 匹配恢复模式
    │
    ├─→ 执行恢复步骤 (最多3次)
    │     │
    │     ├─→ 成功 → 继续任务
    │     └─→ 失败 (第3次) → 升级
    │
    └─→ 升级路径:
          ├─→ degeneration-guard: SURPRISE 信号
          ├─→ evaluator-optimizer: 记录 recovery_attempted
          └─→ 用户可见报告: "⚠️ 恢复失败: [错误] → [尝试的步骤]"
```

---

## 恢复安全规则

| 规则 | 说明 |
|------|------|
| **不静默覆盖** | chmod 后恢复原权限，用 git diff 确认无意外改动 |
| **上限3次** | 同一操作同一错误最多恢复3次 → 升级 |
| **有迹可查** | 每次恢复尝试写入日志 |
| **不猜权限** | chmod u+w 而非 chmod 777（最小权限原则） |
| **做备份** | 损坏恢复前 cp → .bak |

---

## 与退化检测的协作

```
恢复模式触发 → degeneration-guard 记录
  ├─→ 同一任务 ≥3 次恢复 → ⚠️ RECOVERY_LOOP (不同错误，系统性问题)
  └─→ 同一错误 ≥3 次恢复 → 🔴 SURPRISE (恢复模式不匹配)
```

---

## 验证方法

```
测试场景:
  echo '{"key": "value"' > broken.json    # 故意损坏
  chmod 444 locked.txt && echo "data" > locked.txt  # 只读写入

期望行为:
  1. write_file locked.txt → 检测 EACCES → chmod u+w → 写入 → (可选恢复 chmod 444)
  2. read_file broken.json → 检测损坏 → strict=False 解析 → 成功
```

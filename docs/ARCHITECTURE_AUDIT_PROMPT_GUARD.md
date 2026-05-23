# prompt_builder 安全代码提取审计

**日期**：2026-05-21  
**来源**：EV-A05（琬弦架构方案方向一 — Agent Core 职责重划）

> **Prompt 安全真源（2026-05-24）** → [`docs/phase0/prompt-builder-security-audit.md`](./phase0/prompt-builder-security-audit.md)。下文为历史快照。

## 安全逻辑位置

| 函数 | 行号 | 职责 | 注入模式 |
|------|------|------|---------|
| `scan_context_content()` | L57-79 | 上下文文件注入检测 | 不可见 Unicode + 威胁正则 |
| `truncate_content()` | L401-412 | 上下文文件截断 | 长度限制（`CONTEXT_FILE_MAX_CHARS`） |
| `strip_yaml_frontmatter()` | L414-422 | 移除 YAML frontmatter | 分隔符 `---` 解析 |
| `load_context_file()` | L433-472 | 加载上下文文件的完整流程 | 穿透 `scan` → `truncate` → `strip` |
| `_auto_load_inject_chunk()` | L960-984 | 自动注入 `<auto-loaded-skills>` 块 | 技能注入防护 |

## 注入模式清单

| 模式 | 检测方式 | 覆盖 |
|------|---------|:--:|
| 不可见 Unicode 字符 | `_CONTEXT_INVISIBLE_CHARS` 集合 | ✅ |
| System prompt 覆盖 | 正则 `_CONTEXT_THREAT_PATTERNS` | ✅ |
| Markdown 指令注入 | 正则匹配 `ignore previous` / `system:` / `assistant:` 等 | ✅ |
| 技能注入绕过 | `_auto_load_inject_chunk()` 的 frontmatter 格式守卫 | ✅ |
| 路径遍历 | `load_context_file()` 的文件存在性检查 | ⚠️ 无显式路径沙箱 |

## 可拆粒度分析

| 函数 | 可独立提取？ | 拆出模块 | 影响 |
|------|:--:|------|------|
| `scan_context_content()` | ✅ | `agent/guard/prompt_scan.py` | 低 — 纯函数，无类依赖 |
| `truncate_content()` | ✅ | 同上 | 低 — 纯函数 |
| `strip_yaml_frontmatter()` | ✅ | `agent/guard/yaml_util.py` | 低 |
| `load_context_file()` | ⚠️ | 需保留在 prompt_builder.py | 中 — 调用链 `scan→truncate→strip` |
| `_auto_load_inject_chunk()` | ⚠️ | 同上 | 低 |
| `_CONTEXT_THREAT_PATTERNS` | ✅ | `agent/guard/threat_db.py` | 低 — 纯数据 |

## 拆分影响面

| 拆分方案 | 涉及文件 | 风险 |
|---------|---------|:--:|
| 提取 3 个安全函数 → `agent/guard/` | prompt_builder.py + 新 2 文件 | 🟢 低（纯函数，无副作用） |
| 提取威胁模式数据 → `agent/guard/` | prompt_builder.py + 新 1 文件 | 🟢 低（纯数据） |
| 保留 `load_context_file()` 在原地 | 无变更 | — |

## 建议

**这是方向一最安全的拆分起点**：`scan_context_content` 是纯函数（输入文本 → 输出清理后文本），无类依赖、无副作用、从 prompt_builder.py 提取不会影响任何调用方。建议方向一的第一刀从这里下手。

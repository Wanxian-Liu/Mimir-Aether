# EV-A05 — prompt_builder 安全审计（2026-05-24）

> `agent/prompt_builder.py` **1569** 行。交叉：[agent-core-responsibility-map.md](./agent-core-responsibility-map.md)（guard 未独立）、[intent-predictor-audit](./intent-predictor-audit.md)（`intent_action_guard` 互补）。

## 摘要

- 安全逻辑**内嵌** prompt_builder：**10** 条 `_CONTEXT_THREAT_PATTERNS` + 不可见 Unicode 集。
- **双实现**：`scan_context_content`（L57）与 `_scan_context_content`（L1202）逻辑重复（Hermès 兼容）。
- **独立 guard 无**；`subdirectory_hints.py` 直接 import `_scan_context_content`。
- 运行时「光说不做」由 `**intent_action_guard`**（`agent_loop`）负责，非本文件。

## 安全函数 / 数据


| 符号                                       | 行         | 职责                             |
| ---------------------------------------- | --------- | ------------------------------ |
| `_CONTEXT_THREAT_PATTERNS`               | 38–48     | 注入/窃密正则                        |
| `scan_context_content`                   | 57–79     | 上下文文件扫描 → BLOCKED 或原文          |
| `truncate_content` / `_truncate_content` | 408, 1248 | `CONTEXT_FILE_MAX_CHARS=20000` |
| `load_context_file`                      | 440+      | scan→truncate→strip 链          |
| `_auto_load_inject_chunk`                | 967+      | auto-load skills 块（2000 字截断）   |


## 模式覆盖


| 类                            | 覆盖                                         |
| ---------------------------- | ------------------------------------------ |
| 不可见 Unicode                  | ✅                                          |
| ignore/disregard system 指令   | ✅                                          |
| HTML 隐藏 / exfil curl / 读密钥文件 | ✅                                          |
| 路径遍历沙箱                       | ⚠️ 存在性检查为主                                 |
| 工具层 deferral                 | ➡️ `intent_action_guard`（非 prompt_builder） |


## 可拆粒度


| 提取目标                                          | 风险  | 说明             |
| --------------------------------------------- | --- | -------------- |
| `scan_*` + 威胁表 → `agent/guard/prompt_scan.py` | 🟢  | 纯函数；需合并双份实现    |
| `load_context_file` 留原处                       | —   | 编排仍属 prompt 构建 |
| 与 `tool_guard`                                | —   | 工具风险标注，非重复     |


## vs 2026-05-21 / Phase 1

行号漂移小；**第一刀**仍为抽 `scan_context_content`（合并 L57/L1202）；同步改 `subdirectory_hints` import。EV-A01 **P1 prompt_guard** 仍成立；勿与 intent-action guard 合并。
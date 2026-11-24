---
name: mimiraether-world-model-paper-analysis
description: 初代世界模型论文研读与改进方案撰写流程 — 非像素、CPU可跑方向
auto_load: false
---

# 世界模型论文研读 → 改进方案技能

## 触发条件

刘哥发来论文/论文链接/论文编号，要求「读→理解→给启发→写方案」。

或用户说「世界模型」「world model」「改进方案」「初代WM」等关键词时，结合当前会话上下文判断是否触发。

## 前置检查

1. **读方向文档**：`docs/MIMIR_IQ_EVOLUTION_DIRECTION.md` §0～§4（确认方向一致性）
2. **读现有方案**：`docs/proposals/world-model-evolution-plan.md`（已有方案，新论文追加而非重写）
3. **读现有文件**：`~/.mimiraether/research/world-models-reading-list.md`（已有阅读笔记）
4. **读 bridge**：`docs/MIMIR_LIU_CURSOR_BRIDGE.md`（看进度签收记录）

## 流程

### Step 1: 获取论文内容

- 如果是 arXiv ID → `web_extract(arxiv.org/abs/XXXX.XXXXX)` 获取摘要
- 如果是 PDF 链接 → `web_extract(pdf_url)` 直接提取全文 markdown
- 如果是论文名 → 先 `web_search` 找到链接再提取

### Step 2: 分析论文

对每篇论文提取以下信息：

| 维度 | 提取内容 |
|------|---------|
| 核心贡献 | 一句话说清这篇论文做了什么 |
| 关键§节 | 哪几节对你方向直接有用（标注§号） |
| 概念映射 | 论文概念 → 你现有代码/架构的对应关系 |
| 可做改进 | 基于这篇论文，你的系统能升级什么 |
| 代价评估 | 实现难度（低/中/高）+ 是否需要GPU |

### Step 3: 对比已有方案

打开 `docs/proposals/world-model-evolution-plan.md`，看：

- 新论文的概念是否已被覆盖
- 新论文的改进与现有方案是竞争还是互补
- 是否需要在方案中追加新章节（新Phase/新改进）

### Step 4: 更新方案文档

追加到 `docs/proposals/world-model-evolution-plan.md`：

1. 在「论文索引表」加一行
2. 追加新§章节（编号接续现有）
3. 每个改进点标注：`**灵感来源**：P{N} §X.X`
4. 更新「实施路线图」的 Phase 表（如有必要）

### Step 5: 签收 bridge

在 `docs/MIMIR_LIU_CURSOR_BRIDGE.md` §4 追加签收行：

```
|| YYYY-MM-DD | **本轮ID** | **Mimir** | 研读 P{N} 论文名 → 启发/改进N条 → 方案文档位置 |
```

### Step 6: 回报刘哥

飞书回复包含：

1. ✅ 已读论文：论文名 + arXiv
2. ✅ 核心启发：2-3句人话总结
3. ✅ 方案更新：追加了几个改进点
4. ✅ bridge §4 已签收

**格式**：先说结论，再给数据。不要甩模板当回复。

## 陷阱

- ❌ 不要只检索已有记忆——新论文需要实际 `web_extract` 读原文
- ❌ 不要把论文索引表写成孤立清单——每个引用必须标注「对你系统有什么用」
- ❌ 不要一次读太多——刘哥方向是非像素CPU，远离像素级/大规模GPU论文
- ❌ 不要只说话不发工具——每条响应至少带一个工具调用

## 论文索引格式模板

```
| # | 论文 | arXiv | 发表 | 对应方案§ | 关键词 |
|---|------|-------|------|----------|--------|
| P5 | 论文名 | XXXX.XXXXX | YYYY.MM | §X | 关键词 |
```

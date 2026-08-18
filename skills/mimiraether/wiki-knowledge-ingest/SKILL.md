---
name: wiki-knowledge-ingest
description: 将论文/开源项目/知识源摄入四方共享 LLM Wiki 的三层流水线（Layer1 raw 原始文件 → Layer2 concepts 概念卡 → Layer3 index/log 索引），含验证与 git commit 闭环。触发词：论文入库/克隆论文/建论文库/项目快照入库/raw/papers/raw/hardware/知识储备。
version: 1.0.0
auto_load: true
priority: medium
---

# Wiki 知识源入库流水线（2026-08-15 三次实战固化：Graph RAG / DeepMind / AERIS-10）

## 何时用
用户要求"把 X 论文/项目克隆到本地/入库/做知识储备"时。目标目录是四方共享 wiki：`/home/rayliu/wiki`（**必须用绝对路径**——沙盒 HOME=/home/rayliu/.mimiraether，`~/wiki` 会解析到空壳目录）。

## 三层结构（对齐 LLM Wiki 架构）
| 层 | 位置 | 内容 |
|----|------|------|
| Layer1 原始层 | `~/wiki/raw/papers/<topic>/`（论文）或 `~/wiki/raw/hardware/<name>/`（项目） | PDF / 源码快照，**不提交进 git 的二进制大头用 .gitignore 或单独管理**（见坑点5） |
| Layer2 提炼层 | `~/wiki/concepts/<name>.md` | 概念卡：标准 frontmatter + 要点 + 溯源 + 四方共读标注（若适用） |
| Layer3 索引 | `~/wiki/index.md` + `~/wiki/log.md` | index 加条目、log 记 ingest |

## 执行步骤
1. **选层定位**：论文→`raw/papers/`，GitHub 项目→`raw/hardware/`（若用户是视频/链接指来的项目，先检索 GitHub 确认最高星真身）
2. **下载/快照**：
   - 论文：arXiv 直链 `https://arxiv.org/pdf/<id>` 下载 PDF
   - 项目：**优先 GitHub tarball**（`https://github.com/<owner>/<repo>/archive/refs/heads/main.tar.gz`）而非 git clone——clone 会超时 + 嵌套 git 仓库污染 wiki 单仓
3. **验证原始层**：`%PDF` 魔数（`xxd -l 4` 或 Python `open(f,'rb').read(4)==b'%PDF'`）+ `ls -la` 大小；项目快照记录上游 SHA（git ls-remote 或下载前查）
4. **写概念卡**：标准 frontmatter（title/created/type/tags/sources/relations/properties），含热度证据表、核心要点、与我们系统的关联、入库快照信息（路径/版本/日期）
5. **更新索引**：`index.md` 加条目 + `log.md` 记 ingest 行
6. **git commit**：wiki 侧 commit（`cd /home/rayliu/wiki && git add ... && git commit`）
7. **（可选）四方共读卡**：若刘哥要求四方共读，开 discussion 卡标记 `status: pending`——**等刘哥主动提起再执行，不主动启动**；刘哥偏好"共读不分工"（每篇大家都要读，非各读一篇）

## 坑点（全部实战踩过）
1. **沙盒 HOME 陷阱**：`~/wiki` 解析到 `/home/rayliu/.mimiraether/wiki`（空壳）——一律用绝对路径 `/home/rayliu/wiki/`
2. **tarball 而非 clone**：git clone 180s 超时 + 嵌套 .git 破坏 wiki 单仓历史——用 tarball 解压（断点续传用 curl -C -）
3. **热度的证据链**：报告"最高星/前三"必须有 API 检索合并验证（多关键词 GitHub search + 星数对比 + "名字带 radar 的软件 ≠ 雷达硬件"这类排除逻辑），不拍脑袋
4. **frontmatter 标准**：参考已有卡（如 concepts/actmem-arxiv-paper.md：title/created/type/tags/sources/relations/properties 含 code_github/paper_date/source_lab）
5. **大文件 git 策略**：218MB 快照入库后 commit 会很大（3.1M insertions）——确认 wiki 仓库可承受；若体积过大考虑只入库概念卡 + 记录外部引用
6. **论文编号核实**：HippoRAG2 曾出现 2502.14802 vs 2502.14739 不一致——下载时用 arXiv 页面确认真实编号，概念卡与文件名保持一致
7. **落盘纪律**：每层写完后 grep/stat 验证（字节>0 + 关键字段命中）再报告；"下载完成"= 文件在盘 + 魔数验证，不是 curl 输出

## 验证清单
- [ ] Layer1 文件存在 + 魔数/大小验证
- [ ] Layer2 概念卡 grep frontmatter 关键字段命中
- [ ] Layer3 index/log 条目 grep 命中
- [ ] git commit 存在（git log --oneline | head -1 可见）
- [ ] （若共读卡）discussion 卡 status=pending + commit 记录

## 实战案例
- Graph RAG（2026-08-09）：7 篇 PDF → raw/papers/graph-rag/ + concepts/graph-rag.md
- DeepMind（2026-08-15）：2 篇 PDF → raw/papers/deepmind-2026/ + 2 张概念卡 + 共读卡 pending
- AERIS-10（2026-08-15）：tarball 快照 218MB → raw/hardware/aeris10/ + concepts/aeris10-开源相控阵雷达.md

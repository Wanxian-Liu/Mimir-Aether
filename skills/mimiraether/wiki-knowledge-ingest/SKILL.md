---
name: wiki-knowledge-ingest
description: 将论文/开源项目/知识源摄入四方共享 LLM Wiki 的三层流水线（Layer1 raw 原始文件 → Layer2 concepts 概念卡 → Layer3 index/log 索引），含验证与 git commit 闭环。触发词：论文入库/克隆论文/建论文库/项目快照入库/raw/papers/raw/hardware/知识储备。
version: 1.0.0
auto_load: true
priority: medium
---

# Wiki 知识源入库流水线（2026-08-15 三次实战固化：Graph RAG / DeepMind / AERIS-10）

## 何时用
用户要求"把 X 论文/项目克隆到本地/入库/做知识储备"时。目标目录是四方共享 wiki：`~/wiki`（**必须用绝对路径**——沙盒 HOME=~/.mimiraether，`~/wiki` 会解析到空壳目录）。

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
6. **git commit**：wiki 侧 commit（`cd ~/wiki && git add ... && git commit`）
7. **（可选）四方共读卡**：若刘哥要求四方共读，开 discussion 卡标记 `status: pending`——**等刘哥主动提起再执行，不主动启动**；刘哥偏好"共读不分工"（每篇大家都要读，非各读一篇）

## 坑点（全部实战踩过）
0. **批量论文入库（10+ 篇）用 arXiv API 检索 + 后台下载**（2026-09-11 Contextual Retrieval 28 篇实战）：
   - 检索：`export.arxiv.org/api/query`，**带引号的短语查询必须全 URL 编码**（`urllib.parse.quote(q, safe='')`）——保留 `"` 会让 arXiv 返回空响应（`no element found`），首轮 16 查询 12 条因此失败；查询间隔 ≥3s。
   - 下载：**PDF 批量下载不能用 `execute_code`**（300s 硬上限，4-5 份即超时）→ 写脚本后 `terminal(background=True)` + `nohup python3 dl.py > dl.log 2>&1 &`，单份 arXiv PDF 约 20-60s，25 份约 12 分钟。
   - 每份下完即 `open(f,'rb').read(4)==b'%PDF'` 校验 + 记录字节数（放进 `_manifest.json`）。
   - 引用数别依赖 Semantic Scholar 单条接口（大量空/429）→ 用批量 endpoint，或直接读 arXiv 的 `comment` 字段判会议等级（ACL/NeurIPS/ICML/ECIR/S&P）。
1. **沙盒 HOME 陷阱**：`~/wiki` 解析到 `~/.mimiraether/wiki`（空壳）——一律用绝对路径 `~/wiki/`
2. **tarball 而非 clone**：git clone 180s 超时 + 嵌套 .git 破坏 wiki 单仓历史——用 tarball 解压（断点续传用 curl -C -）
3. **热度的证据链**：报告"最高星/前三"必须有 API 检索合并验证（多关键词 GitHub search + 星数对比 + "名字带 radar 的软件 ≠ 雷达硬件"这类排除逻辑），不拍脑袋
4. **frontmatter 标准**：参考已有卡（如 concepts/actmem-arxiv-paper.md：title/created/type/tags/sources/relations/properties 含 code_github/paper_date/source_lab）
5. **大文件 git 策略**：218MB 快照入库后 commit 会很大（3.1M insertions）——确认 wiki 仓库可承受；若体积过大考虑只入库概念卡 + 记录外部引用
6. **论文编号核实**：HippoRAG2 曾出现 2502.14802 vs 2502.14739 不一致——下载时用 arXiv 页面确认真实编号，概念卡与文件名保持一致
7. **落盘纪律**：每层写完后 grep/stat 验证（字节>0 + 关键字段命中）再报告；"下载完成"= 文件在盘 + 魔数验证，不是 curl 输出
8. **PDF 完整性：`%PDF` 魔数不够**（2026-09-11 实战）——27 份 arXiv PDF 中 **11 份实为截断文件却全部通过魔数检查**（首字节永远是 `%PDF`）。正确校验 = `pdfinfo <f> | grep '^Pages:'`（或尾部含 `%%EOF`）；失败用 `curl -sL -C -`（可续传）重下，慢链路用 Python `Range` 分块续传（每块 300-400KB + 独立 timeout）。报告「入库 N 份」前**逐份**校验。
9. **同一派单可能被多会话并行执行**（2026-09-11 同一 Buzz 派单被唤醒三次）——**开工第一动作 = 查盘**：目标目录 / 索引 json / 讨论卡回执 / `inbox-processed.log`。已交付则只做「补 / 合 / 跳过」，禁重复交付（重复回执会污染审计链）。
10. **收敛/删除重复目录前先 `git ls-files <dir>`**——本轮"重复"裸目录里藏着**已入库的 ROADMAP 文件**，`rm -rf` 会误删追踪交付物；用 `mv` 到 /tmp 代替删除（可回滚，且不需审批）。
8. **PDF 不能靠 `read_file` 取正文（2026-09-11 实测）**：`read_file` 直读 `.pdf` 返回的是**原始字节流**（`%PDF-1.7` + FlateDecode 二进制），**不是文本层**；其中可用的只有 `/Title`、`/Author`、`/arXivID` 等**元数据**（xmp/Info 字典，通常在文件尾部 obj 中）。要标题+abstract 走 **arXiv API**（一次可批量）：
   `web_extract("https://export.arxiv.org/api/query?id_list=id1,id2,id3&max_results=10")` → 返回 Atom，含 `<title>`+`<summary>`（abstract）+ 作者+日期。**注意** `https://arxiv.org/abs/<id>` 经 web_extract 常只拿到标题/元表格，**拿不到 abstract**——abs 页不行就换 API。
   正文精读需要 PDF 文本提取工具（本技能当前不覆盖），别把「读过 PDF」写进报告——会被抓。
9. **PDF 双目录命名漂移**：同一批论文曾被下载两次（`raw/papers/<topic>/<id>.pdf` 裸 ID 版 vs `<topic>-arch/<id>-<slug>.pdf` 描述名版）→ 重叠 14 篇。入库前先 `search_files` 查重；报告清单时写清「去重合计」而不是相加。

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

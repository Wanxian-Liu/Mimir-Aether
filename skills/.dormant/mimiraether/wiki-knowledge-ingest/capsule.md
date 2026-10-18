# [DORMANT] wiki-knowledge-ingest

**沉寂时间**: 2026-10-18T05:34:01.072108+00:00
**原始分类**: mimiraether
**描述**: 将论文/开源项目/知识源摄入四方共享 LLM Wiki 的三层流水线（Layer1 raw 原始文件 → Layer2 concepts 概念卡 → Layer3 index/log 索引），含验证与 git commit 闭环。触发词：论文入库/克隆论文/建论文库/项目快照入库/raw/papers/raw/hardware/知识储备。
**触发阈值**: 60天未触碰

---

## 技能要点

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
1. **沙盒 HOME 陷阱**：`~/wiki` 解析到 `~/.m

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("wiki-knowledge-ingest")` 即可自动唤醒。

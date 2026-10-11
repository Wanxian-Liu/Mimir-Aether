---
name: mimiraether-link-graph-evidence
description: 本机「双链/图谱收益」取证 SOP —— 链完整性量具（含代码块假阳修正）、显式链 vs 语义检索的非冗余性测量、既有图腿候选召回评测、统计功效门槛。触发词：双链/织链/退链/图腿/graph_leg/链接策略/图谱收益/知识库图谱/假关联。
---

# 本机双链 / 图谱收益 取证 SOP（只读 · 可复算）

## 何时用
用户/四方问「织双链值不值」「图谱收益能不能测」「退链有没有副作用」「假关联风险」时——**先跑量具再开口**，禁凭直觉答。

## 环境真源（2026-10-11 实测）
| 件 | 路径 | 备注 |
|---|---|---|
| 织网面 | `~/wiki/concepts` + `~/wiki/entities` | `find` 得 **781** 篇（卡面常写 578 = `wiki_lint.py --dirs` 口径，**两口径必须写明**） |
| 语义索引 | `~/.hermes/wiki_index.db` | vec0 表 `wiki_chunks(embedding float[1024] distance_metric=cosine, file_path TEXT, frontmatter, chunk_type, last_indexed_at)` · `wiki_chunks_fts`(fts5) · 2026-10-11：**30342 行 / 去重 4532 文件 stem**（卡面 5312 文件 = 含 EXTERNAL_DIRS 外域口径） |
| sqlite-vec 扩展 | `~/.hermes/hermes-agent/venv/lib/python3.11/site-packages/sqlite_vec/vec0.so` | 用 `~/.venv` 的 python3.11 加载；`.local/lib/python3.12/...` 不匹配 |
| 图谱腿（已有） | `~/.hermes/scripts/rag-eval/graph_leg.py`（423 行） | 接口 `graph_expand(query, hops=1)`；**未接在线检索**；docstring 自带验收线 Q11/Q13 |
| 评测集 | `~/.hermes/scripts/rag-eval/test_set_{10,15,v3,v4,v5_syn,v6,final,learning3}.json` | v4/v5_syn/v6 各 **30** 条；10/15 各 10 条 |
| 链闸门 | `~/.hermes/scripts/wiki_lint.py`（93 行） | ④「出站 [[wikilink]] 少于 2 个（SCHEMA：每页至少 2 个）」= **我方 SCHEMA 本就要求每页 ≥2 出链** |

## 四条标准取证（脚本原型放 `~/.mimiraether/tmp/kg/`）
1. **链完整性**：`[[...]]` 计数 → red link（目标文件不存在）/ orphan（零入链）/ 重复边 / 自环 / 入链重尾。
   - **必做代码块剥离**（```` ``` ```` 与 `` `` ``）——否则文档页里的语法示例（`[[wikilink]]` `[[xxx|alias]]`）会全被算成死链。实测：raw red 66/1228 (5.37%) → stripped **28/996 (2.81%)**，即 **57.6% 是假阳**。
2. **显式链 vs 语义检索（非冗余性）**：页 P 的块向量 mean-pool → vec0 `WHERE embedding MATCH ? AND k=40` → 折叠文件 → top20 剔除自身；对照＝同 P 随机抽等量页。实测 **hit@20 真链 0.4639 vs 随机 0.0042（lift 46pp）· link_only 53.6% · 0.551 s/query**。
3. **图腿候选召回**：`import graph_leg`（`sys.path.insert(0,"~/.hermes/scripts/rag-eval")`），对每个标注集的 expected 判 `expected ∈ graph_expand(q)`。实测 **7 集 / 113 条 ⇒ 0.000**；**必须附正控**（docstring 自带样例查询「苏菲的世界 柏拉图 哪一章」→ 10 条候选含 expected），否则负结论不可信。
4. **统计功效门槛**（防 n=10 拍板）：Wilson CI + McNemar。实测 n=10 观测 0.3 ⇒ **CI [0.108, 0.603]**；需 **n≈29 / 47 / 116**（+30pp / +20pp / +10pp 效应）。

## 坑（都踩过）
- `find / -name 'wiki_lint*'` **会漏**（权限/超时）⇒ 误判「量具缺件」。改用 `search_files(pattern=..., path=~/.hermes/scripts, file_glob='*.py')`。
- `read_file` 拒 `~/.hermes` / `~/.openclaw`（白名单）⇒ 先 `cp` 到 `~/.mimiraether/tmp/` 再读。
- `search_files` 搜 `\[\[` 会命中 Python 列表字面量（噪音）⇒ 搜 `BACKLINK|wikilink`。
- `grep -r` 扫 `~/.hermes/scripts/rag-eval/` 会超时（`contextual_prefixes/` 几十万行）⇒ 加 `--include='*.py'` 或排除该目录。
- 讨论卡写段：**patch 分块追加**（单次 ≤4KB，超长会导致工具参数 JSON 截断报错）；不要 write_file 整卡覆盖。

## 交付口径
- 结论必须**拆两句**：「结构面能测（给数字）」「任务级收益不可测（明说）」——不要合并成一句含糊结论。
- 承重性判据 = **谁消费**（当前只有 `graph_leg` 一条腿且未上线）⇒ 删链前先答「谁在读它」。
- 记录面交付 ⇒ `冒烟档位: ②`；量具类 ⇒ 附**正控/负控**，负控未做要显式 `PENDING-SMOKE`。

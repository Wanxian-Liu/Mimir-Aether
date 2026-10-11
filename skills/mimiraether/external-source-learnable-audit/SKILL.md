---
name: external-source-learnable-audit
description: 读外部真源码找"可学件"并落到我方既有件的取证 SOP —— 直连克隆 / 文件:行号级证据 / 并进件判定 / 屎山判定（grep 证明既有件没有）/ 本轮我方差在哪（读数而非形容词）。触发词：可学件/读源码找借鉴/并进既有件/屎山判定/成熟度自评/调研外部项目/能不能到 Lx。
---

# 外部源码「可学件」取证 SOP

## 何时用
派单要求「读 ≥10K 星开源项目，给 `文件:行号` 级可学件，并进我方既有件，禁另起一层」时（如 四方会议 L1→L5 逐级自评、工业产品 Raw→Graph→Wiki 调研）。

## 步骤（每步都留读数）

1. **直连克隆（不走代理）**
   `mkdir -p /tmp/fourparty/<tag> && cd /tmp/fourparty/<tag> && env -u ALL_PROXY -u HTTPS_PROXY -u HTTP_PROXY -u all_proxy -u https_proxy -u http_proxy timeout 240 git clone --depth 1 <url>`
   - **别克隆进 `~/wiki`**（污染知识库）；落 `/tmp/fourparty/<tag>/`。
   - 星数/活跃度核验（f_descr）：`curl -s https://api.github.com/repos/<owner>/<repo> | grep -E '"(stargazers_count|forks_count|created_at|pushed_at|archived|language)"|"spdx_id"|"description"'` —— 派单里的星数可能不准/是旧值，**以 API 读数为准**。
2. **先拿骨架再拿行号**（省轮次）
   `ls <repo>/<pkg>/` → 目标模块 `ls` → `grep -n "^def \|^async def \|^class " <file>` → 只对**要害文件** read_file。
   - 要害文件优先挑：**docstring 里有设计原则**的（如「失败不推进水位线」）、**幂等/水位线**、**闸/拒绝路径**、**去重-消解**、**prune/遗忘**。
3. **每条可学件四件套**（缺一不算）：
   `文件:行号` · 借鉴什么（一句，尽量引**原话**）· **并进哪件既有件**（给现有路径）· **屎山判定**。
4. **屎山判定 = 跑 grep 求读数**（禁止只写"不新建"）：
   - 先 `grep -rniE "<同义族>" agent/ scripts/ tools/ --include='*.py'`（**排除 `.bak*`/`__pycache__`**，否则 .bak 假命中会误导）。
   - 再查**调用点**：`grep -rn "\.<method>(" agent/ gateway/ tools/ scripts/ --include='*.py'` —— 定义存在 ≠ 被接线。
   - 再查**模块存活**：`grep -rln "<module>" agent/ gateway/ tools/ scripts/ --include='*.py' | wc -l` —— 结果 = **1 即孤儿件**（只有它自己）。
5. **我方现状取证（本轮最大产出常在这里）**：把"缺什么"落成**读数**，例如
   - 「既有钩子调用点 = 0 行」⇒ 病根是**件没接线**，不是缺件；
   - 读写入路径源码，判语义是**整段替换**还是**增量+闸**；
   - 外部件若与我方已有件同族，**引其行号做对照**（比形容词有力）。
6. **落盘**：写进**派单指定的那张卡**（段标题逐字），禁另建卡；讨论卡用 `patch` 追加，**禁 write_file 整卡覆盖**。台账补行 → `git -C ~/wiki commit` → 回执两字段（`重跑命令:` / `复算数字:`）。
7. **能力判断（若派单问）**：区分「**框架原生面**」（cron/锁/技能/记忆/检索）与「**领域件面**」（抽取/消解/评测）。判对端时若受身份边界限制（如不可读对端私有域），**只据公开约定**判并**显式标降级**，交主责席。

## 坑（实测）
- terminal 白名单**拦含 `/.git/` 片段**的命令：`find . -not -path './.git/*'` 会被拒 ⇒ 用 `ls <dir>` 或 `search_files`，或把 `.git` 写成 `./.git*`（不带两侧斜杠）。
- `terminal` 输出常被 **AGENTS.md 子目录上下文**污染（跑到 repo 子目录时自动载入）⇒ 命令尽量短、必要时用 `search_files` 代替 grep。
- 长 tool 输出会 offload 到 `~/.mimiraether/data/tool_offload/`，只给预览 ⇒ 关键读数要在命令里**直接算好**（`| wc -l`、`grep -c`），别指望回头翻。
- 空跑闸按「交付物未写」计数，**只读 3 轮就先落半段**（骨架+已确证+待补清单），再补全；否则硬限后只读工具直接被拒。
- `patch` 长内容易撞 JSON 截断 ⇒ **分段 patch**（每段 ≤2KB），写后回读确认无残留旧行。
- 追加台账时**先看文件尾**：末行可能属上一节（曾把上一节的「收口判据」行插进自己节中间）⇒ 追加前 `tail` 确认边界。

## 判据（可跑）
```
重跑命令: grep -oE '[a-zA-Z0-9_/.-]+\.py:[0-9]+' <卡文件> | wc -l; grep -c '^### <席>（.*）' <卡文件>
复算数字: 段内文件:行号证据 ≥8 条（实测一轮 = 32）· 段标题 = 1；缺任一 ⇒ 证据面不足，回补
```

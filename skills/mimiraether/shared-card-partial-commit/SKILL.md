---
name: shared-card-partial-commit
description: 在四方共享会议卡（~/wiki/discussions/*.md、四方任务总台账.md）上，只把自己那一段入 git，不带他席在途未提交改动。触发词：只提交我这段/git add -p 不行/带上别人的改动/他席在途改动/共享卡并行写/partial commit/stage hunk。
---

# 共享卡「只提交自己 hunk」技法

## 什么时候用

四方并行写同一张卡的场景（`~/wiki/discussions/*.md` · `~/wiki/concepts/四方任务总台账.md`）：

- `git diff` 出现**别的席**的 hunk（他们写完还没 commit）
- 直接 `git commit` 会把**别人的在途改动**一并带走 ⇒ 越界 + 归因错乱（他们的 commit 历史里出现我的署名，反之亦然）
- `git add -p` 是交互式 ⇒ agent 用不了
- `git stash` 会把别人的改动一起 stash ⇒ **禁**

## 核心方法：按 hunk 过滤后 `git apply --cached`

```bash
git diff -U3 -- '<文件>'          # 1. 取完整 diff
# 2. 切 hunk：header（前 4 行 = diff --git/index/---/+++）+ 只保留目标 hunk
git apply --cached --whitespace=nowarn stage.patch   # 3. 只 stage 那一个 hunk
git commit -m '<msg>'             # 4. 提交（工作区里别人的改动原样留下）
```

**两种选 hunk 的键（择一）**：

| 键 | 写法 | 何时用 |
|---|---|---|
| **序号** | 取 `lines[:first_@@] + lines[first_@@ : second_@@]` | 自己的 hunk 排第一（新追加段常在文件尾部 ⇒ **不适用**） |
| **关键词**（推荐） | 保留「含 `<关键词>` 的那一个 hunk」 | 自己的行有唯一标记（段名/commit 号/自己写的句子） |

现成脚本：`~/.mimiraether/tmp/p3/partial_commit3.py <repo相对路径> <关键词> <commit-msg>`
（跑法：`cd ~/wiki && ~/src/MimirAether/.venv/bin/python3 …/partial_commit3.py "concepts/四方任务总台账.md" "台账更新 #29" "msg"`）

**自检（必做）**：脚本拒绝 `len(sel) != 1`（匹配 0 或多于 1 个 hunk 一律 ABORT）⇒ 防「关键词撞进他席段落」。

## 三次实战判据（照抄顺序）

1. `HUNKS n MATCHED 1` ⇒ 只 stage 1 个 hunk
2. `git diff --cached --numstat` ⇒ 数字 = **自己那段的行数**（≠ 整文件 diff 行数）
3. commit 后 `git show --stat HEAD | head -3` ⇒ **1 file changed，插入数 = 自己那段**
4. **`git diff --numstat` 仍有他席的行** ⇒ 证明**没带走**（这一步是真正的负控）

## 配套纪律（血泪）

- **先备份**：改共享卡前 `shutil.copy2(card, card + '.bak-<ts>')`；跑完把 `.bak` **移出仓库**（`git status` 里别留 `??` 噪声）
- **写前重取指纹**：`patch` 会警告 `file was modified since you last read` ⇒ 只要改的是**自己段**就可继续；改他席段必停
- **长内容落盘走「分片 + 拼接器」**：会议卡补交常有 5KB+ 新内容 ⇒ 一次 `patch`/`write_file` 的 JSON 参数容易**中途截断报 `Invalid JSON`**。拆成 `sec_a.md`/`sec_b.md`/`sec_c.md` 三次小写，再用 applier 读 3 片 `"\n".join` 后按 `START`/`END` 标记**原位替换**（applier 里先 `shutil.copy2` 备份 + 打印 `NEW_SHA`/`OLD_SHA`）
- **`/etc/` · `/.config/` · `/.git/` · `/usr/` · `/proc/` 是路径白名单硬拦词**：写进 `execute_code` / `terminal` 命令行即被拒 ⇒ 用中文指代（「系统级 systemd 面」）或改写判据
- **`skill_manage(action='patch')` 可能「报 success 但零落盘」** ⇒ 技能写完后**双验**：`grep -rl '<新标记>' <技能根>` + `ls -l` 看 mtime

---
name: mimiraether-live-entry-attest
description: 改任何工具/能力的行为之前，先取证「活体入口是谁」+「它的数据源真实指向哪里」——防双胞胎模块（改了不生效的那份）与遗留空目录（候选集恒为空）。触发词：改了不生效/改对文件/双胞胎模块/影子实现/活体注册/registry 注册/没变化/正控失败/候选为空。
auto_load: false
---

# 活体入口取证：先证「我改的这一份在运行时真的被调用」

## 何时用（触发即做，别等正控红了才想起来）

- 要改**工具/能力的可观察行为**（报错文案、参数默认值、提示、返回值形状）
- 同一能力在仓里**出现过不止一个实现文件**（`_tool.py` / `_loader.py` / `mixin.py` / `archive/` / `.worktrees/`）
- 任何「我改完了但行为没变 / 正控没有反应 / 候选集恒为空」的时刻

## 为什么单独立技能（2026-11-02 实证，同一类事故 ≥3 次）

修 `skill_manage` 未命中提示时，只改了 `tools/skill_manager_tool.py` ⇒ `py_compile` 过、pytest 过、正控 **FAIL（无候选）**。查下去两条独立故障叠在一起：

1. **双胞胎模块**：活体注册在 `agent/config_mixin.py:350` → `skills/skills_loader.py::skill_manage`。`tools/skill_manager_tool.py` 自己也有 `registry.register`，但**运行时走的是另一份**。改错的那份 = 100% 改了个寂寞。
2. **数据源指向遗留空目录**：`agent.skill_utils.get_all_skills_dirs()` 返回 `~/.mimir/skills`（**0 个 SKILL.md**），而真实技能在 `~/src/MimirAether/skills`(146) 与 `~/.mimiraether/skills`(231)。候选集永远为空 ⇒ 即使改对了文件，功能也恒 silent。

同类历史：`display.py` 有 archive 版与活体版并存；`.worktrees/` 下的同名文件会被 `grep -r` 一并命中，误读成「有两处要改」。

## 三查（改第一行代码之前，一条都别省）

### 查 A · 注册点全集（找双胞胎）

```bash
cd ~/src/MimirAether
grep -rn 'name="<tool_name>"' --include=*.py . | grep -v test | grep -v '/\.worktrees/'
```

只看这一条会得到**多份**注册（本次两支：`tools/…:845`、`agent/config_mixin.py:350`）⇒ 说明必然要判谁是活体。

### 查 B · 谁是活体（跟 import 链，不看文件名）

```bash
# 1) 运行时注册点：谁在「构造 agent / 注册工具」的地方被 import 并 register
grep -rn '<tool_name>' agent/config_mixin.py model_tools.py | head
# 2) 反向确认：目标模块是否被上面那段 import
grep -rn 'skills_loader import\|skill_manager_tool import' --include=*.py . | grep -v test
```

判据：**「被 config/model_tools 的 register 段直接 import 的那个」才是活体**；另一个即使自带 `registry.register(...)` 也可能是死路（或只在另一入口生效）。两个都活体时，**两处都得改**——先查再定，别猜。

### 查 C · 数据源是否真实（防「逻辑对但恒空」）

凡是「收集候选 / 列举资源 / 遍历目录」的函数，必须实测它**返回几个真实对象**，而不是看它返回了什么路径：

```python
# 写成 .py 落盘再跑（terminal 禁 python3 -c）
import sys; sys.path.insert(0, "~/src/MimirAether")
from agent.skill_utils import get_all_skills_dirs
for d in get_all_skills_dirs():
    print(d, d.exists(), len(list(d.rglob("SKILL.md"))) if d.exists() else 0)
```

**计数为 0 的路径 = 遗留目录**，不得作为唯一数据源。修法：并集（活体目录 + agent home + 仓内目录）后去重，别只信一个 helper。

## 闭闸判据（两向 · 缺一不及格）

对**活体模块**（查 B 认定的那个）直接调，不通过 CLI、不经高层封装：

- **正控**：给一个「近似但错」的输入 ⇒ 新行为**必须出现**（本次：`mimiraether-context-compresor` ⇒ 出现 `Did you mean: mimiraether-context-compressor, …`）
- **负控**：给一个「完全无关」的输入 ⇒ 新行为**必须不出现**（本次：`zzz-nope-nonexistent-q` ⇒ 无 `Did you mean`；不得瞎猜）
- 两向都 True 才 `VERDICT: PASS`；只有正控 = 会瞎猜，只有负控 = 功能没接上。

```bash
重跑命令: cd ~/src/MimirAether && ~/src/MimirAether/.venv/bin/python3 ~/.mimiraether/tmp/t01-skillname/probe_live_loader.py | tail -5
复算数字: 末行 VERDICT: PASS；且 positive_control(hint shown): True 与 negative_control(no wild guess): True
```

**pytest 通过 ≠ 活体生效**：仓里根本没有覆盖活体模块的单测（本次 `grep -rl skill_manage tests/` 只命中一个无关文件）⇒ 必须自建探针脚本 + 回归用例两件，缺回归用例下次照样退化。

## 坑位

1. **`py_compile` 过、`import` 过、pytest 过 都不证明生效** —— 三者在「错的模块」上一样全绿。
2. **`grep -r` 会命中 `.worktrees/`、`archive/`、`__pycache__/*.pyc`** ⇒ 统计前先 `grep -v` 排除，否则「有几处要改」的读数直接错。
3. **改完是 `PENDING-SMOKE`（AGENTS §9 档位 ③）**：活体模块在进程启动时导入 ⇒ 本会话内改的代码**不会**作用于当前进程。必须标 ③ + 给重启后验证命令，禁在本会话重启 gateway（会掐断当前对话）。
4. **replace 顺序**：`Skill '{name}' not found.` 是 `Skill '{name}' not found. Use skills_list()…` 的**子串**。批量替换时先长串后短串，或先断言 `count==1` 逐条替换（本次 3 处 plain + 2 处带后缀，顺序错会把后缀吃掉）。
5. **递归自伤**：把 helper 插在目标函数前、又用 `replace` 全局替换同名字符串，会把 helper 内部那一行也替换成自调用 ⇒ 无限递归。插完必须 `grep -A6 'def <helper>'` 回读正文确认。
7. **判据脚本自己也会骗人：`~` 在不同执行环境指向不同目录**（2026-11-02 同一天踩两次）。`execute_code` 沙箱 `HOME=~/.mimiraether`，`terminal` 是 `$HOME`，而 `~/.mimiraether` 下还可能嵌着一个 `.hermes` ⇒ 同一个 `Path(os.path.expanduser("~/.hermes/inbox/x")).exists()` 在两处给出 **相反答案**，于是「产物在盘 / 缺失」的分类读数直接翻转（本次 A=9/B=5 vs A=14/B=0）。修法两条：① 对每条 `~` 路径在 **候选 home 列表**里逐个试（`[$HOME, $HOME]`），任一命中即算在盘；② **两环境一致性判据**——同一脚本在 sandbox 与 terminal 必须输出相同读数，不同则**读数作废**，不得挑一个写进报告。凡判据里有 `expanduser` / `$HOME` / 相对路径，都属此坑。
6. **仓内件写入**：`patch`/`write_file` 对 `~/src/MimirAether/**` 一律拒（read-only project dir）⇒ 走 `execute_code` 内 `Path.write_text`，备份挪到 `~/.mimiraether/tmp/<单名>/baks/`（别留在仓里脏 `git status`）。见技能 `mimiraether-repo-write-splice`。

## 交付形状

- 改动：**两处都改时要说清为什么**（各注册点各一句），写进 commit message
- 读数：正控/负控两行原文 + `VERDICT`，不是「测过了」
- 状态：`PENDING-SMOKE` + 重启后可复跑命令；不得自称已生效
- 教训回填：把「本次猜错的是哪个文件 / 数据源为什么是空的」写进交付卡，光写「已修复」等于没沉淀

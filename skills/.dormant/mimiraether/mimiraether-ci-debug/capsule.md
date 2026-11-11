# [DORMANT] mimiraether-ci-debug

**沉寂时间**: 2026-11-11T23:59:45.337434+00:00
**原始分类**: mimiraether
**描述**: Use when GitHub Actions CI (Ralph Tier-0 / pytest-wide / lint) fails, or when local tests pass but CI is red. Systematic 4-layer diagnosis: Gate1 syntax/import, Gate2 pytest parity, submodule init, CI dependency gaps.
**触发阈值**: 60天未触碰

---

## 技能要点

# MimirAether CI 排障方法论（GitHub Actions）

## 触发条件

- GitHub CI（Ralph Tier-0 / pytest-wide / lint）failure
- 本地 pytest 全绿但 CI 红
- 分批推送时某批 CI 不通过
- 本地/远端测试结果不一致

## 4 层诊断框架（按顺序排查，每层验证后再进下一层）

> **先看第 5 类（不属于上面 4 层，但排查性价比最高）：「env 泄漏型假绿」** ——
> 本地全绿、CI 红，失败断言是「某字段不得为空」。根因 = 被测值的**兜底来自环境变量**，
> 而该变量在你本地进程里恰好存在 ⇒ **`tmp_path` / `MIMIR_AETHER_HOME` 隔离挡不住**
> （隔离的是文件系统，不是环境变量）。第一动作：`env -u <候选兜底变量> pytest <文件>`。
> 完整取证法 / 判据 / 修复形态见文末 **「实战案例 3」**（2026-09-13 实证）。



### Layer 1 — Gate1 Syntax/Import
**症状**：`SyntaxError` / `ModuleNotFoundError` / import 失败
**排查**：
1. `python3 -m py_compile <file>` 或直接 import 测试
2. 查历史垃圾行：`git log --all -S "关键字" --oneline`（截断/损坏代码可能藏匿在旧提交，如 `def broken_fu`）
3. 若 CI 报的文件本地是干净的 → 检查该文件在**当前 commit 快照**里的内容（可能被意外带入）
**修复**：filter-branch 重写历史删除垃圾行（`git filter-branch --tree-filter` / `git filter-repo`）→ force push

### Layer 2 — Gate2 pytest parity
**症状**：`fixture 'xxx' not found` / collection ERROR / 本地无法复现
**关键教训**：**pytest 版本回归**——9.1.1 在多路径组合跑时不加载 `tests/agent/conftest.py`，9.0.2 不触发
**排查**：
1. 用 CI 同版 pytest 复现：`pip install pytest==<CI版本>` → 跑 CI 的完整文件列表
2. 二分定位：`pytest agent/` 全绿 → `pytest tests/` 红 → 组合才红 → conftest 加载差异
3. `pytest --fixtures` 对比：fixture 收集时可见但执行时 not found = conftest 未加载
4. 干净 worktree 排除 `__pycache__`：`git worktree add /tmp/clean-repro HEAD`
**修复**：fixture 上移到公共 conftest（如 `tests/conftest.py`，组合时必加载）

### Layer 3 — submodule 初始化
**症状**：`Submodule 'xxx' ... not initialized` / checkout 失败
**排查**：
1. `git submodule status` 看指针
2. `git ls-remote origin <submodule-branch>` 看远端是否有该指针
3. 本地领先远端 → 指针未推送
**修复**：先 push submodule 到远端（必要时 merge 远端 PR）→ 再 push 主仓库

### Layer 4 — CI 依赖缺口
**症状**：测试 fail-open 返回 False / import 静默失败
**排查**：`chroma_available()` 之类依赖 chromadb importable → CI 未装包
**修复**：`requirements-ci.txt` 加缺失包（锁定本地验证过的版本，如 `chromadb==1.5.8`）

## 通用诊断命令

```bash
# CI 日志
gh run view <run_id> --log | grep -E "FAILED|ERROR|short test summary"

# 本地精确复现（CI 同版本）
pip install pytest==<CI版本>
pytest <CI文件列表> -x

# 二分
pytest agent/ && p

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-ci-debug")` 即可自动唤醒。

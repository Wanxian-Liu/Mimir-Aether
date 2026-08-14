---
name: mimiraether-ci-debug
description: Use when GitHub Actions CI (Ralph Tier-0 / pytest-wide / lint) fails, or when local tests pass but CI is red. Systematic 4-layer diagnosis: Gate1 syntax/import, Gate2 pytest parity, submodule init, CI dependency gaps.
version: 1.0.0
auto_load: false
---

# MimirAether CI 排障方法论（GitHub Actions）

## 触发条件

- GitHub CI（Ralph Tier-0 / pytest-wide / lint）failure
- 本地 pytest 全绿但 CI 红
- 分批推送时某批 CI 不通过
- 本地/远端测试结果不一致

## 4 层诊断框架（按顺序排查，每层验证后再进下一层）

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
pytest agent/ && pytest tests/ && pytest <组合>

# 干净 worktree
git worktree add /tmp/clean-repro HEAD

# submodule 指针检查
git ls-remote origin <submodule-branch>
```

## 坑点 / 反模式

1. **skipif 掩盖**：CI 红时加 `skipif(CI)` 是偷懒——治标不治本，留下历史麻烦（刘哥明确反对"不能留下历史麻烦"）
2. **本地"全绿"≠CI 绿**：本地环境不同（版本/路径/包）→ CI 才暴露；必须用 CI 同版本复现
3. **分批推送偏差**：在完整历史 HEAD 上 commit 再 push = 一次带走上百提交；分批推送必须在提交前规划批次边界（分支/cherry-pick）
4. **fail-open 掩盖**：`return False` 的 fail-open 设计让依赖缺失表现为"测试失败"而非"环境错误"——查依赖链
5. **旧提交垃圾行**：Gate1 之前一直挂在同一行垃圾上，Gate2 从未真正跑过——修好 Gate1 后 Gate2 才第一次暴露潜伏问题（这是好事，继续修）

## Anti-Rationalization Table

| 借口 | 为什么错 | 正确行动 |
|------|---------|---------|
| "本地全绿，CI 是环境问题，跳过" | CI 环境差异恰恰是真实缺陷（版本回归/缺包） | 用 CI 同版本本地复现，定位根因 |
| "加个 skipif 先绿了再说" | 掩盖问题，CI 少覆盖，留下历史麻烦 | 修根因（conftest/依赖/代码） |
| "broken_fu 是历史垃圾，不影响功能" | Gate1 直接挂，整个 CI 全红 | filter-branch 清历史，不留污点 |
| "push 太快带上了中间提交" | 分批推送策略未在提交前规划 | 先规划批次边界（分支/cherry-pick）再推 |
| "这是 CI 独有的，本地复现不了" | 大概率是版本/路径/依赖差异，可复现 | 换 CI 同版本 pytest + 干净 worktree 再试 |

## 如何验证

1. 本地：`bash run_ralph_tier0.sh` → 期望 PASS（Gate2 全绿 + Gate3 通过）
2. CI：`gh run list --limit 3` → conclusion=success
3. 回归：比较修复前后 passed/failed 数量，零新回归（基线对比）

## 实战案例（2026-08-15 · GitHub CI 全绿）

4 层问题一次清：broken_fu 垃圾行 / pytest 9.1.1 conftest 回归 / mimicore submodule 指针 / chromadb 缺失
完整记录：`~/wiki/concepts/GitHub-CI全绿报告-20260815.md`
commit 链：filter-branch 重写 → 1f1b9e5 → 4be1203（conftest）→ bbdb010（submodule）→ 2fd2cd5（chromadb）→ 8fe6a8d（M6）

---
name: mimiraether-ship
description: 结构化发布流程 — 当开发完成需要推送到远程仓库时触发。包含：预发布检查 → 提交策略 → 推送 → 验证 → 文档同步。
version: 1.0.0
---

# MimirAether Ship — 结构化发布

## 触发条件

当以下任一条件满足时，加载本技能：

1. 用户说"提交""推送""发布""ship""上线"
2. 任何 `git commit` 之前（联动 skill-solidify 检查是否有遗漏的经验需要固化）
3. Phase/里程碑完成后的收尾

## 硬约束（不可跳过）

### 门控 0：未提交前预检

```
□ Ralph tier0 全绿？         → ./run_ralph_tier0.sh，Gate1+Gate2+Gate3 必须全过
□ 无死引用？                 → ./scripts/check_dead_refs.py
□ 无 import hermes_cli？     → grep -r "hermes_cli" agent/ gateway/ tools/ --include="*.py" | grep -v ".pyc" | grep -v "__pycache__"
□ 无 import mimcore？        → grep -r "from mimcore" agent/ gateway/ tools/ --include="*.py" | grep -v ".pyc"
```

任何一项不过 → 先修复，不过不提交。

### 门控 1：经验固化检查

```
□ 上轮工作有没有"踩坑→解决"的循环？    → produce_capsule() 或 skill_manage(patch)
□ 有没有非平凡工具组合（5+调用）？       → 考虑 skill_manage(create)
□ 有没有加载的 skill 发现不准/过期？     → skill_manage(patch) 立即修
```

先固化，再提交。代码和经验一起推。

### 门控 2：提交策略

根据改动量和类型选择：

| 场景 | 策略 | 示例 |
|------|------|------|
| 单一主题（<5文件） | 1 commit | `feat: 工具参数类型强制` |
| 多主题（5-20文件） | 2-3 commits 拆分 | `删除hermes_cli` → `迁移mimcore` → `增强技能` |
| 大规模（20+文件） | 3-5 commits 逻辑分组 | 按模块/阶段拆分 |

commit message 格式：`type: what changed`，type ∈ {feat, fix, refactor, chore, docs, skill}

### 门控 3：推送

```bash
git push origin main --force-with-lease
```

pre-push hook 自动跑 Ralph tier0，双重保险。

### 门控 4：推送后验证

```
□ git status 干净？          → 仅运行时文件可忽略
□ remote ahead=0？           → git status -sb 确认
□ 飞书实战（如涉及）？        → Gateway 双平台 connected
```

### 门控 5：文档同步

```
□ MAINLINE_STATUS.md         → 更新最近更新 + 更新日志
□ docs/evolution_log.md      → 如有 agent/gateway/tools 改动，./scripts/record_m6_evolution.sh
□ Phase 总结                  → 如完成了一个 Phase，更新 ground_truth.json
```

## Ship 流程总览

```
预检(Ralph) → 固化(经验) → 提交(策略) → 推送(force-with-lease) → 验证(远端+飞书) → 文档(M6+MAINLINE)
```

## 反模式

- **"小改动不用跑Ralph"** → 必须跑。任何 Python 文件改动都可能破坏导入链
- **"经验下次再固化"** → 不会的。现在不做就丢失
- **"push 就行，不用验证"** → push 不等于 deploy。飞书实战确认才算闭环
- **"一个巨型 commit"** → 除非真的只有一个原子改动，否则拆分

### Anti-Rationalization Table

| LLM 常用借口 | 为什么是错的 | 正确行动 |
|:------------|:-----------|:---------|
| "只改了文档，不用跑 Ralph" | 文档也在 repo 中，Ralph 检查引用 | 跑 `./run_ralph_tier0.sh` 5 分钟就行 |
| "我已经提交了，不用看状态" | git status 是唯一真相。记忆不准 | 跑 `git status -sb` 确认干净才关闭 |
| "远程就是最新的" | `--force-with-lease` 可能不同步 | `git status -sb` 检查 ahead/behind |
| "这次是单纯 bug 修复，不开新分支" | 主分支直接修改 = 不可回滚 | 用 worktree 隔离，验证后再合并 |
| "经验固化太慢了，先提交再说" | 不固化 2 小时后忘光 | 至少一行 `skill_manage(patch)`

## 与 Pipeline 其他技能的关系

```
brainstorming → plan-mode → subagent-driven-dev → verification → 🚢 ship → 闭环
                                                                              ↑
                                                           本技能覆盖的范围 ───┘
```

ship 是 pipeline 的最后一环。前面的 verification 确认代码正确，ship 确认代码安全地到达远端并记录在案。

## 关联技能

| 技能 | 用途 |
|------|------|
| `mimiraether-verification` | ship 前的代码验证 |
| `mimiraether-skill-solidify` | ship 前的经验固化 |
| `mimiraether-brainstorming` | 入口门控（确保设计审批后再编码） |

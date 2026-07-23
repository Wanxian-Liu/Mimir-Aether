# [DORMANT] mimiraether-skill-prune

**沉寂时间**: 2026-07-23T06:18:46.646626+00:00
**原始分类**: mimiraether
**描述**: Use when removing unused bundled skills, cleaning upstream Hermes imports, or user says skills are useless—follow git prune SOP; never blind rm. Read with mimiraether-tool-triggers.
**触发阈值**: 60天未触碰

---

## 技能要点

# MimirAether — 技能删除（Prune）SOP

**真源文档**：仓库 `docs/skills/SKILLS_POLICY.md`（路径、保留分级、2026-05-24 已删表）。

**与 solidify 分工**：`mimiraether-skill-solidify` = 创建/修补；**本技能** = 判定无用后的**安全删除**。

## 何时加载本技能

- 用户说：技能没用、清理上游、删 Hermes 带来的、减 skills 体积、空目录整理  
- 你发现 `skills_list` 里大量从未 `skill_view` 的包，想批量删  
- **不要**在「单个自建小技能」场景用本技能 → 用 `skill_manage(delete)` + 用户确认（见 solidify）

## 必做流程（顺序不可跳）

### 1. 先读政策

`read_file` 或确认已读过：`docs/skills/SKILLS_POLICY.md` §3。

### 2. 证明「可删」

对每个候选包：

```text
rg -l '<skill-name>|<dir-name>' skills/ optional-skills/ agent/ gateway/ tools/ docs/
```

- `agent/` / `gateway/` / `tools/` **有 import** → **不可删**（报用户）  
- 仅 `docs/`、`learnings/`、`skills/**` 互引 → 可删，但须改交叉引用  
- `optional-skills/` 里有同名 → 说明「bundled 删了仍可从 optional install」

### 3. 向用户交清单（批量必做）

表格列：`category/name` | 理由（0 生产引用 / 仅上游） | 是否改交叉引用 | 是否动 home 副本。

**等用户确认**后再删（≥3 包或动 P1 目录时强制）。

### 4. 执行（repo）

- 删 **`skills/<category>/<name>/` 整目录**（PowerPoint 等大树一次删根目录）  
- 修 **tool-triggers / arxiv / related_skills** 等仍指向旧名的 SKILL.md  
- 空类目录：删 `skills/gaming/` 等或写 `README.md`：「本类已清空，见 SKILLS_POLICY §4」  
- **禁止**：`skill_manage(delete)` 批量清上游树；**禁止**与 `persistent.json`、gateway 修复同 commit

### 5. 验证

```bash
python3 scripts/audit_skills_auto_load.py --roots skills
# 若还改了 agent/gateway/tools：
./run_ralph_tier0.sh
```

### 6. Runtime home（报告，不擅自删）

```bash
ls "${MIMIR_AETHER_HOME:-$HOME/.mimiraether}/skills/" 2>/dev/null
```

告诉用户：repo 已删 ≠ home 已删；要清安装副本需另确认。

## 反模式（禁止）

| 反模式 | 正确做法 |
|--------|----------|
| 「没用」就直接 `rm -rf skills/*` | 先 rg + 清单 + 用户确认 |
| 只删 `SKILL.md` 留脚本/XSD 垃圾 | 删整包目录 |
| 删完不改进度/触发器里的示例名 | 改 `mimiraether-tool-triggers` 等 |
| 用 `skill_manage(delete)` 删 18 个上游包 | git 删目录 + `chore(skills)` commit |
| 默认删 `optional-skills/` | 除非用户明确点名 |

## 2026-05-24 刘哥已裁（勿重复删）

gaming×2, leisure find-nearby, media×5, obsidian, productivity×6, godmode, openhue, xitter — 详见 `docs/skills/SKILLS_POLICY.md` §4。若工作区未 commit，应 **按 §3 收口 commit**，不要当作「还没删」再删一遍。

## 相关技能

| 技能 | 用途 |
|------|------|
| `

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-skill-prune")` 即可自动唤醒。

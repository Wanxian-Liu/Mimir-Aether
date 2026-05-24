# MimirAether Skills 治理（真源）

> **读者**：刘哥、Cursor、Mimir Agent。  
> **Agent 操作手册（必 `skill_view`）**：`mimiraether-skill-prune`（删）、`mimiraether-skill-solidify`（增/改）。  
> **审计脚本**：`python3 scripts/audit_skills_auto_load.py --roots skills optional-skills`

## 1. 三层目录（不要混）

| 层 | 路径 | 谁发现 | 何时动 |
|----|------|--------|--------|
| **Bundled** | 仓库 `skills/` | `skills_list` 默认扫描 | 团队共用、要进 git 的 |
| **Optional** | 仓库 `optional-skills/` | 仅 `mimir skills install` 后 | 重、冷门、多密钥 |
| **Runtime 安装** | `$MIMIR_AETHER_HOME/skills/`（或 profile） | install 副本 | 与 repo 删除**独立**；删 repo 不等于删 home |

**真源路径**：`mimir_constants.get_mimir_home()` / `get_mimir_data_dir()` — 见 `docs/path-contract.md`。

## 2. 保留策略（2026-05-24 口径）

| 优先级 | 目录 | 策略 |
|--------|------|------|
| P0 | `skills/mimiraether/` | 主线能力；删任一包需刘哥确认 |
| P1 | `skills/software-development/`、`github/`、`productivity/`（delegate、session-tracker、insights、snippets、skills-qa） | Mimir 日常工程 |
| P2 | `skills/research/`、`general/`、`mcp/`、`testing/` | 按需 `skill_view` |
| P3 | `skills/mlops/` | 训练/推理；不做 ML 可整类迁 `optional-skills/` 或下轮再裁 |
| — | `optional-skills/` | 默认不删；只减 install 面 |

## 3. 正确删除流程（Mimir 必须按此执行）

**禁止**：凭「感觉没用」直接 `rm -rf skills/...`、混在 unrelated commit、删 `optional-skills/` 无授权、提交 `data/persistent.json`。

### 3.1 判定「可删」

1. `skill_view` / `skills_list` 确认包名与路径。  
2. 全仓库 `rg`：包名、目录名、脚本 import（**0 生产引用** 才可删 bundled）。  
3. 可选：`skills-qa` / `audit_skills_auto_load.py` 记录质量分。  
4. **向用户列出拟删清单**，等确认（批量 ≥3 或含 `mimiraether/` 外 P1 时必确认）。

### 3.2 执行删除（repo）

1. 删 **`skills/<category>/<name>/` 整目录**（勿留空壳仅 `DESCRIPTION.md` 的类 — 要么删类目录，要么写 `README` 说明已清空）。  
2. **修交叉引用**（至少）：仍指向该名的 `SKILL.md` 的 `related_skills`、示例、`mimiraether-tool-triggers` 示例。  
3. **单独 commit**：`chore(skills): prune <names>` — 不与 gateway/agent/tools 功能混提交。  
4. 触达 `agent/`/`gateway/`/`tools/` 时跑 `./run_ralph_tier0.sh`；纯 `skills/`+`docs/skills/` 可只跑 `audit_skills_auto_load.py`。

### 3.3 Runtime 副本

```bash
# 列出 home 里是否还有安装副本（不自动删，报告给用户）
ls -la "${MIMIR_AETHER_HOME:-$HOME/.mimiraether}/skills/" 2>/dev/null
```

用户确认后再删 home 下对应目录。

### 3.4 不要用 `skill_manage(delete)` 的场景

- **整包上游清理**、多文件 XSD/脚本树 → 用 **git 删目录** + 文档，不用 `skill_manage` 逐文件删。  
- `skill_manage(delete)` 仅适合 **单个** 自建小技能且用户已确认。

## 4. 2026-05-24 已裁 bundled 清单（上游未用）

| 类 | 已删 skill |
|----|------------|
| gaming | minecraft-modpack-server, pokemon-player |
| leisure | find-nearby |
| media | gif-search, heartmula, songsee, spotify, youtube-content |
| note-taking | obsidian |
| productivity | google-workspace, linear, nano-pdf, notion, ocr-and-documents, powerpoint |
| red-teaming | godmode |
| smart-home | openhue |
| social-media | xitter |

空壳类（待收口）：`gaming/`, `media/`, `leisure/`, `note-taking/`, `smart-home/`, `social-media/` — 删目录或加 `README`。

## 5. 新增技能（同一流程）

见 `mimiraether-skill-solidify`：`create` → `skill_view` → 质量清单 → 独立 commit。

# Skills & Tools 架构对比：Hermes vs MimirAether

> **Day 4 深度学习报告 - 2025年6月29日**

---

## 一、架构概览

### Hermes Skills 架构（文档驱动 + 工具注册）

```
agent/skill_utils.py          ← 轻量元数据工具（独立于工具注册）
agent/skill_commands.py        ← 斜杠命令系统 (/skill-name)
tools/skills_tool.py           ← ★ 核心注册：skills_list/skill_view/skill_manage
tools/skill_manager_tool.py    ← CRUD 操作实现
tools/skills_guard.py          ← 安全扫描（150+ 威胁模式）
tools/skills_hub.py            ← Hub 集成（GitHub 源适配器、锁文件）
tools/skills_sync.py           ← 同步功能
hermes_cli/skills_config.py    ← CLI 配置
```

### MimirAether Skills 架构（三层共存）

```
skills/skill_manager.py        ← 🆕 运行时 Skill 执行引擎（handler 注册 + 演化）
skills/skills_loader.py        ← 🔄 1:1 移植（独立函数，非工具注册）
skills/loader.py               ← 🆕 动态 Python 模块加载器
skills/__init__.py             ← 🆕 包初始化
tools/skill_manager_tool.py    ← 🔄 移植自 Hermes（含 MimirAether 适配）
tools/skills_guard.py          ← 🔄 移植自 Hermes
tools/skills_sync.py           ← 🔄 移植自 Hermes
agent/skill_utils.py           ← 🔄 移植自 Hermes
agent/skills_qa.py             ← 🆕 技能 QA 系统
agent/skills_hub.py            ← 🔄 移植自 Hermes + 扩展
memory/providers/skill.py      ← 🆕 技能记忆提供者
```

### Tools 注册对比

| | Hermes | MimirAether |
|---|---|---|
| `tools/registry.py` (ToolRegistry) | ✅ | ✅ (1:1) |
| `tools/skills_tool.py` (skills_list/view/manage) | ✅ | ❌ **缺失** |
| `tools/skill_manager_tool.py` | ✅ | ✅ (移植) |
| `tools/skills_guard.py` | ✅ | ✅ (移植) |
| `tools/skills_hub.py` | ✅ | ✅ (移植) |
| `tools/skills_sync.py` | ✅ | ✅ (移植) |

---

## 二、Hermes 设计亮点（5个）

### 亮点 1：渐进式披露架构（Progressive Disclosure）

源自 Anthropic Claude Skills 设计理念，三级加载：

```
Tier 1: 元数据 (name ≤64c, description ≤1024c) → skills_list() 始终显示
Tier 2: 完整指令 → skill_view(name) 按需加载 SKILL.md
Tier 3: 链接文件 → skill_view(name, file_path="references/...") 按需加载
```

**MimirAether 现状：** `skills_loader.py` 有 `skills_list()`/`skill_view()` 函数实现分页，但（1）未被注册为 agent 工具，无法在对话中调用；（2）`skill_view()` 不支持加载 references 子文件。

### 亮点 2：斜杠命令系统（Slash Commands）

Hermes 的 `agent/skill_commands.py` 让用户通过 `/skill-name` 在 CLI/Telegram 中激活技能。整个系统包含：
- 自动扫描「SKILLS_DIR + 外部目录」发现技能
- 多平台命令格式适配（Telegram 的下划线 vs CLI 的连字符）
- 预加载（session-wide preloading for --skill flags）

**MimirAether 现状：** 完全缺失。没有 `/skill-name` 命令系统。

### 亮点 3：安全扫描守卫（Skills Guard）

Hermes 的 `tools/skills_guard.py` 包含 150+ 威胁模式的正则扫描，覆盖：
- 数据窃取（环境变量、SSH密钥、凭证文件）
- 提示注入（DAN模式、角色劫持、隐藏指令）
- 破坏性操作（rm -rf /、dd写入、mkfs）
- 持久化（crontab、ssh authorized_keys、systemd）
- 混淆/供应链（base64解码+管道执行、curl|sh）

三级信任策略：`builtin`(总是允许) → `trusted`(允许caution) → `community`(发现即拦截)

**MimirAether 现状：** 已移植，但与技能创建流程的集成采用 try/except 降级（`_GUARD_AVAILABLE` 检查），可能导致安全旁路。

### 亮点 4：Secret Capture 机制

技能可通过 YAML frontmatter 声明所需的环境变量，Hermes 在首次加载时自动：
1. 检查 `.env` 文件和 `os.getenv`
2. 触发 secret capture callback 提示用户输入
3. 通过 Gateway 的跨平台 secret 管理

```yaml
setup:
  collect_secrets:
    - env_var: OPENAI_API_KEY
      prompt: Enter your OpenAI API key
      provider_url: https://platform.openai.com/api-keys
```

**MimirAether 现状：** 缺失。无技能级别的 secret 声明和捕获流程。

### 亮点 5：外部技能目录 + 平台感知

```python
# agent/skill_utils.py
def get_external_skills_dirs() -> List[Path]:
    """读取 skills.external_dirs，支持 ~ 和 ${VAR} 展开，去重"""
    
def skill_matches_platform(frontmatter) -> bool:
    """检查 platforms: [macos, linux] vs sys.platform"""
```

**MimirAether 现状：** 已通过 1:1 移植获得。但 `skills_loader.py` 中的 `build_skills_prompt()` 不遵循平台过滤。

---

## 三、MimirAether 差距列表（按优先级）

### P0 - 阻塞性问题

| # | 差距 | 影响 | 修复建议 |
|---|------|------|---------|
| 1 | **缺少 `tools/skills_tool.py`** - skills_list/skill_view/skill_manage 未注册为 agent 工具 | Agent 无法在对话中加载技能；`build_skills_prompt()` 将技能列表注入 system prompt 但 agent 无法按需加载完整技能内容 | 创建 `tools/skills_tool.py`，将 `skills_loader.py` 中的函数移植过来并在 `registry.register()` 注册 |
| 2 | **`skills_loader.py` 未与 ToolRegistry 集成** | 与 Hermes 架构脱节，导致二重维护 | 将 `skills_loader.py` 重构为 `tools/skills_tool.py` 的后端，从 registry 路径统一加载 |

### P1 - 高优先级

| # | 差距 | 影响 | 修复建议 |
|---|------|------|---------|
| 3 | **无斜杠命令系统** | 用户无法通过 `/skill-name` 快捷激活技能 | 移植 `agent/skill_commands.py`，对接 `skills_loader.py` 或新的 `tools/skills_tool.py` |
| 4 | **`skill_view()` 不支持加载 references/子文件** | 渐进式披露的 Tier 3 不可用 | 扩展 `skill_view()` 支持 `file_path` 参数（参考 Hermes 实现） |
| 5 | **Secret Capture 缺失** | 技能声明 `collect_secrets` 无人消费 | 在 `tools/skills_tool.py` 中实现 `check_skills_requirements()` 和 `_capture_required_environment_variables()` |

### P2 - 中优先级

| # | 差距 | 影响 | 修复建议 |
|---|------|------|---------|
| 6 | **SkillManager 与 SKILL.md 系统正交** | `skills/skill_manager.py` 的 handler 执行模型与 SKILL.md 文档模型是两套独立系统，概念混乱 | 决策：要么统一到 SKILL.md（Hermes 路线），要么明确定义两者关系（handler 是 SKILL.md 的可选执行补充） |
| 7 | **`build_skills_prompt()` 不遵循平台过滤 + disabled 过滤** | 在 macOS 上会看到 Windows 专用技能 | 在 `build_skills_prompt()` 中加入 `skill_matches_platform()` 和 `get_disabled_skill_names()` 检查 |
| 8 | **`skills/loader.py` 的模块加载器无人使用** | `skills/modules/` 目录为空，`SkillLoader` 无调用方 | 评估是否必要；如需要，集成到 `skill_manager.py` 中 |

### P3 - 低优先级

| # | 差距 | 影响 | 修复建议 |
|---|------|------|---------|
| 9 | **SkillsQA 功能重叠** | `agent/skills_qa.py` 的验证逻辑与 Hermes 的 `_validate_frontmatter()` + `_get_disabled_skill_names()` + `skills_guard` 功能重叠 | 整合为统一的技能健康检查模块 |
| 10 | **`memory/providers/skill.py` 耦合到不存在的 SkillMemory** | 导入 `from ..memory_manager import SkillMemory` 可能失败 | 检查依赖，确认 `memory_manager.py` 是否存在 `SkillMemory` 类 |
| 11 | **ToolRegistry 注册缺失** | `tools/skills_sync.py` 和 `tools/skills_hub.py` 中的函数未在 registry 注册 | 评估哪些函数需要暴露为 agent 工具并注册 |

---

## 四、MimirAether 相对于 Hermes 的独特创新

并非全是差距——MimirAether 有一些 Hermes 没有的东西：

| 模块 | 创新点 | 评价 |
|------|--------|------|
| `skills/skill_manager.py` | 运行时 Skill 执行引擎（`execute_skill()`、`evolve_skill()`）、使用统计、成功率跟踪 | 概念上新颖但与 SKILL.md 文档模型冲突。建议作为 SKILL.md 的可选执行层，非替代 |
| `agent/skills_qa.py` | 技能质量保障：过期检测（30天）、结构验证、JSON 报告导出 | 有价值，可作为 CI/CD 检查集成。需与现有验证逻辑去重 |
| `memory/providers/skill.py` | 将技能学习结果持久化到记忆系统 | 方向正确，但需澄清与 SkillManager 的 `_save_skills_metadata()` 的关系 |

---

## 五、推荐行动计划

### Step 1：补 P0（阻塞项）- 预计 2-3 小时
1. 创建 `tools/skills_tool.py`
   - 从 `skills/skills_loader.py` 移植 `skills_list()` / `skill_view()` / `skill_manage()`
   - 在 module 级别调用 `registry.register()` 注册全部工具
   - 添加 `skill_view()` 的 `file_path` 参数支持
2. 重构 `skills_loader.py`
   - 保留 `build_skills_prompt()`（用于 system prompt 构建）
   - 将其它函数转发到 `tools/skills_tool.py`
   - 加上 `# Deprecated: use tools.skills_tool instead` 注释

### Step 2：补 P1（核心功能）- 预计 2-3 小时
3. 移植/适配 `agent/skill_commands.py`
   - 对接 MimirAether 的 SKILLS_DIR 路径（`~/.openclaw/mimir-aether/skills/`）
   - 确保与 CLI 和 Gateway 兼容
4. 实现 Secret Capture
   - 参考 Hermes 的 `_capture_required_environment_variables()`
   - 对接 MimirAether 的 `.env` 加载机制

### Step 3：澄清架构（P2）- 预计 1-2 小时
5. 决定 SkillManager 定位
   - 方案A：废弃 `skill_manager.py`，完全走 SKILL.md（更接近 Hermes）
   - 方案B：保留为 SKILL.md 的执行层（`skill_manage()` + `skill_view()` 加载文档，`skill_manager.py` 提供可选的 handler 执行）
6. 修复 `build_skills_prompt()` 的平台过滤

---

## 六、关键架构决策记录

### 决策 1：工具注册 vs 内置函数

Hermes 选择将 skills_list/skill_view/skill_manage 注册为 agent 工具（通过 ToolRegistry），因此 LLM 可以在对话中自主决定加载哪个技能。MimirAether 当前的 `build_skills_prompt()` 将所有技能列表注入 system prompt，但 LLM 无法调用 `skill_view()` 加载完整内容——因为它是 Python 函数而非注册工具。

**建议：** 两种方式互补。保持 system prompt 中的技能目录（用于意识），同时注册 `skill_view()`/`skill_manage()` 为工具（用于行动）。

### 决策 2：SkillManager 执行引擎 vs SKILL.md 文档

MimirAether 的 `skill_manager.py` 采用动态 handler 注册 (`register_skill(name, handler, schema)`) 并支持 `evolve_skill()`。这与 Hermes 的设计理念不同——Hermes 将技能视为**纯文档**（SKILL.md），由 LLM 读取后自行执行。

**建议：** 保留两者但明确定位。SKILL.md 是知识源（what + how），handler 是可选的自动化快捷方式（run）。`evolve_skill()` 可以改为更新 SKILL.md 内容而非替换 handler。

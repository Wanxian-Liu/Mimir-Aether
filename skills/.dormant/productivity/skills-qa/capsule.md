# [DORMANT] skills-qa

**沉寂时间**: 2026-07-14T18:58:41.168765+00:00
**原始分类**: productivity
**描述**: MimirAether技能质量保障系统 - 检查技能目录结构、验证SKILL.md、检测过期技能、生成质量报告
**触发阈值**: 60天未触碰

---

## 技能要点

# Skills QA - 技能质量保障系统

## 概述

基于Hermes skills_guard + Harness Engineering熵管理设计思路，为MimirAether skills提供质量保障功能。确保技能符合标准化结构，及时更新维护。

## 核心功能

| 功能 | 说明 |
|------|------|
| 目录结构检查 | 验证技能目录是否存在及基本结构（递归搜索） |
| SKILL.md验证 | 检查文件存在性、YAML frontmatter、必需字段 |
| 过期检测 | 检测超过30天未更新的技能 |
| 幽灵检测 | 检测空壳技能、无frontmatter技能、无description技能 |
| **熵管理审计** | 质量评分(0-100) + 漂移检测 + 策展分类(fresh/stale/dormant) |
| **策展报告** | CuratorReport：熵比例/质量分布/漂移警告/低分技能 |
| 质量报告 | 生成结构化报告，支持JSON导出 |
| CLI工具 | 命令行快速执行QA检查 |

## 使用方法

### Python API

```python
from skills_qa import SkillsQA

# 初始化（使用默认目录 ~/.mimiraether/skills）
qa = SkillsQA()

# 运行QA检查
report = qa.run_qa_check()

# 打印报告
qa.print_report()

# 获取无效技能
invalid = qa.get_invalid_skills()

# 获取过期技能
expired = qa.get_expired_skills()

# 导出JSON报告
qa.export_report_json("/path/to/report.json")
```

### CLI命令

```bash
# 基本检查
python skills_qa.py

# 指定技能目录
python skills_qa.py --dir /path/to/skills

# 导出JSON报告
python skills_qa.py --json report.json

# 静默模式（只显示摘要）
python skills_qa.py --quiet

# 跳过过期检测
python skills_qa.py --no-expiry
```

## 验证规则

### 必需文件
- `SKILL.md` - 技能描述文件

### 必需元数据字段
- `name` - 技能名称
- `description` - 技能描述

### 可选元数据字段
- `version` - 版本号
- `author` - 作者
- `license` - 许可证
- `metadata` - 额外元数据

### 过期阈值
- 默认30天未更新标记为过期

## 报告输出示例

```
Skills QA Report
==================================================
Skills Directory: /home/user/.mimiraether/skills
Total Skills: 25
Valid Skills: 23
Expired Skills (>30 days): 2

Issues Found:
  - Errors: 0
  - Warnings: 2
  - Info: 0
```

## 数据结构

### SkillIssue
```python
@dataclass
class SkillIssue:
    skill_name: str      # 技能名称
    severity: str        # error/warning/info
    issue_type: str      # 问题类型
    message: str         # 问题描述
    file_path: str       # 相关文件路径
```

### SkillQAReport
```python
@dataclass
class SkillQAReport:
    skills_dir: str                    # 技能目录
    total_skills: int                  # 总技能数
    valid_skills: int                  # 有效技能数
    issues: List[SkillIssue]        

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("skills-qa")` 即可自动唤醒。

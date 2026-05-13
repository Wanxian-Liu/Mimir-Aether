"""
技能质量保障系统 - SkillsQA
参考 Hermes skills_guard 设计思路，确保 MimirAether skills 的质量标准

功能：
- 检查技能目录结构
- 验证 SKILL.md 存在性和基本结构
- 技能过期检测（超过30天未更新）
- 生成质量报告
"""

import os
import yaml
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class IssueSeverity(Enum):
    """问题严重级别"""
    ERROR = "error"      # 必须修复
    WARNING = "warning" # 建议修复
    INFO = "info"       # 参考信息


class SkillHealth(Enum):
    """技能健康状态（熵管理分类）"""
    FRESH = "fresh"        # 活跃：<30天 且 质量≥70
    STALE = "stale"        # 陈旧：30-90天 或 质量下降
    DORMANT = "dormant"   # 休眠：>90天 或 质量<40


@dataclass
class SkillIssue:
    """技能问题记录"""
    skill_name: str
    severity: IssueSeverity
    issue_type: str
    message: str
    file_path: Optional[str] = None


@dataclass
class SkillExpiryInfo:
    """技能过期信息"""
    skill_name: str
    last_modified: float  # Unix timestamp
    days_since_update: int
    is_expired: bool
    file_path: str


@dataclass
class SkillQAReport:
    """技能质量报告"""
    skills_dir: str
    total_skills: int = 0
    valid_skills: int = 0
    issues: List[SkillIssue] = field(default_factory=list)
    skill_details: Dict[str, Dict] = field(default_factory=dict)
    expiry_info: Dict[str, SkillExpiryInfo] = field(default_factory=dict)
    expired_skills: List[str] = field(default_factory=list)
    
    def add_issue(self, issue: SkillIssue):
        self.issues.append(issue)
    
    def get_summary(self) -> str:
        error_count = sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)
        info_count = sum(1 for i in self.issues if i.severity == IssueSeverity.INFO)
        expired_count = len(self.expired_skills)
        return (
            f"Skills QA Report\n"
            f"{'=' * 50}\n"
            f"Skills Directory: {self.skills_dir}\n"
            f"Total Skills: {self.total_skills}\n"
            f"Valid Skills: {self.valid_skills}\n"
            f"Expired Skills (>30 days): {expired_count}\n"
            f"\nIssues Found:\n"
            f"  - Errors: {error_count}\n"
            f"  - Warnings: {warning_count}\n"
            f"  - Info: {info_count}\n"
        )


@dataclass
class SkillQualityScore:
    """技能质量评分（0-100）"""
    skill_name: str
    freshness: int = 0       # 0-25: 基于最后修改时间
    completeness: int = 0    # 0-25: 必需字段+可选字段+正文
    depth: int = 0           # 0-25: 内容长度
    structure: int = 0       # 0-25: 章节/代码块/示例
    total: int = 0           # 0-100

    def grade(self) -> str:
        if self.total >= 80:
            return "A"
        elif self.total >= 60:
            return "B"
        elif self.total >= 40:
            return "C"
        else:
            return "D"


@dataclass
class CuratorReport:
    """技能策展报告（熵管理输出）"""
    skills_dir: str
    total: int = 0
    fresh: int = 0
    stale: int = 0
    dormant: int = 0
    quality_scores: Dict[str, SkillQualityScore] = field(default_factory=dict)
    drift_warnings: Dict[str, List[str]] = field(default_factory=dict)
    curator_nudge: Optional[str] = None  # 主动提醒消息

    @property
    def entropy_ratio(self) -> float:
        """熵比例：非 fresh 技能占比"""
        if self.total == 0:
            return 0.0
        return (self.stale + self.dormant) / self.total


class SkillsQA:
    """技能质量保障系统"""
    
    # 必需的文件
    REQUIRED_FILES = ["SKILL.md"]
    
    # SKILL.md 必需的前端元数据字段
    REQUIRED_META_FIELDS = ["name", "description"]
    
    # 可选的元数据字段
    OPTIONAL_META_FIELDS = ["version", "author", "license", "metadata"]
    
    # 技能过期阈值（天）
    EXPIRY_THRESHOLD_DAYS = 30
    
    def __init__(self, skills_dir: Optional[str] = None):
        if skills_dir is None:
            from mimir_constants import get_skills_dir

            skills_dir = str(get_skills_dir())
        self.skills_dir = Path(skills_dir)
        self.report: Optional[SkillQAReport] = None
    
    def check_directory_structure(self) -> Tuple[bool, List[str]]:
        """检查技能目录是否存在及基本结构
        
        Returns:
            Tuple[bool, List[str]]: (目录是否存在, 问题列表)
        """
        issues = []
        
        if not self.skills_dir.exists():
            issues.append(f"Skills directory does not exist: {self.skills_dir}")
            return False, issues
        
        if not self.skills_dir.is_dir():
            issues.append(f"Path exists but is not a directory: {self.skills_dir}")
            return False, issues
        
        return True, issues
    
    def discover_skills(self) -> List[str]:
        """发现所有技能目录（递归搜索 SKILL.md）

        技能目录特征：包含 SKILL.md 文件的目录

        Returns:
            List[str]: 技能目录相对路径列表
        """
        skills = []
        if not self.skills_dir.exists():
            return skills

        for skill_md in self.skills_dir.rglob("SKILL.md"):
            skill_dir = skill_md.parent
            rel_path = str(skill_dir.relative_to(self.skills_dir))
            skills.append(rel_path)

        return sorted(skills)
    
    def validate_skill_md(self, skill_name: str) -> Tuple[bool, Optional[Dict], List[SkillIssue]]:
        """验证单个技能的 SKILL.md
        
        Args:
            skill_name: 技能名称
            
        Returns:
            Tuple[bool, Optional[Dict], List[SkillIssue]]:
                (是否有效, 解析的元数据, 问题列表)
        """
        issues = []
        skill_path = self.skills_dir / skill_name
        skill_md_path = skill_path / "SKILL.md"
        
        # 检查文件是否存在
        if not skill_md_path.exists():
            issues.append(SkillIssue(
                skill_name=skill_name,
                severity=IssueSeverity.ERROR,
                issue_type="missing_file",
                message=f"SKILL.md not found",
                file_path=str(skill_md_path)
            ))
            return False, None, issues
        
        # 解析 YAML frontmatter
        try:
            content = skill_md_path.read_text(encoding="utf-8")
            metadata, body = self._parse_yaml_frontmatter(content)
        except Exception as e:
            issues.append(SkillIssue(
                skill_name=skill_name,
                severity=IssueSeverity.ERROR,
                issue_type="parse_error",
                message=f"Failed to parse SKILL.md: {e}",
                file_path=str(skill_md_path)
            ))
            return False, None, issues
        
        # 检查必需字段
        if not metadata:
            issues.append(SkillIssue(
                skill_name=skill_name,
                severity=IssueSeverity.ERROR,
                issue_type="empty_metadata",
                message="SKILL.md has no YAML frontmatter",
                file_path=str(skill_md_path)
            ))
            return False, None, issues
        
        for field in self.REQUIRED_META_FIELDS:
            if field not in metadata:
                issues.append(SkillIssue(
                    skill_name=skill_name,
                    severity=IssueSeverity.ERROR,
                    issue_type="missing_field",
                    message=f"Required field '{field}' is missing",
                    file_path=str(skill_md_path)
                ))
        
        # 检查内容是否存在
        if not body or not body.strip():
            issues.append(SkillIssue(
                skill_name=skill_name,
                severity=IssueSeverity.WARNING,
                issue_type="empty_body",
                message="SKILL.md has no content body",
                file_path=str(skill_md_path)
            ))
        
        is_valid = all(field in metadata for field in self.REQUIRED_META_FIELDS)
        return is_valid, metadata, issues
    
    def check_skill_expiry(self, skill_name: str) -> SkillExpiryInfo:
        """检查技能是否过期（基于 SKILL.md 修改时间）
        
        技能被标记为过期条件：超过30天未更新
        
        Args:
            skill_name: 技能名称
            
        Returns:
            SkillExpiryInfo: 过期信息
        """
        skill_md_path = self.skills_dir / skill_name / "SKILL.md"
        
        if not skill_md_path.exists():
            # 文件不存在时，返回当前时间戳
            current_time = time.time()
            return SkillExpiryInfo(
                skill_name=skill_name,
                last_modified=current_time,
                days_since_update=0,
                is_expired=False,
                file_path=str(skill_md_path)
            )
        
        # 获取文件修改时间
        mtime = skill_md_path.stat().st_mtime
        current_time = time.time()
        days_since_update = int((current_time - mtime) / (24 * 3600))
        is_expired = days_since_update > self.EXPIRY_THRESHOLD_DAYS
        
        return SkillExpiryInfo(
            skill_name=skill_name,
            last_modified=mtime,
            days_since_update=days_since_update,
            is_expired=is_expired,
            file_path=str(skill_md_path)
        )
    
    def _parse_yaml_frontmatter(self, content: str) -> Tuple[Optional[Dict], str]:
        """解析 YAML frontmatter
        
        Args:
            content: 文件内容
            
        Returns:
            Tuple[Optional[Dict], str]: (元数据字典, 正文内容)
        """
        lines = content.split('\n')
        
        # 检查是否有 frontmatter 标记
        if not lines or lines[0].strip() != '---':
            return None, content
        
        # 找到结束标记
        end_idx = None
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == '---':
                end_idx = i
                break
        
        if end_idx is None:
            return None, content
        
        # 解析 YAML
        yaml_content = '\n'.join(lines[1:end_idx])
        body_content = '\n'.join(lines[end_idx + 1:])
        
        try:
            metadata = yaml.safe_load(yaml_content)
            return metadata, body_content
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parse error: {e}")
    
    def run_qa_check(self, check_expiry: bool = True) -> SkillQAReport:
        """执行完整的 QA 检查
        
        Args:
            check_expiry: 是否检查技能过期状态
            
        Returns:
            SkillQAReport: 质量报告
        """
        self.report = SkillQAReport(skills_dir=str(self.skills_dir))
        
        # 1. 检查目录结构
        dir_ok, dir_issues = self.check_directory_structure()
        for issue_msg in dir_issues:
            self.report.add_issue(SkillIssue(
                skill_name="[directory]",
                severity=IssueSeverity.ERROR,
                issue_type="directory_error",
                message=issue_msg
            ))
        
        if not dir_ok:
            return self.report
        
        # 2. 发现所有技能
        skills = self.discover_skills()
        self.report.total_skills = len(skills)
        
        # 3. 验证每个技能
        for skill_name in skills:
            is_valid, metadata, issues = self.validate_skill_md(skill_name)
            
            if is_valid:
                self.report.valid_skills += 1
            
            # 记录详情
            self.report.skill_details[skill_name] = {
                "valid": is_valid,
                "metadata": metadata,
                "path": str(self.skills_dir / skill_name)
            }
            
            # 添加问题
            for issue in issues:
                self.report.add_issue(issue)
            
            # 4. 检查技能过期状态
            if check_expiry:
                expiry_info = self.check_skill_expiry(skill_name)
                self.report.expiry_info[skill_name] = expiry_info
                
                if expiry_info.is_expired:
                    self.report.expired_skills.append(skill_name)
                    self.report.add_issue(SkillIssue(
                        skill_name=skill_name,
                        severity=IssueSeverity.WARNING,
                        issue_type="skill_expired",
                        message=f"Skill not updated in {expiry_info.days_since_update} days (threshold: {self.EXPIRY_THRESHOLD_DAYS} days)",
                        file_path=expiry_info.file_path
                    ))
        
        return self.report
    
    def print_report(self, report: Optional[SkillQAReport] = None, show_expiry: bool = True):
        """打印报告到标准输出
        
        Args:
            report: 报告对象，默认为 self.report
            show_expiry: 是否显示过期信息
        """
        if report is None:
            report = self.report
        if report is None:
            print("No report available. Run run_qa_check() first.")
            return
        
        print(report.get_summary())
        
        # 显示过期技能列表
        if show_expiry and report.expired_skills:
            print("\nExpired Skills (not updated in >30 days):")
            print("-" * 50)
            for skill_name in report.expired_skills:
                expiry = report.expiry_info.get(skill_name)
                if expiry:
                    from datetime import datetime
                    last_date = datetime.fromtimestamp(expiry.last_modified).strftime("%Y-%m-%d")
                    print(f"  - {skill_name}: {expiry.days_since_update} days ago (last: {last_date})")
        
        if report.issues:
            print("\nDetailed Issues:")
            print("-" * 50)
            for issue in report.issues:
                severity_label = f"[{issue.severity.value.upper()}]"
                print(f"{severity_label} {issue.skill_name}: {issue.message}")
                if issue.file_path:
                    print(f"           File: {issue.file_path}")
    
    def get_invalid_skills(self) -> List[str]:
        """获取无效技能列表
        
        Returns:
            List[str]: 无效技能名称列表
        """
        if not self.report:
            return []
        return [
            skill for skill, details in self.report.skill_details.items()
            if not details["valid"]
        ]
    
    def get_expired_skills(self) -> List[str]:
        """获取过期技能列表
        
        Returns:
            List[str]: 过期技能名称列表
        """
        if not self.report:
            return []
        return self.report.expired_skills.copy()
    
    def get_expiry_info(self, skill_name: str) -> Optional[SkillExpiryInfo]:
        """获取指定技能的过期信息
        
        Args:
            skill_name: 技能名称
            
        Returns:
            Optional[SkillExpiryInfo]: 过期信息
        """
        if not self.report:
            return None
        return self.report.expiry_info.get(skill_name)
    

    # ─── Ghost Skill Detection ────────────────────────────────────────

    GHOST_SHELL_PATTERNS = [
        "gap_reason: 核心能力缺失",
        "骨架技能 - 需要进一步实现具体逻辑",
        "功能1: 待实现",
        "Auto-generated by MimirAether Three-Ring Closed Loop",
    ]

    GHOST_SHELL_MIN_BODY_LENGTH = 500

    def detect_ghost_skills(self) -> Dict[str, List[str]]:
        """检测幽灵技能

        Returns:
            Dict with keys: 'empty_shells', 'no_frontmatter', 'no_description'
        """
        ghosts = {"empty_shells": [], "no_frontmatter": [], "no_description": []}

        for skill_name in self.discover_skills():
            skill_md = self.skills_dir / skill_name / "SKILL.md"
            if not skill_md.exists():
                continue

            content = skill_md.read_text(encoding="utf-8")

            if not content.startswith("---"):
                ghosts["no_frontmatter"].append(skill_name)
                continue

            parts = content.split("---", 2)
            if len(parts) < 3:
                ghosts["no_frontmatter"].append(skill_name)
                continue

            try:
                fm = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                ghosts["no_frontmatter"].append(skill_name)
                continue

            body = parts[2]

            if not fm.get("description"):
                ghosts["no_description"].append(skill_name)

            is_shell = False
            for pattern in self.GHOST_SHELL_PATTERNS:
                if pattern in body:
                    is_shell = True
                    break

            if is_shell and len(body.strip()) < self.GHOST_SHELL_MIN_BODY_LENGTH:
                ghosts["empty_shells"].append(skill_name)

        return ghosts

    def print_ghost_report(self, ghosts: Dict[str, List[str]] = None):
        """打印幽灵技能报告"""
        if ghosts is None:
            ghosts = self.detect_ghost_skills()

        total = sum(len(v) for v in ghosts.values())
        if total == 0:
            print("No ghost skills detected.")
            return

        print(f"\nGhost Skills Report ({total} found)")
        print("=" * 50)

        if ghosts["empty_shells"]:
            print(f"\nEmpty Shells ({len(ghosts['empty_shells'])}): delete these")
            for name in ghosts["empty_shells"]:
                print(f"   - {name}")

        if ghosts["no_frontmatter"]:
            print(f"\nNo Frontmatter ({len(ghosts['no_frontmatter'])}): add YAML frontmatter")
            for name in ghosts["no_frontmatter"]:
                print(f"   - {name}")

        if ghosts["no_description"]:
            print(f"\nNo Description ({len(ghosts['no_description'])}): add description field")
            for name in ghosts["no_description"]:
                print(f"   - {name}")

        print(f"\nTreatment:")
        print(f"  Empty shells  -> delete (rm -rf skills/.../skill-name)")
        print(f"  No frontmatter -> add ---\\nname: ...\\ndescription: ...\\n---")
        print(f"  No description -> add 'description' field to existing frontmatter")

    def export_report_json(self, output_path: str) -> bool:
        """导出报告为 JSON 格式
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            bool: 导出是否成功
        """
        import json
        
        if not self.report:
            return False
        
        # 构建可序列化的报告
        report_data = {
            "skills_dir": self.report.skills_dir,
            "total_skills": self.report.total_skills,
            "valid_skills": self.report.valid_skills,
            "expired_skills": self.report.expired_skills,
            "expiry_threshold_days": self.EXPIRY_THRESHOLD_DAYS,
            "issues": [
                {
                    "skill_name": i.skill_name,
                    "severity": i.severity.value,
                    "issue_type": i.issue_type,
                    "message": i.message,
                    "file_path": i.file_path
                }
                for i in self.report.issues
            ],
            "skill_details": self.report.skill_details,
            "expiry_info": {
                name: {
                    "skill_name": info.skill_name,
                    "last_modified": info.last_modified,
                    "days_since_update": info.days_since_update,
                    "is_expired": info.is_expired,
                    "file_path": info.file_path
                }
                for name, info in self.report.expiry_info.items()
            }
        }
        
        try:
            Path(output_path).write_text(
                json.dumps(report_data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            return True
        except Exception:
            return False

    # ─── Entropy Management ──────────────────────────────────────────

    # 质量评分权重
    FRESHNESS_WEIGHT = 25
    COMPLETENESS_WEIGHT = 25
    DEPTH_WEIGHT = 25
    STRUCTURE_WEIGHT = 25

    # 深度阈值（字符数）
    DEPTH_TIERS = [
        (5000, 25),   # 5000+ = 满分
        (2000, 20),   # 2000+ = 20
        (1000, 15),   # 1000+ = 15
        (500, 10),    # 500+  = 10
        (200, 5),     # 200+  = 5
    ]

    # 新鲜度阈值
    FRESH_THRESHOLD_DAYS = 30    # 新鲜
    STALE_THRESHOLD_DAYS = 90    # 陈旧上限
    DORMANT_THRESHOLD_DAYS = 180 # 休眠

    # 质量分类阈值
    FRESH_QUALITY_MIN = 70
    STALE_QUALITY_MIN = 40

    def score_skill_quality(self, skill_name: str) -> SkillQualityScore:
        """评分单个技能的质量（0-100）

        四个维度各 25 分：新鲜度 / 完整度 / 深度 / 结构
        """
        score = SkillQualityScore(skill_name=skill_name)
        skill_md = self.skills_dir / skill_name / "SKILL.md"

        if not skill_md.exists():
            return score

        content = skill_md.read_text(encoding="utf-8")
        try:
            metadata, body = self._parse_yaml_frontmatter(content)
        except Exception:
            metadata, body = None, content

        mtime = skill_md.stat().st_mtime
        days_since = int((time.time() - mtime) / (24 * 3600))

        # 1. Freshness (0-25)
        if days_since <= self.FRESH_THRESHOLD_DAYS:
            score.freshness = 25
        elif days_since <= self.STALE_THRESHOLD_DAYS:
            score.freshness = 15
        elif days_since <= self.DORMANT_THRESHOLD_DAYS:
            score.freshness = 5
        else:
            score.freshness = 0

        # 2. Completeness (0-25)
        if metadata:
            has_required = all(f in metadata for f in self.REQUIRED_META_FIELDS)
            has_optional = sum(1 for f in self.OPTIONAL_META_FIELDS if f in metadata)
            has_body = bool(body and body.strip())

            score.completeness = 10 if has_required else 0
            score.completeness += min(has_optional * 3, 9)
            score.completeness += 6 if has_body else 0
        else:
            score.completeness = 0

        # 3. Depth (0-25)
        body_len = len(body.strip()) if body else 0
        for threshold, points in self.DEPTH_TIERS:
            if body_len >= threshold:
                score.depth = points
                break
        else:
            score.depth = 0 if body_len == 0 else 2

        # 4. Structure (0-25)
        structure_score = 0
        # 有章节标题（## 开头）
        if body:
            h2_count = body.count('\n## ')
            h3_count = body.count('\n### ')
            structure_score += min(h2_count, 3) * 3  # 最多9分
            structure_score += min(h3_count, 4) * 2  # 最多8分
            # 有代码块
            if '```' in body:
                structure_score += 5
            # 有列表
            if '\n- ' in body or '\n* ' in body:
                structure_score += 3
        score.structure = min(structure_score, 25)

        score.total = score.freshness + score.completeness + score.depth + score.structure
        return score

    def detect_drift(self, skill_name: str) -> List[str]:
        """检测技能漂移——内容是否偏离声明用途

        Returns:
            List[str]: 漂移警告列表（空=无漂移）
        """
        warnings = []
        skill_md = self.skills_dir / skill_name / "SKILL.md"

        if not skill_md.exists():
            return warnings

        content = skill_md.read_text(encoding="utf-8")
        try:
            metadata, body = self._parse_yaml_frontmatter(content)
        except Exception:
            return warnings

        if not metadata or not body:
            return warnings

        description = metadata.get("description", "")
        if not description:
            warnings.append("No description to compare against — can't detect drift")
            return warnings

        body_lower = body.lower()
        desc_lower = description.lower()

        # 提取描述中的关键词
        keywords = [w.strip('.,;:()[]{}"\'') for w in desc_lower.split()
                    if len(w.strip('.,;:()[]{}"\'')) > 3]

        # 计算关键词在正文中的出现率
        if keywords:
            found = sum(1 for kw in keywords if kw in body_lower)
            hit_rate = found / len(keywords)

            if hit_rate < 0.3:
                warnings.append(
                    f"Drift: only {found}/{len(keywords)} description keywords "
                    f"({hit_rate:.0%}) found in body — content may have diverged"
                )
            elif hit_rate < 0.5:
                warnings.append(
                    f"Mild drift: {found}/{len(keywords)} description keywords "
                    f"({hit_rate:.0%}) in body"
                )

        # 描述声称"详细"但正文很短
        depth_indicators = ["detailed", "comprehensive", "complete", "in-depth", "full"]
        if any(w in desc_lower for w in depth_indicators):
            body_len = len(body.strip())
            if body_len < 500:
                warnings.append(
                    f"Drift: description claims depth but body is only {body_len} chars"
                )

        return warnings

    def classify_curator(
        self,
        skill_name: str,
        quality_score: SkillQualityScore,
        days_since_update: int,
    ) -> SkillHealth:
        """策展分类：fresh / stale / dormant"""
        if days_since_update <= self.FRESH_THRESHOLD_DAYS and quality_score.total >= self.FRESH_QUALITY_MIN:
            return SkillHealth.FRESH
        elif days_since_update <= self.STALE_THRESHOLD_DAYS and quality_score.total >= self.STALE_QUALITY_MIN:
            return SkillHealth.STALE
        else:
            return SkillHealth.DORMANT

    def run_entropy_check(self) -> CuratorReport:
        """执行完整熵管理审计

        Returns:
            CuratorReport: 包含质量评分、漂移检测、策展分类
        """
        report = CuratorReport(skills_dir=str(self.skills_dir))
        skills = self.discover_skills()
        report.total = len(skills)

        for skill_name in skills:
            skill_md = self.skills_dir / skill_name / "SKILL.md"

            # 质量评分
            qscore = self.score_skill_quality(skill_name)
            report.quality_scores[skill_name] = qscore

            # 漂移检测
            drift_warnings = self.detect_drift(skill_name)
            if drift_warnings:
                report.drift_warnings[skill_name] = drift_warnings

            # 策展分类
            if skill_md.exists():
                days_since = int((time.time() - skill_md.stat().st_mtime) / (24 * 3600))
            else:
                days_since = 999
            health = self.classify_curator(skill_name, qscore, days_since)

            if health == SkillHealth.FRESH:
                report.fresh += 1
            elif health == SkillHealth.STALE:
                report.stale += 1
            else:
                report.dormant += 1

        # 生成 curator_nudge
        if report.stale + report.dormant > 0:
            nudge_parts = []
            if report.stale > 0:
                nudge_parts.append(f"{report.stale} stale")
            if report.dormant > 0:
                nudge_parts.append(f"{report.dormant} dormant")

            # 挑出最低分技能
            if report.quality_scores:
                worst = min(report.quality_scores.values(),
                           key=lambda s: s.total)
                nudge_parts.append(
                    f"lowest: {worst.skill_name} ({worst.total}/100 grade {worst.grade()})"
                )

            report.curator_nudge = (
                f"Entropy alert: {', '.join(nudge_parts)} | "
                f"Run entropy_check() to triage"
            )

        return report

    def print_curator_report(self, report: CuratorReport = None):
        """打印策展报告"""
        if report is None:
            report = self.run_entropy_check()

        print(f"\nSkills Curator Report (Entropy Audit)")
        print("=" * 55)
        print(f"Total: {report.total} | Fresh: {report.fresh} | "
              f"Stale: {report.stale} | Dormant: {report.dormant}")
        print(f"Entropy Ratio: {report.entropy_ratio:.1%}")
        print("-" * 55)

        # 质量分布
        grades = {"A": 0, "B": 0, "C": 0, "D": 0}
        for qs in report.quality_scores.values():
            grades[qs.grade()] += 1
        print(f"Quality: A={grades['A']} B={grades['B']} "
              f"C={grades['C']} D={grades['D']}")

        # 漂移警告
        if report.drift_warnings:
            print(f"\nDrift Warnings ({len(report.drift_warnings)} skills):")
            for skill, warnings in report.drift_warnings.items():
                for w in warnings:
                    print(f"  ⚠ {skill}: {w}")

        # 低分技能 Top 5
        if report.quality_scores:
            sorted_scores = sorted(
                report.quality_scores.values(),
                key=lambda s: s.total
            )[:5]
            print(f"\nLowest Quality (bottom 5):")
            for qs in sorted_scores:
                print(f"  {qs.grade()} {qs.skill_name}: {qs.total}/100 "
                      f"(F{qs.freshness}/C{qs.completeness}/"
                      f"D{qs.depth}/S{qs.structure})")

        # 策展建议
        if report.curator_nudge:
            print(f"\n📋 {report.curator_nudge}")

    # ─── End Entropy Management ──────────────────────────────────────


# CLI 入口
def main():
    """CLI 主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="MimirAether Skills Quality Assurance"
    )
    parser.add_argument(
        "--dir", "-d",
        default=None,
        help="Skills directory path (default: $MIMIR_AETHER_HOME/skills via mimir_constants)",
    )
    parser.add_argument(
        "--json", "-j",
        default=None,
        help="Export report to JSON file"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only show summary, hide detailed issues"
    )
    parser.add_argument(
        "--no-expiry",
        action="store_true",
        help="Skip skill expiry check"
    )
    parser.add_argument(
        "--expired-only",
        action="store_true",
        help="Show only expired skills"
    )
    parser.add_argument(
        "--entropy", "-e",
        action="store_true",
        help="Run entropy audit (quality scores + drift detection + curator triage)"
    )
    parser.add_argument(
        "--ghosts", "-g",
        action="store_true",
        help="Detect ghost skills (empty shells, no frontmatter, no description)"
    )
    
    args = parser.parse_args()
    
    qa = SkillsQA(skills_dir=args.dir)

    if args.entropy:
        report = qa.run_entropy_check()
        if args.quiet:
            print(f"Fresh: {report.fresh} Stale: {report.stale} "
                  f"Dormant: {report.dormant} | Entropy: {report.entropy_ratio:.1%}")
        else:
            qa.print_curator_report(report)
        if args.json:
            _export_entropy_json(qa, report, args.json)
        return

    if args.ghosts:
        ghosts = qa.detect_ghost_skills()
        qa.print_ghost_report(ghosts)
        return

    report = qa.run_qa_check(check_expiry=not args.no_expiry)
    
    if args.expired_only:
        expired = qa.get_expired_skills()
        if expired:
            print("Expired Skills:")
            for skill_name in expired:
                expiry = qa.get_expiry_info(skill_name)
                if expiry:
                    from datetime import datetime
                    last_date = datetime.fromtimestamp(expiry.last_modified).strftime("%Y-%m-%d")
                    print(f"  {skill_name}: {expiry.days_since_update} days ago (last: {last_date})")
        else:
            print("No expired skills found.")
    elif args.quiet:
        print(report.get_summary())
    else:
        qa.print_report(report, show_expiry=not args.no_expiry)
    
    if args.json:
        if qa.export_report_json(args.json):
            print(f"\nReport exported to: {args.json}")
        else:
            print(f"\nFailed to export report to: {args.json}")


if __name__ == "__main__":
    main()

# Security Scanner - 危险模式检测
DANGEROUS_PATTERNS = ['subprocess shell=True', 'eval(', 'exec(', 'os.system']
SENSITIVE_PATTERNS = ['api_key', 'password', 'secret', 'token']


def _export_entropy_json(qa, report, output_path):
    """导出熵审计报告为 JSON"""
    import json

    data = {
        "skills_dir": report.skills_dir,
        "total": report.total,
        "fresh": report.fresh,
        "stale": report.stale,
        "dormant": report.dormant,
        "entropy_ratio": report.entropy_ratio,
        "curator_nudge": report.curator_nudge,
        "quality_scores": {
            name: {
                "total": qs.total,
                "grade": qs.grade(),
                "freshness": qs.freshness,
                "completeness": qs.completeness,
                "depth": qs.depth,
                "structure": qs.structure,
            }
            for name, qs in report.quality_scores.items()
        },
        "drift_warnings": report.drift_warnings,
    }
    Path(output_path).write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nEntropy report exported to: {output_path}")


def check_security_scan(file_path):
    """检测危险模式"""
    issues = []
    try:
        with open(file_path) as f:
            for i, line in enumerate(f, 1):
                for pattern in DANGEROUS_PATTERNS:
                    if pattern in line:
                        issues.append(f"Line {i}: Dangerous pattern: {pattern}")
                for pattern in SENSITIVE_PATTERNS:
                    if pattern in line and not line.strip().startswith('#'):
                        issues.append(f"Line {i}: Sensitive pattern: {pattern}")
    except:
        pass
    return issues

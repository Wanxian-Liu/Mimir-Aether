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
            skills_dir = os.path.expanduser("~/.openclaw/projects/MimirAether/skills")
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
        """发现所有技能目录
        
        技能目录特征：包含 SKILL.md 文件的目录
        
        Returns:
            List[str]: 技能名称列表
        """
        skills = []
        if not self.skills_dir.exists():
            return skills
        
        for item in self.skills_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skills.append(item.name)
        
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
        help="Skills directory path (default: ~/.openclaw/projects/MimirAether/skills)"
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
    
    args = parser.parse_args()
    
    qa = SkillsQA(skills_dir=args.dir)
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

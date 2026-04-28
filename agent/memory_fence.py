"""
MimirAether Memory Fence - 记忆围栏系统
防止敏感信息泄露，确保记忆安全和质量

功能：
- 敏感信息检测 (API keys, passwords, tokens)
- 个人信息过滤
- 记忆分类 (public/private/sensitive/restricted)
- 安全审查建议
"""

import re
import os
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum


class MemoryLevel(Enum):
    """记忆敏感级别"""
    PUBLIC = "public"           # 公开，可分享
    PRIVATE = "private"         # 私有，仅本人可见
    SENSITIVE = "sensitive"     # 敏感，需脱敏处理
    RESTRICTED = "restricted"   # 禁止存储


@dataclass
class SensitiveMatch:
    """敏感信息匹配结果"""
    pattern_type: str
    matched_text: str
    start_pos: int
    end_pos: int
    suggestion: str


@dataclass
class MemoryAudit:
    """记忆审计结果"""
    file_path: str
    level: MemoryLevel
    passed: bool
    sensitive_matches: List[SensitiveMatch]
    warnings: List[str]
    suggestions: List[str]


class MemoryFence:
    """记忆围栏 - 敏感信息检测和安全审查"""
    
    # 敏感模式定义
    SENSITIVE_PATTERNS = {
        # API Keys
        "openai_key": {
            "pattern": r'sk-[A-Za-z0-9]{20,}',
            "description": "OpenAI API Key",
            "example": "sk-1234567890abcdefghij",
            "severity": "high"
        },
        "anthropic_key": {
            "pattern": r'sk-ant-[A-Za-z0-9]{20,}',
            "description": "Anthropic API Key",
            "example": "sk-ant-1234567890abcdefghij",
            "severity": "high"
        },
        "aws_access_key": {
            "pattern": r'AKIA[0-9A-Z]{16}',
            "description": "AWS Access Key",
            "example": "AKIAIOSFODNN7EXAMPLE",
            "severity": "critical"
        },
        "aws_secret_key": {
            "pattern": r'[A-Za-z0-9/+=]{40}',
            "description": "AWS Secret Key",
            "example": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "severity": "critical"
        },
        "github_token": {
            "pattern": r'ghp_[A-Za-z0-9]{36,}',
            "description": "GitHub Personal Access Token",
            "example": "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
            "severity": "high"
        },
        "slack_token": {
            "pattern": r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}[a-zA-Z0-9-]*',
            "description": "Slack Token",
            "example": "xoxb-1234567890123-1234567890123-abcdefghijklmnop",
            "severity": "high"
        },
        "stripe_key": {
            "pattern": r'sk_live_[A-Za-z0-9]{24,}',
            "description": "Stripe Live Key",
            "example": "sk_live_abcdefghijklmnopqrstuvwx",
            "severity": "critical"
        },
        "generic_secret": {
            "pattern": r'(?i)(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*[\'"]?[A-Za-z0-9_\-]{20,}[\'"]?',
            "description": "Generic API Key/Secret",
            "example": "api_key = 'your-secret-key-here'",
            "severity": "medium"
        },
        
        # Passwords
        "password_assignment": {
            "pattern": r'(?i)(password|passwd|pwd)\s*[:=]\s*[\'"]?.{6,}[\'"]?',
            "description": "Password Assignment",
            "example": "password = 'mypassword123'",
            "severity": "high"
        },
        "db_connection": {
            "pattern": r'(?i)(mysql|postgres|mongodb|redis):\/\/[^\s\'"]+:[^\s\'"]+@',
            "description": "Database Connection String",
            "example": "mysql://user:password@localhost:3306/db",
            "severity": "high"
        },
        
        # Private Information
        "email": {
            "pattern": r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            "description": "Email Address",
            "example": "user@example.com",
            "severity": "low"
        },
        "phone_number": {
            "pattern": r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            "description": "Phone Number",
            "example": "+1 (555) 123-4567",
            "severity": "medium"
        },
        "credit_card": {
            "pattern": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            "description": "Credit Card Number",
            "example": "1234-5678-9012-3456",
            "severity": "critical"
        },
        "ssn": {
            "pattern": r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
            "description": "Social Security Number",
            "example": "123-45-6789",
            "severity": "critical"
        },
        
        # Tokens/Sessions
        "jwt_token": {
            "pattern": r'eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',
            "description": "JWT Token",
            "example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "severity": "high"
        },
        "bearer_token": {
            "pattern": r'Bearer\s+[A-Za-z0-9_\-\.]+',
            "description": "Bearer Token",
            "example": "Bearer abc123def456ghi789",
            "severity": "medium"
        },
    }
    
    # 建议排除的文件模式
    EXCLUDED_PATTERNS = [
        r'\.git/',
        r'node_modules/',
        r'__pycache__/',
        r'\.venv/',
        r'venv/',
        r'\.env$',
        r'\.key$',
        r'\.pem$',
        r'\.crt$',
    ]
    
    def __init__(self, memory_dir: Optional[str] = None):
        if memory_dir is None:
            memory_dir = os.path.expanduser("~/.openclaw/projects/MimirAether")
        self.memory_dir = memory_dir
    
    def scan_file(self, file_path: str) -> MemoryAudit:
        """扫描单个文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            MemoryAudit: 审计结果
        """
        matches = []
        warnings = []
        suggestions = []
        
        # 读取文件
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            return MemoryAudit(
                file_path=file_path,
                level=MemoryLevel.RESTRICTED,
                passed=False,
                sensitive_matches=[],
                warnings=[f"无法读取文件: {e}"],
                suggestions=["检查文件权限"]
            )
        
        # 检查排除模式
        for pattern in self.EXCLUDED_PATTERNS:
            if re.search(pattern, file_path):
                return MemoryAudit(
                    file_path=file_path,
                    level=MemoryLevel.PUBLIC,
                    passed=True,
                    sensitive_matches=[],
                    warnings=[],
                    suggestions=["文件已排除敏感检查"]
                )
        
        # 扫描敏感信息
        for pattern_name, pattern_info in self.SENSITIVE_PATTERNS.items():
            for match in re.finditer(pattern_info["pattern"], content):
                matched_text = match.group()
                
                # 计算位置
                start_pos = match.start()
                end_pos = match.end()
                
                # 计算行号
                line_num = content[:start_pos].count('\n') + 1
                
                # 生成建议
                suggestion = self._get_suggestion(pattern_name, matched_text)
                
                matches.append(SensitiveMatch(
                    pattern_type=pattern_name,
                    matched_text=matched_text[:50] + "..." if len(matched_text) > 50 else matched_text,
                    start_pos=start_pos,
                    end_pos=end_pos,
                    suggestion=suggestion
                ))
                
                suggestions.append(
                    f"第{line_num}行: {pattern_info['description']} - {suggestion}"
                )
        
        # 确定记忆级别
        max_severity = self._get_max_severity(matches)
        level = self._severity_to_level(max_severity)
        
        passed = (level in [MemoryLevel.PUBLIC, MemoryLevel.PRIVATE] 
                  and len(matches) == 0)
        
        return MemoryAudit(
            file_path=file_path,
            level=level,
            passed=passed,
            sensitive_matches=matches,
            warnings=warnings,
            suggestions=suggestions
        )
    
    def scan_directory(self, subdirs: Optional[List[str]] = None) -> List[MemoryAudit]:
        """扫描目录
        
        Args:
            subdirs: 子目录列表，默认扫描主要目录
            
        Returns:
            list: 审计结果列表
        """
        if subdirs is None:
            subdirs = ["learnings", "sessions"]
        
        results = []
        
        for subdir in subdirs:
            dir_path = os.path.join(self.memory_dir, subdir)
            if not os.path.exists(dir_path):
                continue
            
            for root, _, files in os.walk(dir_path):
                for filename in files:
                    if filename.startswith('.'):
                        continue
                    
                    file_path = os.path.join(root, filename)
                    if filename.endswith(('.md', '.txt', '.json', '.py', '.yaml', '.yml')):
                        result = self.scan_file(file_path)
                        results.append(result)
        
        return results
    
    def audit_all(self) -> Dict[str, List[MemoryAudit]]:
        """审计所有记忆文件
        
        Returns:
            dict: 按敏感级别分类的结果
        """
        all_results = self.scan_directory()
        
        classified = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
            "passed": []
        }
        
        for result in all_results:
            if not result.passed:
                severity = self._level_to_severity(result.level)
                if severity in classified:
                    classified[severity].append(result)
            else:
                classified["passed"].append(result)
        
        return classified
    
    def _get_max_severity(self, matches: List[SensitiveMatch]) -> str:
        """获取最高严重级别"""
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        
        max_level = "none"
        max_score = 0
        
        for match in matches:
            pattern_info = self.SENSITIVE_PATTERNS.get(match.pattern_type, {})
            severity = pattern_info.get("severity", "low")
            score = severity_order.get(severity, 0)
            
            if score > max_score:
                max_score = score
                max_level = severity
        
        return max_level if max_level != "none" else "low"
    
    def _severity_to_level(self, severity: str) -> MemoryLevel:
        """转换严重级别到记忆级别"""
        mapping = {
            "critical": MemoryLevel.RESTRICTED,
            "high": MemoryLevel.SENSITIVE,
            "medium": MemoryLevel.PRIVATE,
            "low": MemoryLevel.PRIVATE
        }
        return mapping.get(severity, MemoryLevel.PRIVATE)
    
    def _level_to_severity(self, level: MemoryLevel) -> str:
        """转换记忆级别到严重级别"""
        mapping = {
            MemoryLevel.RESTRICTED: "critical",
            MemoryLevel.SENSITIVE: "high",
            MemoryLevel.PRIVATE: "medium",
            MemoryLevel.PUBLIC: "low"
        }
        return mapping.get(level, "low")
    
    def _get_suggestion(self, pattern_type: str, matched_text: str) -> str:
        """获取处理建议"""
        suggestions = {
            "openai_key": "使用环境变量或Hermes凭证池管理",
            "anthropic_key": "使用环境变量或Hermes凭证池管理",
            "aws_access_key": "使用IAM角色替代硬编码密钥",
            "aws_secret_key": "使用AWS Secrets Manager",
            "github_token": "使用GitHub Actions secrets",
            "slack_token": "使用Slack OAuth或旋转令牌",
            "stripe_key": "使用服务端API密钥管理",
            "generic_secret": "使用密钥管理服务",
            "password_assignment": "使用密码管理器或环境变量",
            "db_connection": "使用连接池和密钥管理",
            "email": "考虑是否需要脱敏",
            "phone_number": "考虑是否需要脱敏",
            "credit_card": "立即删除，使用支付网关",
            "ssn": "立即删除，不应存储SSN",
            "jwt_token": "避免在日志中记录JWT",
            "bearer_token": "使用安全的token存储"
        }
        return suggestions.get(pattern_type, "考虑移除或脱敏")
    
    def generate_report(self) -> str:
        """生成审计报告
        
        Returns:
            str: 格式化报告
        """
        classified = self.audit_all()
        
        lines = [
            "=" * 60,
            "MimirAether 记忆围栏审计报告",
            "=" * 60,
            ""
        ]
        
        # 汇总统计
        total = sum(len(v) for v in classified.values())
        passed_count = len(classified["passed"])
        
        lines.extend([
            f"【审计统计】",
            f"  总文件数: {total}",
            f"  通过检查: {passed_count}",
            f"  发现问题: {total - passed_count}",
            ""
        ])
        
        # 关键问题
        if classified["critical"]:
            lines.append("【🚨 CRITICAL - 必须立即处理】")
            for result in classified["critical"]:
                lines.append(f"  文件: {result.file_path}")
                for s in result.suggestions:
                    lines.append(f"    → {s}")
            lines.append("")
        
        if classified["high"]:
            lines.append("【⚠️ HIGH - 建议尽快处理】")
            for result in classified["high"]:
                lines.append(f"  文件: {result.file_path}")
                for s in result.suggestions[:3]:  # 限制显示数量
                    lines.append(f"    → {s}")
            lines.append("")
        
        if classified["medium"]:
            lines.append("【📋 MEDIUM - 建议检查】")
            lines.append(f"  {len(classified['medium'])} 个文件需要审查")
            lines.append("")
        
        # 通过的文件
        if classified["passed"]:
            lines.append(f"【✓ 通过】{len(classified['passed'])} 个文件安全")
        
        lines.extend([
            "",
            "=" * 60
        ])
        
        return "\n".join(lines)


# CLI
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MimirAether Memory Fence")
    parser.add_argument("--dir", type=str, help="指定记忆目录")
    parser.add_argument("--file", type=str, help="扫描单个文件")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    
    args = parser.parse_args()
    
    fence = MemoryFence(args.dir)
    
    if args.file:
        result = fence.scan_file(args.file)
        print(f"文件: {result.file_path}")
        print(f"级别: {result.level.value}")
        print(f"通过: {result.passed}")
        print(f"问题数: {len(result.sensitive_matches)}")
        for s in result.suggestions:
            print(f"  → {s}")
    else:
        print(fence.generate_report())

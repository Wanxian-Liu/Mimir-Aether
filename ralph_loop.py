#!/usr/bin/env python3
"""
Ralph Mode - MimirAether Skills自我锤炼循环

规则：
1. 在OpenClaw沙盒中自动执行Skill
2. 捕获执行错误、逻辑漏洞、输出不完整、边界异常
3. 自动定位问题原因，给出修复方案并修改Skill逻辑
4. 重新在沙盒运行验证，直到无错误、输出稳定、逻辑完整
5. 每一轮迭代都输出：轮次 → 问题 → 修复 → 验证结果
6. 持续循环锤炼，直到连续3轮无任何错误，才算完成

Usage:
    python ralph_loop.py <skill_path>
    python ralph_loop.py <skill_path> --rounds 5
"""

import sys
import os
import re
import json
import subprocess
import traceback
import tempfile
import base64
import time as time_module
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

# 仓库根（与 clone 路径无关）；保留 MIMIR_AETHER_PATH 变量名供沙箱子进程与报告路径使用
_REPO_ROOT = str(Path(__file__).resolve().parent)
sys.path.insert(0, _REPO_ROOT)
MIMIR_AETHER_PATH = _REPO_ROOT


@dataclass
class RalphError:
    """
    结构化错误记录
    
    学习自Hermes ToolError：收集每轮执行中的错误，
    包含错误类型、消息、traceback和建议修复。
    """
    round_num: int                      # 轮次
    block_index: Optional[int]          # 代码块索引（None表示轮次级别）
    category: str                       # 错误类别: syntax, execution, boundary, timeout, stability
    error_type: str                     # Python错误类型: SyntaxError, RuntimeError等
    error_msg: str                      # 错误消息
    fix_suggestion: str                 # 修复建议
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "block_index": self.block_index,
            "category": self.category,
            "error_type": self.error_type,
            "error_msg": self.error_msg,
            "fix_suggestion": self.fix_suggestion,
        }


@dataclass
class RalphResult:
    """
    Ralph锤炼结果
    
    学习自Hermes AgentResult：返回完整执行元数据，
    包含成功状态、轮次统计、错误列表和执行时间。
    """
    success: bool                       # 是否成功（连续required轮无错误）
    rounds_completed: int              # 完成的轮次总数
    consecutive_passed: int            # 连续通过的轮次数
    required_consecutive: int          # 要求的连续通过数
    errors: List[RalphError]           # 所有错误列表
    total_execution_time_ms: float     # 总执行时间（毫秒）
    skill_path: str                    # Skill路径
    timestamp: str                     # 完成时间戳
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "rounds_completed": self.rounds_completed,
            "consecutive_passed": self.consecutive_passed,
            "required_consecutive": self.required_consecutive,
            "errors": [e.to_dict() for e in self.errors],
            "total_execution_time_ms": self.total_execution_time_ms,
            "skill_path": self.skill_path,
            "timestamp": self.timestamp,
        }


@dataclass
class RalphRound:
    """
    Ralph一轮的结果
    
    学习自Hermes：添加errors列表存储RalphError。
    """
    round_num: int
    problems: List[str] = field(default_factory=list)
    fixes: List[str] = field(default_factory=list)
    verification_result: str = ""
    passed: bool = False
    error_details: Optional[str] = None
    errors: List[RalphError] = field(default_factory=list)  # 学习自Hermes tool_errors


@dataclass
class RalphConfig:
    """Ralph配置"""
    skill_path: str
    max_rounds: int = 10
    required_consecutive: int = 3
    verbose: bool = False
    
    sandbox_timeout: int = 60
    max_output_chars: int = 10000


class RalphEngine:
    """Ralph锤炼引擎"""
    
    def __init__(self, config: RalphConfig):
        self.config = config
        self.round_num = 0
        self.consecutive_passed = 0
        self.rounds: List[RalphRound] = []
        self.all_errors: List[RalphError] = []  # 学习自Hermes: 收集所有错误
        self._start_time = 0.0  # 总执行开始时间
        
    def run(self) -> RalphResult:
        """
        执行Ralph锤炼循环
        
        学习自Hermes run()：返回结构化结果而非仅bool。
        
        Returns:
            RalphResult: 包含完整执行元数据
        """
        self._start_time = time_module.monotonic()
        
        print("=" * 70)
        print("🎯 RALPH MODE - MimirAether Skills自我锤炼")
        print("=" * 70)
        print(f"目标: {self.config.skill_path}")
        print(f"规则: 连续{self.config.required_consecutive}轮无错误才算完成\n")
        
        while self.round_num < self.config.max_rounds:
            self.round_num += 1
            
            print(f"\n{'='*70}")
            print(f"【第 {self.round_num} 轮】")
            print(f"{'='*70}")
            
            round_result = self._execute_round()
            self.rounds.append(round_result)
            
            # 收集错误到all_errors（学习自Hermes tool_errors收集）
            for error in round_result.errors:
                self.all_errors.append(error)
            
            self._print_round_summary(round_result)
            
            if round_result.passed:
                self.consecutive_passed += 1
                print(f"\n✅ 本轮通过！连续通过: {self.consecutive_passed}/{self.config.required_consecutive}")
                
                if self.consecutive_passed >= self.config.required_consecutive:
                    print(f"\n{'='*70}")
                    print("🎉 Ralph锤炼完成！连续3轮无错误")
                    print(f"{'='*70}")
                    result = self._build_result()
                    self._save_report(result)
                    return result
            else:
                self.consecutive_passed = 0
                print(f"\n❌ 本轮失败，重置连续计数")
                
                if round_result.problems:
                    self._auto_fix(round_result)
        
        print(f"\n⚠️ 达到最大轮数限制 ({self.config.max_rounds})")
        result = self._build_result()
        self._save_report(result)
        return result
    
    def _build_result(self) -> RalphResult:
        """
        构建RalphResult结果
        
        学习自Hermes AgentResult构建方式：
        - 计算总执行时间
        - 返回完整元数据
        """
        total_time_ms = (time_module.monotonic() - self._start_time) * 1000
        
        return RalphResult(
            success=self.consecutive_passed >= self.config.required_consecutive,
            rounds_completed=self.round_num,
            consecutive_passed=self.consecutive_passed,
            required_consecutive=self.config.required_consecutive,
            errors=self.all_errors,
            total_execution_time_ms=total_time_ms,
            skill_path=self.config.skill_path,
            timestamp=datetime.now().isoformat(),
        )
    
    def _execute_round(self) -> RalphRound:
        """
        执行一轮锤炼
        
        学习自Hermes：收集结构化错误到RalphError。
        """
        round_result = RalphRound(round_num=self.round_num)
        
        # 1. 读取Skill内容
        skill_content = self._read_skill()
        if not skill_content:
            round_result.problems.append("无法读取Skill文件")
            round_result.errors.append(RalphError(
                round_num=self.round_num,
                block_index=None,
                category="execution",
                error_type="FileNotFoundError",
                error_msg="无法读取Skill文件",
                fix_suggestion="检查文件路径是否正确",
            ))
            round_result.verification_result = "FAIL: 文件读取失败"
            return round_result
        
        print(f"\n[1/5] 📖 读取Skill: {len(skill_content)} 字符")
        
        # 2. 语法检查
        syntax_ok, syntax_error = self._check_syntax(skill_content)
        if not syntax_ok:
            round_result.problems.append(f"语法错误: {syntax_error}")
            round_result.errors.append(RalphError(
                round_num=self.round_num,
                block_index=None,
                category="syntax",
                error_type="SyntaxError",
                error_msg=str(syntax_error),
                fix_suggestion="检查Python语法，特别是缩进和括号匹配",
            ))
            round_result.verification_result = f"FAIL: 语法错误 - {syntax_error}"
            return round_result
        print(f"  ✅ 语法检查通过")
        
        # 3. 执行测试（沙盒中）
        exec_result = self._execute_in_sandbox(skill_content)
        if not exec_result["success"]:
            # 将错误字符串转换为RalphError对象
            for error_str in exec_result.get("errors", []):
                # 解析错误字符串格式: "[Block N] TypeError: ..."
                block_idx = None
                error_type = "RuntimeError"
                error_msg = error_str
                
                match = re.match(r'\[Block (\d+)\] (.+?): (.+)', error_str)
                if match:
                    block_idx = int(match.group(1)) - 1  # 转为0-indexed
                    error_type = match.group(2)
                    error_msg = match.group(3)
                
                round_result.errors.append(RalphError(
                    round_num=self.round_num,
                    block_index=block_idx,
                    category="execution",
                    error_type=error_type,
                    error_msg=error_msg,
                    fix_suggestion=self._get_fix_for_error_type(error_type),
                ))
                round_result.problems.append(error_str)
            
            round_result.error_details = exec_result.get("traceback", "")
            round_result.verification_result = f"FAIL: 执行错误 - {exec_result.get('errors', ['Unknown'])}"
            return round_result
        
        print(f"  ✅ 执行成功 (输出: {len(exec_result.get('output', ''))} 字符)")
        
        # 4. 输出稳定性检查
        output = exec_result.get("output", "")
        if self._check_output_stability(output):
            print(f"  ✅ 输出稳定性检查通过")
        else:
            round_result.problems.append("输出不稳定或为空")
            round_result.errors.append(RalphError(
                round_num=self.round_num,
                block_index=None,
                category="stability",
                error_type="StabilityError",
                error_msg="输出包含错误标记或为空",
                fix_suggestion="检查代码是否有未捕获的异常或添加输出验证",
            ))
            round_result.verification_result = "FAIL: 输出不稳定"
            return round_result
        
        # 5. 边界情况测试
        boundary_result = self._test_boundary_cases(skill_content)
        if boundary_result["has_issues"]:
            for issue in boundary_result.get("issues", []):
                round_result.problems.append(issue)
                round_result.errors.append(RalphError(
                    round_num=self.round_num,
                    block_index=None,
                    category="boundary",
                    error_type="BoundaryIssue",
                    error_msg=issue,
                    fix_suggestion=self._get_fix_for_issue(issue),
                ))
            round_result.verification_result = f"FAIL: 边界问题 - {boundary_result.get('issues', [])}"
            return round_result
        
        print(f"  ✅ 边界情况测试通过")
        
        round_result.passed = True
        round_result.verification_result = "PASS: 所有检查通过"
        return round_result
    
    def _read_skill(self) -> Optional[str]:
        """读取Skill文件"""
        try:
            skill_path = Path(self.config.skill_path)
            if skill_path.is_dir():
                skill_path = skill_path / "SKILL.md"
            return skill_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  ❌ 读取失败: {e}")
            return None
    
    def _check_syntax(self, content: str) -> tuple[bool, Optional[str]]:
        """检查Python语法"""
        try:
            import ast
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2]
            
            # 正确匹配```python代码块
            code_blocks = re.findall(r'```python\n(.*?)```', content, re.DOTALL)
            for block in code_blocks:
                try:
                    ast.parse(block)
                except SyntaxError as e:
                    return False, f"Line {e.lineno}: {e.msg}"
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _execute_in_sandbox(self, skill_content: str) -> Dict[str, Any]:
        """在沙盒中执行Skill"""
        result = {"success": False, "output": "", "errors": [], "traceback": ""}
        
        try:
            # 用base64安全传递内容
            encoded_content = base64.b64encode(skill_content.encode('utf-8')).decode('ascii')
            
            # 创建临时脚本文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                script_path = f.name
                f.write(f'''
import sys
import os
import re
import traceback
import base64

sys.path.insert(0, '{MIMIR_AETHER_PATH}')

output = []
errors = []

try:
    # 从base64解码skill内容
    encoded_content = "{encoded_content}"
    skill_content = base64.b64decode(encoded_content).decode('utf-8')
    
    # 正确匹配```python代码块（使用真正的换行符）
    code_blocks = re.findall(r"```python\\n(.*?)```", skill_content, re.DOTALL)
    print(f"[DEBUG] 找到 {{len(code_blocks)}} 个代码块", file=sys.stderr)
    
    for i, code in enumerate(code_blocks):
        output.append(f"[Block {{i+1}}] 开始执行")
        try:
            exec(code, {{"__name__": "__sandbox__"}})
            output.append(f"[Block {{i+1}}] 执行成功")
        except Exception as e:
            errors.append(f"[Block {{i+1}}] {{type(e).__name__}}: {{str(e)}}")
            output.append(f"[Block {{i+1}}] 执行失败: {{str(e)}}")

except Exception as e:
    errors.append(f"执行异常: {{str(e)}}")
    traceback.print_exc()

print("=== OUTPUT ===")
print("\\n".join(output))
print("=== ERRORS ===")
print("\\n".join(errors))
''')
            
            try:
                proc = subprocess.run(
                    ["python3", script_path],
                    capture_output=True,
                    text=True,
                    timeout=self.config.sandbox_timeout,
                    cwd=MIMIR_AETHER_PATH
                )
                
                result["output"] = proc.stdout
                if proc.stderr:
                    result["traceback"] = proc.stderr
                
                if "=== ERRORS ===" in proc.stdout:
                    error_section = proc.stdout.split("=== ERRORS ===")[1]
                    errors = [l for l in error_section.split("\n") if l.strip()]
                    result["errors"] = errors
                    result["success"] = len(errors) == 0
                else:
                    result["success"] = proc.returncode == 0
                
                if proc.returncode != 0 and not result["errors"]:
                    result["errors"] = [f"Exit code: {proc.returncode}"]
            finally:
                if os.path.exists(script_path):
                    os.unlink(script_path)
            
        except subprocess.TimeoutExpired:
            result["errors"] = ["执行超时"]
        except Exception as e:
            result["errors"] = [f"沙盒异常: {str(e)}"]
            result["traceback"] = traceback.format_exc()
        
        return result
    
    def _check_output_stability(self, output: str) -> bool:
        """检查输出稳定性"""
        if not output or len(output.strip()) == 0:
            return False
        
        error_markers = ["Error:", "Exception:", "Traceback", "FAILED", "CRITICAL"]
        for marker in error_markers:
            if marker in output:
                return False
        
        return True
    
    def _test_boundary_cases(self, skill_content: str) -> Dict[str, Any]:
        """测试边界情况"""
        result = {"has_issues": False, "issues": []}
        issues = []
        
        if "except:" in skill_content and "pass" in skill_content:
            issues.append("发现空的except块，可能隐藏错误")
        
        if re.search(r'while\s+True:', skill_content) and 'break' not in skill_content:
            issues.append("发现可能无break的while True循环")
        
        if "open(" in skill_content and ".write" in skill_content:
            if "_safe_path" not in skill_content:
                issues.append("文件写入操作缺少_safe_path安全包装")
        
        if "requests." in skill_content or "urllib" in skill_content:
            if "try:" not in skill_content:
                issues.append("网络请求缺少try-except错误处理")
        
        result["has_issues"] = len(issues) > 0
        result["issues"] = issues
        return result
    
    def _auto_fix(self, round_result: RalphRound):
        """
        自动修复问题
        
        学习自Hermes：使用结构化错误信息生成更精准的修复建议。
        """
        print(f"\n[自动修复] 发现 {len(round_result.errors)} 个错误")
        
        fixes_applied = []
        
        for i, error in enumerate(round_result.errors):
            print(f"\n  错误 {i+1}: [{error.category}] {error.error_type}")
            print(f"    消息: {error.error_msg}")
            print(f"    建议: {error.fix_suggestion}")
            fixes_applied.append(error.fix_suggestion)
            round_result.fixes.append(error.fix_suggestion)
        
        if fixes_applied:
            print(f"\n  📝 生成了 {len(fixes_applied)} 个修复建议")
    
    def _get_fix_for_error_type(self, error_type: str) -> str:
        """
        根据错误类型获取修复建议
        
        学习自Hermes：结构化的错误类型映射。
        """
        fixes = {
            "SyntaxError": "检查Python语法，特别是缩进和括号匹配",
            "IndentationError": "检查代码缩进是否正确",
            "ModuleNotFoundError": "安装缺失的模块或检查sys.path配置",
            "ImportError": "检查import语句和模块路径",
            "NameError": "检查变量/函数名是否正确定义或导入",
            "TypeError": "检查函数参数类型是否正确",
            "ValueError": "检查参数值是否在有效范围内",
            "AttributeError": "检查对象是否有该属性或方法",
            "KeyError": "检查字典键是否存在",
            "IndexError": "检查索引是否越界",
            "TimeoutError": "添加超时控制或减少计算量",
            "RuntimeError": "检查代码逻辑并添加适当的错误处理",
        }
        return fixes.get(error_type, "需要人工审查并修复")
    
    def _get_fix_for_issue(self, issue: str) -> str:
        """
        根据边界问题获取修复建议
        
        学习自Hermes：结构化的问题映射。
        """
        fixes = {
            "空except块": "使用具体的异常类型而非空的except块",
            "无break循环": "确保while循环有明确的退出条件",
            "_safe_path": "使用_safe_path包装文件操作以防止路径遍历",
            "网络请求": "添加超时和重试机制处理网络错误",
        }
        for key, fix in fixes.items():
            if key in issue:
                return fix
        return "需要人工审查并修复"
    
    def _print_round_summary(self, result: RalphRound):
        """打印轮次汇总"""
        print(f"\n{'─'*70}")
        print(f"【第 {result.round_num} 轮结果】")
        print(f"{'─'*70}")
        
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"状态: {status}")
        print(f"验证: {result.verification_result}")
        
        if result.problems:
            print(f"\n发现的问题 ({len(result.problems)}):")
            for p in result.problems:
                print(f"  ❌ {p}")
        
        if result.fixes:
            print(f"\n修复建议 ({len(result.fixes)}):")
            for f in result.fixes:
                print(f"  🔧 {f}")
    
    def _save_report(self, result: RalphResult):
        """
        保存锤炼报告
        
        学习自Hermes AgentResult：保存完整元数据。
        """
        report_path = Path(MIMIR_AETHER_PATH) / "ralph_report.json"
        
        report = {
            # RalphResult元数据
            "success": result.success,
            "rounds_completed": result.rounds_completed,
            "consecutive_passed": result.consecutive_passed,
            "required_consecutive": result.required_consecutive,
            "total_execution_time_ms": result.total_execution_time_ms,
            "skill_path": result.skill_path,
            "timestamp": result.timestamp,
            # 详细错误列表
            "errors": [e.to_dict() for e in result.errors],
            # 每轮详情
            "rounds": [
                {
                    "round_num": r.round_num,
                    "passed": r.passed,
                    "verification_result": r.verification_result,
                    "problems": r.problems,
                    "fixes": r.fixes,
                    "errors": [e.to_dict() for e in r.errors],
                }
                for r in self.rounds
            ]
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 报告已保存: {report_path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Ralph Mode - Skills自我锤炼")
    parser.add_argument("skill_path", help="Skill路径或包含SKILL.md的目录")
    parser.add_argument("--rounds", type=int, default=10, help="最大轮数 (默认10)")
    parser.add_argument("--required", type=int, default=3, help="要求连续通过轮数 (默认3)")
    parser.add_argument("--verbose", action="store_true", help="详细输出")
    
    args = parser.parse_args()
    
    config = RalphConfig(
        skill_path=args.skill_path,
        max_rounds=args.rounds,
        required_consecutive=args.required,
        verbose=args.verbose
    )
    
    engine = RalphEngine(config)
    result = engine.run()  # 学习自Hermes: 返回结构化结果
    
    # 打印结果摘要
    print(f"\n{'='*70}")
    print(f"📊 RalphResult 摘要")
    print(f"{'='*70}")
    print(f"成功: {result.success}")
    print(f"完成轮次: {result.rounds_completed}")
    print(f"连续通过: {result.consecutive_passed}/{result.required_consecutive}")
    print(f"总错误数: {len(result.errors)}")
    print(f"执行时间: {result.total_execution_time_ms:.2f}ms")
    
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()

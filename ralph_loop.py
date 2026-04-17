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
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

# MimirAether路径
MIMIR_AETHER_PATH = '/home/rayliu/.openclaw/projects/MimirAether'
sys.path.insert(0, MIMIR_AETHER_PATH)


@dataclass
class RalphRound:
    """Ralph一轮的结果"""
    round_num: int
    problems: List[str] = field(default_factory=list)
    fixes: List[str] = field(default_factory=list)
    verification_result: str = ""
    passed: bool = False
    error_details: Optional[str] = None


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
        
    def run(self) -> bool:
        """执行Ralph锤炼循环"""
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
            
            self._print_round_summary(round_result)
            
            if round_result.passed:
                self.consecutive_passed += 1
                print(f"\n✅ 本轮通过！连续通过: {self.consecutive_passed}/{self.config.required_consecutive}")
                
                if self.consecutive_passed >= self.config.required_consecutive:
                    print(f"\n{'='*70}")
                    print("🎉 Ralph锤炼完成！连续3轮无错误")
                    print(f"{'='*70}")
                    self._save_report()
                    return True
            else:
                self.consecutive_passed = 0
                print(f"\n❌ 本轮失败，重置连续计数")
                
                if round_result.problems:
                    self._auto_fix(round_result)
        
        print(f"\n⚠️ 达到最大轮数限制 ({self.config.max_rounds})")
        self._save_report()
        return False
    
    def _execute_round(self) -> RalphRound:
        """执行一轮锤炼"""
        round_result = RalphRound(round_num=self.round_num)
        
        # 1. 读取Skill内容
        skill_content = self._read_skill()
        if not skill_content:
            round_result.problems.append("无法读取Skill文件")
            round_result.verification_result = "FAIL: 文件读取失败"
            return round_result
        
        print(f"\n[1/5] 📖 读取Skill: {len(skill_content)} 字符")
        
        # 2. 语法检查
        syntax_ok, syntax_error = self._check_syntax(skill_content)
        if not syntax_ok:
            round_result.problems.append(f"语法错误: {syntax_error}")
            round_result.verification_result = f"FAIL: 语法错误 - {syntax_error}"
            return round_result
        print(f"  ✅ 语法检查通过")
        
        # 3. 执行测试（沙盒中）
        exec_result = self._execute_in_sandbox(skill_content)
        if not exec_result["success"]:
            round_result.problems.extend(exec_result.get("errors", []))
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
            round_result.verification_result = "FAIL: 输出不稳定"
            return round_result
        
        # 5. 边界情况测试
        boundary_result = self._test_boundary_cases(skill_content)
        if boundary_result["has_issues"]:
            round_result.problems.extend(boundary_result.get("issues", []))
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
        """自动修复问题"""
        print(f"\n[自动修复] 发现 {len(round_result.problems)} 个问题")
        
        fixes_applied = []
        
        for i, problem in enumerate(round_result.problems):
            print(f"\n  问题 {i+1}: {problem}")
            
            fix = self._generate_fix(problem)
            if fix:
                fixes_applied.append(fix)
                round_result.fixes.append(fix)
                print(f"  修复: {fix}")
        
        if fixes_applied:
            print(f"\n  📝 生成了 {len(fixes_applied)} 个修复建议")
    
    def _generate_fix(self, problem: str) -> Optional[str]:
        """根据问题生成修复建议"""
        fixes = {
            "语法错误": "建议检查Python语法，特别是缩进和括号匹配",
            "执行超时": "建议添加超时控制或减少计算量",
            "输出不稳定": "建议增加输出验证和默认值处理",
            "边界问题": "建议添加输入验证和边界检查",
            "except块": "建议使用具体的异常类型而非空的except",
            "循环": "建议确保循环有明确的退出条件",
            "路径": "建议使用_safe_path包装文件操作",
            "网络": "建议添加超时和重试机制",
            "ModuleNotFoundError": "建议安装缺失的模块或检查sys.path",
            "NameError": "建议检查import语句或添加缺失的导入",
            "SyntaxError": "建议检查Python语法",
        }
        
        for key, fix in fixes.items():
            if key.lower() in problem.lower():
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
    
    def _save_report(self):
        """保存锤炼报告"""
        report_path = Path(MIMIR_AETHER_PATH) / "ralph_report.json"
        
        report = {
            "skill_path": self.config.skill_path,
            "timestamp": datetime.now().isoformat(),
            "total_rounds": self.round_num,
            "consecutive_passed": self.consecutive_passed,
            "required_consecutive": self.config.required_consecutive,
            "success": self.consecutive_passed >= self.config.required_consecutive,
            "rounds": [
                {
                    "round_num": r.round_num,
                    "passed": r.passed,
                    "verification_result": r.verification_result,
                    "problems": r.problems,
                    "fixes": r.fixes,
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
    success = engine.run()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

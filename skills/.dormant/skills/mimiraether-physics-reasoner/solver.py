"""物理求解引擎 — SymPy 推导 + NumPy 数值计算

核心流程：
  PhysicsQuery → FormulaMatcher → SymPy求解 → NumPy计算 → Solution
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import math

import sympy as sp
import numpy as np

try:
    from .formulas.mechanics import Formula, match_formula, MECHANICS_FORMULAS
except ImportError:
    from formulas.mechanics import Formula, match_formula, MECHANICS_FORMULAS


# ── 数据结构 ────────────────────────────────────────

@dataclass
class PhysicsQuery:
    """物理求解请求"""
    domain: str           # "kinematics" / "dynamics" / "energy" / "momentum"
    given: dict           # {"mass": 5, "height": 10, "g": 9.8}
    target: str           # "velocity" / "time" / "force" / ...


@dataclass
class Solution:
    """求解结果"""
    result: float
    unit: str
    formula_used: str
    steps: list = field(default_factory=list)
    success: bool = True
    error: str = ""


# ── 单位映射 ────────────────────────────────────────

_UNIT_MAP = {
    "v": "m/s", "v0": "m/s", "v1": "m/s", "v2": "m/s",
    "v1_before": "m/s", "v2_before": "m/s", "v1_after": "m/s", "v2_after": "m/s",
    "v1": "m/s",
    "x": "m", "h": "m", "h1": "m", "h2": "m",
    "H": "m", "R": "m", "L": "m",
    "t": "s", "T": "s",
    "a": "m/s²",
    "F": "N", "F_parallel": "N",
    "E_k": "J", "E_p": "J",
    "p": "kg·m/s",
    "m": "kg", "m1": "kg", "m2": "kg",
    "g": "m/s²",
    "k": "N/m",
    "mu": "",
    "theta": "rad",
}


class PhysicsSolver:
    """物理求解器

    使用 SymPy 做符号推导，NumPy 做数值计算。
    LLM 不参与中间计算——只在入口做路由、出口做解释。
    """

    # 预定义 SymPy 符号（所有公式中共用的基本物理量）
    SYMBOLS = {
        "g": sp.Symbol("g", positive=True),
        "m": sp.Symbol("m", positive=True),
        "m1": sp.Symbol("m1", positive=True),
        "m2": sp.Symbol("m2", positive=True),
        "h": sp.Symbol("h"),
        "h1": sp.Symbol("h1"),
        "h2": sp.Symbol("h2"),
        "v": sp.Symbol("v"),
        "v0": sp.Symbol("v0"),
        "v1": sp.Symbol("v1"),
        "v1_before": sp.Symbol("v1_before"),
        "v2_before": sp.Symbol("v2_before"),
        "v1_after": sp.Symbol("v1_after"),
        "v2_after": sp.Symbol("v2_after"),
        "v2": sp.Symbol("v2"),
        "a": sp.Symbol("a"),
        "t": sp.Symbol("t"),
        "x": sp.Symbol("x"),
        "theta": sp.Symbol("theta", nonnegative=True),
        "F": sp.Symbol("F"),
        "F_parallel": sp.Symbol("F_parallel"),
        "mu": sp.Symbol("mu", nonnegative=True),
        "k": sp.Symbol("k", positive=True),
        "p": sp.Symbol("p"),
        "E_k": sp.Symbol("E_k"),
        "E_p": sp.Symbol("E_p"),
        "T": sp.Symbol("T", positive=True),
        "R": sp.Symbol("R"),
        "H": sp.Symbol("H"),
        "L": sp.Symbol("L", positive=True),
        "N": sp.Symbol("N"),
        "omega": sp.Symbol("omega"),
    }

    def __init__(self, formulas: list[Formula] = None):
        self.formulas = formulas or MECHANICS_FORMULAS

    def solve(self, query: PhysicsQuery) -> Solution:
        """主求解入口。

        Args:
            query: 物理问题（领域 + 已知量 + 目标量）

        Returns:
            Solution 含结果数值、单位、公式、步骤
        """
        # Step 1: 公式匹配
        candidates = match_formula(query.domain, query.given, query.target)
        if not candidates:
            return Solution(
                result=0, unit="", formula_used="",
                success=False,
                error=f"无匹配公式: domain={query.domain}, target={query.target}"
            )

        formula = candidates[0]

        # Step 2: 选择表达式（主表达式或变体）
        expr_str = formula.expression
        sym_target = _target_to_symbol(formula.target)
        if sym_target and sym_target.name not in query.given:
            # 尝试变体
            var_key = query.target if query.target in formula.variants else sym_target.name if sym_target and sym_target.name in formula.variants else None
            if not var_key:
                # 进一步映射 target → symbol name
                var_key = _target_to_symbol_name(query.target)
            if var_key and var_key in formula.variants:
                expr_str = formula.variants[var_key]

        # Step 3: SymPy 符号推导
        try:
            # 使用 self.SYMBOLS 作为 locals，确保 sp.sympify 解析出的
            # 符号与 subs_dict 中的符号是同一对象
            lhs_str = expr_str.split("=")[0].strip()
            rhs_str = "=".join(expr_str.split("=")[1:]).strip()
            lhs = sp.sympify(lhs_str, locals=self.SYMBOLS)
            rhs = sp.sympify(rhs_str, locals=self.SYMBOLS)
            eq = sp.Eq(lhs, rhs)

            # 代入已知值 — 键与 sp.sympify 使用的符号一致
            subs_dict = {}
            for key, val in query.given.items():
                sym = self.SYMBOLS.get(key)
                if sym is None:
                    sym = sp.Symbol(key)
                subs_dict[sym] = val

            # 求解目标变量（统一符号）
            target_sym = self.SYMBOLS.get(sym_target.name if sym_target else query.target)
            if target_sym is None:
                target_sym = sp.Symbol(query.target)

            # 代入已知量后求解
            eq_substituted = eq.subs(subs_dict)
            solutions = sp.solve(eq_substituted, target_sym, dict=True)

            if not solutions:
                return Solution(
                    result=0, unit="", formula_used=formula.name,
                    success=False,
                    error=f"SymPy 无解: {eq_substituted} = 0 对 {target_sym} 无实数解"
                )

            # 取第一个有效解（正数优先）
            result_val = None
            for sol in solutions:
                val_expr = sol[target_sym]
                try:
                    numeric_val = float(val_expr.evalf())
                    if np.isfinite(numeric_val) and not np.iscomplex(numeric_val):
                        if result_val is None or (numeric_val > 0 and result_val <= 0):
                            result_val = numeric_val
                except (TypeError, ValueError, AttributeError):
                    continue

            if result_val is None:
                return Solution(
                    result=0, unit="", formula_used=formula.name,
                    success=False,
                    error=f"SymPy 解出但无法转为数值: {solutions}"
                )

            # Step 4: 约束验证
            for constraint in formula.constraints:
                c_expr = sp.sympify(constraint)
                c_sub = c_expr.subs({target_sym: result_val, **subs_dict})
                try:
                    if not bool(c_sub):
                        return Solution(
                            result=result_val, unit="", formula_used=formula.name,
                            success=False,
                            error=f"违反约束: {constraint} (代入后={c_sub})"
                        )
                except TypeError:
                    pass  # 涉及未定义符号的约束无法验证

            # Step 5: 构建步骤
            unit = _get_unit(target_sym.name if hasattr(target_sym, 'name') else str(target_sym))
            steps = self._build_steps(formula, query.given, expr_str, result_val, unit)

            return Solution(
                result=round(result_val, 4),
                unit=unit,
                formula_used=formula.name,
                steps=steps,
            )

        except Exception as e:
            return Solution(
                result=0, unit="", formula_used=formula.name,
                success=False,
                error=f"求解异常: {type(e).__name__}: {e}"
            )

    def _build_steps(self, formula: Formula, given: dict, expr_str: str,
                     result: float, unit: str) -> list[str]:
        """构建自然语言步骤"""
        steps = []
        steps.append(f"1. 识别问题类型: {formula.description}")
        steps.append(f"2. 选定公式: {expr_str}")
        for key, val in given.items():
            steps.append(f"3. 已知 {key} = {val}")
        steps.append(f"4. 代入公式计算: {result} {unit}")
        return steps


def _target_to_symbol(target: str) -> Optional[sp.Symbol]:
    """目标变量名 → SymPy Symbol"""
    return PhysicsSolver.SYMBOLS.get(target)


def _target_to_symbol_name(target: str) -> Optional[str]:
    """目标变量名 → 符号名（反向映射常见术语）"""
    mapping = {
        "velocity": "v", "final_velocity": "v", "speed": "v",
        "displacement": "x", "distance": "x",
        "time": "t", "period": "T",
        "acceleration": "a",
        "force": "F", "parallel_force": "F_parallel",
        "kinetic_energy": "E_k", "potential_energy": "E_p",
        "momentum": "p",
        "range": "R", "max_height": "H",
        "v1_after": "v1_after", "v2_after": "v2_after",
        "v2": "v2",
    }
    return mapping.get(target, target)


def _get_unit(symbol_name: str) -> str:
    return _UNIT_MAP.get(symbol_name, "")

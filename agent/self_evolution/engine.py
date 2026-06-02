"""
SelfEvolutionEngine — JEPA Closed Loop for Code Self-Evolution

物理世界闭环:
    Encoder(场景→状态) → WorldModel(预测) → Cost(评估) → Planner(搜索) → Memory(记录)
    └──────────────────────────── 反馈 ←────────────────────────────────────┘

代码世界闭环:
    StateEncoder(agent/→依赖图) → EvolutionCost(IC+TC评估) →
    SafestPathPlanner(排序) → EvolutionMemory(记录结果)
    └────────────────── 下次规划参考历史 ←─────────────────────────────────┘

这是JEPA框架从物理领域到代码架构领域的迁移验证。
"""

import json
import os
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

from .state_encoder import StateEncoder, CodebaseState
from .cost import EvolutionCost, CostResult
from .planner import SafestPathPlanner, PlanResult
from .memory import EvolutionMemory, EvolutionRecord

logger = logging.getLogger(__name__)


@dataclass
class EvolutionReport:
    """演化闭环报告"""
    timestamp: float
    status: str                     # "healthy" | "evolved" | "blocked"
    state: Optional[CodebaseState] = None
    plan: Optional[PlanResult] = None
    record: Optional[EvolutionRecord] = None
    cycle_time_ms: float = 0.0
    summary: str = ""


class SelfEvolutionEngine:
    """
    JEPA 自我进化引擎

    用法:
        engine = SelfEvolutionEngine()
        report = engine.run_cycle(["skill_evolution.py"])
        print(report.summary)
    """

    def __init__(
        self,
        agent_dir: Optional[str] = None,
        memory_path: Optional[str] = None,
    ):
        self.encoder = StateEncoder(agent_dir)
        self.cost = EvolutionCost(self.encoder)
        self.memory = EvolutionMemory(persistence_path=memory_path)
        self.planner = SafestPathPlanner(self.encoder, self.cost, self.memory)

        self._cycle_count: int = 0
        self._last_report: Optional[EvolutionReport] = None

    def analyze(
        self, candidate_files: List[str],
        run_tier0: bool = False,
    ) -> Dict[str, Any]:
        """
        分析：不改任何代码，只评估和规划

        Args:
            candidate_files: 候选改动文件列表
            run_tier0: 是否运行 tier0 脚本（慢~35s，默认False）

        Returns:
            完整分析结果
        """
        # 1. 编码当前状态
        state = self.encoder.encode(force_refresh=True, run_tier0=run_tier0)
        state_summary = {
            "total_files": state.total_files,
            "total_lines": state.total_lines,
            "constraint_groups": list(state.constraint_map.keys()),
            "tier0_status": state.tier0_status,
        }

        # 2. 对每个候选文件评估代价
        cost_analysis = {}
        violations = []
        for fpath in candidate_files:
            result = self.cost.evaluate([fpath])
            cost_analysis[fpath] = {
                "passed": result.passed,
                "ic_cost": result.ic_cost,
                "tc_cost": result.tc_cost,
                "total_cost": result.total,
                "ic_violations": result.ic_violations,
                "tc_breakdown": result.tc_breakdown,
                "dependents": self.encoder.get_dependents(fpath),
                "fan_out": self.encoder.get_fan_out(fpath),
            }
            violations.extend(result.ic_violations)

        # 3. 规划
        plan = self.planner.plan(candidate_files)

        # 4. 记忆查询
        memory_hints = {}
        for fpath in candidate_files:
            history = self.memory.query_by_file(fpath, limit=3)
            if history:
                memory_hints[fpath] = [
                    {"outcome": r.outcome, "when": r.timestamp}
                    for r in history
                ]

        return {
            "state": state_summary,
            "cost_analysis": cost_analysis,
            "plan": {
                "recommended_order": plan.recommended_order,
                "ic_violations": plan.ic_violations,
                "safe_files": plan.safe_files,
                "total_cost": plan.total_cost,
                "notes": plan.notes,
            },
            "memory_hints": memory_hints,
            "cycle_count": self._cycle_count,
        }

    def run_cycle(
        self,
        candidate_files: List[str],
        execute_callback: Optional[Callable] = None,
        run_tier0: bool = False,
    ) -> EvolutionReport:
        """
        执行一次完整演化闭环

        Args:
            candidate_files: 候选改动文件
            execute_callback: 实际执行改动的回调 (可选)
                             签名: callback(file_path) -> {"outcome": str, "tier0": str}
            run_tier0: 是否运行 tier0 脚本（慢~35s，默认False）。
                       首次 run_cycle 建议传 True 以建立基线。

        Returns:
            EvolutionReport
        """
        t0 = time.time()
        self._cycle_count += 1

        # 1. 编码
        state = self.encoder.encode(force_refresh=True, run_tier0=run_tier0)

        # 2. 规划
        plan = self.planner.plan(candidate_files)

        # 3. 过滤被阻塞的文件
        actionable = [
            f for f in plan.recommended_order
            if self.memory.should_retry(f)
        ]

        # 4. 如果没有可执行的文件 → blocked
        if not actionable and plan.recommended_order:
            report = EvolutionReport(
                timestamp=time.time(),
                status="blocked",
                state=state,
                plan=plan,
                cycle_time_ms=(time.time() - t0) * 1000,
                summary=f"所有 {len(plan.recommended_order)} 个文件都被阻塞（连续失败次数过多），"
                        f"IC违规: {len(plan.ic_violations)}",
            )
            self._write_ledger_entry({
                "timestamp": time.time(),
                "cycle": self._cycle_count,
                "ok": 0,
                "status": "blocked",
                "candidates": candidate_files,
                "safe_files": 0,
                "ic_violations": len(plan.ic_violations),
                "recommended": plan.recommended_order[:3],
                "elapsed_ms": (time.time() - t0) * 1000,
                "reason": "all_files_blocked_by_memory_retry_limit",
            })
            self._last_report = report
            return report

        # 5. 如果没有安全文件 → 报告IC违规
        if not plan.safe_files:
            report = EvolutionReport(
                timestamp=time.time(),
                status="blocked",
                state=state,
                plan=plan,
                cycle_time_ms=(time.time() - t0) * 1000,
                summary=f"无安全文件可改。IC违规 ({len(plan.ic_violations)}): "
                        f"{'; '.join(plan.ic_violations[:3])}",
            )
            self._write_ledger_entry({
                "timestamp": time.time(),
                "cycle": self._cycle_count,
                "ok": 0,
                "status": "blocked",
                "candidates": candidate_files,
                "safe_files": 0,
                "ic_violations": len(plan.ic_violations),
                "elapsed_ms": (time.time() - t0) * 1000,
                "reason": "no_safe_files_ic_violations",
            })
            self._last_report = report
            return report

        # 6. 记录演化（不改代码，只评估）
        recommended = plan.recommended_order[0] if plan.recommended_order else ""
        record = EvolutionRecord(
            timestamp=time.time(),
            changes=[recommended] if recommended else [],
            ic_cost=0.0,
            tc_cost=plan.cost_per_file.get(recommended, CostResult(0, 0, 0)).tc_cost,
            total_cost=plan.total_cost,
            outcome="planned",  # 因为没实际执行，标记为 planned
            tier0_result="not_run",
            notes=f"周期#{self._cycle_count}: {len(plan.safe_files)}个安全文件, "
                  f"{len(plan.ic_violations)}个IC违规",
        )
        self.memory.push(record)

        # 7. 如果有回调，执行最安全的改动
        if execute_callback and recommended:
            try:
                cb_result = execute_callback(recommended)
                record.outcome = cb_result.get("outcome", "unknown")
                record.tier0_result = cb_result.get("tier0", "not_run")
            except Exception as e:
                record.outcome = "failed"
                record.notes += f" | 回调异常: {e}"

        report = EvolutionReport(
            timestamp=time.time(),
            status="evolved" if record.outcome == "success" else "healthy",
            state=state,
            plan=plan,
            record=record,
            cycle_time_ms=(time.time() - t0) * 1000,
            summary=(
                f"周期#{self._cycle_count}: {len(plan.safe_files)}个安全文件, "
                f"{len(plan.ic_violations)}个IC违规. "
                f"建议顺序: {' → '.join(plan.recommended_order[:5])}"
            ),
        )
        self._write_ledger_entry({
            "timestamp": time.time(),
            "cycle": self._cycle_count,
            "ok": 1 if record.outcome in ("success", "planned") else 0,
            "status": report.status,
            "candidates": candidate_files,
            "safe_files": len(plan.safe_files),
            "ic_violations": len(plan.ic_violations),
            "elapsed_ms": (time.time() - t0) * 1000,
            "reason": f"outcome={record.outcome}",
        })
        self._last_report = report
        return report

    def get_last_report(self) -> Optional[EvolutionReport]:
        """获取上一次演化报告"""
        return self._last_report

    def get_stats(self) -> Dict[str, Any]:
        """获取引擎统计"""
        ledger = self.read_ledger()
        total = len(ledger)
        ok_count = sum(1 for e in ledger if e.get("ok") == 1)
        rolled_back_count = sum(
            1 for e in ledger
            if e.get("reason", "").startswith("outcome=rolled_back")
        )
        return {
            "cycles": self._cycle_count,
            "memory": self.memory.get_stats(),
            "ledger": {
                "total_entries": total,
                "ok_count": ok_count,
                "rolled_back_count": rolled_back_count,
                "ok_pct": round(ok_count / total * 100, 1) if total > 0 else None,
            },
            "last_report": (
                {"status": self._last_report.status, "summary": self._last_report.summary}
                if self._last_report else None
            ),
        }

    # ── 持久化账本 ──

    @staticmethod
    def _ledger_path() -> Path:
        """标准账本路径: $MIMIR_AETHER_HOME/data/evolution_ledger.json"""
        home = Path(os.environ.get(
            "MIMIR_AETHER_HOME",
            Path.home() / ".mimiraether",
        ))
        path = home / "data" / "evolution_ledger.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _write_ledger_entry(self, entry: Dict[str, Any]) -> None:
        """追加一条账目到 evolution_ledger.json"""
        path = self._ledger_path()
        ledger = []
        if path.exists():
            try:
                ledger = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                ledger = []
        if not isinstance(ledger, list):
            ledger = []
        ledger.append(entry)
        path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def read_ledger() -> List[Dict[str, Any]]:
        """读取完整账本"""
        path = SelfEvolutionEngine._ledger_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []


# ── Agent Loop 集成钩子 ──
# 
# 不修改 agent_loop.py 本身，而是提供可导入的安全门函数。
# 刘哥或 Cursor 在 agent loop 合适位置加入一行即可激活：
#
#   from agent.self_evolution.engine import pre_action_check
#   if not pre_action_check(proposed_files):
#       return "Blocked by self_evolution IC constraints"
#
# 或者使用上下文管理器（无需改 agent loop 核心逻辑）：
#
#   from agent.self_evolution.engine import evolution_guard
#   with evolution_guard(["file1.py", "file2.py"]) as safe_files:
#       for f in safe_files:
#           do_modify(f)  # 只遍历通过 IC 的文件
#
#   # 上下文退出时自动记录到 EvolutionMemory

_engine_singleton: Optional[SelfEvolutionEngine] = None

import contextlib
from typing import Generator


@contextlib.contextmanager
def evolution_guard(
    proposed_files: List[str],
    *,
    run_tier0: bool = False,
) -> Generator[List[str], None, None]:
    """
    安全上下文管理器：只让通过 IC 约束的文件进入修改块。

    用法（在 agent loop 或任何修改 agent/ 代码的地方）：
        with evolution_guard(["skill_evolution.py"]) as safe:
            for fpath in safe:
                patch(fpath, ...)  # 只修改通过约束的文件

    Args:
        proposed_files: 拟改动的文件列表
        run_tier0: 是否先跑 tier0 基线检查

    Yields:
        通过 IC 约束的文件列表（被 blocked 的文件不在此列表中）
    """
    engine = get_engine()
    state = engine.encoder.encode(force_refresh=True, run_tier0=run_tier0)
    plan = engine.planner.plan(proposed_files)
    
    safe_files = plan.safe_files
    blocked = [f for f in proposed_files if f not in safe_files]
    
    if blocked:
        logger.warning(
            f"evolution_guard blocked {len(blocked)} files: {blocked}. "
            f"IC violations: {plan.ic_violations}"
        )
    
    try:
        yield safe_files
    finally:
        # 出口：记录结果到演化记忆
        for fpath in safe_files:
            record = EvolutionRecord(
                timestamp=time.time(),
                changes=[fpath],
                ic_cost=0.0,
                tc_cost=plan.cost_per_file.get(fpath, CostResult(0, 0, 0)).tc_cost,
                total_cost=plan.total_cost,
                outcome="completed",
                tier0_result="not_run",
                notes="evolution_guard context exit",
            )
            engine.memory.push(record)


def get_engine(agent_dir: Optional[str] = None) -> SelfEvolutionEngine:
    """获取引擎单例（agent loop 的集成入口）"""
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = SelfEvolutionEngine(agent_dir=agent_dir)
    return _engine_singleton


def pre_action_check(proposed_files: List[str]) -> bool:
    """
    行动前安全门：agent loop 在改任何文件前调用此函数。
    返回 True = 安全，False = 被 IC 阻止。
    """
    engine = get_engine()
    return engine.cost.is_safe(proposed_files)


def post_action_log(changed_files: List[str], outcome: str) -> None:
    """行动后记录：agent loop 在改动完成后调用，记录到演化记忆。"""
    engine = get_engine()
    from .memory import EvolutionRecord
    record = EvolutionRecord(
        timestamp=time.time(),
        changes=changed_files,
        ic_cost=0.0,
        tc_cost=0.0,
        total_cost=0.0,
        outcome=outcome,
        tier0_result="not_run",
        notes=f"agent_loop hook: {outcome}",
    )
    engine.memory.push(record)


def ic_advisor(blocked_file: str) -> dict:
    """
    IC 拦截后顾问（EV-VOE07）：不只说 no，还提供更安全的替代方案。

    Returns:
        {"blocked": str, "blast_radius": int, "alternatives": [...], "suggestion": str}
    """
    engine = get_engine()
    state = engine.encoder.encode(force_refresh=False)

    if blocked_file not in state.files:
        return {
            "blocked": blocked_file,
            "blast_radius": 0,
            "alternatives": [],
            "suggestion": f"'{blocked_file}' 不在 agent/ 分析范围内，无法生成替代方案",
        }

    deps = state.files[blocked_file]
    blast_radius = len(deps.imported_by)

    blocked_dir = blocked_file.rsplit("/", 1)[0]
    # Same-directory alternatives (narrow search)
    alternatives = []
    for fpath, info in sorted(state.files.items(), key=lambda x: len(x[1].imported_by)):
        if fpath == blocked_file:
            continue
        # If blocked_file has no dir component, blocked_dir == blocked_file itself;
        # fall back to comparing directory prefix only.
        fdir = fpath.rsplit("/", 1)[0]
        if fdir == blocked_dir and blocked_dir != blocked_file:
            pass  # same directory, keep
        elif blocked_dir == blocked_file and "/" not in fpath:
            pass  # both in root agent/ dir
        else:
            continue
        result = engine.cost.evaluate([fpath])
        tc = result.tc_cost
        alternatives.append({
            "file": fpath,
            "tc": round(float(tc), 3),
            "blast_radius": len(info.imported_by),
        })

    # Wider search: if no alternatives, expand to prompts/ and low-blast-radius files
    if not alternatives:
        for fpath, info in sorted(state.files.items(), key=lambda x: len(x[1].imported_by)):
            if fpath == blocked_file:
                continue
            # Accept prompts/ directory or any file with blast_radius <= 1
            if not fpath.startswith("prompts/") and len(info.imported_by) > 1:
                continue
            alternatives.append({
                "file": fpath,
                "tc": 0,  # not evaluating cost for wide search
                "blast_radius": len(info.imported_by),
            })
        alternatives.sort(key=lambda x: x["blast_radius"])

    alternatives.sort(key=lambda x: x["tc"])
    top3 = alternatives[:3]

    if top3:
        best = top3[0]
        suggestion = (
            f"'{blocked_file}' 影响 {blast_radius} 个依赖。"
            f"建议改 '{best['file']}'（影响面={best['blast_radius']}, TC={best['tc']}）。"
        )
        if len(top3) > 1:
            suggestion += f" 备选: {', '.join(a['file'] for a in top3[1:])}"
    else:
        suggestion = (
            f"'{blocked_file}' 被 IC 拦截，无安全替代文件。"
            " 可考虑改 tests/ 对应文件 或 开 HANDOFF 文档征求意见。"
        )

    return {
        "blocked": blocked_file,
        "blast_radius": blast_radius,
        "alternatives": top3,
        "suggestion": suggestion,
    }

"""
VoE (Violation of Expectation) 违背预期检测器

基于 LeCun LeWM 2026 §3.2: VoE = ‖预测状态 − 实际状态‖² > τ
迁移到代码世界: 改动面与历史模式的偏离度。

原则: 不靠人类列规则，让世界模型自己判断"这个改动是否异常"。
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.self_evolution.memory import EvolutionMemory


class VoEDetector:
    """违背预期检测器

    Input:  一次改动的元数据 {files, estimated_lines}
    Process: 与 MemoryBuffer 中的历史记录对比 → z-score 多维度加权
    Output:  {surprise_score: 0-1, reasons: [...], level: "safe"|"caution"|"unusual"}
    """

    # 各维度的权重
    W_N_FILES = 0.30          # 文件数量偏离
    W_MODULE_NOVELTY = 0.35   # 模块组合新颖度（最重要——跨模块改动最异常）
    W_IC_PROXIMITY = 0.20     # IC 边界接近度
    W_OUTCOME = 0.15          # 历史成功率

    # 阈值
    THRESHOLD_CAUTION = 0.30   # > 0.30 → caution
    THRESHOLD_UNUSUAL = 0.70   # > 0.70 → unusual

    def __init__(self):
        self._fitted = False
        self._n_files_mu: float = 0.0
        self._n_files_sigma: float = 1.0
        self._known_modules: set[str] = set()
        self._module_combos: set[frozenset[str]] = set()
        self._success_rate: float = 1.0

    # ── 训练：从历史记忆学习正常模式 ──

    def fit(self, memory: "EvolutionMemory") -> "VoEDetector":
        """从 EvolutionMemory 学习正常改动模式"""
        records = list(memory._records)
        if not records:
            self._fitted = True  # 无历史 → 一切正常
            return self

        # 1. 文件数量分布
        n_files_list = [len(r.changes) for r in records]
        n = len(n_files_list)
        self._n_files_mu = sum(n_files_list) / n
        variance = sum((x - self._n_files_mu) ** 2 for x in n_files_list) / n
        self._n_files_sigma = math.sqrt(variance) if variance > 0 else 1.0

        # 2. 已知模块和模块组合
        self._known_modules = set()
        self._module_combos = set()
        for r in records:
            modules = self._extract_modules(r.changes)
            self._known_modules.update(modules)
            if len(modules) >= 2:
                self._module_combos.add(frozenset(modules))

        # 3. 历史成功率
        self._success_rate = memory.get_success_rate()

        self._fitted = True
        return self

    # ── 检测 ──

    def detect(self, files: list[str], estimated_lines: int = 0) -> dict:
        """检测一次改动的惊讶度

        Returns:
            {
                "surprise_score": float (0-1),
                "dimensions": {name: score},
                "reasons": [str],
                "level": "safe" | "caution" | "unusual"
            }
        """
        if not self._fitted:
            return self._no_history_result()

        modules = self._extract_modules(files)
        n_files = len(files)

        # D1: 文件数量 z-score
        d1 = self._n_files_zscore(n_files)

        # D2: 模块组合新颖度
        d2 = self._module_novelty(modules)

        # D3: IC 边界接近度
        d3 = self._ic_proximity(files)

        # D4: 历史成功率衰减
        d4 = 1.0 - self._success_rate

        # 加权
        score = (
            self.W_N_FILES * d1
            + self.W_MODULE_NOVELTY * d2
            + self.W_IC_PROXIMITY * d3
            + self.W_OUTCOME * d4
        )
        score = min(1.0, max(0.0, score))

        # 归类
        if score >= self.THRESHOLD_UNUSUAL:
            level = "unusual"
        elif score >= self.THRESHOLD_CAUTION:
            level = "caution"
        else:
            level = "safe"

        return {
            "surprise_score": round(score, 4),
            "dimensions": {
                "n_files_zscore": round(d1, 4),
                "module_novelty": round(d2, 4),
                "ic_proximity": round(d3, 4),
                "outcome_risk": round(d4, 4),
            },
            "reasons": self._build_reasons(score, d1, d2, d3, n_files, modules),
            "level": level,
        }

    # ── 维度计算 ──

    def _n_files_zscore(self, n_files: int) -> float:
        """文件数量偏离 → [0, 1]"""
        if self._n_files_sigma < 1e-9:
            return 0.0 if n_files <= self._n_files_mu else 1.0
        z = abs(n_files - self._n_files_mu) / self._n_files_sigma
        # sigmoid 归一化到 [0,1]: z=2 → 0.88, z=3 → 0.95
        return min(1.0, 1.0 / (1.0 + math.exp(-(z - 2.0))))

    def _module_novelty(self, modules: set[str]) -> float:
        """模块组合新颖度 → [0, 1]"""
        if len(modules) < 2:
            # 单模块改动 → 低新颖度
            return 0.1 if modules and modules not in self._known_modules else 0.0

        combo = frozenset(modules)
        if combo in self._module_combos:
            return 0.0  # 常见组合

        # 全新组合 — 模块越多越异常
        novel_modules = modules - self._known_modules
        novelty = len(novel_modules) / max(len(modules), 1)
        if novelty > 0:
            return min(1.0, 0.5 + 0.5 * novelty)  # 全新模块 → 高分
        else:
            return 0.4  # 已有模块但新组合 → 中等异常

    def _ic_proximity(self, files: list[str]) -> float:
        """IC 边界接近度 → [0, 1]"""
        PROTECTED_DIRS = {
            "agent/agent_loop.py", "agent/exec_mixin.py",
            "agent/core_loop.py", "agent/prompt_guard.py",
            "gateway/run.py", "gateway/platforms/",
            "tools/tool_registry.py",
        }
        count = 0
        for f in files:
            for pd in PROTECTED_DIRS:
                if f.startswith(pd) or f == pd.rstrip("/"):
                    count += 1
                    break
        if count == 0:
            return 0.0
        ratio = count / max(len(files), 1)
        return min(1.0, ratio * 2.0)  # 50%文件接近IC → 1.0

    def _build_reasons(
        self, score: float, d1: float, d2: float, d3: float,
        n_files: int, modules: set[str]
    ) -> list[str]:
        reasons = []
        if d1 > 0.5:
            reasons.append(f"文件数 {n_files} 偏离历史均值 {self._n_files_mu:.1f}±{self._n_files_sigma:.1f}")
        if d2 > 0.3:
            reasons.append(f"模块组合 {sorted(modules)} 异常（跨模块改动）")
        if d3 > 0.3:
            reasons.append("改动接近 IC 保护区")
        if not reasons:
            reasons.append("改动模式与历史一致")
        return reasons

    # ── 工具 ──

    @staticmethod
    def _extract_modules(files: list[str]) -> set[str]:
        """从文件列表提取顶层模块"""
        modules = set()
        for f in files:
            parts = f.split("/")
            if len(parts) >= 1:
                modules.add(parts[0])
        return modules

    def _no_history_result(self) -> dict:
        return {
            "surprise_score": 0.0,
            "dimensions": {"n_files_zscore": 0, "module_novelty": 0, "ic_proximity": 0, "outcome_risk": 0},
            "reasons": ["无历史记录，无法判断异常"],
            "level": "safe",
        }

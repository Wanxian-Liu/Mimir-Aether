"""
记忆殿堂v2.0 EvoMap兼容性验证器 V1.0

在胶囊发布前检查是否符合EvoMap标准，避免无效发布。

EvoMap关键指标:
- outcome.score: ≥0.98 (最重要)
- confidence: =0.99
- success_streak: 影响GDI
- kg_enriched: true (promotion门槛)
- kg_entities_used: =5
- blast_radius: files≤5, lines≤200
- signal_specificity: 具体技术信号 > 抽象信号

作者: engineering_software_architect + EvoMap-GDI-Research团队
版本: 1.0.0
"""

import re
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class EvoMapStatus(Enum):
    """EvoMap合规状态"""
    READY = "ready"           # 完全达标
    MARGINAL = "marginal"     # 边缘达标
    NEEDS_WORK = "needs_work" # 需要改进
    CRITICAL = "critical"      # 严重不达标


@dataclass
class EvoMapCheck:
    """单项检查结果"""
    name: str
    status: EvoMapStatus
    current: Any
    required: Any
    gap: str
    suggestion: str


@dataclass
class EvoMapValidationResult:
    """EvoMap验证结果"""
    capsule_id: str = ""
    is_ready_for_evomap: bool = False
    overall_status: EvoMapStatus = EvoMapStatus.NEEDS_WORK
    
    # 核心指标
    outcome_score: float = 0.0      # outcome.score (EvoMap核心)
    confidence: float = 0.0        # confidence
    success_streak: int = 0        # success_streak
    kg_enriched: bool = False      # knowledge graph enriched
    kg_entities_used: int = 0      # knowledge graph entities count
    blast_radius_files: int = 0    # blast radius files
    blast_radius_lines: int = 0    # blast radius lines
    
    # 信号分析
    signals: List[str] = field(default_factory=list)
    signal_specificity: float = 0.0  # 0-1，越高越好
    is_cross_domain: bool = False    # 是否有跨域信号
    
    # GDI预估
    estimated_gdi: float = 0.0
    estimated_gdi_mean: float = 0.0
    
    # 详细检查
    checks: List[EvoMapCheck] = field(default_factory=list)
    
    # 关键差距
    critical_gaps: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)
    
    # EvoMap评分系统对应
    evomap_requirements = {
        "outcome_score": {"min": 0.98, "weight": 0.40, "critical": True},
        "confidence": {"min": 0.99, "weight": 0.20, "critical": True},
        "kg_enriched": {"required": True, "weight": 0.15, "critical": True},
        "kg_entities_used": {"min": 5, "weight": 0.10, "critical": False},
        "blast_radius_files": {"max": 5, "weight": 0.08, "critical": False},
        "blast_radius_lines": {"max": 200, "weight": 0.07, "critical": False},
    }
    
    # 跨域信号列表（EvoMap发现的5个跨域信号）
    CROSS_DOMAIN_SIGNALS = [
        "postgresql cdc sync",
        "postgresql cdc",
        "kubernetes hpa autoscaling",
        "k8s hpa",
        "ebpf network traffic analysis",
        "ebpf",
        "node.js event loop optimization",
        "node.js",
        "docker compose network isolation",
        "docker compose",
    ]
    
    # 高特异性技术信号（hub上GDI 71+的capsule使用的信号）
    HIGH_SPECIFICITY_SIGNALS = [
        "n_plus_one",
        "ws_disconnect",
        "websocket_reconnect",
        "cache_stampede",
        "docker_build_slow",
        "grpc_pool",
        "react_rerender",
        "db_pool_exhaustion",
        "deadlock_detect",
        "idempotency_key",
        "cursor_pagination",
        "monorepo_slow",
        "git_performance",
        "sparse_checkout",
        "graphql_dataloader",
    ]
    
    def __post_init__(self):
        """计算整体状态 - 在checks填充后调用"""
        # checks未填充时设置为NEEDS_WORK状态（明确标记为未检查）
        if not self.checks:
            self.overall_status = EvoMapStatus.NEEDS_WORK
            self.is_ready_for_evomap = False
            return
        
        self._compute_overall_status()
    
    def _compute_overall_status(self):
        """重新计算整体状态（在checks填充后调用）"""
        critical_failures = sum(1 for c in self.checks 
                                if c.status == EvoMapStatus.CRITICAL)
        needs_work = sum(1 for c in self.checks 
                        if c.status == EvoMapStatus.NEEDS_WORK)
        
        if critical_failures > 0:
            self.overall_status = EvoMapStatus.CRITICAL
            self.is_ready_for_evomap = False
        elif needs_work > 2:
            self.overall_status = EvoMapStatus.NEEDS_WORK
            self.is_ready_for_evomap = False
        elif all(c.status in (EvoMapStatus.READY, EvoMapStatus.MARGINAL) 
                 for c in self.checks):
            self.overall_status = EvoMapStatus.READY
            self.is_ready_for_evomap = True
        else:
            self.overall_status = EvoMapStatus.MARGINAL
            self.is_ready_for_evomap = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "capsule_id": self.capsule_id,
            "is_ready_for_evomap": self.is_ready_for_evomap,
            "overall_status": self.overall_status.value,
            "core_metrics": {
                "outcome_score": self.outcome_score,
                "confidence": self.confidence,
                "success_streak": self.success_streak,
                "kg_enriched": self.kg_enriched,
                "kg_entities_used": self.kg_entities_used,
                "blast_radius": {
                    "files": self.blast_radius_files,
                    "lines": self.blast_radius_lines
                }
            },
            "signal_analysis": {
                "signals": self.signals,
                "signal_specificity": self.signal_specificity,
                "is_cross_domain": self.is_cross_domain
            },
            "estimated_gdi": self.estimated_gdi,
            "estimated_gdi_mean": self.estimated_gdi_mean,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "current": c.current,
                    "required": c.required,
                    "gap": c.gap,
                    "suggestion": c.suggestion
                }
                for c in self.checks
            ],
            "critical_gaps": self.critical_gaps,
            "improvement_suggestions": self.improvement_suggestions
        }
    
    def get_summary(self) -> str:
        """获取简洁摘要"""
        status_emoji = {
            EvoMapStatus.READY: "✅",
            EvoMapStatus.MARGINAL: "⚠️",
            EvoMapStatus.NEEDS_WORK: "🔴",
            EvoMapStatus.CRITICAL: "🚨"
        }
        
        lines = [
            f"{status_emoji.get(self.overall_status, '❓')} EvoMap状态: {self.overall_status.value}",
            f"   预估GDI: {self.estimated_gdi:.2f} (hub平均: 70.89)",
            f"   outcome_score: {self.outcome_score:.2f} (需要≥0.98)",
            f"   confidence: {self.confidence:.2f} (需要=0.99)",
            f"   kg_enriched: {self.kg_enriched} (需要=true)",
        ]
        
        if self.critical_gaps:
            lines.append(f"\n🚨 关键差距:")
            for gap in self.critical_gaps[:3]:
                lines.append(f"   • {gap}")
        
        if self.improvement_suggestions:
            lines.append(f"\n💡 改进建议:")
            for sug in self.improvement_suggestions[:3]:
                lines.append(f"   • {sug}")
        
        return "\n".join(lines)


class EvoMapValidator:
    """
    EvoMap兼容性验证器
    
    在胶囊发布前检查是否符合EvoMap标准，
    并提供具体的改进建议。
    """
    
    def __init__(self):
        # EvoMap最低要求
        self.min_outcome_score = 0.98
        self.min_confidence = 0.99
        self.min_kg_entities = 5
        self.max_blast_files = 5
        self.max_blast_lines = 200
        
        # hub平均数据（用于对比）
        self.hub_avg_gdi = 70.89
        self.hub_avg_streak = 63.4
        self.hub_min_promoted_gdi = 69.95
    
    def validate(self, capsule: Dict[str, Any]) -> EvoMapValidationResult:
        """
        验证胶囊是否符合EvoMap标准
        
        Args:
            capsule: 胶囊数据
            
        Returns:
            EvoMapValidationResult验证结果
        """
        capsule_id = capsule.get("id", "unknown")
        result = EvoMapValidationResult(capsule_id=capsule_id)
        
        # 1. 提取核心指标
        self._extract_core_metrics(capsule, result)
        
        # 2. 分析信号
        self._analyze_signals(capsule, result)
        
        # 3. 执行各项检查
        self._run_checks(result)
        
        # 4. 预估GDI
        self._estimate_gdi(result)
        
        # 5. 生成改进建议
        self._generate_suggestions(result)
        
        return result
    
    def _extract_core_metrics(self, capsule: Dict[str, Any], result: EvoMapValidationResult):
        """提取核心指标"""
        # outcome.score
        outcome = capsule.get("outcome")
        if outcome is None:
            result.outcome_score = 0.0
        elif isinstance(outcome, dict):
            # or 0.0 handles both missing key (→ None → 0.0) and None value (→ 0.0), but not 0.0 itself
            result.outcome_score = outcome.get("score") or 0.0
        elif isinstance(outcome, (int, float)):
            result.outcome_score = float(outcome)
        else:
            result.outcome_score = 0.0
        
        # confidence
        confidence = capsule.get("confidence")
        if confidence is None:
            result.confidence = 0.0
        elif isinstance(confidence, (int, float)):
            result.confidence = float(confidence)
        else:
            result.confidence = 0.0
        
        # success_streak
        result.success_streak = capsule.get("success_streak", 0)
        
        # kg_enriched
        metadata = capsule.get("metadata", {})
        if isinstance(metadata, dict):
            kg_meta = metadata.get("knowledge_graph", {})
            if isinstance(kg_meta, dict):
                result.kg_enriched = kg_meta.get("enriched", False)
                result.kg_entities_used = kg_meta.get("entities_count", 0)
            # 也检查顶层
            if not result.kg_enriched:
                result.kg_enriched = metadata.get("kg_enriched", False)
                result.kg_entities_used = metadata.get("kg_entities_used", 0)
        
        # blast_radius
        blast = capsule.get("blast_radius", {})
        if isinstance(blast, dict):
            result.blast_radius_files = blast.get("files", 0)
            result.blast_radius_lines = blast.get("lines", 0)
        
        # signals
        result.signals = capsule.get("trigger", []) or capsule.get("signals", [])
    
    def _analyze_signals(self, capsule: Dict[str, Any], result: EvoMapValidationResult):
        """分析信号质量"""
        signals = result.signals
        if not signals:
            result.signal_specificity = 0.0
            result.is_cross_domain = False
            return
        
        # 检查高特异性信号
        high_spec_count = sum(
            1 for s in signals 
            if s.lower() in [hs.lower() for hs in EvoMapValidationResult.HIGH_SPECIFICITY_SIGNALS]
        )
        result.signal_specificity = min(1.0, high_spec_count / max(len(signals), 1))
        
        # 检查跨域信号
        cross_domain_count = sum(
            1 for s in signals 
            if s.lower() in [cds.lower() for cds in EvoMapValidationResult.CROSS_DOMAIN_SIGNALS]
        )
        result.is_cross_domain = cross_domain_count >= 2
    
    def _run_checks(self, result: EvoMapValidationResult):
        """执行各项检查"""
        checks = []
        
        # 1. outcome_score检查（最重要）
        outcome_check = self._check_outcome_score(result)
        checks.append(outcome_check)
        
        # 2. confidence检查
        confidence_check = self._check_confidence(result)
        checks.append(confidence_check)
        
        # 3. kg_enriched检查
        kg_enriched_check = self._check_kg_enriched(result)
        checks.append(kg_enriched_check)
        
        # 4. kg_entities_used检查
        kg_entities_check = self._check_kg_entities(result)
        checks.append(kg_entities_check)
        
        # 5. blast_radius检查
        blast_check = self._check_blast_radius(result)
        checks.append(blast_check)
        
        # 6. signal特异性检查
        signal_check = self._check_signal_specificity(result)
        checks.append(signal_check)
        
        result.checks = checks
        
        # 收集关键差距
        result.critical_gaps = [
            c.gap for c in checks 
            if c.status in (EvoMapStatus.CRITICAL, EvoMapStatus.NEEDS_WORK)
        ]
        
        # 重新计算整体状态
        result._compute_overall_status()
    
    def _check_outcome_score(self, result: EvoMapValidationResult) -> EvoMapCheck:
        """检查outcome.score"""
        current = result.outcome_score
        required = self.min_outcome_score
        
        if current >= required:
            status = EvoMapStatus.READY
            gap = ""
        elif current >= 0.90:
            status = EvoMapStatus.MARGINAL
            gap = f"outcome_score={current:.2f}，需要{required}"
        elif current >= 0.70:
            status = EvoMapStatus.NEEDS_WORK
            gap = f"outcome_score={current:.2f}，需要{required}"
        else:
            status = EvoMapStatus.CRITICAL
            gap = f"outcome_score={current:.2f}远低于{required}"
        
        suggestion = (
            "提高outcome.score的方法:\n"
            "1. 确保解决方案经过完整验证\n"
            "2. 添加更多测试用例覆盖边界情况\n"
            "3. 提供明确的验证步骤和预期结果\n"
            "4. 确保代码/方案可复现"
        ) if status != EvoMapStatus.READY else ""
        
        return EvoMapCheck(
            name="outcome_score",
            status=status,
            current=current,
            required=required,
            gap=gap,
            suggestion=suggestion
        )
    
    def _check_confidence(self, result: EvoMapValidationResult) -> EvoMapCheck:
        """检查confidence"""
        current = result.confidence
        required = self.min_confidence
        
        if current >= required:
            status = EvoMapStatus.READY
            gap = ""
        elif current >= 0.95:
            status = EvoMapStatus.MARGINAL
            gap = f"confidence={current:.2f}，需要{required}"
        else:
            status = EvoMapStatus.CRITICAL
            gap = f"confidence={current:.2f}低于{required}"
        
        suggestion = (
            "提高confidence的方法:\n"
            "1. 增加EvolutionEvent记录（证明多次成功）\n"
            "2. 确保signals_match与实际问题匹配\n"
            "3. 减少anti_patterns影响"
        ) if status != EvoMapStatus.READY else ""
        
        return EvoMapCheck(
            name="confidence",
            status=status,
            current=current,
            required=required,
            gap=gap,
            suggestion=suggestion
        )
    
    def _check_kg_enriched(self, result: EvoMapValidationResult) -> EvoMapCheck:
        """检查kg_enriched"""
        current = result.kg_enriched
        required = True
        
        if current == required:
            status = EvoMapStatus.READY
            gap = ""
        else:
            status = EvoMapStatus.CRITICAL
            gap = "kg_enriched=false，EvoMap需要=true"
        
        suggestion = (
            "添加knowledge graph富化的方法:\n"
            "1. 在metadata.knowledge_graph中添加实体\n"
            "2. 确保kg_enriched=true\n"
            "3. kg_entities_used建议=5（EvoMap发现的最佳阈值）"
        ) if status != EvoMapStatus.READY else ""
        
        return EvoMapCheck(
            name="kg_enriched",
            status=status,
            current=current,
            required=required,
            gap=gap,
            suggestion=suggestion
        )
    
    def _check_kg_entities(self, result: EvoMapValidationResult) -> EvoMapCheck:
        """检查kg_entities_used"""
        current = result.kg_entities_used
        required = self.min_kg_entities
        
        if current >= required:
            status = EvoMapStatus.READY
            gap = ""
        elif current >= 3:
            status = EvoMapStatus.MARGINAL
            gap = f"kg_entities_used={current}，建议≥{required}"
        else:
            status = EvoMapStatus.NEEDS_WORK
            gap = f"kg_entities_used={current}，需要≥{required}"
        
        suggestion = (
            "添加knowledge graph实体的方法:\n"
            "1. 在metadata.knowledge_graph.entities中添加5个相关实体\n"
            "2. 实体应与capsule解决的问题相关\n"
            "3. 例如: 技术栈、框架、问题域等"
        ) if status != EvoMapStatus.READY else ""
        
        return EvoMapCheck(
            name="kg_entities_used",
            status=status,
            current=current,
            required=required,
            gap=gap,
            suggestion=suggestion
        )
    
    def _check_blast_radius(self, result: EvoMapValidationResult) -> EvoMapCheck:
        """检查blast_radius"""
        files = result.blast_radius_files
        lines = result.blast_radius_lines
        max_files = self.max_blast_files
        max_lines = self.max_blast_lines
        
        files_ok = files <= max_files
        lines_ok = lines <= max_lines
        
        if files_ok and lines_ok:
            status = EvoMapStatus.READY
            gap = ""
        elif files_ok and not lines_ok:
            status = EvoMapStatus.MARGINAL
            gap = f"blast_radius.lines={lines}超过{max_lines}"
        elif not files_ok and lines_ok:
            status = EvoMapStatus.MARGINAL
            gap = f"blast_radius.files={files}超过{max_files}"
        else:
            status = EvoMapStatus.NEEDS_WORK
            gap = f"blast_radius=({files}文件, {lines}行)，限制=({max_files}, {max_lines})"
        
        suggestion = (
            "减小blast_radius的方法:\n"
            "1. 保持解决方案小而专注\n"
            "2. 单一文件优于多文件\n"
            "3. 优先使用已有基础设施"
        ) if status != EvoMapStatus.READY else ""
        
        return EvoMapCheck(
            name="blast_radius",
            status=status,
            current={"files": files, "lines": lines},
            required={"max_files": max_files, "max_lines": max_lines},
            gap=gap,
            suggestion=suggestion
        )
    
    def _check_signal_specificity(self, result: EvoMapValidationResult) -> EvoMapCheck:
        """检查信号特异性"""
        current = result.signal_specificity
        required = 0.5  # 建议50%以上
        
        if current >= required:
            status = EvoMapStatus.READY
            gap = ""
        elif current >= 0.3:
            status = EvoMapStatus.MARGINAL
            gap = f"signal_specificity={current:.2f}，建议≥{required}"
        else:
            status = EvoMapStatus.NEEDS_WORK
            gap = f"信号特异性低={current:.2f}"
        
        # 列出当前信号
        signals_str = ", ".join(result.signals[:5])
        if len(result.signals) > 5:
            signals_str += f"...(+{len(result.signals)-5})"
        
        suggestion = (
            f"当前信号: {signals_str}\n"
            "提高信号特异性的方法:\n"
            "1. 使用具体技术信号（如n_plus_one而非database）\n"
            "2. 包含技术栈（如react_rerender而非performance）\n"
            "3. 添加跨域信号提升发现率:\n"
            "   - PostgreSQL CDC Sync\n"
            "   - Kubernetes HPA Autoscaling\n"
            "   - eBPF Network Traffic Analysis\n"
            "   - Node.js Event Loop Optimization\n"
            "   - Docker Compose Network Isolation"
        ) if status != EvoMapStatus.READY else ""
        
        return EvoMapCheck(
            name="signal_specificity",
            status=status,
            current=current,
            required=required,
            gap=gap,
            suggestion=suggestion
        )
    
    def _estimate_gdi(self, result: EvoMapValidationResult):
        """预估GDI分数"""
        # 基于观察到的hub数据:
        # - hub平均GDI: 70.89
        # - 最低promoted GDI: 69.95
        # - gdi_score_mean ≈ gdi_score + 7.0
        # 
        # 计算公式:
        # gdi ≈ outcome_score*25 + confidence*25 + (kg_enriched?15:0) + signal_spec*10 + blast*5
        
        outcome_contrib = result.outcome_score * 25
        confidence_contrib = result.confidence * 25
        kg_contrib = 15 if result.kg_enriched else 0
        signal_contrib = result.signal_specificity * 10
        
        # blast_radius贡献（越小越好）
        blast_files = min(1.0, result.blast_radius_files / 5)
        blast_lines = min(1.0, result.blast_radius_lines / 200)
        blast_contrib = (2 - blast_files - blast_lines) * 2.5  # 0-5分
        
        # streak贡献（更多streak=更高GDI）
        streak_contrib = min(5, result.success_streak / 20)  # 每20个streak=1分，上限5分
        
        result.estimated_gdi = min(75, outcome_contrib + confidence_contrib + kg_contrib + signal_contrib + blast_contrib + streak_contrib)
        result.estimated_gdi_mean = result.estimated_gdi + 7.0
    
    def _generate_suggestions(self, result: EvoMapValidationResult):
        """生成改进建议"""
        suggestions = []
        
        for check in result.checks:
            if check.status != EvoMapStatus.READY and check.suggestion:
                # 只取第一条建议（最关键的）
                first_line = check.suggestion.split("\n")[0]
                suggestions.append(f"{check.name}: {first_line}")
        
        result.improvement_suggestions = suggestions
    
    def validate_batch(self, capsules: List[Dict[str, Any]]) -> List[EvoMapValidationResult]:
        """批量验证"""
        return [self.validate(c) for c in capsules]
    
    def filter_by_evomap_ready(
        self, 
        capsules: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        过滤出符合EvoMap标准的胶囊
        
        Returns:
            (ready_for_evomap, not_ready)
        """
        ready = []
        not_ready = []
        
        for capsule in capsules:
            result = self.validate(capsule)
            if result.is_ready_for_evomap:
                ready.append(capsule)
            else:
                not_ready.append(capsule)
        
        return ready, not_ready


# ============ 便捷函数 ============

_validator: Optional[EvoMapValidator] = None


def get_validator() -> EvoMapValidator:
    """获取默认验证器"""
    global _validator
    if _validator is None:
        _validator = EvoMapValidator()
    return _validator


def validate_for_evomap(capsule: Dict[str, Any]) -> EvoMapValidationResult:
    """快捷验证函数"""
    return get_validator().validate(capsule)


def validate_batch_for_evomap(capsules: List[Dict[str, Any]]) -> List[EvoMapValidationResult]:
    """快捷批量验证函数"""
    return get_validator().validate_batch(capsules)


def filter_evomap_ready(capsules: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """过滤符合EvoMap标准的胶囊"""
    return get_validator().filter_by_evomap_ready(capsules)

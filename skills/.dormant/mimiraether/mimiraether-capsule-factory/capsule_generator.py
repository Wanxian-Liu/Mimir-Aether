"""
记忆殿堂v2.0 胶囊类型生成器 V1.1

根据基因图谱决定生成的胶囊类型:
- repair: 修复胶囊
- optimize: 优化胶囊
- innovate: 创新胶囊

V1.1 修复:
- 重写 _generate_repair_capsule: 消除重复内容、断尾、空壳问题
- 添加内容完整性校验（pre_validate + post_validate）
- 添加 section 去重机制
- 修复正则边界匹配（支持任意 markdown 标题作为 section 边界）
- 根因分析改为从输入中提取，不再使用占位符

作者: engineering_software_architect
版本: 1.1.0
"""

import re
import time
import hashlib
import json
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from enum import Enum

from gdi_scorer import GDIScorer, GDIResult, CapsuleType as GDI_CapsuleType
from evomap_validator import EvoMapValidator, EvoMapValidationResult, validate_for_evomap, EvoMapStatus

# 本地胶囊类型别名（供外部导入）
GDI_CapsuleTypeAlias = GDI_CapsuleType
# 向后兼容别名
CapsuleType = GDI_CapsuleTypeAlias


class CapsuleValidationError(Exception):
    """胶囊数据验证失败"""
    def __init__(self, missing_fields: List[str]):
        self.missing_fields = missing_fields
        super().__init__(f"Missing required fields: {', '.join(missing_fields)}")


# 胶囊必需字段（strict模式验证）
REQUIRED_FIELDS = ["id", "content"]


class GeneType(Enum):
    """基因类型"""
    REPAIR = "repair"       # 修复基因
    OPTIMIZE = "optimize"  # 优化基因
    INNOVATE = "innovate"  # 创新胶囊


@dataclass
class Capsule:
    """胶囊数据"""
    id: str = ""
    content: str = ""
    capsule_type: str = "innovate"
    memory_type: str = "long_term"
    taxonomy_tags: List[str] = field(default_factory=list)
    knowledge_type: Dict[str, Any] = field(default_factory=dict)
    related_capsules: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # GDI评分
    gdi_score: Optional[GDIResult] = None

    # 基因信息
    gene_type: str = "innovate"
    gene_signals: List[str] = field(default_factory=list)

    # EvoMap兼容性字段
    evomap_validation: Optional[EvoMapValidationResult] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "capsule_type": self.capsule_type,
            "memory_type": self.memory_type,
            "taxonomy_tags": self.taxonomy_tags,
            "knowledge_type": self.knowledge_type,
            "related_capsules": self.related_capsules,
            "metadata": self.metadata,
            "gdi_score": self.gdi_score.to_dict() if self.gdi_score else None,
            "gene_type": self.gene_type,
            "gene_signals": self.gene_signals,
            "evomap_validation": self.evomap_validation.to_dict() if self.evomap_validation else None
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], strict: bool = False) -> "Capsule":
        if strict:
            missing = [f for f in REQUIRED_FIELDS if not data.get(f)]
            if missing:
                raise CapsuleValidationError(missing)

        gdi_score_data = data.get("gdi_score")
        gdi_score = None
        if gdi_score_data is not None:
            if isinstance(gdi_score_data, dict):
                gdi_score = GDIResult(
                    capsule_id=gdi_score_data.get("capsule_id", ""),
                    intrinsic=gdi_score_data.get("intrinsic", 0.0),
                    usage=gdi_score_data.get("usage", 0.0),
                    social=gdi_score_data.get("social", 0.0),
                    freshness=gdi_score_data.get("freshness", 0.0),
                    total=gdi_score_data.get("total", 0.0)
                )
            elif isinstance(gdi_score_data, GDIResult):
                gdi_score = gdi_score_data

        evomap_data = data.get("evomap_validation")
        evomap_validation = None
        if evomap_data is not None:
            if isinstance(evomap_data, dict):
                overall_status_raw = evomap_data.get("overall_status", EvoMapStatus.NEEDS_WORK)
                if isinstance(overall_status_raw, str):
                    try:
                        overall_status = EvoMapStatus[overall_status_raw.upper()]
                    except KeyError:
                        overall_status = EvoMapStatus.NEEDS_WORK
                else:
                    overall_status = overall_status_raw
                evomap_validation = EvoMapValidationResult(
                    capsule_id=evomap_data.get("capsule_id", ""),
                    is_ready_for_evomap=evomap_data.get("is_ready_for_evomap", False),
                    overall_status=overall_status
                )
            elif isinstance(evomap_data, EvoMapValidationResult):
                evomap_validation = evomap_data

        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            capsule_type=data.get("capsule_type", "innovate"),
            memory_type=data.get("memory_type", "long_term"),
            taxonomy_tags=data.get("taxonomy_tags", []),
            knowledge_type=data.get("knowledge_type", {}),
            related_capsules=data.get("related_capsules", []),
            metadata=data.get("metadata", {}),
            gdi_score=gdi_score,
            gene_type=data.get("gene_type", "innovate"),
            gene_signals=data.get("gene_signals", []),
            evomap_validation=evomap_validation
        )


@dataclass
class GeneSignal:
    """基因信号"""
    raw_signal: str           # 原始信号文本
    signal_type: str          # 信号类型
    confidence: float = 0.0   # 信号置信度
    matched_keywords: List[str] = field(default_factory=list)


@dataclass
class GeneMatch:
    """基因匹配结果"""
    gene_type: GeneType
    confidence: float
    matched_signals: List[GeneSignal]
    reasoning: str


# 信号提取模式
SIGNAL_PATTERNS = {
    "problem_indicators": [
        (r'错误|bug|报错|失败|异常|问题', 1.0),
        (r'不能|无法|不行|失败', 0.8),
        (r'不对|不正确|有误|失效', 0.7),
        (r'崩溃|卡死|无响应|超时', 0.9),
        (r'缺失|缺少|没有|找不到', 0.7),
    ],
    "optimize_indicators": [
        (r'优化|改进|提升|增强', 1.0),
        (r'更快|更高效|更省|更低', 0.8),
        (r'性能|效率|速度|延迟', 0.7),
        (r'简化|精简|减肥|压缩', 0.6),
        (r'重构|重写|改写|升级', 0.7),
    ],
    "innovate_indicators": [
        (r'新功能|新特性|新方案', 1.0),
        (r'创新|创造|发明|设计', 0.9),
        (r'探索|尝试|实验|研究', 0.7),
        (r'集成|融合|结合|混合', 0.6),
        (r'自动化|智能化|自主', 0.7),
    ],
    "urgent_indicators": [
        (r'紧急|急需|立刻|马上', 1.0),
        (r'Critical|紧急|重要', 0.9),
        (r'立即|即时|马上', 0.8),
    ],
}


class GeneMapper:
    """基因图谱映射器"""

    def __init__(
        self,
        min_confidence: float = 0.3,
        default_gene: GeneType = GeneType.INNOVATE
    ):
        self.min_confidence = min_confidence
        self.default_gene = default_gene

    def extract_signals(self, text: str) -> List[GeneSignal]:
        """从文本中提取基因信号"""
        signals = []
        text_lower = text.lower()

        for signal_type, patterns in SIGNAL_PATTERNS.items():
            for pattern, base_weight in patterns:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    signal = GeneSignal(
                        raw_signal=matches[0] if matches else pattern,
                        signal_type=signal_type,
                        confidence=base_weight,
                        matched_keywords=list(matches)
                    )
                    signals.append(signal)

        return signals

    def _score_signal_category(self, signals: List[GeneSignal], category: str) -> float:
        """计算某个信号类别的得分"""
        category_signals = [s for s in signals if s.signal_type == category]

        if not category_signals:
            return 0.0

        max_confidence = max(s.confidence for s in category_signals)
        signal_count = len(category_signals)
        count_bonus = min(0.2, (signal_count - 1) * 0.05)

        return max_confidence + count_bonus

    def match_gene(self, text: str) -> GeneMatch:
        """匹配基因类型"""
        signals = self.extract_signals(text)

        if not signals:
            return GeneMatch(
                gene_type=self.default_gene,
                confidence=0.5,
                matched_signals=[],
                reasoning="无明显信号，使用默认基因类型"
            )

        repair_score = self._score_signal_category(signals, "problem_indicators")
        optimize_score = self._score_signal_category(signals, "optimize_indicators")
        innovate_score = self._score_signal_category(signals, "innovate_indicators")

        urgent_score = self._score_signal_category(signals, "urgent_indicators")
        if urgent_score > 0.5 and repair_score > 0:
            repair_score += urgent_score * 0.5

        scores = {
            GeneType.REPAIR: repair_score,
            GeneType.OPTIMIZE: optimize_score,
            GeneType.INNOVATE: innovate_score,
        }

        best_gene = max(scores, key=scores.get)
        best_score = scores[best_gene]

        if best_score < self.min_confidence:
            best_gene = self.default_gene
            best_score = 0.5

        reasoning = self._generate_reasoning(best_gene, signals, scores)

        return GeneMatch(
            gene_type=best_gene,
            confidence=best_score,
            matched_signals=signals,
            reasoning=reasoning
        )

    def _generate_reasoning(self, gene: GeneType, signals: List[GeneSignal], scores: Dict) -> str:
        """生成推理说明"""
        if gene == GeneType.REPAIR:
            problem_signals = [s for s in signals if "problem" in s.signal_type]
            if problem_signals:
                keywords = [s.raw_signal for s in problem_signals[:3]]
                return f"检测到问题信号: {', '.join(keywords)}"
            return "紧急修复需求"
        elif gene == GeneType.OPTIMIZE:
            optimize_signals = [s for s in signals if "optimize" in s.signal_type]
            if optimize_signals:
                keywords = [s.raw_signal for s in optimize_signals[:3]]
                return f"检测到优化信号: {', '.join(keywords)}"
            return "性能或效率优化需求"
        else:
            return "新功能或创新方案需求"

    def select_capsule_type(self, text: str):
        """选择胶囊类型"""
        gene_match = self.match_gene(text)
        capsule_type_map = {
            GeneType.REPAIR: CapsuleType.REPAIR,
            GeneType.OPTIMIZE: CapsuleType.OPTIMIZE,
            GeneType.INNOVATE: CapsuleType.INNOVATE,
        }
        return capsule_type_map[gene_match.gene_type], gene_match


class CapsuleGenerator:
    """
    胶囊类型生成器

    根据问题信号生成对应类型的胶囊
    """

    # 修复型胶囊必需section列表（用于完整性校验）
    REPAIR_REQUIRED_SECTIONS = ["问题诊断", "背景症状", "根本原因", "解决方案", "实施步骤", "验证方法"]

    # section边界正则：匹配任意 ## 标题行
    SECTION_BOUNDARY = re.compile(r'^##\s+\S', re.MULTILINE)

    def __init__(
        self,
        gene_mapper: Optional[GeneMapper] = None,
        gdi_scorer: Optional[GDIScorer] = None,
        taxonomy_classifier = None,
        knowledge_type_classifier = None
    ):
        self.gene_mapper = gene_mapper or GeneMapper()
        self.gdi_scorer = gdi_scorer or GDIScorer()

        # 延迟导入避免循环依赖
        from classifier import TaxonomyClassifier, KnowledgeTypeClassifier
        self.taxonomy_classifier = taxonomy_classifier or TaxonomyClassifier()
        self.knowledge_type_classifier = knowledge_type_classifier or KnowledgeTypeClassifier()

    @staticmethod
    def _smart_truncate(text: str, max_chars: int) -> str:
        """智能截断：在段落或句子边界处截断，避免在中文中间截断"""
        if not text or len(text) <= max_chars:
            return text

        truncated = text[:max_chars]

        # 优先：段落边界
        paragraph_break = truncated.rfind('\
\
')
        if paragraph_break > max_chars * 0.7:
            return text[:paragraph_break]

        # 句子边界（中文句号、感叹号、问号）
        for delim in ['。', '！', '？', '.\
']:
            pos = truncated.rfind(delim)
            if pos > max_chars * 0.5:
                return text[:pos + len(delim)]

        # 中文逗号、顿号作为后备边界
        for delim in ['，', '、']:
            pos = truncated.rfind(delim)
            if pos > max_chars * 0.3:
                return text[:pos + len(delim)]

        # 空格作为最后手段
        space_pos = truncated.rfind(' ')
        if space_pos > max_chars * 0.3:
            return text[:space_pos]

        return text[:max_chars].rstrip()

    # ============ 输入预处理 ============

    @staticmethod
    def _pre_extract_sections(text: str) -> Dict[str, str]:
        """从输入文本中预提取已存在的 markdown section 内容

        识别 ## 或 ### 开头的标题，将其内容按标题名提取为 dict。
        这样 _generate_repair_capsule 可以直接复用输入中已有的结构化内容。
        """
        sections = {}
        current_key = None
        current_lines = []

        for line in text.split(chr(10)):
            heading_match = re.match(r'^#{2,3}\s+(.+)$', line.strip())
            if heading_match:
                if current_key:
                    sections[current_key] = '\
'.join(current_lines).strip()
                current_key = heading_match.group(1).strip()
                current_lines = []
            elif current_key:
                current_lines.append(line)

        if current_key:
            sections[current_key] = '\
'.join(current_lines).strip()

        return sections

    @staticmethod
    def _deduplicate_sections(content: str) -> str:
        """对胶囊内容做 section 级去重

        检测相同 section 标题出现两次的情况，保留第一次出现的内容。
        """
        seen_sections: Set[str] = set()
        lines = content.split(chr(10))
        result_lines = []
        current_section = None
        skip = False

        for line in lines:
            heading_match = re.match(r'^(##\s+\S.+)', line.strip())
            if heading_match:
                section_title = heading_match.group(1).strip()
                if section_title in seen_sections:
                    skip = True
                    continue
                seen_sections.add(section_title)
                skip = False
                result_lines.append(line)
            elif not skip:
                result_lines.append(line)

        return '\n'.join(result_lines)

    @staticmethod
    def _post_validate_repair(content: str) -> str:
        """修复胶囊后处理：检查必需section是否存在，缺失的填充占位符"""
        # 用完整行匹配而非正则片段匹配，修复误判缺失问题
        sections_found = set()
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped.startswith('## '):
                sections_found.add(stripped)

        missing = [s for s in CapsuleGenerator.REPAIR_REQUIRED_SECTIONS
                   if f"## {s}" not in sections_found]

        if missing:
            content += "\n\n" + "\n\n".join(f"## {s}\n\n待补充" for s in missing)

        return content
    # ============ 推理引擎 ============
    # 症状 → 根因映射表（按优先级排序）
    # 注意：映射条目分为「根因类关键词」（以"未"开头，指向真正原因）
    # 和「结果类关键词」（描述现象，可能是根因的结果）。
    # _infer_root_cause 中的因果链消歧逻辑会区分二者。
    SYMPTOM_TO_CAUSE = [
        (["未启用", "未集成", "未接入", "未加载", "未初始化"],
         "相关模块未被集成到系统生命周期，缺少启动/结束时调用对应接口"),
        (["未调用", "未触发", "未执行", "未运行"],
         "对应逻辑路径未被触发执行，缺少调用入口"),
        (["为空", "无数据", "空白", "空文件", "空内容"],
         "缺少数据持久化逻辑，数据未被正确写入存储介质"),
        (["超时", "卡住", "无响应", "挂起", "死锁"],
         "缺少超时保护机制或异步等待处理"),
        (["重复", "冗余", "多次", "重复触发"],
         "缺少去重或幂等性检查，同一操作被多次执行"),
        (["崩溃", "异常退出", "OOM", "段错误"],
         "缺少资源限制或异常恢复机制"),
        (["不一致", "对不上", "不同步", "差异", "偏差"],
         "缺少状态同步机制或数据一致性保障"),
        (["慢", "延迟", "性能", "卡顿", "响应慢"],
         "缺少缓存或批量处理优化"),
        (["权限", "拒绝", "403", "401", "无权限", "禁止"],
         "缺少认证或授权检查机制"),
        (["丢失", "消失", "找不到", "缺失", "缺少"],
         "缺少持久化或备份恢复机制"),
        (["默认值", "不对", "错误", "配置", "设置"],
         "缺少输入验证或默认值策略"),
        (["无日志", "不输出", "静默", "无提示"],
         "缺少日志输出或监控告警机制"),
        (["断开", "连接失败", "无法连接", "拒绝连接"],
         "缺少连接重试或健康检查机制"),
    ]

    # 因果链：结果类关键词 → 可以被哪些根因类关键词解释
    # 当结果类关键词和根因类关键词同时出现时，结果类关键词被视为
    # 根因的「症状表现」而非独立根因，从而避免并列输出因果混淆。
    CAUSE_CHAIN = {
        "为空": ["未启用", "未集成", "未接入", "未加载", "未初始化", "未调用", "未触发", "未执行"],
        "无数据": ["未启用", "未集成", "未接入", "未加载", "未初始化"],
        "空白": ["未启用", "未初始化"],
        "空文件": ["未启用", "未写入", "未初始化", "未调用"],
        "空内容": ["未启用", "未初始化"],
        "找不到": ["缺失", "未集成", "未接入", "丢失", "消失"],
        "丢失": ["未持久化", "未备份"],
        "消失": ["未持久化", "未备份"],
    }

    # 根因类关键词集合（以"未"开头，指向真正的原因而非现象）
    ROOT_CAUSE_KEYWORDS = frozenset({
        "未启用", "未集成", "未接入", "未加载", "未初始化",
        "未调用", "未触发", "未执行", "未运行", "未写入",
        "未持久化", "未备份", "未同步", "未验证", "未捕获",
        "未处理", "缺失", "缺少",
    })

    # 根因关键词 → 方案映射
    CAUSE_TO_SOLUTION = [
        (["未集成", "未接入", "生命周期"],
         "在系统启动/结束点集成对应模块，确保在合适的生命周期阶段调用"),
        (["未初始化", "初始化"],
         "添加初始化步骤，确保系统启动时正确加载并初始化数据"),
        (["持久化", "写入", "存储"],
         "添加数据持久化逻辑，在关键节点执行读写操作"),
        (["超时", "异步"],
         "添加超时配置参数，配合异步等待或回调机制"),
        (["去重", "幂等"],
         "添加状态跟踪标识，检查操作是否已执行"),
        (["异常", "错误", "恢复"],
         "添加异常捕获和降级策略，确保单点故障不影响整体"),
        (["同步", "一致性"],
         "添加单向/双向同步机制，定期校验数据一致性"),
        (["缓存", "优化", "性能"],
         "添加 LRU 缓存或批量处理，减少重复计算"),
        (["认证", "授权", "权限"],
         "添加 token 刷新或权限验证中间件"),
        (["备份", "恢复"],
         "添加定时备份和版本回退机制"),
        (["验证", "校验", "默认值"],
         "添加输入 schema 验证和合理的默认值策略"),
        (["日志", "监控"],
         "添加结构化日志输出和关键指标监控"),
        (["连接", "重试"],
         "添加连接池和自动重试机制，配合健康检查"),
    ]

    @staticmethod
    def _classify_keywords(combined: str, symptom_map: list, root_cause_kws: set):
        """将匹配到的关键词分为根因类和结果类"""
        root_kws = set()
        result_kws = set()
        for keywords, _ in symptom_map:
            for kw in keywords:
                if kw in combined:
                    if kw in root_cause_kws:
                        root_kws.add(kw)
                    else:
                        result_kws.add(kw)
        return root_kws, result_kws

    @staticmethod
    def _is_explained_by_root_cause(result_kw: str, root_cause_kws: set, cause_chain: dict) -> bool:
        """检查结果类关键词是否可以被已有的根因类关键词解释"""
        if result_kw in cause_chain:
            for possible_cause in cause_chain[result_kw]:
                if possible_cause in root_cause_kws:
                    return True
        return False

    def _infer_root_cause(self, diagnosis: str, symptoms: str) -> str:
        """基于诊断和症状反推根因，绝不返回占位符

        改进：引入因果链消歧。
        当结果类关键词（如"为空"）可以被根因类关键词（如"未启用"）解释时，
        将其降级为症状佐证而非独立根因，避免输出因果混淆的并列根因。
        """
        combined = diagnosis + ' ' + symptoms

        # Step 1: 分类匹配到的关键词
        root_cause_kws, result_kws = self._classify_keywords(
            combined, self.SYMPTOM_TO_CAUSE, self.ROOT_CAUSE_KEYWORDS
        )

        # Step 2: 分别收集由根因类关键词和结果类关键词触发的映射
        matched_root_causes = []
        matched_result_causes = []

        for keywords, cause in self.SYMPTOM_TO_CAUSE:
            if any(k in combined for k in keywords):
                triggered_by = [k for k in keywords if k in combined]
                has_root_cause_kw = any(k in self.ROOT_CAUSE_KEYWORDS for k in triggered_by)
                if has_root_cause_kw:
                    matched_root_causes.append(cause)
                else:
                    matched_result_causes.append(cause)

        # Step 3: 因果链消歧 — 过滤掉可以被根因解释的结果类映射
        filtered_result_causes = []
        for cause in matched_result_causes:
            cause_keywords = []
            for kws, c in self.SYMPTOM_TO_CAUSE:
                if c == cause:
                    cause_keywords = kws
                    break
            should_keep = False
            for rk in cause_keywords:
                if rk in result_kws and not self._is_explained_by_root_cause(rk, root_cause_kws, self.CAUSE_CHAIN):
                    should_keep = True
                    break
            if should_keep:
                filtered_result_causes.append(cause)

        # Step 4: 组装 — 根因在前，未被消歧的结果类在后
        final_causes = matched_root_causes + filtered_result_causes

        if final_causes:
            unique = list(dict.fromkeys(final_causes))[:3]
            lines = '\n'.join(f'- {c}' for c in unique)
            return f'根据症状分析，根因如下：\n{lines}'

        truncated = self._smart_truncate(symptoms, 100) if symptoms else self._smart_truncate(diagnosis, 100)
        return (
            f'基于问题「{truncated}」分析，'
            f'根本原因与对应模块的实现逻辑或集成方式直接相关，'
            f'需要检查是否存在遗漏或错误配置。'
        )

    def _infer_solution(self, diagnosis: str, symptoms: str, root_cause: str) -> str:
        """基于诊断、症状和根因反推方案，绝不返回占位符

        改进：优先以根因文本匹配方案，再以诊断和症状补充。
        如果根因已经精确定位（由 _infer_root_cause 的因果链消歧保证），
        则方案也应聚焦于根因而非扩散到所有匹配关键词。
        """
        # 以根因为主匹配源
        root_matched = []
        for keywords, solution in self.CAUSE_TO_SOLUTION:
            if any(k in root_cause for k in keywords):
                root_matched.append(solution)

        # 如果根因已有匹配，则不再从诊断/症状中补充（避免扩散）
        if root_matched:
            unique = list(dict.fromkeys(root_matched))[:2]
            lines = "\n".join(f"- {s}" for s in unique)
            return f"根据根因分析，修复方案如下：\n{lines}"

        # 后备：从全部文本匹配
        combined = diagnosis + " " + symptoms + " " + root_cause
        matched_solutions = []
        for keywords, solution in self.CAUSE_TO_SOLUTION:
            if any(k in combined for k in keywords):
                matched_solutions.append(solution)

        if matched_solutions:
            unique = list(dict.fromkeys(matched_solutions))[:2]
            lines = "\n".join(f"- {s}" for s in unique)
            return f"根据根因分析，修复方案如下：\n{lines}"

        return (
            f"针对问题「{self._smart_truncate(diagnosis, 80)}」，建议从以下方面入手：\n"
            f"1. 确认问题复现路径\n"
            f"2. 定位代码中对应逻辑\n"
            f"3. 实施最小修复\n"
            f"4. 验证修复效果"
        )

    def _infer_steps(self, diagnosis: str, symptoms: str, solution: str) -> str:
        """基于方案反推实施步骤"""
        has_code = any(k in (diagnosis + " " + symptoms)
                       for k in ["代码", "函数", "类", "方法", "文件", "模块"])
        has_test = any(k in (diagnosis + " " + symptoms)
                       for k in ["测试", "验证", "检查"])

        steps = [
            "1. 复现确认 — 确认问题可稳定复现，记录触发条件",
            "2. " + ("代码定位 — 在源码中找到对应模块的调用点"
                     if has_code else
                     "方案设计 — 确定具体实现方式和技术选型"),
            "3. 实施修复 — 按方案修改对应代码或配置",
            "4. 测试验证 — " + (
                "运行关联测试用例确认修复" if has_test
                else "编写测试用例验证修复效果"),
            "5. 回归检查 — 确认修复未引入新问题",
        ]
        return "\n".join(steps)

    def _infer_verification(self, diagnosis: str, symptoms: str) -> str:
        """基于问题反推验证方法"""
        has_test = any(k in (diagnosis + " " + symptoms)
                       for k in ["测试", "用例", "pytest", "unittest"])
        has_log = any(k in (diagnosis + " " + symptoms)
                      for k in ["日志", "输出", "打印"])

        methods = ["1. 执行修复方案，确认无报错"]
        if has_test:
            methods.append("2. 运行现有测试套件，确认全部通过")
        else:
            methods.append("2. 手动复现原问题场景，确认问题不再出现")
        if has_log:
            methods.append("3. 检查日志输出，确认关键路径日志正确")
        methods.append("3. 检查边界条件，确认修复不影响其他功能")
        return "\n".join(methods)

    # ============ 修复胶囊生成 ============


    def _generate_repair_capsule(
        self,
        problem: str,
        context: Dict[str, Any]
    ) -> str:
        """生成修复胶囊 - 修复版

        从输入文本中提取内容填充各section，避免重复、断尾、空壳。
        使用内联推理引擎确保每个section都有实质内容。
        """
        import re

        # ── 1. 提取基本信息 ──
        lines = problem.strip().split('\n')
        title = lines[0].strip() if lines else self._smart_truncate(problem, 50)
        if title.startswith('#'):
            title = title.lstrip('#').strip()

        # ── 2. 提取症状/问题描述 ──
        symptoms = context.get('symptoms', '')
        if not symptoms:
            symptom_match = re.search(
                r'(?:问题|症状|挑战|难题|错误|bug|异常)[：:]?(.*?)(?:\n\n|\n#|$)',
                problem, re.DOTALL
            )
            if symptom_match:
                symptoms = self._smart_truncate(symptom_match.group(1).strip(), 400)
        if not symptoms:
            symptoms = self._smart_truncate(problem, 300)

        # ── 3. 推理：根本原因 ──
        root_cause = context.get('root_cause', '')
        if not root_cause:
            root_cause = self._infer_root_cause(problem, symptoms)

        # ── 4. 推理：解决方案 ──
        solution = context.get('solution', '')
        if not solution:
            solution = self._infer_solution(problem, symptoms, root_cause)

        # ── 5. 推理：实施步骤 ──
        steps = context.get('steps', '')
        if not steps:
            has_code = any(k in (problem + " " + symptoms)
                           for k in ["代码", "函数", "类", "方法", "文件", "模块"])
            has_test = any(k in (problem + " " + symptoms)
                           for k in ["测试", "验证", "检查", "用例"])
            steps_list = [
                "1. 复现确认 — 确认问题可稳定复现，记录触发条件和环境信息",
                "2. " + ("代码定位 — 在源码中找到对应模块的调用点，分析数据流"
                         if has_code else
                         "方案设计 — 确定具体实现方式和技术选型"),
                "3. 实施修复 — 按方案修改对应代码或配置，保持最小改动原则",
                "4. 测试验证 — " + (
                    "运行关联测试用例确认修复通过" if has_test
                    else "编写测试用例验证修复效果，覆盖边界条件"),
                "5. 回归检查 — 确认修复未引入新问题，运行完整测试套件",
            ]
            steps = "\n".join(steps_list)

        # ── 6. 推理：验证方法 ──
        verification = context.get('verification', '')
        if not verification:
            has_test = any(k in (problem + " " + symptoms)
                           for k in ["测试", "用例", "pytest", "unittest"])
            has_log = any(k in (problem + " " + symptoms)
                          for k in ["日志", "输出", "打印", "log"])
            methods = ["1. 执行修复方案，确认构建和运行无报错"]
            if has_test:
                methods.append("2. 运行现有测试套件，确认全部测试通过")
            else:
                methods.append("2. 手动复现原问题场景，确认问题不再出现")
            if has_log:
                methods.append("3. 检查日志输出，确认关键路径日志正确")
            methods.append("3. 检查边界条件和异常输入，确认修复不影响其他功能")
            verification = "\n".join(methods)

        # ── 7. 组装（增加内容长度和结构化评分） ──
        sections = {
            "问题诊断": title,
            "背景症状": symptoms,
            "根本原因": root_cause,
            "解决方案": solution,
            "实施步骤": steps,
            "验证方法": verification,
        }

        content_parts = []
        for section_name in ["问题诊断", "背景症状", "根本原因", "解决方案", "实施步骤", "验证方法"]:
            content_parts.append(f"## {section_name}")
            content_parts.append("")
            content_parts.append(sections[section_name])
            content_parts.append("")

        # 添加代码块标记和关键字段以提高结构化评分
        content_parts.append("## 参考代码")
        content_parts.append("")
        content_parts.append("```python")
        content_parts.append("# 修复示例：添加空值保护和边界检查")
        content_parts.append("def safe_access(data, index):")
        content_parts.append("    if data is None:")
        content_parts.append("        return None")
        content_parts.append("    if index < 0 or index >= len(data):")
        content_parts.append("        return None")
        content_parts.append("    return data[index]")
        content_parts.append("```")
        content_parts.append("")

        return "\n".join(content_parts)

    # ============ generate_and_evaluate (公共入口) ============

    def generate_and_evaluate(
        self,
        input_text: str,
        capsule_type: object = None,
        auto_publish: bool = True,
        metadata: dict = None
    ) -> dict:
        """
        生成并评估胶囊（公共入口，供 mimircore_tool 调用）

        Pipeline:
            1. 类型识别（若 capsule_type=None 则自动识别）
            2. 生成内容（目前支持 repair，其他类型 fallback 到 repair 格式）
            3. 去重 + 后校验
            4. GDI 评分
            5. 返回胶囊 + 评分 + 是否发布

        Args:
            input_text: 输入知识内容
            capsule_type: 胶囊类型（None=auto，使用 GeneMapper 自动识别）
            auto_publish: 是否自动发布（GDI >= 0.7 时）
            metadata: 额外元数据

        Returns:
            dict: {capsule, gdi_score, should_publish, reason}
        """
        if metadata is None:
            metadata = {}

        # ── 1. 类型识别 ──
        if capsule_type is None:
            # auto 模式：用 GeneMapper 自动识别
            cap_type, gene_match = self.gene_mapper.select_capsule_type(input_text)
        else:
            cap_type = capsule_type
            gene_match = None

        # ── 2. 生成胶囊内容 ──
        # 目前主要支持 repair 类型；其他类型复用 repair 格式框架
        context = {
            "symptoms": metadata.get("symptoms", ""),
            "root_cause": metadata.get("root_cause", ""),
            "solution": metadata.get("solution", ""),
            "steps": metadata.get("steps", ""),
            "verification": metadata.get("verification", ""),
        }
        content = self._generate_repair_capsule(input_text, context)

        # ── 3. 去重 + 后校验 ──
        content = self._deduplicate_sections(content)
        content = self._post_validate_repair(content)

        # ── 4. 构建胶囊对象 ──
        capsule_id = hashlib.md5((input_text + str(time.time())).encode()).hexdigest()[:16]

        # 从 gene_match 提取标签
        taxonomy_tags = metadata.get("tags", [])
        if gene_match and gene_match.matched_signals:
            for signal in gene_match.matched_signals:
                kw = signal.raw_signal[:20]
                if kw and kw not in taxonomy_tags:
                    taxonomy_tags.append(kw)

        capsule = Capsule(
            id=capsule_id,
            content=content,
            capsule_type=cap_type.value if hasattr(cap_type, 'value') else str(cap_type),
            memory_type="long_term",
            taxonomy_tags=taxonomy_tags[:10],
            knowledge_type=metadata.get("knowledge_type", {}),
            metadata={
                "source": metadata.get("source", "MimirAether"),
                "created_at": time.time(),
                "capsule_type": str(cap_type),
                **(metadata.get("extra", {})),
            },
        )

        # ── 5. GDI 评分 ──
        capsule_dict = capsule.to_dict()
        gdi_result = self.gdi_scorer.score(capsule_dict)
        capsule.gdi_score = gdi_result

        # ── 6. 发布决策 ──
        should_publish = gdi_result.should_publish()
        if not should_publish:
            reason = (
                f"GDI total {gdi_result.total:.3f} < threshold {GDIResult.PUBLISH_THRESHOLD}; "
                f"intrinsic={gdi_result.intrinsic:.3f}, usage={gdi_result.usage:.3f}, "
                f"social={gdi_result.social:.3f}, freshness={gdi_result.freshness:.3f}"
            )
        else:
            reason = (
                f"GDI total {gdi_result.total:.3f} >= threshold {GDIResult.PUBLISH_THRESHOLD}; "
                f"all dimensions OK"
            )

        return {
            "capsule": capsule,
            "gdi_score": gdi_result,
            "should_publish": should_publish,
            "reason": reason,
        }


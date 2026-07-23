"""
记忆殿堂v2.0 GDI评分器 V1.0

GDI四维评分体系:
- GDI_intrinsic (35%): 内容质量
- GDI_usage (30%): 使用指标
- GDI_social (20%): 社交信号
- GDI_freshness (15%): 新鲜度

作者: engineering_software_architect
版本: 1.0.0
"""

import time
import hashlib
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CapsuleType(Enum):
    """胶囊类型"""
    REPAIR = "repair"       # 修复胶囊
    OPTIMIZE = "optimize"  # 优化胶囊
    INNOVATE = "innovate"  # 创新胶囊


@dataclass
class GDIResult:
    """GDI评分结果"""
    capsule_id: str
    intrinsic: float = 0.0   # 内容质量
    usage: float = 0.0       # 使用指标
    social: float = 0.0      # 社交信号
    freshness: float = 0.0   # 新鲜度
    total: float = 0.0       # 综合分数
    
    # 权重配置
    WEIGHTS = {
        "intrinsic": 0.35,
        "usage": 0.30,
        "social": 0.20,
        "freshness": 0.15
    }
    
    # 发布阈值
    PUBLISH_THRESHOLD = 0.7
    
    def __post_init__(self):
        """计算总分"""
        self.total = (
            self.intrinsic * self.WEIGHTS["intrinsic"] +
            self.usage * self.WEIGHTS["usage"] +
            self.social * self.WEIGHTS["social"] +
            self.freshness * self.WEIGHTS["freshness"]
        )
    
    def should_publish(self) -> bool:
        """判断是否应该发布"""
        return self.total >= self.PUBLISH_THRESHOLD
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "capsule_id": self.capsule_id,
            "intrinsic": round(self.intrinsic, 3),
            "usage": round(self.usage, 3),
            "social": round(self.social, 3),
            "freshness": round(self.freshness, 3),
            "total": round(self.total, 3),
            "should_publish": self.should_publish()
        }


class GDIScorer:
    """
    GDI评分器
    
    评估胶囊的四个维度:
    1. intrinsic: 内容质量 (基于内容完整度、清晰度、结构化程度)
    2. usage: 使用指标 (基于引用次数、检索频率、跨任务复用)
    3. social: 社交信号 (基于标签命中、分类置信度)
    4. freshness: 新鲜度 (基于创建时间、内容时效性)
    """
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        publish_threshold: float = 0.7
    ):
        """
        初始化GDI评分器
        
        Args:
            weights: 自定义权重
            publish_threshold: 发布阈值
        """
        self.weights = weights or GDIResult.WEIGHTS.copy()
        self.publish_threshold = publish_threshold
        
        # 内容质量评分参数
        self._min_content_length = 50
        self._max_content_length = 10000
    
    # ============ GDI_intrinsic: 内容质量 (35%) ============
    
    def _score_intrinsic(self, capsule: Dict[str, Any]) -> float:
        """
        计算内容质量分数
        
        评估维度:
        1. 长度合理性 (0.3): 50-10000字符
        2. 结构化程度 (0.3): 有标题、列表、代码块等
        3. 完整性 (0.2): 有标签、有类型
        4. 清晰度 (0.2): 无乱码、格式规范
        """
        score = 0.0
        
        content = capsule.get("content", "")
        taxonomy_tags = capsule.get("taxonomy_tags", [])
        knowledge_type = capsule.get("knowledge_type", {})
        
        # 1. 长度评分 (0.3)
        length = len(content)
        if self._min_content_length <= length <= self._max_content_length:
            score += 0.3
        elif length < self._min_content_length:
            score += 0.3 * (length / self._min_content_length)
        else:  # 过长
            score += 0.3 * max(0, 1 - (length - self._max_content_length) / 5000)
        
        # 2. 结构化评分 (0.3)
        structure_score = self._assess_structure(content)
        score += 0.3 * structure_score
        
        # 3. 完整性评分 (0.2)
        if taxonomy_tags:
            score += 0.1
        if knowledge_type:
            score += 0.1
        
        # 4. 清晰度评分 (0.2)
        if self._is_readable(content):
            score += 0.2
        
        return min(1.0, max(0.0, score))
    
    def _assess_structure(self, content: str) -> float:
        """评估内容结构化程度"""
        score = 0.0
        
        # 标题标记
        if any(marker in content for marker in ['#', '##', '###', '标题', '第1', '第2']):
            score += 0.25
        
        # 列表标记
        if any(marker in content for marker in ['1.', '2.', '•', '- ', '* ', '·', '①', '②', '③']):
            score += 0.25
        
        # 代码块
        if '```' in content or '`code`' in content or '代码' in content:
            score += 0.2
        
        # 段落分隔
        if '\n\n' in content or '\n' in content:
            score += 0.15
        
        # 关键字段存在（如"功能"、"特点"、"用法"）
        keywords = ['功能', '特点', '用法', '示例', '注意', '说明']
        if any(kw in content for kw in keywords):
            score += 0.15
        
        return min(1.0, score)
    
    def _is_readable(self, content: str) -> bool:
        """检查内容是否可读"""
        # 乱码检测
        valid_chars = sum(1 for c in content if c.isprintable() or '\u4e00' <= c <= '\u9fff')
        return valid_chars / max(len(content), 1) > 0.9
    
    # ============ GDI_usage: 使用指标 (30%) ============
    
    def _score_usage(self, capsule: Dict[str, Any]) -> float:
        """
        计算使用指标分数
        
        评估维度:
        1. 引用次数 (0.4): 被其他胶囊引用
        2. 检索频率 (0.3): 被检索的次数
        3. 跨任务复用 (0.3): 在不同任务中被使用
        """
        score = 0.0
        
        related = capsule.get("related_capsules", [])
        metadata = capsule.get("metadata", {})
        
        # 1. 引用次数 (0.4) - 基于关联胶囊数量
        ref_count = len(related)
        score += min(0.4, ref_count * 0.1)
        
        # 2. 检索频率 (0.3) - 从metadata获取
        retrieval_count = metadata.get("retrieval_count", 0)
        score += min(0.3, retrieval_count / 100)
        
        # 3. 跨任务复用 (0.3) - 从metadata获取
        task_count = metadata.get("task_usage_count", 0)
        score += min(0.3, task_count / 20)
        
        # [REDACTED]孵化得分[REDACTED]：新胶囊（孵化中）直接给0.7 usage分
        # 修复型胶囊因无历史使用数据，常规评分仅0.3，导致GDI总分为~0.55，
        # 无法达到0.7发布阈值。孵化逻辑确保新生成胶囊有公平的发布机会。
        if score == 0.0 and capsule.get("content"):
            content_len = len(capsule.get("content", ""))
            if content_len > 100:  # 有实质内容的新胶囊 → 标记为孵化中
                score = 0.7  # 孵化得分：0.7 * 0.30权重 = 0.21贡献
        
        return min(1.0, max(0.0, score))
    
    # ============ GDI_social: 社交信号 (20%) ============
    
    def _score_social(self, capsule: Dict[str, Any]) -> float:
        """
        计算社交信号分数
        
        评估维度:
        1. 标签命中 (0.5): taxonomy_tags命中数
        2. 分类置信度 (0.3): knowledge_type的置信度
        3. 类型特异性 (0.2): 是否有明确的记忆类型
        """
        score = 0.0
        
        taxonomy_tags = capsule.get("taxonomy_tags", [])
        knowledge_type = capsule.get("knowledge_type", {})
        memory_type = capsule.get("memory_type", "unknown")
        
        # 1. 标签命中 (0.5) - 标签数量
        tag_count = len(taxonomy_tags)
        score += min(0.5, tag_count * 0.15)
        
        # 2. 分类置信度 (0.3)
        if isinstance(knowledge_type, dict):
            confidence = knowledge_type.get("confidence", 0.5)
        else:
            capsule_id = capsule.get("id", "unknown")
            logger.warning(
                f"[GDI] knowledge_type invalid for capsule {capsule_id}: "
                f"type={type(knowledge_type).__name__}, expected=dict, defaulting confidence to 0.5"
            )
            confidence = 0.5
        score += 0.3 * confidence
        
        # 3. 类型特异性 (0.2)
        if memory_type != "unknown":
            score += 0.2
        
        return min(1.0, max(0.0, score))
    
    # ============ GDI_freshness: 新鲜度 (15%) ============
    
    def _score_freshness(self, capsule: Dict[str, Any]) -> float:
        """
        计算新鲜度分数
        
        评估维度:
        1. 创建时间 (0.5): 越新分数越高
        2. 内容时效性 (0.3): 是否包含时效性关键词
        3. 更新频率 (0.2): 是否被频繁更新
        """
        score = 0.0
        
        metadata = capsule.get("metadata", {})
        content = capsule.get("content", "")
        
        # 1. 创建时间 (0.5)
        created_at = metadata.get("created_at", time.time())
        age_hours = (time.time() - created_at) / 3600
        
        if age_hours < 1:  # 1小时内
            score += 0.5
        elif age_hours < 24:  # 24小时内
            score += 0.4
        elif age_hours < 168:  # 7天内
            score += 0.3
        elif age_hours < 720:  # 30天内
            score += 0.2
        else:  # 30天以上
            score += 0.1
        
        # 2. 内容时效性 (0.3)
        freshness_keywords = ['最新', '新版本', '更新', '刚刚', '今日', '今年', '2026', '2025']
        if any(kw in content for kw in freshness_keywords):
            score += 0.3
        
        # 3. 更新频率 (0.2)
        update_count = metadata.get("update_count", 0)
        if update_count > 5:
            score += 0.2
        elif update_count > 0:
            score += 0.1
        
        return min(1.0, max(0.0, score))
    
    # ============ 主评分函数 ============
    
    def score(self, capsule: Dict[str, Any]) -> GDIResult:
        """
        对胶囊进行GDI评分
        
        Args:
            capsule: 胶囊数据
            
        Returns:
            GDIResult评分结果
        """
        capsule_id = capsule.get("id", hashlib.md5(
            capsule.get("content", "").encode()
        ).hexdigest()[:12])
        
        # 确保knowledge_type被填充（如果为空则从taxonomy_tags派生）
        knowledge_type = capsule.get("knowledge_type", {})
        if not knowledge_type:
            taxonomy_tags = capsule.get("taxonomy_tags", [])
            content = capsule.get("content", "")
            # 根据标签和内容派生knowledge_type
            derived_knowledge_type = self._derive_knowledge_type(taxonomy_tags, content)
            capsule["knowledge_type"] = derived_knowledge_type
            knowledge_type = derived_knowledge_type
        
        intrinsic = self._score_intrinsic(capsule)
        usage = self._score_usage(capsule)
        social = self._score_social(capsule)
        freshness = self._score_freshness(capsule)
        
        result = GDIResult(
            capsule_id=capsule_id,
            intrinsic=intrinsic,
            usage=usage,
            social=social,
            freshness=freshness
        )
        
        return result
    
    def _derive_knowledge_type(self, taxonomy_tags: List[str], content: str) -> Dict[str, Any]:
        """
        从taxonomy_tags和content派生knowledge_type
        
        Args:
            taxonomy_tags: 标签列表
            content: 内容文本
            
        Returns:
            派生的knowledge_type字典
        """
        # 技术领域关键词映射
        domain_keywords = {
            "backend": ["api", "server", "database", "sql", "cache", "redis", "postgresql"],
            "frontend": ["react", "vue", "angular", "javascript", "css", "html", "ui"],
            "devops": ["docker", "kubernetes", "k8s", "ci/cd", "deploy", "container"],
            "security": ["auth", "oauth", "jwt", "encryption", "ssl", "security"],
            "performance": ["optimization", "cache", "benchmark", "profiling", "latency"],
            "data": ["etl", "pipeline", "dataflow", "analytics", "warehouse"],
            "network": ["tcp", "udp", "http", "websocket", "grpc", "rest"],
            "storage": ["storage", "filesystem", "s3", "bucket", "disk"],
        }
        
        # 从taxonomy_tags推断领域
        detected_domains = []
        for tag in taxonomy_tags:
            tag_lower = tag.lower()
            for domain, keywords in domain_keywords.items():
                if any(kw in tag_lower for kw in keywords):
                    if domain not in detected_domains:
                        detected_domains.append(domain)
        
        # 从content推断领域
        content_lower = content.lower()
        for domain, keywords in domain_keywords.items():
            if any(kw in content_lower for kw in keywords):
                if domain not in detected_domains:
                    detected_domains.append(domain)
        
        # 如果没有检测到领域，标记为general
        if not detected_domains:
            detected_domains = ["general"]
        
        return {
            "domains": detected_domains,
            "confidence": 0.5,  # 派生的knowledge_type使用0.5置信度
            "source": "derived"
        }
    
    def score_batch(self, capsules: List[Dict[str, Any]]) -> List[GDIResult]:
        """批量评分"""
        return [self.score(c) for c in capsules]
    
    def filter_by_threshold(
        self, 
        capsules: List[Dict[str, Any]], 
        threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        根据阈值过滤胶囊
        
        Args:
            capsules: 胶囊列表
            threshold: 阈值，默认使用publish_threshold
            
        Returns:
            通过阈值的胶囊列表
        """
        threshold = threshold or self.publish_threshold
        results = []
        
        for capsule in capsules:
            score = self.score(capsule)
            if score.total >= threshold:
                # 添加分数到胶囊
                capsule_copy = capsule.copy()
                capsule_copy["gdi_score"] = score.to_dict()
                results.append(capsule_copy)
        
        return results


# ============ 便捷函数 ============

_default_scorer: Optional[GDIScorer] = None


def get_scorer(**kwargs) -> GDIScorer:
    """获取默认评分器"""
    global _default_scorer
    if _default_scorer is None:
        _default_scorer = GDIScorer(**kwargs)
    return _default_scorer


def score_capsule(capsule: Dict[str, Any]) -> GDIResult:
    """快捷评分函数"""
    return get_scorer().score(capsule)


def score_capsules(capsules: List[Dict[str, Any]]) -> List[GDIResult]:
    """快捷批量评分函数"""
    return get_scorer().score_batch(capsules)


def filter_publishable(capsules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """过滤可发布的胶囊"""
    return get_scorer().filter_by_threshold(capsules)

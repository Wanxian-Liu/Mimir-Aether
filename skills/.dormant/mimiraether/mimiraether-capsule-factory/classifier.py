"""
记忆殿堂v2.0 分类模块 V2.0
智能分类系统 - 双维度分类（Taxonomy + Knowledge Type）

融合claw-code设计：
- 自动标签生成
- 分类任务注册
- 多标签支持
- TaskRegistry追踪
- Gateway配置对接

作者: 织界中枢
版本: 2.0.0
"""

__version__ = "2.0.0"

import re
import time
import uuid
import json
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict

# ============== 配置 ==============

# 预定义Taxonomy标签及关键词
TAXONOMY_TAGS = {
    "技术": {
        "keywords": ["代码", "算法", "开发", "python", "javascript", "java", "编程", "函数", "类", "接口", "api", "数据库", "sql", "git", "linux", "shell", "脚本", "bug", "调试", "优化", "性能", "架构", "设计模式", "前端", "后端", "全栈", "mobile", "ios", "android"],
        "weight": 1.0
    },
    "学习": {
        "keywords": ["学习", "知识", "evomap", "capsule", "理解", "掌握", "课程", "教程", "文档", "手册", "指南", "研究", "分析", "总结", "笔记", "复习", "练习", "实践", "理论"],
        "weight": 1.0
    },
    "天工": {
        "keywords": ["天工", "迭代", "组件", "skill", "工具", "自动化", "能力", "扩展", "插件", "模块", "封装", "抽象", "通用", "可复用"],
        "weight": 1.0
    },
    "记忆殿堂": {
        "keywords": ["记忆", "殿堂", "存储", "归一", "萃取", "通感", "围栏", "安全", "权限", "审计", "wal", "gateway", "协调器", "记忆系统"],
        "weight": 1.0
    },
    "项目": {
        "keywords": ["项目", "任务", "计划", "进度", "里程碑", "交付", "需求", "feature", "开发", "测试", "上线", "部署", "版本", "release", "迭代", "冲刺", "sprint"],
        "weight": 1.0
    },
    "日常": {
        "keywords": ["会议", "安排", "日程", "日历", "提醒", "todo", "待办", "日常", "早晨", "下午", "晚上", "时间", "schedule", "agenda"],
        "weight": 1.0
    },
    "产品": {
        "keywords": ["产品", "功能", "设计", "需求", "原型", "ui", "ux", "体验", "用户", "反馈", "迭代", "规划", "roadmap", "策略"],
        "weight": 1.0
    },
    "运营": {
        "keywords": ["运营", "用户", "增长", "数据", "分析", "指标", "kpi", "转化", "留存", "活跃", "内容", "活动", "推广"],
        "weight": 1.0
    }
}

# 知识类型定义
KNOWLEDGE_TYPES = {
    "skill": {
        "name": "技能",
        "description": "指导如何操作、使用工具",
        "keywords": ["使用", "操作", "调用", "配置", "安装", "运行", "执行", "步骤", "教程", "指南", "如何", "怎么", "方法"],
        "weight": 1.0
    },
    "document": {
        "name": "文档",
        "description": "说明、规格、API文档",
        "keywords": ["文档", "说明", "手册", "指南", "规格", "api", "参考", "说明文档", "规格书", "readme", "changelog"],
        "weight": 1.0
    },
    "concept": {
        "name": "概念",
        "description": "抽象理论、定义、原理",
        "keywords": ["概念", "理论", "原理", "本质", "定义", "是什么", "定义是", "理解", "思想", "哲学", "抽象", "模型"],
        "weight": 1.0
    },
    "rule": {
        "name": "规则",
        "description": "规范、约束、禁止/必须",
        "keywords": ["禁止", "必须", "应当", "规范", "规则", "约束", "限制", "要求", "不要", "不能", "应该", "必须", "不得", "准则"],
        "weight": 1.0
    },
    "pattern": {
        "name": "模式",
        "description": "最佳实践、案例、经验",
        "keywords": ["模式", "范例", "案例", "经验", "最佳实践", "通常", "一般", "推荐", "建议", "例子", "sample", "example", "典型"],
        "weight": 1.0
    },
    "workflow": {
        "name": "流程",
        "description": "有序步骤、工作流",
        "keywords": ["首先", "然后", "最后", "步骤", "流程", "步骤1", "步骤2", "步骤3", "第一步", "第二步", "第三步", "接着", "接下来", "之后", "工作流"],
        "weight": 1.0
    }
}

# ============== 数据模型 ==============

class TaskStatus(Enum):
    """分类任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ClassificationResult:
    """分类结果"""
    def __init__(
        self,
        content: str,
        taxonomy_tags: List[str],
        knowledge_type: Dict[str, Any],
        task_id: str = None
    ):
        self.content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        self.taxonomy_tags = taxonomy_tags
        self.knowledge_type = knowledge_type
        self.task_id = task_id or str(uuid.uuid4())[:8]
        self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "content_hash": self.content_hash,
            "taxonomy_tags": self.taxonomy_tags,
            "knowledge_type": self.knowledge_type,
            "timestamp": self.timestamp
        }
    
    def __repr__(self):
        return f"ClassificationResult(tags={self.taxonomy_tags}, type={self.knowledge_type.get('primary_type', 'unknown')})"

class ClassificationTask:
    """分类任务"""
    def __init__(
        self,
        task_id: str,
        content: str,
        mode: str = "dual",
        timeout: int = 30
    ):
        self.task_id = task_id
        self.content = content
        self.mode = mode  # dual, taxonomy_only, knowledge_type_only
        self.timeout = timeout
        self.status = TaskStatus.PENDING
        self.result: Optional[ClassificationResult] = None
        self.error: Optional[str] = None
        self.created_at = time.time()
        self.completed_at: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "mode": self.mode,
            "result": self.result.to_dict() if self.result else None,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }

# ============== TaskRegistry ==============

class TaskRegistry:
    """分类任务注册表"""
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._tasks: Dict[str, ClassificationTask] = {}
        self._history: List[Dict] = []  # 历史记录用于学习
        self._tag_frequency: Dict[str, int] = defaultdict(int)  # 标签频率统计
    
    def register(self, task: ClassificationTask) -> str:
        """注册新任务"""
        if len(self._tasks) >= self.max_size:
            # 清理已完成的任务
            completed = [k for k, v in self._tasks.items() if v.status == TaskStatus.COMPLETED]
            for k in completed[:10]:
                del self._tasks[k]
        
        self._tasks[task.task_id] = task
        return task.task_id
    
    def update(self, task_id: str, status: TaskStatus, result: ClassificationResult = None, error: str = None):
        """更新任务状态"""
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.status = status
            if result:
                task.result = result
            if error:
                task.error = error
            if status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                task.completed_at = time.time()
    
    def get(self, task_id: str) -> Optional[ClassificationTask]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def list_tasks(self, status: TaskStatus = None, limit: int = 100) -> List[ClassificationTask]:
        """列出任务"""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return sorted(tasks, key=lambda x: x.created_at, reverse=True)[:limit]
    
    def record_history(self, result: ClassificationResult):
        """记录历史用于学习"""
        self._history.append(result.to_dict())
        if len(self._history) > 1000:
            self._history = self._history[-1000:]
        
        # 更新标签频率
        for tag in result.taxonomy_tags:
            self._tag_frequency[tag] += 1
        
        # 更新知识类型频率
        kt = result.knowledge_type.get("primary_type")
        if kt:
            self._tag_frequency[f"kt:{kt}"] += 1
    
    def get_popular_tags(self, top_n: int = 5) -> List[Tuple[str, int]]:
        """获取热门标签"""
        sorted_tags = sorted(self._tag_frequency.items(), key=lambda x: x[1], reverse=True)
        return sorted_tags[:top_n]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self._tasks)
        by_status = defaultdict(int)
        for task in self._tasks.values():
            by_status[task.status.value] += 1
        
        return {
            "total_tasks": total,
            "by_status": dict(by_status),
            "history_size": len(self._history),
            "top_tags": self.get_popular_tags(10)
        }

# ============== Taxonomy分类器 ==============

class TaxonomyClassifier:
    """Taxonomy标签分类器"""
    
    def __init__(self, custom_tags: Dict[str, List[str]] = None):
        self.tags = TAXONOMY_TAGS.copy()
        if custom_tags:
            for tag, data in custom_tags.items():
                if isinstance(data, list):
                    self.tags[tag] = {"keywords": data, "weight": 1.0}
                else:
                    self.tags[tag] = data
    
    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        text = text.lower()
        tokens = re.findall(r'[\w\u4e00-\u9fff]+', text)
        return tokens
    
    def _score_tag(self, text: str, tag: str, tag_data: Dict) -> float:
        """计算标签得分"""
        text_lower = text.lower()
        score = 0.0
        
        keywords = tag_data.get("keywords", [])
        weight = tag_data.get("weight", 1.0)
        
        for kw in keywords:
            if kw.lower() in text_lower:
                score += weight
                # 精确匹配加分
                if re.search(rf'\b{re.escape(kw)}\b', text_lower, re.IGNORECASE):
                    score += 0.5
        
        return score
    
    def classify(self, text: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """分类并返回top_k标签及其得分"""
        scores = []
        
        for tag, tag_data in self.tags.items():
            score = self._score_tag(text, tag, tag_data)
            if score > 0:
                scores.append((tag, score))
        
        # 按分数排序
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
    
    def classify_multi_label(self, text: str, threshold: float = 1.0) -> List[str]:
        """多标签分类"""
        scores = self.classify(text, top_k=len(self.tags))
        return [tag for tag, score in scores if score >= threshold]

# ============== 知识类型分类器 ==============

class KnowledgeTypeClassifier:
    """知识类型分类器"""
    
    def __init__(self):
        self.types = KNOWLEDGE_TYPES
    
    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        text = text.lower()
        tokens = re.findall(r'[\w\u4e00-\u9fff]+', text)
        return tokens
    
    def classify(self, text: str) -> Dict[str, Any]:
        """分类知识类型"""
        text_lower = text.lower()
        scores = {}
        
        for type_id, type_data in self.types.items():
            score = 0.0
            keywords = type_data.get("keywords", [])
            
            for kw in keywords:
                if kw.lower() in text_lower:
                    score += 1.0
                    # 精确匹配加分
                    if re.search(rf'\b{re.escape(kw)}\b', text_lower, re.IGNORECASE):
                        score += 0.5
            
            if score > 0:
                scores[type_id] = score
        
        if not scores:
            return {
                "primary_type": "concept",
                "type_name": "概念",
                "confidence": 0.3,
                "multi_label": []
            }
        
        # 归一化得分
        max_score = max(scores.values())
        total_score = sum(scores.values())
        
        normalized = {k: v / total_score for k, v in scores.items()}
        
        # 获取主类型
        primary_type = max(scores, key=scores.get)
        
        # 获取多标签
        multi_label = [
            {"type": t, "name": self.types[t]["name"], "score": normalized[t]}
            for t in sorted(scores, key=scores.get, reverse=True)
            if normalized[t] > 0.1
        ]
        
        return {
            "primary_type": primary_type,
            "type_name": self.types[primary_type]["name"],
            "confidence": normalized[primary_type],
            "multi_label": multi_label
        }

# ============== 自动标签生成器 ==============

class AutoTagger:
    """自动标签生成器"""
    
    def __init__(
        self,
        taxonomy_classifier: TaxonomyClassifier = None,
        knowledge_classifier: KnowledgeTypeClassifier = None,
        task_registry: TaskRegistry = None,
        use_history: bool = True
    ):
        self.taxonomy_classifier = taxonomy_classifier or TaxonomyClassifier()
        self.knowledge_classifier = knowledge_classifier or KnowledgeTypeClassifier()
        self.task_registry = task_registry or TaskRegistry()
        self.use_history = use_history
    
    def _get_history_boost(self, tag: str) -> float:
        """根据历史记录获取标签提升"""
        if not self.use_history:
            return 1.0
        
        freq = self.task_registry._tag_frequency.get(tag, 0)
        # 频率越高，提升越大（但有上限）
        if freq > 100:
            return 1.5
        elif freq > 50:
            return 1.3
        elif freq > 20:
            return 1.2
        elif freq > 10:
            return 1.1
        return 1.0
    
    def _merge_with_history(self, taxonomy_tags: List[Tuple[str, float]]) -> List[Tuple[str, float]]:
        """合并历史记录提升"""
        merged = []
        for tag, score in taxonomy_tags:
            boost = self._get_history_boost(tag)
            merged.append((tag, score * boost))
        return sorted(merged, key=lambda x: x[1], reverse=True)
    
    def classify(
        self,
        content: str,
        mode: str = "dual",
        top_k: int = 3,
        threshold: float = 1.0
    ) -> ClassificationResult:
        """执行分类"""
        task_id = str(uuid.uuid4())[:8]
        
        # Taxonomy分类
        taxonomy_tags_with_scores = self.taxonomy_classifier.classify(content, top_k=top_k + 2)
        taxonomy_tags_with_scores = self._merge_with_history(taxonomy_tags_with_scores)
        
        if threshold > 0:
            taxonomy_tags = [tag for tag, score in taxonomy_tags_with_scores if score >= threshold]
        else:
            taxonomy_tags = [tag for tag, _ in taxonomy_tags_with_scores[:top_k]]
        
        if not taxonomy_tags:
            taxonomy_tags = [tag for tag, _ in taxonomy_tags_with_scores[:1]]
        
        # 知识类型分类
        knowledge_type = self.knowledge_classifier.classify(content)
        
        result = ClassificationResult(
            content=content,
            taxonomy_tags=taxonomy_tags,
            knowledge_type=knowledge_type,
            task_id=task_id
        )
        
        # 记录历史
        self.task_registry.record_history(result)
        
        return result
    
    def classify_dual(self, content: str) -> Dict[str, Any]:
        """双维度分类（V2.0）"""
        result = self.classify(content, mode="dual")
        
        primary_taxonomy = result.taxonomy_tags[0] if result.taxonomy_tags else "未分类"
        primary_knowledge_type = result.knowledge_type.get("primary_type", "concept")
        
        return {
            "taxonomy_tags": result.taxonomy_tags,
            "knowledge_type": result.knowledge_type,
            "dual_result": {
                "primary_taxonomy": primary_taxonomy,
                "primary_knowledge_type": primary_knowledge_type,
                "combined_label": f"{primary_taxonomy}|{primary_knowledge_type}"
            }
        }
    
    def classify_taxonomy_only(self, content: str, top_k: int = 3) -> List[str]:
        """仅Taxonomy分类"""
        scores = self.taxonomy_classifier.classify(content, top_k=top_k)
        return [tag for tag, _ in scores]
    
    def classify_knowledge_type_only(self, content: str) -> Dict[str, Any]:
        """仅知识类型分类"""
        return self.knowledge_classifier.classify(content)

# ============== 分类引擎 ==============

class ClassificationEngine:
    """分类引擎 - 统一入口"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.task_registry = TaskRegistry(
            max_size=self.config.get("max_tasks", 1000)
        )
        self.taxonomy_classifier = TaxonomyClassifier()
        self.knowledge_classifier = KnowledgeTypeClassifier()
        self.auto_tagger = AutoTagger(
            taxonomy_classifier=self.taxonomy_classifier,
            knowledge_classifier=self.knowledge_classifier,
            task_registry=self.task_registry
        )
    
    def classify(
        self,
        content: str,
        mode: str = "dual",
        top_k: int = 3,
        threshold: float = 1.0,
        track_task: bool = True
    ) -> Dict[str, Any]:
        """分类入口"""
        task_id = str(uuid.uuid4())[:8]
        
        # 注册任务
        if track_task:
            task = ClassificationTask(task_id, content, mode)
            self.task_registry.register(task)
            self.task_registry.update(task_id, TaskStatus.RUNNING)
        
        try:
            start_time = time.time()
            
            if mode == "dual":
                result = self.auto_tagger.classify_dual(content)
            elif mode == "taxonomy_only":
                tags = self.auto_tagger.classify_taxonomy_only(content, top_k)
                result = {"taxonomy_tags": tags}
            elif mode == "knowledge_type_only":
                kt = self.auto_tagger.classify_knowledge_type_only(content)
                result = {"knowledge_type": kt}
            else:
                result = self.auto_tagger.classify(content)
            
            elapsed = time.time() - start_time
            
            # 更新任务状态
            if track_task:
                class_result = ClassificationResult(
                    content=content,
                    taxonomy_tags=result.get("taxonomy_tags", []),
                    knowledge_type=result.get("knowledge_type", {}),
                    task_id=task_id
                )
                self.task_registry.update(task_id, TaskStatus.COMPLETED, class_result)
            
            return {
                "task_id": task_id,
                "result": result,
                "elapsed_ms": round(elapsed * 1000, 2)
            }
            
        except Exception as e:
            if track_task:
                self.task_registry.update(task_id, TaskStatus.FAILED, error=str(e))
            raise
    
    def classify_batch(self, contents: List[str], mode: str = "dual") -> List[Dict[str, Any]]:
        """批量分类"""
        results = []
        for content in contents:
            try:
                result = self.classify(content, mode, track_task=False)
                results.append(result)
            except Exception as e:
                results.append({
                    "content_hash": hashlib.md5(content.encode()).hexdigest()[:12],
                    "error": str(e)
                })
        return results
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.task_registry.get_stats()
    
    def add_custom_taxonomy(self, tag: str, keywords: List[str], weight: float = 1.0):
        """添加自定义Taxonomy标签"""
        self.taxonomy_classifier.tags[tag] = {
            "keywords": keywords,
            "weight": weight
        }

# ============== 快捷函数 ==============

# 全局默认引擎
_default_engine: Optional[ClassificationEngine] = None

def get_engine() -> ClassificationEngine:
    """获取默认引擎"""
    global _default_engine
    if _default_engine is None:
        _default_engine = ClassificationEngine()
    return _default_engine

def classify(content: str, mode: str = "dual", **kwargs) -> Dict[str, Any]:
    """快捷分类函数"""
    return get_engine().classify(content, mode, **kwargs)

def classify_dual(content: str) -> Dict[str, Any]:
    """快捷双维度分类"""
    return get_engine().classify(content, mode="dual")

def register_task(content: str, mode: str = "dual") -> str:
    """快捷任务注册"""
    engine = get_engine()
    task = ClassificationTask(str(uuid.uuid4())[:8], content, mode)
    engine.task_registry.register(task)
    engine.task_registry.update(task.task_id, TaskStatus.RUNNING)
    return task.task_id

def get_task(task_id: str) -> Optional[ClassificationTask]:
    """获取任务状态"""
    return get_engine().task_registry.get(task_id)

def get_stats() -> Dict[str, Any]:
    """获取统计信息"""
    return get_engine().get_stats()

# ============== CLI支持 ==============

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        content = sys.argv[1]
        if sys.argv[-1] == "--dual":
            result = classify_dual(content)
        else:
            result = classify(content)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # 交互式测试
        print("记忆殿堂分类器 V2.0")
        print("=" * 40)
        print("输入内容进行分类 (输入 'quit' 退出)")
        print()
        
        while True:
            try:
                content = input("> ")
                if content.lower() in ("quit", "exit", "q"):
                    break
                if not content.strip():
                    continue
                
                result = classify_dual(content)
                print()
                print("Taxonomy标签:", result["taxonomy_tags"])
                print("知识类型:", result["knowledge_type"]["primary_type"], 
                      f"({result['knowledge_type']['type_name']})", 
                      f"置信度: {result['knowledge_type']['confidence']:.2f}")
                print("综合标签:", result["dual_result"]["combined_label"])
                print()
            except (KeyboardInterrupt, EOFError):
                break
        
        print("\n统计信息:", get_stats())

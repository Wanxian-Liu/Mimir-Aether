"""
跨会话记忆管理器 - CrossSessionMemory

让MimirAether在每次会话之间保持"知道自己是谁"。
不是任务恢复（那是checkpoint_manager的工作），
而是身份记忆：我上次结束时在想什么、在做什么、学到了什么。

用法：
    from cross_session_memory import CrossSessionMemory
    
    mem = CrossSessionMemory()
    
    # 会话开始时：加载上次的记忆
    mem.load()
    if mem.is_first_session():
        print("初次见面")
    else:
        print(f"上次会话: {mem.get('last_session_end')}")
        print(f"上次在做什么: {mem.get_progress('current_objective')}")
    
    # 会话中：记录重要决策
    mem.add_decision("选择了跨会话记忆作为第一优先级")
    mem.add_pattern("tool-triggers 必须在任务开始时加载")
    
    # 会话结束时：保存
    mem.set_progress(current_objective="打通跨会话记忆",
                     completed=["体检报告分析", "决策：优先打通记忆"],
                     pending=["五条药方的后续执行"])
    mem.save()
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path


# 持久化文件路径
PERSISTENT_FILE = Path.home() / ".openclaw" / "projects" / "MimirAether" / "data" / "persistent.json"


class CrossSessionMemory:
    """跨会话记忆管理器"""
    
    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or PERSISTENT_FILE
        self._data = self._default_data()
        self._loaded = False
    
    def _default_data(self) -> Dict:
        return {
            "version": "1.0",
            "last_session_end": None,
            "session_count": 0,
            "identity": {
                "name": "MimirAether",
                "soul": "智慧之泉",
                "last_known_mission": None
            },
            "memory": {
                "key_decisions": [],
                "learned_patterns": [],
                "active_projects": [],
                "user_preferences": {},
                "skills_used": []
            },
            "progress": {
                "current_objective": None,
                "completed_milestones": [],
                "pending_tasks": []
            }
        }
    
    def load(self) -> bool:
        """加载持久化记忆"""
        try:
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # 合并默认值（兼容旧版本）
                default = self._default_data()
                # 深度合并
                for key in default:
                    if key not in data:
                        data[key] = default[key]
                    elif isinstance(default[key], dict) and isinstance(data[key], dict):
                        for subkey in default[key]:
                            if subkey not in data[key]:
                                data[key][subkey] = default[key][subkey]
                self._data = data
                self._loaded = True
                return True
            else:
                self._data = self._default_data()
                self._loaded = True
                return False  # 首次运行
        except (json.JSONDecodeError, IOError) as e:
            print(f"[CrossSessionMemory] 加载失败: {e}，使用默认值")
            self._data = self._default_data()
            self._loaded = True
            return False
    
    def save(self) -> bool:
        """保存持久化记忆"""
        try:
            self._data["last_session_end"] = datetime.now(timezone.utc).isoformat()
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            # 原子写入
            temp_path = self.file_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            temp_path.rename(self.file_path)
            return True
        except (IOError, OSError) as e:
            print(f"[CrossSessionMemory] 保存失败: {e}")
            return False
    
    def is_first_session(self) -> bool:
        """是否是首次会话（无历史记忆）"""
        return self._data["session_count"] == 0
    
    def get(self, key: str, default=None):
        """获取顶层字段"""
        return self._data.get(key, default)
    
    def set(self, key: str, value):
        """设置顶层字段"""
        self._data[key] = value
    
    # ---- 记忆操作 ----
    
    def add_decision(self, decision: str, context: str = ""):
        """记录关键决策"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision": decision,
            "context": context
        }
        self._data["memory"]["key_decisions"].append(entry)
        # 保留最近20条
        if len(self._data["memory"]["key_decisions"]) > 20:
            self._data["memory"]["key_decisions"] = self._data["memory"]["key_decisions"][-20:]
    
    def add_pattern(self, pattern: str, evidence: str = ""):
        """记录学到的模式"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pattern": pattern,
            "evidence": evidence
        }
        self._data["memory"]["learned_patterns"].append(entry)
        if len(self._data["memory"]["learned_patterns"]) > 30:
            self._data["memory"]["learned_patterns"] = self._data["memory"]["learned_patterns"][-30:]
    
    def add_project(self, project: str, status: str = "active"):
        """记录活跃项目"""
        for p in self._data["memory"]["active_projects"]:
            if p["name"] == project:
                p["status"] = status
                p["updated_at"] = datetime.now(timezone.utc).isoformat()
                return
        self._data["memory"]["active_projects"].append({
            "name": project,
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    def set_preference(self, key: str, value):
        """设置用户偏好"""
        self._data["memory"]["user_preferences"][key] = value
    
    def add_skill_used(self, skill_name: str):
        """记录使用的技能"""
        if skill_name not in self._data["memory"]["skills_used"]:
            self._data["memory"]["skills_used"].append(skill_name)
            if len(self._data["memory"]["skills_used"]) > 50:
                self._data["memory"]["skills_used"] = self._data["memory"]["skills_used"][-50:]
    
    # ---- 进度操作 ----
    
    def set_progress(self, current_objective: str = None,
                     completed: List[str] = None,
                     pending: List[str] = None):
        """更新进度"""
        if current_objective is not None:
            self._data["progress"]["current_objective"] = current_objective
        if completed:
            for item in completed:
                if item not in self._data["progress"]["completed_milestones"]:
                    self._data["progress"]["completed_milestones"].append(item)
        if pending is not None:
            self._data["progress"]["pending_tasks"] = pending
    
    def get_progress(self, key: str = None):
        """获取进度"""
        if key:
            return self._data["progress"].get(key)
        return self._data["progress"]
    
    def get_memory(self, key: str = None):
        """获取记忆"""
        if key:
            return self._data["memory"].get(key, [])
        return self._data["memory"]
    
    # ---- 会话管理 ----
    
    def begin_session(self):
        """会话开始时的记账"""
        self._data["session_count"] += 1
    
    def end_session(self):
        """会话结束时的记账"""
        self._data["last_session_end"] = datetime.now(timezone.utc).isoformat()
    
    def summary(self) -> str:
        """生成可读的记忆摘要（给agent自己看）"""
        lines = []
        lines.append(f"=== 跨会话记忆摘要 ===")
        lines.append(f"会话次数: {self._data['session_count']}")
        lines.append(f"上次结束: {self._data.get('last_session_end', '从未')}")
        
        prog = self._data["progress"]
        if prog.get("current_objective"):
            lines.append(f"当前目标: {prog['current_objective']}")
        if prog.get("completed_milestones"):
            lines.append(f"已完成里程碑: {len(prog['completed_milestones'])} 项")
        if prog.get("pending_tasks"):
            lines.append(f"待办任务: {len(prog['pending_tasks'])} 项")
        
        decisions = self._data["memory"]["key_decisions"]
        if decisions:
            lines.append(f"关键决策: {len(decisions)} 条")
            for d in decisions[-3:]:
                lines.append(f"  - {d['decision']}")
        
        patterns = self._data["memory"]["learned_patterns"]
        if patterns:
            lines.append(f"学到的模式: {len(patterns)} 条")
        
        return "\n".join(lines)


# 便捷函数
def load_memory() -> CrossSessionMemory:
    """加载跨会话记忆（一步到位）"""
    mem = CrossSessionMemory()
    mem.load()
    return mem


# 测试
if __name__ == "__main__":
    mem = load_memory()
    if mem.is_first_session():
        print("首次会话")
    else:
        print(mem.summary())
    
    mem.begin_session()
    mem.add_decision("测试跨会话记忆系统")
    mem.set_progress(current_objective="验证跨会话记忆是否正常工作")
    mem.end_session()
    mem.save()
    print("\n记忆已保存")

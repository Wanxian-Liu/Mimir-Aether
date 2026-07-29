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

import copy
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path

from agent.memory_write_facade import get_persistent_path, save_persistent_merged

logger = logging.getLogger(__name__)


# 持久化文件路径（随 MIMIR_AETHER_HOME 解析；与 persistent_store 一致）
PERSISTENT_FILE = get_persistent_path()


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
                "behavioral_constraints": [],
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
                self._normalize_memory_shapes()
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

    def _normalize_memory_shapes(self) -> None:
        """Coerce hand-edited or legacy persistent.json into expected dict rows.

        Older files store ``key_decisions`` / ``learned_patterns`` / ``active_projects``
        as plain strings; code paths expect dict rows with ``decision`` / ``pattern`` /
        ``name`` keys. Without this, :meth:`summary` and :meth:`add_project` raise
        ``string indices must be integers, not 'str'``.
        """
        mem = self._data.get("memory")
        if not isinstance(mem, dict):
            return
        now = datetime.now(timezone.utc).isoformat()

        kd = mem.get("key_decisions")
        if isinstance(kd, list):
            fixed: List[Any] = []
            for item in kd:
                if isinstance(item, str):
                    fixed.append({"timestamp": "", "decision": item, "context": ""})
                elif isinstance(item, dict):
                    fixed.append(item)
                else:
                    fixed.append({"timestamp": "", "decision": str(item), "context": ""})
            mem["key_decisions"] = fixed

        lp = mem.get("learned_patterns")
        if isinstance(lp, list):
            fixed_lp: List[Any] = []
            for item in lp:
                if isinstance(item, str):
                    fixed_lp.append({"timestamp": "", "pattern": item, "evidence": ""})
                elif isinstance(item, dict):
                    fixed_lp.append(item)
                else:
                    fixed_lp.append({"timestamp": "", "pattern": str(item), "evidence": ""})
            mem["learned_patterns"] = fixed_lp

        ap = mem.get("active_projects")
        if isinstance(ap, list):
            fixed_ap: List[Any] = []
            for item in ap:
                if isinstance(item, str):
                    fixed_ap.append({
                        "name": item,
                        "status": "active",
                        "created_at": now,
                        "updated_at": now,
                    })
                elif isinstance(item, dict):
                    fixed_ap.append(item)
                else:
                    fixed_ap.append({
                        "name": str(item),
                        "status": "active",
                        "created_at": now,
                        "updated_at": now,
                    })
            mem["active_projects"] = fixed_ap
    
    def save(self) -> bool:
        """保存持久化记忆（单写者锁 + 磁盘合并，ADR-001）。

        如果 .distilled 哨兵文件存在（蒸馏刚写完盘），在合并前重载磁盘数据
        到 self._data，避免用旧缓存（59 kd）覆盖蒸馏结果（20 kd）。
        """
        self._data["last_session_end"] = datetime.now(timezone.utc).isoformat()
        self.file_path = get_persistent_path()

        # 哨兵检测：蒸馏已完成，重载磁盘数据覆盖内存缓存
        sentinel_path = self.file_path.parent / ".distilled"
        if sentinel_path.exists():
            try:
                sentinel_ts = sentinel_path.read_text(encoding="utf-8").strip()
                logger.info(
                    "[CrossSessionMemory] 检测到蒸馏哨兵 (%s)，从磁盘重载缓存",
                    sentinel_ts,
                )
                with open(self.file_path, "r", encoding="utf-8") as f:
                    disk_data = json.load(f)
                # 用磁盘数据替换内存缓存（保留 last_session_end 等运行时字段）
                disk_data["last_session_end"] = self._data.get("last_session_end")
                disk_data["session_count"] = self._data.get("session_count", 0)
                self._data = disk_data
                logger.info(
                    "[CrossSessionMemory] 缓存已从磁盘重载: kd=%d, lp=%d",
                    len(disk_data.get("memory", {}).get("key_decisions", [])),
                    len(disk_data.get("memory", {}).get("learned_patterns", [])),
                )
                # 清理哨兵，避免每次 save 都重载
                sentinel_path.unlink(missing_ok=True)
            except Exception as e:
                logger.warning(
                    "[CrossSessionMemory] 读哨兵/重载缓存失败: %s，继续使用原缓存", e,
                )

        ok = save_persistent_merged(
            self._data,
            CrossSessionMemory.merge_disk_into_memory,
            self.file_path,
        )
        if not ok:
            print("[CrossSessionMemory] 保存失败")
        return ok

    def _merge_disk_changes(self) -> None:
        """合并磁盘快照到 ``self._data``（供会话内逻辑；保存走 :meth:`save`）。"""
        try:
            if not self.file_path.exists():
                return
            with open(self.file_path, "r", encoding="utf-8") as f:
                disk_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return
        merged = self.merge_disk_into_memory(disk_data, self._data)
        self._data = merged

    @staticmethod
    def merge_disk_into_memory(disk_data: dict, memory_data: dict) -> dict:
        """将磁盘上 agent 手动 patch 的字段合并进内存快照并返回完整写入体。"""
        out = copy.deepcopy(memory_data)

        disk_obj = disk_data.get("progress", {}).get("current_objective")
        mem_obj = out.get("progress", {}).get("current_objective")
        if disk_obj and disk_obj != mem_obj:
            out.setdefault("progress", {})["current_objective"] = disk_obj

        disk_ms = disk_data.get("progress", {}).get("completed_milestones", [])
        if disk_ms:
            mem_ms = out.setdefault("progress", {}).setdefault("completed_milestones", [])
            existing = set(mem_ms)
            for item in disk_ms:
                if item not in existing:
                    mem_ms.append(item)

        disk_ap = disk_data.get("memory", {}).get("active_projects", [])
        if disk_ap:
            mem_ap = out.setdefault("memory", {}).setdefault("active_projects", [])
            mem_by_name = {p.get("name"): p for p in mem_ap if isinstance(p, dict)}
            for dp in disk_ap:
                if not isinstance(dp, dict):
                    continue
                name = dp.get("name")
                if not name:
                    continue
                if name in mem_by_name:
                    for k, v in dp.items():
                        mem_by_name[name][k] = v
                else:
                    mem_ap.append(dp)

        disk_lp = disk_data.get("memory", {}).get("learned_patterns", [])
        mem_lp = out.setdefault("memory", {}).setdefault("learned_patterns", [])
        seen_patterns = set()
        if disk_lp:
            for item in mem_lp:
                if isinstance(item, dict) and item.get("pattern"):
                    seen_patterns.add(item["pattern"])
            for item in disk_lp:
                if isinstance(item, dict) and item.get("pattern"):
                    if item["pattern"] not in seen_patterns:
                        mem_lp.append(item)
                        seen_patterns.add(item["pattern"])

        disk_kd = disk_data.get("memory", {}).get("key_decisions", [])
        mem_kd = out.setdefault("memory", {}).setdefault("key_decisions", [])
        seen_decisions = set()
        if disk_kd:
            for item in mem_kd:
                if isinstance(item, dict) and item.get("decision"):
                    seen_decisions.add(item["decision"])
            for item in disk_kd:
                if isinstance(item, dict) and item.get("decision"):
                    if item["decision"] not in seen_decisions:
                        mem_kd.append(item)
                        seen_decisions.add(item["decision"])

        # 更新 ByteRover AKL last_access（磁盘合并 = 记忆被访问）
        _now_akl = datetime.now(timezone.utc).isoformat()
        for item in mem_kd:
            if isinstance(item, dict):
                item["last_access"] = _now_akl
        if disk_lp:
            for item in mem_lp:
                if isinstance(item, dict):
                    item["last_access"] = _now_akl

        for key in ("skill_usage", "dormant_skills"):
            if key in disk_data:
                disk_seg = disk_data.get(key) or {}
                mem_seg = out.get(key) or {}
                if isinstance(disk_seg, dict) and isinstance(mem_seg, dict):
                    out[key] = {**disk_seg, **mem_seg}
                elif key not in out:
                    out[key] = copy.deepcopy(disk_seg)

        if "curator_nudge" in disk_data and "curator_nudge" not in out:
            out["curator_nudge"] = copy.deepcopy(disk_data["curator_nudge"])

        # PMD 共同进化：合并 behavioral_constraints（来自梦境蒸馏，用磁盘版替换内存版）
        disk_behavioral = disk_data.get("memory", {}).get("behavioral_constraints")
        if disk_behavioral:
            out.setdefault("memory", {})["behavioral_constraints"] = copy.deepcopy(disk_behavioral)

        # Fallthrough: 保留 disk_data 中所有被 out 遗漏的顶层键
        # 确保 metadata 等手动写入的字段不被静默丢弃
        for key in disk_data:
            if key not in out:
                out[key] = copy.deepcopy(disk_data[key])

        return out
    
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
        self.refresh_skill_curator_nudge()
        self.run_curator_actions()
    
    def refresh_skill_curator_nudge(self) -> str:
        """
        刷新技能策展轻推，写入 persistent.json 的 curator_nudge 字段。

        Returns:
            nudge 文本
        """
        try:
            from agent.skill_curator import nudge_report
            nudge = nudge_report()
            self._data["curator_nudge"] = nudge
            return nudge
        except Exception:
            return ""

    def run_curator_actions(self) -> dict:
        """
        自动执行策展行动。

        仅执行确定性动作（capsulize_now），不确定动作保留为轻推。

        Returns:
            {capsulized: [...], errors: [...]}
        """
        try:
            from agent.skill_curator import curator_actions, capsulize_and_dormant, CuratorAction
            ca = curator_actions()
            capsulized: list = []
            errors: list = []
            for a in ca.get("actions", []):
                if a.get("action") != CuratorAction.CAPSULIZE_NOW:
                    continue
                name = a["name"]
                # 安全检查：不胶囊化自引用/基础设施技能
                if name.startswith("mimiraether-curator") or name in (
                    "mimiraether-tool-triggers",
                    "mimiraether-cross-session",
                    "mimiraether-auto-load",
                ):
                    continue
                try:
                    r = capsulize_and_dormant(name)
                    if r.get("success"):
                        capsulized.append(name)
                    else:
                        errors.append(f"{name}: {r.get('error', 'unknown')}")
                except Exception as e:
                    errors.append(f"{name}: {e}")
            if capsulized:
                self._data.setdefault("curator_capsulized", [])
                self._data["curator_capsulized"].extend(capsulized)
            return {"capsulized": capsulized, "errors": errors}
        except Exception as e:
            return {"capsulized": [], "errors": [str(e)]}

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
                if isinstance(d, dict):
                    lines.append(f"  - {d.get('decision', d)}")
                else:
                    lines.append(f"  - {d}")
        
        patterns = self._data["memory"]["learned_patterns"]
        if patterns:
            lines.append(f"学到的模式: {len(patterns)} 条")

        # 技能策展轻推
        nudge = self._data.get("curator_nudge", "")
        if nudge:
            lines.append(f"\n{'-' * 30}")
            lines.append(f"📋 技能策展提醒:")
            lines.append(nudge)

        # 技能策展自动操作
        capsulized = self._data.get("curator_capsulized", [])
        if capsulized:
            lines.append(f"\n{'─' * 30}")
            lines.append(f"📦 已自动胶囊化({len(capsulized)}): {', '.join(capsulized)}")
        
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

"""
EvolutionMemory — JEPA Short-Term Memory for Self-Evolution

物理世界: MemoryBuffer 存 (t, state, energy) 三元组
代码世界: 存 (timestamp, change, ic_cost, tc_cost, outcome) 记录

用于规划器参考过去演化结果，避免重复失败路径。
"""

import time
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import deque


@dataclass
class EvolutionRecord:
    """一次演化记录"""
    timestamp: float
    changes: List[str]              # 改动的文件列表
    ic_cost: float
    tc_cost: float
    total_cost: float
    outcome: str                    # "success" | "partial" | "failed" | "unknown"
    tier0_result: str = ""          # tier0 跑完的结果
    notes: str = ""                 # 备注

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "changes": self.changes,
            "ic_cost": self.ic_cost,
            "tc_cost": self.tc_cost,
            "total_cost": self.total_cost,
            "outcome": self.outcome,
            "tier0_result": self.tier0_result,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EvolutionRecord":
        return cls(
            timestamp=d.get("timestamp", 0),
            changes=d.get("changes", []),
            ic_cost=d.get("ic_cost", 0),
            tc_cost=d.get("tc_cost", 0),
            total_cost=d.get("total_cost", 0),
            outcome=d.get("outcome", "unknown"),
            tier0_result=d.get("tier0_result", ""),
            notes=d.get("notes", ""),
        )


class EvolutionMemory:
    """
    JEPA Memory: 存储过去演化记录

    类比 WM MemoryBuffer:
    - push(): 记录一次演化
    - query(): 查询相似场景的历史
    - should_retry(): 判断是否值得重试
    """

    def __init__(self, capacity: int = 1000, persistence_path: Optional[str] = None):
        self.capacity = capacity
        self._records: deque[EvolutionRecord] = deque(maxlen=capacity)
        self._by_file: Dict[str, List[EvolutionRecord]] = {}  # file → records touching it
        self._success_count: int = 0
        self._failure_count: int = 0

        # 持久化
        self.persistence_path = persistence_path
        if persistence_path:
            self._load()

    def push(self, record: EvolutionRecord) -> None:
        """记录一次演化"""
        self._records.append(record)
        if record.outcome == "success":
            self._success_count += 1
        elif record.outcome == "failed":
            self._failure_count += 1

        # 更新文件索引
        for fpath in record.changes:
            if fpath not in self._by_file:
                self._by_file[fpath] = []
            self._by_file[fpath].append(record)

        if self.persistence_path:
            self._save()

    def query_by_file(self, file_path: str, limit: int = 10) -> List[EvolutionRecord]:
        """查询：改动过某文件的历次演化"""
        records = self._by_file.get(file_path, [])
        return sorted(records, key=lambda r: r.timestamp, reverse=True)[:limit]

    def query_recent(self, limit: int = 20) -> List[EvolutionRecord]:
        """查询最近 N 条记录"""
        records = list(self._records)
        return sorted(records, key=lambda r: r.timestamp, reverse=True)[:limit]

    def should_retry(self, file_path: str, max_failures: int = 3) -> bool:
        """
        判断：是否值得再改这个文件？
        - 连续失败 ≥ max_failures → False (跳过)
        - 最近一次成功 → True
        - 无记录 → True (探索)
        """
        history = self.query_by_file(file_path)
        if not history:
            return True  # 从未改过，值得探索

        # 检查连续失败
        consecutive_failures = 0
        for record in history:
            if record.outcome == "failed":
                consecutive_failures += 1
            else:
                break
        return consecutive_failures < max_failures

    def get_success_rate(self) -> float:
        """演化成功率"""
        total = self._success_count + self._failure_count
        return self._success_count / total if total > 0 else 1.0

    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        return {
            "total_records": len(self._records),
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": self.get_success_rate(),
            "tracked_files": len(self._by_file),
        }

    # ── 持久化 ──

    def _save(self) -> None:
        if not self.persistence_path:
            return
        try:
            data = {
                "records": [r.to_dict() for r in self._records],
                "success_count": self._success_count,
                "failure_count": self._failure_count,
            }
            Path(self.persistence_path).write_text(json.dumps(data, indent=2))
        except Exception:
            pass  # 静默失败，不影响主流程

    def _load(self) -> None:
        if not self.persistence_path:
            return
        try:
            p = Path(self.persistence_path)
            if p.exists():
                data = json.loads(p.read_text())
                for r_dict in data.get("records", []):
                    record = EvolutionRecord.from_dict(r_dict)
                    self._records.append(record)
                    for fpath in record.changes:
                        if fpath not in self._by_file:
                            self._by_file[fpath] = []
                        self._by_file[fpath].append(record)
                self._success_count = data.get("success_count", 0)
                self._failure_count = data.get("failure_count", 0)
        except Exception:
            pass

"""SkillMigrator — Mode-2 → Mode-1 自动迁移

杨立昆 §4.1 核心机制：
  "After Mode-2 has produced an optimal action sequence, the policy module can be
   trained to approximate the optimal actions. The policy module can then act
   reactively (Mode-1) without the world model."

实现：
  当同类型问题被 System 2（慢推理，SymPy 完整推导）解决 ≥N 次后，
  自动生成 System 1（快查表）条目。下次同类问题直接查表返回，
  跳过 SymPy 推导——从 O(100ms) 降到 O(1ms)，越用越快。

区别于 Mathematica / Wolfram Alpha：
  AI 会越来越快，符号引擎不会。
"""

from dataclasses import dataclass, field
from typing import Any, Optional
import json
import os


@dataclass
class CannedSolution:
    """缓存解 — System 1 快速查表条目"""
    result: float
    unit: str
    formula_used: str
    steps: list
    migration_count: int = 1       # 已迁移次数（同类型累积）
    last_used: str = ""            # ISO 时间戳


class SkillMigrator:
    """Mode-2 → Mode-1 自动迁移管理器

    生命周期：
      1. on_solve() — 每次 System 2 求解后调用
      2. 当同类型问题解决 ≥ MIGRATION_THRESHOLD 次 → 自动生成快查条目
      3. lookup() — 查询是否已有缓存解
    """

    MIGRATION_THRESHOLD = 3  # 同一问题类型 3 次后自动迁移到 Mode-1

    def __init__(self, cache_path: str = None):
        """
        Args:
            cache_path: 缓存文件路径。默认 ~/.mimiraether/data/physics_fast_path.json
        """
        if cache_path is None:
            home = os.environ.get("MIMIR_AETHER_HOME",
                                  os.path.expanduser("~/.mimiraether"))
            cache_path = os.path.join(home, "data", "physics_fast_path.json")
        self.cache_path = cache_path
        self.counter: dict[str, int] = {}       # problem_type → 求解次数
        self.fast_path: dict[str, CannedSolution] = {}  # problem_type → 缓存解
        self._load()

    def _problem_key(self, domain: str, target: str, given: dict) -> str:
        """生成问题唯一标识。对 given 的键排序确保一致性。"""
        given_str = ",".join(f"{k}={given[k]}" for k in sorted(given.keys()))
        return f"{domain}:{target}:({given_str})"

    def on_solve(self, domain: str, target: str, given: dict,
                 result: float, unit: str, formula_used: str, steps: list) -> bool:
        """记录一次 System 2 求解，超过阈值则自动迁移到 System 1。

        Returns:
            True 如果此次求解触发了 Mode-2 → Mode-1 迁移
        """
        key = self._problem_key(domain, target, given)
        self.counter[key] = self.counter.get(key, 0) + 1

        if self.counter[key] >= self.MIGRATION_THRESHOLD:
            from datetime import datetime, timezone
            self.fast_path[key] = CannedSolution(
                result=result,
                unit=unit,
                formula_used=formula_used,
                steps=steps,
                migration_count=self.counter[key],
                last_used=datetime.now(timezone.utc).isoformat(),
            )
            self._save()
            return True
        return False

    def lookup(self, domain: str, target: str, given: dict) -> Optional[CannedSolution]:
        """System 1 查表：是否已有缓存解？"""
        key = self._problem_key(domain, target, given)
        return self.fast_path.get(key)

    def get_stats(self) -> dict:
        """获取迁移统计"""
        return {
            "total_counter_entries": len(self.counter),
            "total_fast_path_entries": len(self.fast_path),
            "migration_threshold": self.MIGRATION_THRESHOLD,
            "fast_path": {
                k: {"count": v.migration_count, "last_used": v.last_used}
                for k, v in self.fast_path.items()
            },
        }

    def _save(self):
        """保存到磁盘"""
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        data = {
            "counter": self.counter,
            "fast_path": {
                k: {
                    "result": v.result,
                    "unit": v.unit,
                    "formula_used": v.formula_used,
                    "steps": v.steps,
                    "migration_count": v.migration_count,
                    "last_used": v.last_used,
                }
                for k, v in self.fast_path.items()
            },
        }
        with open(self.cache_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load(self):
        """从磁盘加载"""
        if not os.path.exists(self.cache_path):
            return
        try:
            with open(self.cache_path) as f:
                data = json.load(f)
            self.counter = data.get("counter", {})
            fp = data.get("fast_path", {})
            self.fast_path = {
                k: CannedSolution(**v) for k, v in fp.items()
            }
        except (json.JSONDecodeError, KeyError, TypeError):
            self.counter = {}
            self.fast_path = {}

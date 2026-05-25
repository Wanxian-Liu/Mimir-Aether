#!/usr/bin/env python3
"""Run EV-A03 20-query retrieval benchmark: LIKE, FTS5, and optional Chroma semantic."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mimir_constants import get_mimir_data_dir
from tools.fts5_search.engine import FTS5SearchEngine, SearchOptions
from tools.session_search_tool import session_search

# From docs/phase0/memory-retrieval-baseline.md §3
BENCHMARK_QUERIES: List[str] = [
    "persistent.json 截断",
    "tool call 格式 DeepSeek",
    "run_ralph_tier0",
    "MIMIR_AETHER_HOME",
    "237+2",
    "架构方案 琬弦",
    "Gateway 崩溃怎么恢复",
    "跨会话记忆 上次在做什么",
    "压缩 上下文 重叠",
    "智商评分 rubric",
    "memory leak session",
    "FTS5 semantic search",
    "CrossSessionMemory save",
    "2026-05-20 IR",
    "last_session_end",
    "session_id feishu",
    "IR-20260520",
    "E-008 cli shim",
    "JEPA",
    "EV-A03 memory benchmark",
]

# Queries #6–#13 (semantic-heavy); see memory-retrieval-baseline.md §3
SEMANTIC_HEAVY_INDICES = tuple(range(5, 13))


@dataclass
class QueryResult:
    query: str
    like_hits: int
    like_ms: float
    fts_hits: int
    fts_ms: float
    semantic_hits: int = 0
    semantic_ms: float = 0.0


def _hit_rate_subset(rows: List[QueryResult], attr: str, indices: tuple[int, ...]) -> Optional[float]:
    picked = [rows[i] for i in indices if 0 <= i < len(rows)]
    if not picked:
        return None
    return round(sum(1 for r in picked if getattr(r, attr) > 0) / len(picked), 3)


def _like_search(query: str, db_path: Optional[str]) -> tuple[int, float]:
    t0 = time.perf_counter()
    results = session_search(query, db_path=db_path, limit=5, session_limit=3)
    ms = (time.perf_counter() - t0) * 1000
    # session_search returns summaries; message_count is the matched message tally.
    hits = sum(int(r.get("message_count") or 0) for r in results)
    return hits, ms


def _semantic_search(query: str, db_path: Optional[str]) -> tuple[int, float]:
    import os

    old_backend = os.environ.get("SESSION_SEARCH_BACKEND")
    os.environ["SESSION_SEARCH_BACKEND"] = "semantic"
    try:
        t0 = time.perf_counter()
        results = session_search(query, db_path=db_path, limit=5, session_limit=3)
        ms = (time.perf_counter() - t0) * 1000
        hits = sum(int(r.get("message_count") or 0) for r in results)
        return hits, ms
    finally:
        if old_backend is None:
            os.environ.pop("SESSION_SEARCH_BACKEND", None)
        else:
            os.environ["SESSION_SEARCH_BACKEND"] = old_backend


def _fts_search(query: str, engine: FTS5SearchEngine) -> tuple[int, float]:
    t0 = time.perf_counter()
    resp = engine.search(SearchOptions(query=query, limit=10, use_cache=False))
    ms = (time.perf_counter() - t0) * 1000
    return resp.total_matches, ms


def run_benchmark(
    *,
    like_db_path: Optional[str] = None,
    fts_db_path: Optional[str] = None,
) -> Dict[str, Any]:
    from mimir_constants import get_mimir_chroma_dir
    from tools.session_search_tool import _semantic_index_ready

    like_db_path = like_db_path or str(get_mimir_data_dir() / "sessions_search.db")
    fts_db_path = fts_db_path or str(get_mimir_data_dir() / "fts5_search.db")

    fts_engine: Optional[FTS5SearchEngine] = None
    fts_available = Path(fts_db_path).exists()
    if fts_available:
        try:
            fts_engine = FTS5SearchEngine(fts_db_path)
        except Exception:
            fts_available = False
            fts_engine = None

    semantic_available = _semantic_index_ready()
    chroma_dir = str(get_mimir_chroma_dir()) if semantic_available else None

    rows: List[QueryResult] = []
    for q in BENCHMARK_QUERIES:
        like_hits, like_ms = _like_search(q, like_db_path)
        if fts_engine is not None:
            fts_hits, fts_ms = _fts_search(q, fts_engine)
        else:
            fts_hits, fts_ms = 0, 0.0
        if semantic_available:
            semantic_hits, semantic_ms = _semantic_search(q, like_db_path)
        else:
            semantic_hits, semantic_ms = 0, 0.0
        rows.append(
            QueryResult(
                q,
                like_hits,
                like_ms,
                fts_hits,
                fts_ms,
                semantic_hits,
                semantic_ms,
            )
        )

    if fts_engine is not None:
        fts_engine.close()

    like_hit_rate = sum(1 for r in rows if r.like_hits > 0) / len(rows)
    fts_hit_rate = sum(1 for r in rows if r.fts_hits > 0) / len(rows) if fts_available else 0.0
    semantic_hit_rate = (
        sum(1 for r in rows if r.semantic_hits > 0) / len(rows) if semantic_available else None
    )
    like_latencies = [r.like_ms for r in rows]
    fts_latencies = [r.fts_ms for r in rows if fts_available]
    semantic_latencies = [r.semantic_ms for r in rows if semantic_available]

    def _p99(values: List[float]) -> Optional[float]:
        if not values:
            return None
        return round(sorted(values)[max(0, int(len(values) * 0.99) - 1)], 2)

    report: Dict[str, Any] = {
        "queries": len(rows),
        "like_db": like_db_path,
        "fts_db": fts_db_path if fts_available else None,
        "semantic_chroma_dir": chroma_dir,
        "like_hit_rate": round(like_hit_rate, 3),
        "fts_hit_rate": round(fts_hit_rate, 3),
        "semantic_hit_rate": round(semantic_hit_rate, 3) if semantic_hit_rate is not None else None,
        "like_p50_ms": round(statistics.median(like_latencies), 2),
        "like_p99_ms": _p99(like_latencies),
        "fts_p50_ms": round(statistics.median(fts_latencies), 2) if fts_latencies else None,
        "fts_p99_ms": _p99(fts_latencies),
        "semantic_p50_ms": round(statistics.median(semantic_latencies), 2)
        if semantic_latencies
        else None,
        "semantic_p99_ms": _p99(semantic_latencies),
        "semantic_heavy_query_count": len(SEMANTIC_HEAVY_INDICES),
        "like_semantic_heavy_hit_rate": _hit_rate_subset(rows, "like_hits", SEMANTIC_HEAVY_INDICES),
        "semantic_semantic_heavy_hit_rate": _hit_rate_subset(rows, "semantic_hits", SEMANTIC_HEAVY_INDICES)
        if semantic_available
        else None,
        "rows": [asdict(r) for r in rows],
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--like-db", type=str, default=None)
    parser.add_argument("--fts-db", type=str, default=None)
    parser.add_argument("--json-out", type=Path, default=None, help="Write full results JSON")
    args = parser.parse_args()

    report = run_benchmark(like_db_path=args.like_db, fts_db_path=args.fts_db)
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2, ensure_ascii=False))
    print("\n--- per query (like / fts / semantic hits) ---")
    for row in report["rows"]:
        sem = row.get("semantic_hits", 0)
        print(
            f"{row['query'][:36]:36}  {row['like_hits']:3} / {row['fts_hits']:3} / {sem:3}  "
            f"{row['like_ms']:.1f}ms / {row['fts_ms']:.1f}ms / {row.get('semantic_ms', 0):.1f}ms"
        )

    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nWrote {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

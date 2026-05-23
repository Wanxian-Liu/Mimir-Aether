"""E-006 D6-0d — RateLimitTracker thread safety."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.rate_limit_tracker import RateLimitTracker


def test_rate_limit_tracker_concurrent_record_hit():
    tracker = RateLimitTracker()
    provider = "test-provider"

    def hit_many():
        for _ in range(50):
            tracker.record_hit(provider, 429)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: hit_many(), range(8)))

    assert tracker.get_state(provider) is None
    # 8 workers × 50 hits = 400 increments; last count should be 400
    with tracker._lock:
        assert tracker._backoff_count[provider] == 400

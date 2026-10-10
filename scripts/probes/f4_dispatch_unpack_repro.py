"""F-4 minimal repro: parallel read-only tool timeout -> 4-tuple unpack crash.

No need to wait the real 60s: MIMIR_TOOL_TIMEOUT is squeezed to 0.2s while the
dispatcher sleeps 5s, so the genuine asyncio.TimeoutError branch is exercised --
the same path that fired in production at 2026-10-05 02:26:58.

Run: python3 scripts/probes/f4_dispatch_unpack_repro.py
"""
import asyncio
import os
import sys
import time
import traceback

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

os.environ["MIMIR_PARALLEL_TOOLS"] = "1"
os.environ["MIMIR_TOOL_TIMEOUT"] = "0.2"
os.environ["MIMIR_TOOL_RETRY"] = "1"   # 1 retry => same as production attempt 2/2

from agent.parallel_dispatcher import dispatch_all  # noqa: E402


def slow_tool(name, args, tid):
    time.sleep(5.0)
    return "never"


async def main():
    tcs = [
        {"id": "call_a", "type": "function",
         "function": {"name": "search_files", "arguments": '{"pattern":"x"}'}},
        {"id": "call_b", "type": "function",
         "function": {"name": "search_files", "arguments": '{"pattern":"y"}'}},
    ]
    results = await dispatch_all(tcs, None, slow_tool, "acfc4e74")
    print("dispatch_all returned:", results)
    for br in results:
        if br is None:
            print("  (None skipped)")
            continue
        tname, tid, raw_args, tool_result = br   # same unpack as agent_loop.py:862
        print("  unpack OK:", tname, tid)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        traceback.print_exc()
        print("RC=1 CRASH REPRODUCED")
        sys.exit(1)
    print("RC=0 no crash")

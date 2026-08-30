#!/usr/bin/env python3
"""Muon g-2 论文精读 — spawn_multi 真正并行（试点 1 修正版）"""
import json
import time
import sys

sys.path.insert(0, "/home/rayliu/src/MimirAether")
from subagent_bridge import spawn_multi

T0 = time.time()

TASKS = [
    {
        "type": "Explore",
        "prompt": (
            "Read and summarize arXiv:2506.03069 'Measurement of the Positive Muon "
            "Anomalous Magnetic Moment to 127 ppb' (Fermilab Muon g-2 Collaboration, "
            "2025). Extract: 1) exact value of a_mu with uncertainty 2) precision in ppb "
            "3) experimental method (storage ring, spin precession frequency omega_a, "
            "magnetic field calibration) 4) comparison with BNL E821 5) Run-1-6 statistics. "
            "Return structured markdown."
        ),
    },
    {
        "type": "general-purpose",
        "prompt": (
            "Research the theoretical significance of the Fermilab Muon g-2 final result "
            "(arXiv:2506.03069, a_mu = 0.001165920705(148), 127 ppb, 2025) and the 2026 "
            "Breakthrough Prize in Fundamental Physics awarded to the Muon g-2 collaborations. "
            "Extract: 1) Standard Model prediction comparison and the tension (in sigma) "
            "2) hadronic vacuum polarization contribution (HVP) and the CMD-3 puzzle "
            "3) implications for physics beyond the Standard Model 4) why this won the 2026 "
            "Breakthrough Prize. Return structured markdown."
        ),
    },
]

print(f"=== spawn_multi: {len(TASKS)} subagents parallel ===", flush=True)
results = spawn_multi(TASKS)

for i, r in enumerate(results):
    print(f"\n--- Task {i} ({TASKS[i]['type']}) | success={r.success} | exit={r.exit_code} | {time.time()-T0:.1f}s ---")
    print((r.stdout or "")[:3000])
    if r.stderr:
        print(f"[stderr] {r.stderr[:500]}")

print(f"\n=== TOTAL: {time.time()-T0:.1f}s ===")

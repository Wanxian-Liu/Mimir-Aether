#!/usr/bin/env bash
# IQ-EVO-36: print top-5 tools by ok% from tool_quality.db
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export MIMIR_AETHER_HOME="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
python3 - <<'PY'
from agent.tool_quality import ToolQualityManager

qm = ToolQualityManager(enable_persistence=True)
report = qm.get_report()
tools = sorted(report.get("tools", []), key=lambda t: t.get("success_rate", 0), reverse=True)[:5]
print("tool_quality top5 (success_rate):")
for t in tools:
    print(f"  {t.get('tool')}: ok%={t.get('success_rate')} calls={t.get('calls')}")
if not tools:
    print("  (no persisted tool rows — documented empty)")
PY

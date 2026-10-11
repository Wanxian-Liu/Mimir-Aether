#!/usr/bin/env bash
# Deferred gateway restart smoke — must be launched DETACHED via systemd-run.
#
# Why this exists: restart_gateway_hard.sh (the gateway_restart allowlist script)
# kills EVERY gateway/run.py, including the one serving the live turn that called
# it -> the caller's reply is never delivered and the user's session is suspended.
# This wrapper is spawned by the *user manager* (systemd-run --on-active), so it
# survives the restart it triggers, and it writes evidence for the NEXT turn to
# read (the restarting process cannot report on itself).
#
# Usage (detached, from any turn):
#   systemd-run --user --collect --on-active=60s --unit=mimir-smoke-restart \
#     /bin/bash <repo>/scripts/deferred_gateway_restart_smoke.sh
#
# Evidence (append-only): $MIMIR_AETHER_HOME/data/ops/restart_smoke_<UTC>.md
# Exit: 0 always when evidence was written (this is a recorder, not a gate; the
#       verdict comes from post_restart_verify.py, whose rc is recorded too).
set -uo pipefail

REPO="${MIMIR_REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
HOME_DIR="${MIMIR_AETHER_HOME:-${HERMES_HOME:-$HOME/.mimiraether}}"
UNIT="mimiraether.service"
PORT="${MIMIR_PORT:-18999}"
GATE="agent/empty_run_gate.py"
OUT_DIR="$HOME_DIR/data/ops"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$OUT_DIR/restart_smoke_${TS}.md"
mkdir -p "$OUT_DIR"

PY="$REPO/.venv/bin/python3"
[[ -x "$PY" ]] || PY="python3"

sc() { systemctl --user show "$UNIT" -p "$1" --value 2>/dev/null; }

# Count only real interpreter processes: `pgrep -f` also matches bash wrappers
# and editors that merely embed the path in their command line (proven hazard —
# same filter ensure_single_gateway.sh uses).
gw_count() { pgrep -f 'gateway/run\.py' -l 2>/dev/null | awk '$2 ~ /^python/ {c++} END {print c+0}'; }

BEFORE_PID="$(sc MainPID)"
{
  echo "# Gateway restart smoke (deferred) — $TS"
  echo
  echo "## before"
  echo "- MainPID: $BEFORE_PID"
  echo "- NRestarts: $(sc NRestarts)"
  echo "- ActiveState/SubState: $(sc ActiveState)/$(sc SubState)"
  echo "- ExecMainStartTimestamp: $(sc ExecMainStartTimestamp)"
  echo "- gateway python proc count: $(gw_count)"
  echo "- repo HEAD: $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null)"
  echo "- $GATE sha256: $(sha256sum "$REPO/$GATE" 2>/dev/null | cut -d' ' -f1)"
  echo "- $GATE dirty: '$(git -C "$REPO" status --porcelain -- "$GATE" 2>/dev/null)' (empty = running code is the committed version)"
} >> "$OUT"

# --- the restart: systemd owns it, so exactly one instance comes back ---
systemctl --user restart "$UNIT" >/dev/null 2>&1
RC_RESTART=$?
{
  echo
  echo "## restart"
  echo "- cmd: systemctl --user restart $UNIT"
  echo "- rc: $RC_RESTART"
} >> "$OUT"

ready=0
for _ in $(seq 1 60); do
  if curl -sf --max-time 2 "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done

AFTER_PID="$(sc MainPID)"
{
  echo
  echo "## after"
  echo "- health_ready: $ready"
  echo "- MainPID: $AFTER_PID (before=$BEFORE_PID)"
  echo "- pid_changed: $([ "$AFTER_PID" != "$BEFORE_PID" ] && echo yes || echo no)"
  echo "- NRestarts: $(sc NRestarts)"
  echo "- ActiveState/SubState: $(sc ActiveState)/$(sc SubState)"
  echo "- ExecMainStartTimestamp: $(sc ExecMainStartTimestamp)"
  echo "- gateway python proc count: $(gw_count) (1 = single instance held)"
} >> "$OUT"

# --- canonical verifier: J1-J6, --fix recomputes empty cron next_run_at ---
{
  echo
  echo "## post_restart_verify.py --fix (rc recorded below)"
  echo '```'
} >> "$OUT"
"$PY" "$REPO/scripts/post_restart_verify.py" --fix >"$OUT.verify" 2>&1
RC_VERIFY=$?
tail -40 "$OUT.verify" >> "$OUT"
rm -f "$OUT.verify"
{
  echo '```'
  echo "- post_restart_verify rc: $RC_VERIFY (0=PASS 1=FAIL 2=error)"
  echo
  echo "## verdict-relevant readings (for the reporting turn)"
  echo "- pid_changed=$([ "$AFTER_PID" != "$BEFORE_PID" ] && echo yes || echo no) pid=$AFTER_PID (was $BEFORE_PID)"
  echo "- single_instance=$([ "$(gw_count)" = "1" ] && echo yes || echo no) count=$(gw_count)"
  echo "- health_ready=$ready verifier_rc=$RC_VERIFY"
} >> "$OUT"

echo "evidence: $OUT"
exit 0

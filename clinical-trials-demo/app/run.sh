#!/usr/bin/env bash
# The booth screen. Port 8503 because 8501/8502 belong to the fraud demo.
set -euo pipefail
cd "$(dirname "$0")/.."

# The agent tab needs ANTHROPIC_API_KEY. Keeping it in a gitignored .env means it
# survives restarts at a booth without being retyped -- and cannot be committed.
if [ -f .env ]; then
  set -a; . ./.env; set +a
fi
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "note: no ANTHROPIC_API_KEY — tabs 1-5 work, the agent tab will show a setup banner"
fi

# The Exasol VM's clock freezes while the host sleeps, and every lakehouse query
# then fails with a 403 that reads like bad credentials. It has bitten five times
# in two days. Resync before the app starts; it costs about a second.
RUNTIME="$HOME/.exasol/personal/deployments/default/local/runtime"
LAUNCHER=$(ls -t "$HOME/Library/Caches/.exasol/personal/runtime-artifacts/artifacts/exasol-local-runner"/*/*/*/unpack/launcher 2>/dev/null | head -1)
if [ -n "$LAUNCHER" ] && [ -f "$RUNTIME/vm-runtime.json" ]; then
  VM=$( (cd "$RUNTIME" && "$LAUNCHER" run -- date -u '+%s') 2>/dev/null | tail -1 )
  case "$VM" in ''|*[!0-9]*) VM="" ;; esac
  if [ -n "$VM" ]; then
    NOW=$(date -u '+%s'); SKEW=$(( VM > NOW ? VM - NOW : NOW - VM ))
    if [ "$SKEW" -gt 300 ]; then
      echo "VM clock ${SKEW}s behind — resyncing so the lakehouse works…"
      (cd "$RUNTIME" && "$LAUNCHER" run -- hwclock -s) >/dev/null 2>&1 || true
    fi
  fi
fi

VENV=".work/lakeenv"
# Rebuild when the venv is missing OR when a dependency is absent -- the agent
# imports anthropic lazily, so a half-built venv loads the page and then fails
# only when somebody clicks.
if [ ! -x "$VENV/bin/streamlit" ] || ! "$VENV/bin/python" -c "import anthropic, mcp" 2>/dev/null; then
  echo "creating the UI venv (one time)…"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q -r requirements.txt
fi
exec "$VENV/bin/streamlit" run app/app.py \
  --server.port "${PORT:-8503}" --server.headless true --browser.gatherUsageStats false

#!/usr/bin/env bash
# Bring the lake up and prove it is reachable FROM THE DATABASE -- which is the
# only reachability that matters and the one a health check on the host misses.
set -euo pipefail
cd "$(dirname "$0")"
source ../lib/common.sh

say "Lake up"
docker compose up -d >/dev/null 2>&1
for i in $(seq 1 30); do
  if docker compose ps --format '{{.Status}}' | grep -q healthy; then break; fi
  sleep 2
done
docker compose ps --format '    {{.Name}}  {{.Status}}'

# The VM's clock signs every S3 request. After the host sleeps it can freeze,
# and every lake query then fails with a 403 that reads like bad credentials.
say "VM clock (S3 signing depends on it)"
RUNTIME="$DEPLOY_DIR/local/runtime"
LAUNCHER=$(ls -t "$HOME/Library/Caches/.exasol/personal/runtime-artifacts/artifacts/exasol-local-runner"/*/*/*/unpack/launcher 2>/dev/null | head -1 || true)
if [ -n "$LAUNCHER" ] && [ -f "$RUNTIME/vm-runtime.json" ]; then
  VM=$( (cd "$RUNTIME" && "$LAUNCHER" run -- date -u '+%s') 2>/dev/null | tail -1 )
  NOW=$(date -u '+%s')
  SKEW=$(( VM > NOW ? VM - NOW : NOW - VM ))
  if [ "$SKEW" -gt 300 ]; then
    # Fix it rather than report it. This recurs every time the host sleeps, the
    # symptom is a 403 that reads like bad credentials, and the correction is a
    # one-line resync from the VM's own (correct) hardware clock.
    warn "VM clock ${SKEW}s behind — every S3 request would 403. Resyncing…"
    (cd "$RUNTIME" && "$LAUNCHER" run -- hwclock -s) >/dev/null 2>&1 || true
    VM=$( (cd "$RUNTIME" && "$LAUNCHER" run -- date -u '+%s') 2>/dev/null | tail -1 )
    NOW=$(date -u '+%s'); SKEW=$(( VM > NOW ? VM - NOW : NOW - VM ))
    [ "$SKEW" -le 300 ] && ok "clock resynced (${SKEW}s)" \
      || warn "still ${SKEW}s off — run: (cd $RUNTIME && '$LAUNCHER' run -- hwclock -s)"
  else
    ok "clock skew ${SKEW}s"
  fi
else
  warn "could not read the VM clock (launcher not found) — skipping skew check"
fi

say "Reachable from inside Exasol?"
exa_sql "CREATE SCHEMA IF NOT EXISTS LAKEHOUSE;
CREATE OR REPLACE PYTHON3 SCALAR SCRIPT LAKEHOUSE.NET_PROBE(host VARCHAR(100), port DECIMAL(9,0))
RETURNS VARCHAR(200) AS
import socket
def run(ctx):
    s = socket.socket(); s.settimeout(4)
    try:
        s.connect((ctx.host, int(ctx.port))); return 'OPEN'
    except Exception as e:
        return 'FAIL: %s' % e
    finally:
        s.close()
/" >/dev/null
xsql "SELECT 'object storage' AS TARGET, LAKEHOUSE.NET_PROBE('$LAKE_HOST',$LAKE_S3_PORT) AS R FROM DUAL
      UNION ALL SELECT 'iceberg catalog', LAKEHOUSE.NET_PROBE('$LAKE_HOST',$LAKE_CATALOG_PORT) FROM DUAL;"
say "Lake ready — console http://127.0.0.1:19001 (minioadmin/minioadmin)"

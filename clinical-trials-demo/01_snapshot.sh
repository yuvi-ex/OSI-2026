#!/usr/bin/env bash
# STEP 1 — the snapshot. Ships WITH the repo; this only refreshes it.
source "$(dirname "$0")/lib/common.sh"
say "1. ClinicalTrials.gov v2 snapshot (oncology: NSCLC + breast, interventional, 2015+)"
if [ -s "$DATA/trials_snapshot.json.gz" ] && [ "${FORCE:-0}" != "1" ]; then
  python3 -c "
import gzip,json,sys
d=json.load(gzip.open('$DATA/trials_snapshot.json.gz','rt'))
m=d['_meta']; print('    already present:', m['trials'], 'trials, fetched', m['fetched_utc'])
print('    filter:', m['advanced_filter'])"
  ok "using the committed snapshot — a booth must never depend on the venue network"
  say "STEP 1 DONE — set FORCE=1 to refetch"
  exit 0
fi
python3 "$KIT_ROOT/ingest/fetch_snapshot.py" "$DATA/trials_snapshot.json.gz"
say "STEP 1 DONE"

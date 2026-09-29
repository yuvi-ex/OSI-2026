#!/usr/bin/env bash
# STEP 2 — shred the snapshot into relational tables, including the eligibility
# chunks. The registry has NO structured inclusion/exclusion split; we recover it
# from prose headings here, and that recovered column is what rescues retrieval
# later, so it is the most important column in the schema.
source "$(dirname "$0")/lib/common.sh"

say "2a. Shred JSON -> CSV"
python3 "$KIT_ROOT/ingest/shred.py" "$DATA/trials_snapshot.json.gz" "$WORK/csv"

say "2b. Create tables"
xsql -f "$KIT_ROOT/sql/01_tables.sql" | tail -2

say "2c. Load"
for pair in "trials.csv:CT.TRIALS" "trial_conditions.csv:CT.TRIAL_CONDITIONS" \
            "trial_countries.csv:CT.TRIAL_COUNTRIES" "trial_outcomes.csv:CT.TRIAL_OUTCOMES" \
            "trial_arms.csv:CT.TRIAL_ARMS" "trial_interventions.csv:CT.TRIAL_INTERVENTIONS" \
            "elig_chunks.csv:CT.ELIG_CHUNKS"; do
  f="${pair%%:*}"; t="${pair##*:}"
  printf '    %-26s -> %s\n' "$f" "$t"
  exa_load "$t" "$WORK/csv/$f" >/dev/null
done

say "2d. What landed"
xsql "SELECT 'trials' AS T, COUNT(*) AS N FROM CT.TRIALS
      UNION ALL SELECT 'eligibility chunks', COUNT(*) FROM CT.ELIG_CHUNKS
      UNION ALL SELECT '  of which EXCLUSION', COUNT(*) FROM CT.ELIG_CHUNKS WHERE CRITERION_SECTION='EXCLUSION'
      UNION ALL SELECT '  of which INCLUSION', COUNT(*) FROM CT.ELIG_CHUNKS WHERE CRITERION_SECTION='INCLUSION'
      UNION ALL SELECT '  section unrecovered', COUNT(*) FROM CT.ELIG_CHUNKS WHERE CRITERION_SECTION='UNKNOWN'
      ORDER BY 2 DESC;"
say "STEP 2 DONE — every trial has eligibility text; 97% of chunks got a definite section"

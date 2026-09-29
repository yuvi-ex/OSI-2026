#!/usr/bin/env bash
# STEP 3 — the semantic layer: indication, sponsor, phase, status, endpoint, geography.
source "$(dirname "$0")/lib/common.sh"
say "3a. Build the views"
xsql -f "$KIT_ROOT/sql/03_semantic_layer.sql" | tail -2

ask <<'Q'
Which of our six dimensions can the registry actually answer?

  Structured and reliable : sponsor, status, geography, indication
  Structured but LOSSY    : phase -- a third of trials say "not applicable"
  DERIVED, not looked up  : endpoint -- the registry gives free text only
Q
say "3b. Phase: what a naive WHERE PHASE='PHASE3' would silently drop"
xsql "SELECT PHASE, COUNT(*) AS TRIALS,
             ROUND(100*COUNT(*)/SUM(COUNT(*)) OVER(),1) AS PCT
      FROM CT.V_TRIALS GROUP BY PHASE ORDER BY TRIALS DESC;"

say "3c. Endpoint: the cost of free-text outcomes"
xsql "SELECT ENDPOINT_CATEGORY, COUNT(*) AS N,
             ROUND(100*COUNT(*)/SUM(COUNT(*)) OVER(),1) AS PCT
      FROM CT.V_TRIAL_ENDPOINTS WHERE OUTCOME_KIND='PRIMARY'
      GROUP BY 1 ORDER BY N DESC;"

say "3d. Comparator: half a WHERE clause, half retrieval"
xsql "SELECT COMPARATOR_DESIGN, COUNT(*) AS N FROM CT.V_LANDSCAPE GROUP BY 1 ORDER BY N DESC;"
say "3e. CRO persona tables — the same corpus, shaped for a dashboard"
# Materialised and in their own schema: the dashboard harness profiles TABLES and
# skips views, so the grain has to be unambiguous. Scope caveat is in the SQL --
# the registry has no CRO field, so these describe the MARKET, not a portfolio.
xsql -f "$KIT_ROOT/sql/06_cro_tables.sql" | tail -2
xsql "SELECT 'CRO_GLOBAL' AS T, COUNT(*) AS N FROM CT_CRO.CRO_GLOBAL
      UNION ALL SELECT 'CRO_REGION', COUNT(*) FROM CT_CRO.CRO_REGION;"

say "STEP 3 DONE — say the 'unclassified' number out loud before anyone asks"

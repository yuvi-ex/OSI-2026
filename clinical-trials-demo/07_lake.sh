#!/usr/bin/env bash
# STEP 7 — the second source, and the second storage tier.
#
# Steps 1-6 argue that one engine answers a structured question and an
# unstructured one. This step argues the next thing a pharma architect asks:
# the data is never all in one place. Trials are in the warehouse; the evidence
# that a trial ever produced a result is somewhere else entirely.
#
# So publications live in a LAKEHOUSE -- Iceberg on object storage, never loaded
# into Exasol -- and the join happens anyway, in one statement.
source "$(dirname "$0")/lib/common.sh"

ask <<'Q'
The question a registry alone cannot answer:

  "Which completed trials never produced a publication?"

  Answering it needs data the registry does not hold:
    IN EXASOL     phase, status, sponsor, eligibility   -> native tables
    IN THE LAKE   PubMed publications                   -> Iceberg on S3
Q

say "7a. The publication data is NOT in Exasol"
xsql "SELECT COLUMN_TABLE AS LAKE_TABLE, COUNT(*) AS COLS
      FROM EXA_ALL_COLUMNS WHERE COLUMN_SCHEMA='CT_LAKE' GROUP BY 1 ORDER BY 1;"
cat <<'NOTE'

    CT_LAKE is a VIRTUAL schema. There is no table behind it -- the rows are
    Parquet files in object storage, described by an Iceberg catalog, and read
    at query time by a Rust UDF running DataFusion inside the database.
    Nothing was imported. Dropping the lake would empty these tables.
NOTE

say "7b. The join key is real, not fuzzy"
xsql "SELECT COUNT(*) AS LINK_ROWS, COUNT(DISTINCT NCT_ID) AS TRIALS,
             COUNT(DISTINCT PMID) AS PAPERS
      FROM CT_LAKE.TRIAL_PUBLICATIONS;"
cat <<'NOTE'

    PubMed records carry the registry number as a DataBank accession, so this is
    an equi-join on NCT_ID. No title matching, no similarity, nothing that needs
    a caveat. The one place this demo does NOT need retrieval.
NOTE

say "7c. One statement, two storage tiers"
xsql "SELECT t.PHASE,
             COUNT(*)                                                           AS COMPLETED,
             COUNT(DISTINCT p.NCT_ID)                                           AS PUBLISHED,
             COUNT(*) - COUNT(DISTINCT p.NCT_ID)                                AS NO_PUBLICATION,
             ROUND(100.0*(COUNT(*)-COUNT(DISTINCT p.NCT_ID))/COUNT(*),1)        AS PCT
      FROM CT.V_LANDSCAPE t
      LEFT JOIN CT_LAKE.TRIAL_PUBLICATIONS p ON p.NCT_ID = t.NCT_ID
      WHERE t.STATUS_GROUP = 'Completed' AND t.PHASE_IS_STATED
      GROUP BY t.PHASE ORDER BY COMPLETED DESC;"
cat <<'NOTE'

    CT.V_LANDSCAPE is a native Exasol view. CT_LAKE.TRIAL_PUBLICATIONS is
    Parquet in object storage. They are joined in ONE statement, by the planner,
    with no pipeline and no copy -- and the phase column is the semantic layer's,
    so the caveat from step 3 still applies and PHASE_IS_STATED is still honest.
NOTE

say "7d. What this number is, and what it is not"
xsql "SELECT 'trials in corpus'            AS FACT, COUNT(*) AS N FROM CT.V_LANDSCAPE
      UNION ALL SELECT 'with >=1 linked paper', COUNT(DISTINCT p.NCT_ID)
        FROM CT_LAKE.TRIAL_PUBLICATIONS p JOIN CT.V_LANDSCAPE t ON t.NCT_ID=p.NCT_ID
      UNION ALL SELECT 'papers in the lake', COUNT(*) FROM CT_LAKE.PUBLICATIONS;"
cat <<'NOTE'

    SAY THIS OUT LOUD: a paper that never cites its NCT number is invisible to
    this join, so "no linked publication" UNDERCOUNTS publication. It is a lower
    bound on reporting, not proof that a trial was never written up. The honest
    claim is about the LINK, not about the literature.
NOTE

say "7e. What the second tier costs"
python3 - <<'PYEOF'
import statistics, sys
sys.path.insert(0, "bin")
import exasql
for label, sql in (("native  CT.V_LANDSCAPE      ", "SELECT COUNT(*) AS N FROM CT.V_LANDSCAPE;"),
                   ("lake    CT_LAKE.PUBLICATIONS", "SELECT COUNT(*) AS N FROM CT_LAKE.PUBLICATIONS;")):
    ts = [exasql.rows_timed(sql)[1] for _ in range(3)]
    print("    %s  %5d ms" % (label, statistics.median(ts)))
PYEOF
cat <<'NOTE'

    Both numbers include client connect time, so the marginal cost of reaching
    the lake is the DIFFERENCE, not the total. Quote the difference.
NOTE

free_connections
say "STEP 7 DONE — the warehouse and the lake, joined in one statement"

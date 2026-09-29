#!/usr/bin/env bash
# STEP 5 — the platform claim.
#
# NARRATIVE ORDER MATTERS AND WAS WRONG ONCE. An earlier version of this script
# opened with the retrieval failure. It is the most credible material we have,
# but as an OPENING it teaches a general lesson about RAG that is true of any
# database with a WHERE clause -- so it argued for structured data in general
# and for Exasol not at all. The failure now closes step 6 as validation.
#
# What this step argues instead: a pharma question has a STRUCTURED half and an
# UNSTRUCTURED half, most architectures answer them in two systems, and this one
# answers both in a single auditable statement over one engine.
source "$(dirname "$0")/lib/common.sh"

ask <<'Q'
FEASIBILITY, the question that starts every trial:

  "We are planning a Phase 3 NSCLC study in patients who have NOT already had a
   checkpoint inhibitor. Who else is competing for those patients, and where?"

  Answering it needs two different kinds of data:
    STRUCTURED    phase, status, sponsor, geography      -> a WHERE clause
    UNSTRUCTURED  "excludes prior anti-PD-1 therapy"     -> lives only in prose
Q

say "5a. The structured half alone — everything the registry codes"
xsql "SELECT t.PHASE, t.STATUS_GROUP, COUNT(*) AS TRIALS,
             COUNT(DISTINCT t.LEAD_SPONSOR) AS SPONSORS
      FROM CT.V_LANDSCAPE t
      WHERE t.INDICATION = 'NSCLC' AND t.PHASE = 'PHASE3'
      GROUP BY 1,2 ORDER BY TRIALS DESC;"

cat <<'NOTE'

    Clean, fast, and it CANNOT answer the question. Nothing in any coded field
    says whether a trial admits patients who already had a checkpoint inhibitor.
    That fact exists only inside the eligibility prose.
NOTE

say "5b. The unstructured half alone — search the criteria text"
python3 "$KIT_ROOT/bin/search.py" \
  "prior treatment with an anti-PD-1 or anti-PD-L1 antibody" --topk 5

cat <<'NOTE'

    Relevant criteria, and equally unable to answer the question on its own: it
    has no idea which of these trials are Phase 3, recruiting, or anywhere near
    the sites we would use.
NOTE

ask <<'Q'
So most architectures put the two halves in two systems —
a vector store for the text, the warehouse for the facts —
and stitch them together in application code.

Watch what happens when they are in the same engine.
Q

say "5c. BOTH HALVES, ONE STATEMENT — the structured filter runs BEFORE scoring"
python3 "$KIT_ROOT/bin/search.py" \
  "prior treatment with an anti-PD-1 or anti-PD-L1 antibody" \
  --section EXCLUSION \
  --filter "AND t.INDICATION='NSCLC' AND t.PHASE='PHASE3' AND t.STATUS_GROUP='Open'" \
  --topk 8 --show-sql 2>&1 | tail -40

cat <<'NOTE'

    One SQL statement. No pipeline, no second store, no application-side join,
    and no step that a regulator would have to be walked through separately.
    Every row cites the NCT ID it came from.
NOTE

ask <<'Q'
The developer question at this point is always the same:
how is the database doing vector search at all?
Q

say "5d. The mechanism — a vector is rows, similarity is a GROUP BY"
xsql "SELECT COUNT(*) AS VECTOR_ROWS,
             COUNT(DISTINCT NCT_ID || '#' || CHUNK_ID) AS CRITERIA,
             COUNT(*) / COUNT(DISTINCT NCT_ID || '#' || CHUNK_ID) AS DIMS_EACH
      FROM CT.ELIG_VECTORS;"

cat <<'NOTE'

    Exasol has NO vector type and NO vector index. A 96-dimension vector is
    stored as 96 rows, normalised at build time, so cosine similarity is:

        SELECT v.NCT_ID, v.CHUNK_ID, SUM(v.VAL * q.VAL) AS SIM
        FROM   CT.ELIG_VECTORS v JOIN QV q ON q.DIM = v.DIM
        GROUP  BY v.NCT_ID, v.CHUNK_ID

    An exact scan of every row, in about five seconds, because scan-and-aggregate
    across cores is the one thing this engine was built to do. That is WHY both
    halves can live in one place: the unstructured half needs no special
    machinery to sit beside the structured half.
NOTE

ask <<'Q'
And the analytics? Same tables. No copy, no pipeline, no second model.
Q

say "5e. The dashboards read the same corpus the search reads"
xsql "SELECT 'trials in the search corpus' AS CORPUS, COUNT(*) AS N FROM CT.TRIALS
      UNION ALL SELECT 'trials on the global board', COUNT(*) FROM CT_CRO.CRO_GLOBAL
      UNION ALL SELECT 'criteria behind screening burden', COUNT(*) FROM CT.ELIG_CHUNKS;"

cat <<'NOTE'

    The board's screening-burden metric — how many criteria a patient must be
    checked against — exists ONLY because the eligibility prose was shredded for
    retrieval. The unstructured work produced a structured business measure that
    no off-the-shelf trial tracker carries. That is the payoff of one engine, not
    a slogan about it.

    Dashboards: http://127.0.0.1:5100/apps/cro-global
                http://127.0.0.1:5100/apps/cro-region
NOTE

say "STEP 5 DONE — one engine, both halves, one auditable statement"

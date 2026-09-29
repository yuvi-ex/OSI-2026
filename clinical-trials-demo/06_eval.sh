#!/usr/bin/env bash
# STEP 6 — the credibility close.
#
# This is where the failure material lives now. It used to open step 5, which
# made the demo an argument about retrieval instead of an argument about the
# platform. As a CLOSE it does the opposite job and does it well: after the
# claim has been made, showing exactly where the thing breaks is what separates
# a vendor demo from somebody who has actually built it.
source "$(dirname "$0")/lib/common.sh"

ask <<'Q'
Everything so far was the claim. This is the part that makes it believable.

  "Where does this break, and by how much?"
Q

say "6a. The failure — ask for EXCLUSION, get the opposite at rank 1"
python3 "$KIT_ROOT/bin/search.py" \
  "prior systemic therapy for metastatic disease" --topk 5

cat <<'NOTE'

    Read the SEC column. The top answer is an INCLUSION criterion reading "No
    prior systemic therapy for metastatic disease" -- the exact inverse of the
    question. Cosine 1.0000 and BM25 44.67 for BOTH it and the correct answer
    below it: identical scores for opposite meanings. There is no threshold that
    could separate them.
NOTE

say "6b. Why — the negation is deleted before anything is scored"
xsql "SELECT 'A  no prior systemic therapy' AS VARIANT, TERM
      FROM (SELECT CT.QUERY_TERMS('No prior systemic therapy for metastatic disease') FROM DUAL)
      UNION ALL
      SELECT 'B     prior systemic therapy', TERM
      FROM (SELECT CT.QUERY_TERMS('Prior systemic therapy for metastatic disease') FROM DUAL)
      ORDER BY 2, 1;"

cat <<'NOTE'

    Identical term sets. 'no' is an English stopword, so the analyzer removes it
    before scoring -- and this is a property of the retrieval model, not of the
    database. A transformer embedding would retrieve better and would be just as
    blind to it.
NOTE

say "6c. What fixes it — a column, applied before scoring"
python3 "$KIT_ROOT/bin/search.py" \
  "prior systemic therapy for metastatic disease" --section EXCLUSION --topk 5

ask <<'Q'
Now the honest part. How much did that column actually buy,
across a question set rather than one lucky example?
Q

say "6d. Twelve questions, each run twice"
python3 "$KIT_ROOT/eval/run_eval.py" --k "${K:-20}"

cat <<'NOTE'

    Recall 0.675 -> 0.858, and every returned row from the intended half.

    Three things to say before anyone asks:

    1. THE COLUMN NARROWS WHERE THE MODEL CAN BE WRONG. It does not make the
       model right. That cosine is still 1.0000; the wrong answer is merely no
       longer in scope.

    2. IT ONLY WORKS WHEN THE QUESTION MAPS TO ONE HALF. "Trials involving prior
       chemotherapy" could legitimately be either, and then there is nothing to
       filter on.

    3. SOME FAILURES ARE INSIDE ONE HALF. Ask for "EGFR mutation positive" and
       "EGFR mutation negative" ranks above it -- both are INCLUSION criteria,
       so the filter has nothing to separate. Left unfixed, and documented.

    And the gold sets are SQL predicates over this corpus: reproducible, but not
    independent. Review-derived questions are outstanding.
NOTE

say "STEP 6 DONE — the number that matters is the delta, and its limits are stated"

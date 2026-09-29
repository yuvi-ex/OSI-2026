# Review-derived eval questions — OUTSTANDING

`eval/questions.json` currently contains **11 questions, all `snapshot-sql`**:
their gold sets are SQL predicates over the loaded data. That makes them
reproducible and auditable, but it does not make them independent — the same
assumptions that shaped the chunking also shape the gold set.

The brief asks for an eval set derived from **published landscape reviews**, and
that is genuinely different: a review's trial table is ground truth assembled by
domain experts who never saw this pipeline. Deriving those gold sets is reading
work, not scripting, so it is listed here rather than faked.

## What each one needs

For each review, record in `questions.json`:

- `gold_source: "review"`
- `review_citation` — DOI or PMID, so a judge can check it
- `query` — the landscape question the review's table answers
- `gold_nct_ids` — the NCT IDs the review lists (a trial-level gold set, so the
  harness needs a trial-level recall metric alongside the chunk-level one)

## Why it matters more than more questions

Twenty-five review-derived questions beat sixty snapshot-derived ones. The
snapshot-derived set can only tell you whether retrieval agrees with a regex;
the review-derived set can tell you whether it agrees with the field.

## Candidate shapes

- Phase 3 NSCLC first-line immunotherapy trials — tests the phase gap directly,
  since a third of the snapshot is `NA`.
- HER2-low breast cancer trials — a subtype that only exists in text.
- Trials with an active comparator naming a specific agent — the comparator
  question, where half the answer is `armGroup.type` and half is the arm label.

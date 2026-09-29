---
name: clinical-trials-retrieval
description: Answer clinical-trial landscape questions against the local Exasol CT schema — a semantic layer over ClinicalTrials.gov plus hybrid retrieval over eligibility text. Always cites NCT IDs. Triggers — "which trials", "trial landscape", "eligibility criteria", "phase 3 trials for", "who sponsors", "exclude patients with", "NCT".
---

# Answering trial questions on the CT schema

Read the question, decide which half is **structured** and which half is
**text**, then write one SQL statement that uses both. Always cite NCT IDs.

## The layer

- `CT.V_LANDSCAPE` — one row per trial: phase, status group, sponsor type,
  comparator design, primary endpoint category, region count. Start here.
- `CT.V_TRIALS`, `CT.V_TRIAL_GEOGRAPHY`, `CT.V_TRIAL_ENDPOINTS`, `CT.V_TRIAL_DESIGN`
- `CT.ELIG_CHUNKS` — eligibility criteria, one row per criterion, with
  `CRITERION_SECTION` in INCLUSION / EXCLUSION / UNKNOWN.

## Three things that will make you wrong

1. **`PHASE = 'PHASE3'` drops a third of the data.** 34.4% of trials say
   `NOT_APPLICABLE`. If the user asks about phase, say how many trials have no
   phase, or filter on `PHASE_IS_STATED` and state that you did.
2. **`ENDPOINT_CATEGORY` is derived from free text and 35.7% is
   'Other / unclassified'.** Never present an endpoint breakdown without that
   number.
3. **Similarity cannot see negation.** `no`, `not` and `without` are stopwords,
   so "prior treatment with X" and "no prior treatment with X" score the same.
   **Whenever polarity matters, filter `CRITERION_SECTION` — do not trust the
   ranking to do it.**

## The retrieval pattern

`sql/05_hybrid_search.sql.tmpl` is the canonical statement: vector cosine,
BM25, fused with RRF, with the structured filter applied before scoring. Fill
`{{QUERY}}`, `{{SECTION_FILTER}}`, `{{TRIAL_FILTER}}`, `{{TOPK}}`. The query
text appears twice, once per UDF.

Vector search is a join and a `GROUP BY` over `CT.ELIG_VECTORS`; there is no
index, so restrict candidates with the semantic layer first whenever you can.

A UDF that EMITS columns cannot share a SELECT list with other columns — wrap
it in a subquery, always:

```sql
SELECT DIM, VAL FROM (SELECT CT.EMBED_QUERY('...') FROM DUAL)
```

## Citing

Every claim about a trial carries its NCT ID. Every claim about a criterion
quotes the criterion text and names its `CRITERION_SECTION` — a criterion
without its section is not evidence, because the section is the half the
retrieval got wrong.

`CONDITION` and `SECTION` are reserved words in Exasol; the columns are
`CONDITION_NAME` and `CRITERION_SECTION`.

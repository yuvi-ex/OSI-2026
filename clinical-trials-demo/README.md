# Clinical trial intelligence on Exasol

Ask a clinical-trial question in English. An agent writes the SQL, runs it against
Exasol, and answers citing the trial IDs it used. Ask for a landscape instead and
the same data produces a structured report you can send on.

The point the demo makes is not that the engine is fast. It is that **"pembrolizumab
in the US" is 538 trials, or 304, or 50**, depending on three judgements nobody
usually writes down — and that a semantic layer is where those judgements belong.

```
./lake/up.sh             # object storage + an Iceberg catalog (2 containers)
./lake/install_engine.sh # the lakehouse engine into Exasol
./02_load_exasol.sh      # shred the committed snapshot into tables
./03_semantic_layer.sh   # the views, and the resolution layer
./04_build_vectors.sh    # embed offline, load 25.8M rows, install the UDFs
./00_preflight.sh        # GO / NO-GO, 15 checks
./app/run.sh             # the demo, on http://127.0.0.1:8503
```

## What it does

**Three pages.** The challenge, the demo, and how Exasol does it.

**An agent, over MCP.** Claude reaches the database through
[`exasol-mcp-server`](https://github.com/exasol-labs/exasol-mcp-server): it reads
the schema, writes its own SQL, runs it, and cites NCT ids. No query is written
for it, and it reaches Iceberg tables in object storage the same way it reaches
native ones, because a virtual schema is just a schema.

Query execution is **off by default** in that server. Turn it on with
`EXA_MCP_SETTINGS={"enable_read_query": true}`, or the agent can only describe
the schema and never query it.

**Report generation.** A keyword such as *"What is the current trial landscape for
Pembrolizumab in US"* produces a structured report — scope, trials, sponsors,
phase, status, geography, endpoints, publication linkage — downloadable as
Markdown, and convertible with `bin/md2pdf.py`. The sections and their SQL are
fixed, so the same keyword always produces the same document; the model writes
only the summary, over numbers already computed.

**A resolution layer** (`sql/07_resolution.sql`) that publishes its judgements
instead of burying them:

| Judgement | Measured on pembrolizumab |
|---|---|
| Which names are the same drug | 732 by literal name, **760** with aliases — 28 trials say only Keytruda or MK-3475 |
| Which sponsors are one company | 4 strings roll up to Merck & Co.; **Merck KGaA is a different company** and stays separate |
| What "in the US" means | **538** has-a-US-site · **304** US-only · *US-led is not derivable — the registry has no sponsor country* |

Every report opens by stating which reading it took and what the alternatives
would have given.

## The second source, and the second storage tier

Trials are in the warehouse. The evidence that a trial ever produced a *result*
is not, so PubMed publications live in a **lakehouse** -- Iceberg tables on
object storage -- and are never loaded into Exasol. They are read at query time
by `exasol-labs/lakehouse-engine-rs`, a Rust UDF running DataFusion inside the
database, and joined to native tables in one statement:

```sql
SELECT t.PHASE, COUNT(*) - COUNT(DISTINCT p.NCT_ID) AS NO_PUBLICATION
FROM CT.V_LANDSCAPE t                                    -- native Exasol
LEFT JOIN CT_LAKE.TRIAL_PUBLICATIONS p ON p.NCT_ID = t.NCT_ID  -- Parquet on S3
WHERE t.STATUS_GROUP = 'Completed' AND t.PHASE_IS_STATED
GROUP BY t.PHASE;
```

The join key is real: PubMed carries the registry number as a DataBank
accession, so this is an equi-join on `NCT_ID`, not title matching.

**65.8% of completed Phase 3 trials have no linked publication.** Say the caveat
with the number: a paper that never cites its NCT number is invisible to this
join, so it is a lower bound on reporting, not proof a trial went unpublished.

Cost of the second tier, measured: a native count is ~330ms and a lake count
~490ms, both including client connect time -- so reaching the lake costs about
**160ms**, not 490.

### How the lakehouse is installed here

`lake/install_engine.sh` places the engine and its language container into the
database's storage directory and registers the four scripts it needs. On the
local backend the Exasol node shares that directory with the host, so the engine
is installed with a file copy rather than an upload.

`lake/docker-compose.yml` runs MinIO for object storage and
`apache/iceberg-rest-fixture` for the Iceberg catalog — two containers, the same
REST interface a managed catalog exposes.

`lake/up.sh` starts them and verifies that the database can reach both, and
`00_preflight.sh` checks the same path as part of its GO / NO-GO report.

## What it needs

**Cloning this repo is not enough to see the UI.** The snapshots ship with it,
but the database does not — the app opens on *"Exasol is not answering"* until
you have loaded the data locally.

To get from a clone to a running demo you need:

| | Needed for |
|---|---|
| **Exasol Personal**, running locally (`exasol status` says `database_ready`) with the PYTHON3 SLC | everything |
| **Docker** | the offline embedding step, and the two lakehouse containers |
| Steps `02` → `04` | the tables, the views and the 25.8M vector rows. Roughly 15 minutes, most of it the embedding |
| `lake/up.sh` + `lake/install_engine.sh` | the lakehouse sections only. Skip them and those sections hide themselves |
| `ANTHROPIC_API_KEY` in `.env` | the agent and the report summary. Everything else works without it |

`app/run.sh` builds its own virtualenv from `requirements.txt` on first run, so
Python dependencies need no separate step.

Everything reaches the database through the Exasol CLI: `exasol connect` for SQL,
`IMPORT FROM LOCAL CSV FILE` for bulk load, and a plain `cp` into the storage
directory the VM shares with the host. There is no separate load tool and no SSH
to the node.

## The one design idea

Exasol has no vector type and no vector index. So vectors are stored **long and
narrow** — one row per dimension — and cosine similarity is an ordinary join and
`GROUP BY`:

```sql
SELECT v.NCT_ID, v.CHUNK_ID, SUM(v.VAL * q.VAL) AS SIM
FROM CT.ELIG_VECTORS v JOIN QV q ON q.DIM = v.DIM
GROUP BY v.NCT_ID, v.CHUNK_ID
```

Vectors are L2-normalised at build time, so a dot product *is* cosine. 25.8M
rows scan in about 5 seconds. Everything expensive — the TF-IDF fit, the SVD —
happens offline in Docker with sklearn pinned to the version the Exasol SLC
ships, because otherwise the pickle will not unpickle inside the UDF.

## What the data will and will not tell you

Measured on the loaded snapshot (12,404 trials), not quoted from documentation:

| Dimension | Reality |
|---|---|
| sponsor, status, geography, indication | Structured and reliable |
| **phase** | 34.4% say `NA` — "not applicable". `WHERE PHASE='PHASE3'` silently drops a third of the landscape, so the view exposes `PHASE_IS_STATED`. |
| **endpoint** | Free text only (`measure` + `timeFrame`). Derived by pattern into 18 categories; **35.7% still land in "Other / unclassified"** and that number is reported, not hidden. |
| **comparator** | Half structured: `armGroup.type` codes whether a control exists, but *which* drug it is sits in the arm label as prose. |
| **eligibility** | One free-text blob. There is **no** structured inclusion/exclusion field — the split is recovered here from prose headings, and 97.3% of chunks resolve to a definite section. |

## The failure, which is the point

Ask for trials that *exclude* prior PD-1 exposure and the fourth hit is
`NCT02595866`, whose criterion reads **"No prior treatment with anti-PD-1 or
anti-PD-L1"** — in the INCLUSION section. The opposite of the question.

Cosine cannot separate it: **0.9987 against 0.9990**. BM25 scores it *higher*
than two correct rows. The reason is one query away:

```sql
SELECT TERM FROM (SELECT CT.QUERY_TERMS('No prior treatment with anti-PD-1') FROM DUAL);
SELECT TERM FROM (SELECT CT.QUERY_TERMS('Prior treatment with anti-PD-1') FROM DUAL);
```

Identical. `no` is an English stopword, so the analyzer deletes the negation
before any scoring happens. Both rankers are blind, and fusing two blind
rankers does not restore sight.

What fixes it is not a bigger model. It is the recovered `CRITERION_SECTION`
column, applied before scoring:

| | recall@20 | section purity |
|---|---|---|
| text alone | 0.675 | 0.763 |
| with the structured section filter | **0.858** | **1.000** |
| — hybrid questions | 0.713 → 0.925 | 0.769 → 1.000 |
| — polarity questions | 0.600 → **0.725** | 0.750 → 1.000 |

The worst single case is `pol-02`, *"no prior systemic chemotherapy for
metastatic disease"* — **recall 0.15**, because the negation this time is in the
**query**, and the analyzer deletes it there too.

## A second failure the section filter cannot fix

Ask for `EGFR mutation positive`, filtered to INCLUSION, and at **rank 13**
comes *"EGFR mutation or ALK mutation was **negative**"* -- cosine 0.9455, in
INCLUSION, the section that was asked for. A starker example, *"EGFR mutation
negative and ALK fusion negative"* in `NCT07633873`, sits at rank 52. These ranks
are recomputed on every run rather than quoted, because a rank changes whenever
the corpus does. Here `negative` is **not** a
stopword -- it survives tokenisation intact. The vector space simply does not encode that it inverts the
meaning, and BM25 sees a term match. Both the right and wrong criteria sit in
INCLUSION, so **the structured section filter offers no rescue at all**: recall
stays at 0.65 even with it applied (`pol-04`).

So there are two distinct polarity failures, not one:

| | mechanism | fixable by the section column? |
|---|---|---|
| "no prior treatment with X" | stopword deletion — `no` is removed before scoring | Yes, partly |
| "EGFR mutation negative" | antonymy — the token survives, the meaning does not | **No** |

Polarity is the category the structured filter helps *least*, because the
retrieval still cannot tell the two sentences apart; the filter only stops it
looking in the wrong half.

## Honesty

- All eval gold sets are `snapshot-sql`: reproducible predicates over the loaded
  data, **not** an independent ground truth. Review-derived questions are
  outstanding and tracked in `eval/REVIEW_QUESTIONS.md`.
- The vector side is TF-IDF + 96-dim SVD, not a transformer. It explains only
  18% of variance and its similarities are compressed into a narrow band near
  1.0, so *relative* order carries the signal and absolute scores mean little.
  A transformer would retrieve better and would be **just as blind to `no`**.
- The API advertises no rate limits, and the snapshot is committed anyway, so a
  demonstration never depends on network access.

# The demo screen

```
./app/run.sh            # http://127.0.0.1:8503
```

Three pages, built as an ARGUMENT rather than a tool, so it works with nobody
standing next to it:

| Page | What it covers |
|---|---|
| 1 · The challenge | the four shapes the answer is spread across, and what one engine changes |
| 2 · The demo | ask a question (agent writes the SQL) **or** generate a landscape report |
| 3 · How Exasol does it | the architecture, vectors as rows, the virtual schema, and the limits |

Every number is queried live when the page loads — nothing is typed in. A
**Walkthrough** mode reduces the same argument to six full-screen steps for
presenting to a room.

Two of the pages end by admitting a limit, which is deliberate: the stopword
proof is computed by `CT.QUERY_TERMS` on the spot, and the antonymy blind spot
reports its *current* rank rather than a remembered one.

# Local probe UI

```
python3 bin/ui.py     # http://127.0.0.1:8899/
```

Stdlib only. Runs every question BOTH ways -- text alone and with the structured
section filter -- side by side, and highlights in red any top-ranked row that came
from the wrong criteria section. Preset buttons load the two known failures.

## Licence

MIT — see [LICENSE](LICENSE).

The trial data in `data/` comes from [ClinicalTrials.gov](https://clinicaltrials.gov),
a public US National Library of Medicine registry, and is not covered by this licence.

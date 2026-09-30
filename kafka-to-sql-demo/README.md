# Kafka to SQL — real-time fraud detection with Exasol

A live booth demo. A card payment is written to PostgreSQL, captured by Debezium,
carried by Kafka, landed in Exasol next to thirty days of history, and scored by a
model — all in SQL. Then an AI agent investigates it through Exasol's MCP server,
seeing only what the analyst it runs as is allowed to see.

Every number on screen is read live from the running PostgreSQL, Kafka and Exasol.

---

## The UI

Four tabs, one story: the problem, the live pipeline, how it is built, and asking
questions of the result.

### 1 · The challenge

![The challenge](screenshots/1-the-challenge.png)

One payment followed through a typical stream-plus-warehouse setup. The stream has
to decide in seconds with only one message, so it approves; the nightly warehouse
knows it was fraud — nine hours later. Below it, what the gap costs: this payment at
the industry's true cost of fraud, and card fraud losses worldwide.

### 2 · Live — Kafka to SQL

![Live — Kafka to SQL](screenshots/2-live-kafka-to-sql.png)

Press **Suspicious transaction** and the same $8,750 payment runs through the real
pipeline. Each hop is timed, the verdict comes back in about 1.4 seconds, and the
two columns show the difference: **Kafka sees** one raw event; **Exasol knows** its
velocity, how it compares with 30 days of normal spend, the merchant risk and the
model's score. The SQL behind the table is one click away.

### 3 · How it works

![How it works](screenshots/3-how-it-works.png)

The architecture in four phases — **build** the Kafka reader into Exasol once,
**stream** every payment in next to its history, **score** it in SQL with a Python
UDF, **ask** about it in plain English. After a run, the measured per-hop timings
appear underneath: most of the time is transport; the analytics inside Exasol is
well under a second.

### 4 · Agentic investigation

![Agentic investigation](screenshots/4-agentic-investigation.png)

The agent has no database credential of its own. It reaches Exasol through the
official MCP server, signed in as a **persona** — a real database user holding
SELECT on two row-filtered views and nothing else. Ask the same question as the US
analyst, the EU analyst and the fraud lead: the answer changes because the rows do,
not because the agent behaved differently. Every answer cites the statement that
produced it, and the audit trail is read back as that analyst.

---

## How it's built

Five steps for one payment. The last three run inside one database, in about 0.6 s.

| # | Step | Where | What happens |
|---|---|---|---|
| 1 | Payment written | PostgreSQL | a row is inserted into `transactions` |
| 2 | Change captured | Debezium → Kafka | Debezium reads the Postgres change log and publishes the row as Avro on `banking_avro.public.transactions` |
| 3 | Landed | Exasol | the Kafka connector (a Java UDF in BucketFS) runs `IMPORT … FROM SCRIPT` into `KAFKA_STAGE`, then a `MERGE` into `RAW.TRANSACTIONS` — or the host fallback stages it, see below |
| 4 | Features built | Exasol SQL | `07_refresh_analytics_features.sql` compares the payment with that account's 30 days of history using window functions and joins |
| 5 | Scored | Exasol Python UDF | `ANALYTICS.FRAUD_SCORE_UDF` loads the model from BucketFS and returns a fraud probability; a `CASE` turns it into APPROVE (< 0.30), REVIEW or BLOCK (≥ 0.70) |

The training script (`train_pipeline.py`) and the UDF (`02_features_and_udfs.sql`)
live in the parent
[real-time-banking-fraud-pipeline](https://github.com/SanjayG-Data/real-time-banking-fraud-pipeline)
repo.

## The model

**A logistic regression** — scikit-learn `LogisticRegression(class_weight="balanced")`
behind a `StandardScaler`, pickled to BucketFS as `fraud_model.pkl` (`LOGREG_DEMO_v1`).

**Twelve inputs, all computed in SQL** from the payment and its history:

| Group | Features |
|---|---|
| Size | amount; amount vs her 30-day average |
| Velocity | payments in the last hour and 24 hours; their totals |
| Novelty | new country in 30 days; new device in 30 days; cross-border |
| Timing | night-time; weekend |
| Merchant | base risk weight of the merchant category (casino 0.75, café 0.05, …) |

**Why logistic regression**

1. **It explains itself.** One weight per feature; the score is the sum of
   weight × value through a sigmoid. A blocked payment can be justified to a
   regulator or a customer. Its strongest weight is merchant category, ahead of
   both velocity counts.
2. **It is fast and small.** Scoring is a handful of multiplications, so it runs
   inside a SQL UDF in milliseconds, with no separate model server.
3. **It keeps the focus on the architecture.** The point is that event, history
   and model live in one database; a simple model keeps attention there.
4. **It is swappable.** The UDF loads any pickled scikit-learn-style model, so a
   gradient-boosted model (XGBoost, LightGBM) drops in without touching the
   pipeline or the SQL.

**How it was trained — and what not to claim.** The shipped model is trained on
5,000 synthetic rows at a 4% fraud rate, where the fraudulent rows were generated
larger, faster and more often cross-border. The training report shows AUC 1.0;
that only says the model separates data generated to be separable, so it is not
an accuracy figure. In production it would be retrained on real labelled fraud
(chargebacks, confirmed cases), probably with a stronger model;
`train_pipeline.py --source exasol` already trains from labels in
`ANALYTICS.FRAUD_FEATURES` once enough exist.

---

## Run it

This folder runs inside a checkout of
[real-time-banking-fraud-pipeline](https://github.com/SanjayG-Data/real-time-banking-fraud-pipeline):
it reuses that repo's `.venv`, `.env` (PostgreSQL, Exasol and `ANTHROPIC_API_KEY`
for tab 4) and the SQL in its `demo_dashboard.py`. Put this folder at the root of
that checkout, with the pipeline's containers and Exasol running.

```bash
# once, ever
./.venv/bin/python kafka-to-sql-demo/seed_story_persona.py
./.venv/bin/python kafka-to-sql-demo/setup_personas.py
./.venv/bin/python -c "import sys;sys.path.insert(0,'kafka-to-sql-demo');import pipeline;pipeline.sync_history()"

# every time
kafka-to-sql-demo/start_demo.sh
```

Open **http://localhost:8502**.

### Settings

| Variable | Default | What it does |
|---|---|---|
| `DEMO_KAFKA_BOOTSTRAP` | `localhost:29092` (set by `start_demo.sh`) | Where the app itself reads the topic |
| `DEMO_SCHEMA_REGISTRY` | `http://localhost:8081` (set by `start_demo.sh`) | Avro schemas for the same |
| `DEMO_STAGE_MODE` | `auto` | `connector`, `host` or `auto` — see below |
| `DEMO_AGENT_EFFORT` | `medium` | Reasoning effort for the agent; `high` is deeper and slower |

### "Fallback staging"

The intended path is Exasol's own
[Kafka connector](https://github.com/exasol/kafka-connector-extension): Exasol reads
the topic itself with an `IMPORT … FROM SCRIPT`. That needs the Exasol VM to reach
the broker. On a laptop whose managed firewall blocks inbound connections from the
VM bridge, it cannot — so in `auto` mode the app probes the path at start-up and, if
it is blocked, reads the topic on the host and writes the same rows into
`KAFKA_STAGE.TRANSACTIONS`, partition and offset included. The Live tab shows a
**Fallback staging** chip whenever that is happening. Because the connector resumes
from the offsets stored in that table, either path can take over from the other with
nothing skipped or duplicated.

---

## Tested on

The free **Exasol Personal** edition, on a laptop. It shows where the work happens,
not how far it scales.

**Exasol**

| | |
|---|---|
| Edition | Exasol Personal, local deployment (`exasol install local`) |
| Exasol Personal CLI | 2.3.0 |
| Database | Exasol 2026.2.0 (`2026.2.0-nano.3`) |
| Cluster | 1 node |
| VM | 2 vCPUs · 24 GB RAM (`memory-mb = 24576`) · 100 GB data disk |
| UDF languages | Python 3.12 and Java 17 (script-language containers 11.2.0) |
| Connection | `127.0.0.1:8563`, TLS with a self-signed certificate |

**Installed by this demo**

| Component | Detail |
|---|---|
| Kafka connector | `exasol-kafka-connector-extension-2.0.0.jar` in BucketFS — Java UDFs `KAFKA_CONSUMER`, `KAFKA_IMPORT`, `KAFKA_METADATA` |
| Connector tuning | `POLL_TIMEOUT_MS=400`, `MIN_RECORDS_PER_RUN=1`, `MAX_RECORDS_PER_RUN=5000`, `CONSUME_ALL_OFFSETS=true`; Avro via Schema Registry |
| Model | `fraud_model.pkl` in BucketFS, scikit-learn 1.7.2 `LogisticRegression` + `StandardScaler` |
| Data flow | `KAFKA_STAGE` → `RAW` → `CLEANSED` → `ANALYTICS`, plus `FRAUD_DEMO` (row-filtered views for the agent) |

**Host:** Apple M5 Pro (18 cores, 48 GB RAM), macOS 26.6 on arm64. The demo's data
is well under 1 GB; the 24 GB VM covers Exasol's own recommended database RAM for
everything on the instance with room to spare.

---

## On stage

1. `kafka-to-sql-demo/start_demo.sh`
2. **Reset data** on the Live tab — rewinds to the opening state; the 30-day history
   survives.
3. Run one agent question before the audience arrives (≈40 s), which also confirms
   the API key.

Suggested flow: tab 1 sets up the $8,750 payment → tab 2 fires that exact payment and
blocks it live → tab 3 shows where each step ran → tab 4 asks the agent about it as
three different people.

---

## Three things that had to be fixed first

**1. The import took 62 seconds.** The connector defaults to `POLL_TIMEOUT_MS=30000`
and `MIN_RECORDS_PER_RUN=100`, so importing one transaction sits in an empty poll
waiting for 99 more. `POLL_TIMEOUT_MS='400'` and `MIN_RECORDS_PER_RUN='1'` took the
pipeline from **62.96 s to 3.32 s** (`TUNED_IMPORT` in `pipeline.py`).

**2. The scores were nonsense.** Every seeded transaction had been created within
the same half hour, so the velocity window counted the whole dataset and the 30-day
average had nothing to average. `seed_story_persona.py` spreads 49 ordinary payments
across 30 real days: a $29.55 baseline and a genuinely empty velocity window.

**3. Deletes never propagated past RAW.** The analytics refresh only MERGEs, so
deleted transactions stayed in the velocity windows forever and every rehearsal
scored higher than the last. `reset_story()` prunes them (`PRUNE_ORPHANS`).

---

## What this demo does not claim

- **The model is deliberately small** — a logistic regression over twelve features.
- **The customer is synthetic** — seeded, identical on every run.
- **Delivery is at-least-once** — idempotent by key and offset, not exactly-once.
- **One node, small volumes** — it shows where the computation happens, not how far
  it scales.

Figures on tab 1: card fraud losses of $33.41 billion worldwide in 2024
([Nilson Report](https://nilsonreport.com/articles/card-fraud-losses-worldwide-2024/));
every $1 of fraud costs North American financial institutions more than $5
([LexisNexis Risk Solutions, 2025](https://risk.lexisnexis.com/about-us/press-room/press-release/20250910-fraud-multiplier)).
The "~$43,750" is $8,750 at that multiplier; the nine-hour batch window is
illustrative.

---

## Files

```
app.py                 the Streamlit app — four tabs
pipeline.py            connections, tuned import, host staging fallback, run_event, reset
agent.py               the investigation loop (Claude + Exasol MCP)
mcp_client.py          personas and the MCP server settings (read-only)
architecture.py        the drawn diagrams (tabs 1 and 3)
theme.py               styling
chapters.py, story.py  page copy and the scripted payments
seed_story_persona.py  the isolated customer + 30 days of history
setup_personas.py      the three database users and their row-filtered views
sql/                   persona and audit DDL
start_demo.sh          one-command start
screenshots/           the images above
```

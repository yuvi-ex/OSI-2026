# Kafka to SQL — demo brief

Speaker's reference for the Open Source India demo. Every number here was read
off the running system on 27 Sep 2026, not from notes. Where something is a
known weakness, it is written down as one — those are the questions that get
asked from the floor.

App: `story_demo/app.py`, Streamlit on **port 8502**.
The colleague's original dashboard is untouched on **8501** and is the fallback.

---

## 1. What we are trying to do

Show that **a fraud decision can be a SQL query instead of a distributed
system**, and that an AI agent can be pointed at that database safely.

A card payment is committed in PostgreSQL, captured by Debezium, published to
Kafka, imported into Exasol, enriched against thirty days of that customer's
history, scored by a model running inside the database, and turned into
approve / review / block — and every step of that is visible as SQL on screen.
Then an analyst asks a question in plain English and an agent answers it
**as that analyst**, seeing only what that person is entitled to see.

## 2. The point we want to make

Three claims, in the order the demo makes them.

**Claim 1 — one Kafka message is not enough to make a fraud decision.**
A message says "$8,750 at LuckyBet Online". It does not say whether that is
normal *for this customer*. The decision needs history, and history lives in a
database. That is why "stream processing" alone does not close this problem.

**Claim 2 — the history, the feature definitions and the model are all in one
database, so scoring is a query.**
In a typical stack those are three systems: a warehouse, a feature store, and a
model-serving API — three network hops, three things to keep in sync, three
places for training/serving skew to creep in. Here the thirty-day aggregates,
the feature SQL and the scoring function are all inside Exasol. Answering
"is this fraud?" is one statement.

**Claim 3 — the agent is a client, not a superuser.**
The agent holds no database credential of its own. It reaches Exasol only
through an MCP server, read-only, signed in as the person asking. The audit
table records **the analyst's database user, not the agent**, and that identity
is read from the engine (`SELECT CURRENT_USER`), not from anything the model
could assert about itself.

## 3. Versions — the exact answers

| Component | Version | Note |
|---|---|---|
| Exasol | **2026.2.0-nano.3** | Exasol Personal, local single-node. `databaseProductVersion` read live. |
| Kafka connector extension | **1.7.16** | `exasol-kafka-connector-extension-1.7.16.jar`, loaded from BucketFS as a Java SET SCRIPT. |
| Kafka | Confluent Platform **7.5.0** | broker, Zookeeper and Schema Registry, in Docker. |
| PostgreSQL | **15** | source of truth, Debezium captures from it. |
| CDC | Debezium via Kafka Connect | Avro, with Schema Registry. |
| pyexasol | **1.3.0** | the demo app's driver. |
| exasol-mcp-server | **2.2.0** | official, run over stdio. |
| mcp (Python SDK) | **1.30.0** | client side. |
| anthropic SDK | **1.8.0** | |
| Model | **claude-opus-5** | adaptive thinking, tool-use loop, max 10 turns. |
| scikit-learn | **1.7.2** | logistic regression, pickled into BucketFS. |
| Streamlit | **1.64.0** | |

Topic: `banking_avro.public.transactions`, **3 partitions**, Avro.

## 4. Live numbers

Read from the running system, 27 Sep 2026:

- `RAW.TRANSACTIONS` — **74 rows**
- `CLEANSED.FACT_TRANSACTIONS` — **74 rows**
- `ANALYTICS.FRAUD_FEATURES` — **74 rows**
- `FRAUD_DEMO.AGENT_AUDIT` — **50 investigations logged**
- Kafka topic — **226 messages**

**Row-level security, measured by connecting as each user:**

| Persona | DB user | Rows visible |
|---|---|---|
| Fraud Analyst · US retail | `FRAUD_ANALYST_US` | **59** |
| Fraud Analyst · EU retail | `FRAUD_ANALYST_EU` | **15** |
| Fraud Lead · both books | `FRAUD_LEAD` | **74** |

Same view, same query, three different answers — because the view joins on
`CURRENT_USER` against an entitlements table. 59 + 15 = 74, which is the point:
the lead sees exactly the union, nobody sees a row twice.

**Timing, over 7 measured runs:**

- End to end **3.2–4.0s**, median **3.5s**
- Per hop: postgres 4 ms · kafka 2,753 ms · raw merge 52 ms · features 131 ms ·
  score 547 ms
- So **~730 ms is analytics**; the rest is one-off connector startup per import.

## 5. The tuning number — the best engineering moment in the demo

The connector defaults to `POLL_TIMEOUT_MS=30000` and `MIN_RECORDS_PER_RUN=100`.
Importing a single transaction therefore sits in an empty poll waiting for 99
more records that never arrive.

**62.96s → 3.32s**, a 19× improvement, by setting `POLL_TIMEOUT_MS='400'` and
`MIN_RECORDS_PER_RUN='1'`.

This is worth saying out loud: it is the difference between "Kafka to Exasol is
slow" and "Kafka to Exasol is a misconfigured poll window". If someone in the
audience has tried this and found it slow, this is almost certainly why.

## 6. How it works — the four phases

**Phase 1 · Build time (once).** Download the connector jar → upload it into
BucketFS, the database's own storage, with one `curl -X PUT` → name it in SQL
with `CREATE JAVA SET SCRIPT KAFKA_CONSUMER`. After that, reading the stream is
just another thing SQL can do.

**Phase 2 · Live.** `IMPORT INTO ... FROM SCRIPT` pulls from Kafka — Exasol is
the consumer, nothing sits in between. A `MERGE` on `TXN_ID` writes the latest
row per key. The connector resumes from the highest Kafka offset already stored
in the table, which is what makes a repeated import incremental.

**Phase 3 · Query time.** Features are computed in SQL (`COUNT(*) OVER (... 1
HOUR ...)`, `AMOUNT_USD / AVG_30D`). The model is called like any other
function: `SELECT FRAUD_SCORE_UDF(amount, count_1h, ...)`. The decision rule is
visible SQL — `CASE WHEN SCORE >= 0.70 THEN 'BLOCK' WHEN >= 0.30 THEN 'REVIEW'
ELSE 'APPROVE' END` — not hidden application code.

**Phase 4 · Agent time.** The analyst asks in English. The agent connects
through the MCP server as that analyst's database user, read-only, and returns
an answer with the SQL that produced it.

## 7. Security model — three independent layers

Worth being precise here, because this is the question a security-minded
audience will press on.

1. **Database grants.** Each persona has `SELECT` on three views only —
   `V_SCORED_TRANSACTIONS`, `V_CUSTOMERS`, `V_MY_AUDIT`. The base tables are
   denied. Verified by trying and being refused.
2. **MCP server settings.** `enable_write_query: false`,
   `enable_write_bucketfs: false`, `enable_read_bucketfs: false`,
   schemas restricted to `FRAUD_DEMO`, `default_row_limit: 50`.
3. **The agent is outside both.** It has four tools —
   `list_exasol_tables_and_views`, `describe_exasol_tables_and_views`,
   `execute_exasol_query`, `summarize_exasol_table` — and no credential.

If layer 3 is compromised, layer 2 still refuses writes; if layer 2 is
misconfigured, layer 1 still refuses the row. **The identity in the audit table
is read from the engine, so the agent cannot forge who it was acting as.**

## 8. What this demo does NOT claim — say it before you are asked

- **The model is deliberately small.** Logistic regression over twelve
  features. Its strongest coefficient is merchant category, ahead of both
  velocity counts. It is there to show *where computation happens*, not to be a
  good fraud model.
- **The customer is synthetic.** Elena Fischer and her 49 backdated
  transactions were generated with a fixed seed (`random.seed(4242)`), so every
  run is identical. Plausible, not real.
- **Delivery is at-least-once.** Idempotence comes from merging on the primary
  key and resuming at the highest stored offset — not from a distributed
  transaction. Do not call it exactly-once.
- **One node, small volumes.** Local single-node Exasol. This shows where the
  computation lives, not how far it scales.

## 9. Known rough edges — be ready

- **"BLOCK but SETTLED".** `insert_transaction()` hardcodes
  `STATUS='SETTLED'`, so the agent correctly reports that a payment was scored
  BLOCK yet still settled — the block was never enforced. If asked: *this demo
  scores and decides; wiring the decision back into the payment authoriser is
  the part a bank already owns.* That is a true and good answer, but know it is
  coming.
- **Saturated scores.** `FRAUD_SCORE` is `DECIMAL(6,5)`, so a score clips at
  1.00000. The ranking is meaningful; the last digits of a saturated score are
  not.
- **`exakit status` reports "not installed"** on this machine while the
  database is genuinely running. Use `exasol status` for the pre-demo check.
  Do **not** run the starter-kit installer to "fix" it.
- **If nothing connects:** Exasol is down. `exasol status` should say
  `database_ready`; port 8563 must have a listener.

## 10. Prepared questions for the agent

1. *Investigate the blocked payments* — the headline run.
2. *What can you actually see?* — the agent enumerates its own scope. Best
   answer to "how do you know it is really restricted?"
3. *Everything on Elena Fischer*
4. *Is the merchant compromised, or the card?* — the distinction changes who
   the bank contacts.
5. *Find the card-testing pattern* — small charge then a large one, same
   account, minutes apart.
6. *Show me the EU book* — **run this as the US analyst.** The correct answer
   is a refusal. This is the strongest security moment in the demo: the agent
   says it cannot see those rows rather than inventing them.

## 11. Running it

```bash
exasol status                     # must say database_ready
cd ~/real-time-banking-fraud-pipeline
./.venv/bin/streamlit run story_demo/app.py --server.port 8502 \
    --server.headless true --browser.gatherUsageStats false
```

Page 2 has a **Reset data** button that clears the story rows and prunes
orphans, so the demo can be run repeatedly from a clean state.

If a restart appears to do nothing, check the port is not still held by an older
process: `lsof -nP -iTCP:8502 -sTCP:LISTEN` and confirm the PID changed.

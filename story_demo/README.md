# Anatomy of a Card Theft — the stage demo

A story, not a console. Seven acts, one control, every number read live from the
running Postgres, Kafka and Exasol.

Standalone: it adds files under `story_demo/` and one isolated customer in the
database. **`demo_dashboard.py` is untouched and keeps working on port 8501.**

---

## Run it

```bash
# once, ever
./.venv/bin/python story_demo/seed_story_persona.py
./.venv/bin/python -c "import sys;sys.path.insert(0,'story_demo');import pipeline;pipeline.sync_history()"

# every time
./.venv/bin/streamlit run story_demo/app.py --server.port 8502
```

Open **http://localhost:8502**. Press **BEGIN**, then **NEXT** six times.

---

## The story

| Act | What happens | Verdict | Score |
|---|---|---|---|
| 1 | Elena buys coffee, $5.40 | APPROVED | 0.00000 |
| 2 | Card stolen — $1 test charge, Malta, new device | APPROVED | 0.00793 |
| 3 | $180 electronics | APPROVED | 0.00383 |
| 4 | $2,400 wire transfer | **BLOCKED** | 1.00000 |
| 5 | $8,750 at an online casino | **BLOCKED** | 1.00000 |
| 6 | Why it blocked — the score taken apart | — | — |
| 7 | Where all of that ran | — | — |

Acts 1–3 approving is the point, not a weakness: it shows the model is not
trigger-happy. A one-dollar charge from a new country in a new device is *not*
fraud, and the model says so. Then it changes its mind, hard.

Verified identical across consecutive runs. Rehearse as often as you like.

---

## Three things I had to fix first

These were breaking the pipeline before any UI existed.

**1. The import took 62 seconds.** The connector defaults to
`POLL_TIMEOUT_MS=30000` and `MIN_RECORDS_PER_RUN=100`, so importing one
transaction sits in an empty poll waiting for 99 more that never arrive —
measured at 62s with data, 92s idle. Setting `POLL_TIMEOUT_MS='400'` and
`MIN_RECORDS_PER_RUN='1'` took the full pipeline from **62.96s to 3.32s**.
Below 400ms there is no further gain; the remaining ~2.6s is JVM startup inside
the UDF sandbox. See `TUNED_IMPORT` in `pipeline.py`. **This applies to
`demo_dashboard.py` too** and is worth porting across.

**2. The scores were nonsense.** On the original seed data a $4.60 coffee scored
**0.239** and a $1.00 test charge scored **0.963**. Nothing was wrong with the
model or the SQL — every transaction in the database had been created within the
same half hour, so `TXN_COUNT_1H` (the model's #2 coefficient) counted the entire
dataset as velocity, and `ACCOUNT_AVG_AMOUNT_30D` had no history to average.
The fix is `seed_story_persona.py`: 49 ordinary transactions spread across 30
real days, giving a $29.55 baseline and a genuinely empty velocity window.

**3. Deletes never propagated past RAW.** `07_refresh_analytics_features.sql`
only MERGEs — nothing removes rows from `CLEANSED.FACT_TRANSACTIONS` or
`ANALYTICS.FRAUD_FEATURES` when a transaction is deleted upstream. Deleted rows
therefore stayed inside the velocity windows forever, so the *same* demo scored
higher on every rehearsal. `reset_story()` now prunes orphans (`PRUNE_ORPHANS`
in `pipeline.py`); without it, run three would not look like run one.

---

## The receipt (act 6)

Contributions are `coefficient × scaled_value` for the logistic regression in
BucketFS. They sum to the log-odds; the sigmoid of that sum reproduces the score
the database returned **to 0.00e+00**. It is arithmetic, not a post-hoc
explanation.

For act 5 the drivers are, in order: size vs her normal spend (+38.97 — 113×
her average), merchant category risk (+7.27), amount (+3.68), outside home
country (+1.60), transactions in the last hour (+1.28).

Worth knowing on stage: **merchant category is the model's single strongest
coefficient** (+1.4896), ahead of both velocity counts. If someone asks what the
model keys on most, the honest answer is *where* she shopped, not *how fast*.

---

## On stage

- **Reset data** rewinds to the opening state. The 30-day history survives;
  only the story's own transactions are removed. Do this before you walk on.
- **Back** re-shows a completed act without re-running it — results are cached,
  so stepping back costs nothing.
- Each act takes about 3.3 seconds of visible pipeline time. That gap is real
  and worth narrating rather than apologising for.
- Keep Kafka UI on another tab if you want to show the topic; this demo does
  not need it.

## Files

```
story_demo/seed_story_persona.py   the isolated customer + 30 days of history
story_demo/pipeline.py             connections, tuned import, run_event, reset, attribution
story_demo/story.py                the script — acts, narration, amounts
story_demo/theme.py                stage CSS (Plus Jakarta Sans, projector type scale)
story_demo/app.py                  the Streamlit app
```

Nothing outside `story_demo/` was modified.

# Sample data

The data the demo runs on, exported from a live run: one synthetic customer, her
30-day card history, and the three demo payments with the features Exasol computed
and the score the model returned.

Everything here is synthetic. The customer, email (`example.com`), phone (`555`) and
card (Visa's `4111` test number, masked) are fictional.

## Files

| File | Rows | What it is |
|---|---|---|
| `customer.csv` | 1 | Elena Fischer — the demo customer (US, KYC verified, low risk) |
| `account.csv` | 1 | her checking account, `ACC-90000001` |
| `card.csv` | 1 | her debit card |
| `transactions_history.csv` | 49 | 30 days of ordinary spending: coffee, groceries, fuel, the odd online order — all in Austin, US, all from her iPhone. Average $29.55, largest $91.27 |
| `demo_payments.csv` | 3 | the three presets as they were written to PostgreSQL, with their final status |
| `scored_examples.csv` | 3 | the same three payments as Exasol scored them: all twelve model features, the fraud score, the decision and the top drivers |

The three outcomes:

| Payment | Score | Decision | Top drivers |
|---|---|---|---|
| $5.40, Corner Coffee, her phone | 0.00 | APPROVE | none — nothing raised the risk |
| $475, Summit Wire Transfer, her phone | 0.49 | REVIEW | merchant category 50%, size vs normal 48% |
| $8,750, LuckyBet Online, Malta, unknown device | 1.00 | BLOCK | size vs normal 82% (219× her average), merchant category 8% |

The review amount is chosen at run time (see the main README); $475 is what it picks
right after a reset.

## Using it

**For the live demo, use `seed_story_persona.py` rather than these files.** The model's
features are relative to *now* — payments in the last hour, the last 30 days — so a
history with fixed dates slowly falls out of the 30-day window. The seed script
regenerates the same history relative to today (it uses a fixed random seed, so the
payments are identical apart from their dates).

**To inspect or experiment elsewhere**, load the CSVs directly. The column order matches
the parent repo's PostgreSQL schema (`01_schema.sql`):

```bash
psql "$DATABASE_URL" \
  -c "\copy customers    FROM 'customer.csv'             CSV HEADER" \
  -c "\copy accounts     FROM 'account.csv'              CSV HEADER" \
  -c "\copy cards        FROM 'card.csv'                 CSV HEADER" \
  -c "\copy transactions FROM 'transactions_history.csv' CSV HEADER"
```

**To reproduce a score**, pass a row of `scored_examples.csv` to the scoring UDF in
Exasol — the result matches the `FRAUD_SCORE` column. For the blocked payment:

```sql
SELECT ANALYTICS.FRAUD_SCORE_UDF(
         8750,        -- AMOUNT_USD
         2, 2,        -- TXN_COUNT_1H, TXN_COUNT_24H
         480.4, 480.4,-- AMOUNT_SUM_1H, AMOUNT_SUM_24H
         219.0416,    -- AMOUNT_VS_AVG_RATIO
         TRUE, TRUE, TRUE,   -- IS_CROSS_BORDER, IS_NEW_COUNTRY_30D, IS_NEW_DEVICE_30D
         FALSE, FALSE,       -- IS_NIGHT_TXN, IS_WEEKEND_TXN
         0.75)        -- MCC_BASE_RISK
       AS FRAUD_SCORE;   -- 1.0
```

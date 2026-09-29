#!/usr/bin/env python3
"""
Seed an ISOLATED persona for the story demo.

Nothing existing is modified. This creates one new customer, account and card,
plus ~30 days of ordinary spending history for them, so that the fraud-detection
features mean something:

  * ACCOUNT_AVG_AMOUNT_30D becomes a real baseline (~$45) instead of 0
  * TXN_COUNT_1H is 0 when the demo starts, so the fraud run visibly climbs
  * The home country and device are established, so the flags fire correctly

Re-runnable: it deletes and rebuilds only this persona's rows.
"""
import os, random, sys, uuid
from datetime import datetime, timedelta
from pathlib import Path
import psycopg2

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / '.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

# --- the persona -------------------------------------------------------------
CUSTOMER_ID = "e1e0a000-0000-4000-8000-000000000001"
ACCOUNT_ID  = "e1e0a000-0000-4000-8000-000000000002"
CARD_ID     = "e1e0a000-0000-4000-8000-000000000003"
FULL_NAME   = "Elena Fischer"
ACCOUNT_NO  = "ACC-90000001"
HOME_DEVICE = "DEV-ELENA-IPHONE-13"
HOME_CITY, HOME_COUNTRY = "Austin", "US"

# Ordinary life: a coffee habit, a weekly shop, fuel, the odd online order.
# Low-risk MCCs only, so the baseline is genuinely boring.
PATTERN = [
    # (mcc, merchant,           lo,    hi,   channel, per_week)
    ("5812", "Corner Coffee",    4.20,  6.80, "POS",     5),
    ("5411", "H-E-B Groceries", 42.00, 96.00, "POS",     2),
    ("5541", "Shell Station",   34.00, 58.00, "POS",     1),
    ("5812", "Torchy's Tacos",  18.00, 44.00, "POS",     1),
    ("5999", "Amazon Retail",   16.00, 74.00, "ONLINE",  1),
    ("5912", "Walgreens",       11.00, 38.00, "POS",     1),
]
DAYS = 30
random.seed(4242)   # deterministic: every rehearsal seeds identical history


def main():
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"), port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"), user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )
    cur = conn.cursor()

    # Clear only this persona, so re-running is safe.
    cur.execute("DELETE FROM transactions WHERE account_id = %s", (ACCOUNT_ID,))
    removed = cur.rowcount
    cur.execute("DELETE FROM cards    WHERE card_id    = %s", (CARD_ID,))
    cur.execute("DELETE FROM accounts WHERE account_id = %s", (ACCOUNT_ID,))
    cur.execute("DELETE FROM customers WHERE customer_id = %s", (CUSTOMER_ID,))

    cur.execute("""
        INSERT INTO customers (customer_id, full_name, email, phone, date_of_birth,
                               country_code, kyc_status, risk_band)
        VALUES (%s,%s,%s,%s,%s,%s,'VERIFIED','LOW')
    """, (CUSTOMER_ID, FULL_NAME, "elena.fischer@example.com", "+1-512-555-0142",
          "1991-04-17", HOME_COUNTRY))

    cur.execute("""
        INSERT INTO accounts (account_id, customer_id, account_number, account_type,
                              currency, balance, credit_limit, status, opened_at)
        VALUES (%s,%s,%s,'CHECKING','USD',%s,%s,'ACTIVE',%s)
    """, (ACCOUNT_ID, CUSTOMER_ID, ACCOUNT_NO, 12480.00, 5000.00,
          datetime.now() - timedelta(days=900)))

    cur.execute("""
        INSERT INTO cards (card_id, account_id, card_type, masked_pan, last_four,
                           expiry_date, network, status, issued_at)
        VALUES (%s,%s,'DEBIT',%s,'9001',%s,'VISA','ACTIVE',%s)
    """, (CARD_ID, ACCOUNT_ID, "4111-****-****-9001", "2029-08-31",
          datetime.now() - timedelta(days=400)))

    now = datetime.now()
    rows, total = [], 0.0
    for day in range(DAYS, 0, -1):
        date = now - timedelta(days=day)
        for mcc, merchant, lo, hi, channel, per_week in PATTERN:
            if random.random() > per_week / 7.0:
                continue
            amount = round(random.uniform(lo, hi), 2)
            when = date.replace(
                hour=random.randint(7, 20),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
                microsecond=0,
            )
            rows.append((
                str(uuid.uuid4()), ACCOUNT_ID, CARD_ID, "PURCHASE", amount, "USD", "DR",
                merchant, mcc, channel, HOME_DEVICE, HOME_COUNTRY, HOME_CITY,
                "SETTLED", f"HIST-{uuid.uuid4().hex[:10]}", when, when,
            ))
            total += amount

    cur.executemany("""
        INSERT INTO transactions (txn_id, account_id, card_id, txn_type, amount, currency,
                                  direction, merchant_name, merchant_mcc, channel, device_id,
                                  country_code, city, status, reference_id, initiated_at, settled_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, rows)
    conn.commit()

    print(f"removed {removed} prior rows for this persona")
    print(f"{FULL_NAME}  {ACCOUNT_NO}  card ****9001  device {HOME_DEVICE}")
    print(f"seeded {len(rows)} transactions across {DAYS} days")
    print(f"average transaction: ${total/len(rows):,.2f}")
    print(f"span: {min(r[15] for r in rows):%Y-%m-%d} -> {max(r[15] for r in rows):%Y-%m-%d}")
    conn.close()


if __name__ == "__main__":
    main()

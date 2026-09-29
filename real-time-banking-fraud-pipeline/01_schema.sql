-- ============================================================
--  BANKING OLTP SCHEMA  –  PostgreSQL
--  Layer: Source / Transactional
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─────────────────────────────────────────────
-- CUSTOMERS
-- ─────────────────────────────────────────────
CREATE TABLE customers (
    customer_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name       VARCHAR(200) NOT NULL,
    email           VARCHAR(200) NOT NULL UNIQUE,
    phone           VARCHAR(30),
    date_of_birth   DATE        NOT NULL,
    country_code    CHAR(2)     NOT NULL,                 -- ISO 3166-1 alpha-2
    kyc_status      VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                    CHECK (kyc_status IN ('PENDING','VERIFIED','FLAGGED','REJECTED')),
    risk_band       VARCHAR(10) DEFAULT 'UNKNOWN'
                    CHECK (risk_band IN ('LOW','MEDIUM','HIGH','UNKNOWN')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────
-- ACCOUNTS
-- ─────────────────────────────────────────────
CREATE TABLE accounts (
    account_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID        NOT NULL REFERENCES customers(customer_id) ON DELETE RESTRICT,
    account_number  VARCHAR(30) NOT NULL UNIQUE,
    account_type    VARCHAR(20) NOT NULL
                    CHECK (account_type IN ('CHECKING','SAVINGS','CREDIT','LOAN')),
    currency        CHAR(3)     NOT NULL DEFAULT 'USD',   -- ISO 4217
    balance         NUMERIC(18,4) NOT NULL DEFAULT 0,
    credit_limit    NUMERIC(18,4),                        -- only for CREDIT accounts
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE','FROZEN','CLOSED','SUSPENDED')),
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────
-- CARDS
-- ─────────────────────────────────────────────
CREATE TABLE cards (
    card_id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID        NOT NULL REFERENCES accounts(account_id) ON DELETE RESTRICT,
    card_type       VARCHAR(20) NOT NULL
                    CHECK (card_type IN ('DEBIT','CREDIT','VIRTUAL','PREPAID')),
    masked_pan      CHAR(19)    NOT NULL,                 -- e.g. 4111-****-****-1234
    last_four       CHAR(4)     NOT NULL,
    expiry_date     DATE        NOT NULL,
    network         VARCHAR(20) DEFAULT 'VISA'
                    CHECK (network IN ('VISA','MASTERCARD','AMEX','DISCOVER')),
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE','BLOCKED','EXPIRED','LOST','STOLEN')),
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────
-- MERCHANT CATEGORY CODES  (MCC reference table)
-- ─────────────────────────────────────────────
CREATE TABLE mcc_codes (
    mcc             CHAR(4)     PRIMARY KEY,
    description     VARCHAR(200) NOT NULL,
    category        VARCHAR(100),
    base_risk_score NUMERIC(4,3) NOT NULL DEFAULT 0.1    -- 0.0 (low) to 1.0 (high)
);

-- ─────────────────────────────────────────────
-- TRANSACTIONS  (core CDC source)
-- ─────────────────────────────────────────────
CREATE TABLE transactions (
    txn_id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id          UUID        NOT NULL REFERENCES accounts(account_id),
    card_id             UUID        REFERENCES cards(card_id),      -- NULL for ACH/wire
    txn_type            VARCHAR(30) NOT NULL
                        CHECK (txn_type IN (
                            'PURCHASE','ATM_WITHDRAWAL','TRANSFER_OUT','TRANSFER_IN',
                            'REFUND','FEE','INTEREST','DIRECT_DEPOSIT'
                        )),
    amount              NUMERIC(18,4) NOT NULL CHECK (amount > 0),
    currency            CHAR(3)     NOT NULL DEFAULT 'USD',
    direction           CHAR(2)     NOT NULL CHECK (direction IN ('DR','CR')),
    -- Merchant info (nullable for non-purchase types)
    merchant_name       VARCHAR(200),
    merchant_mcc        CHAR(4)     REFERENCES mcc_codes(mcc),
    merchant_id         VARCHAR(100),
    -- Channel & device context
    channel             VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN'
                        CHECK (channel IN ('ONLINE','POS','ATM','MOBILE','BRANCH','API','UNKNOWN')),
    ip_address          INET,
    device_id           VARCHAR(100),
    device_fingerprint  TEXT,
    user_agent          TEXT,
    -- Geo context
    country_code        CHAR(2),
    city                VARCHAR(100),
    latitude            NUMERIC(9,6),
    longitude           NUMERIC(9,6),
    -- Counterparty (for transfers)
    counterparty_account VARCHAR(30),
    counterparty_bank    VARCHAR(100),
    -- Status lifecycle
    status              VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING','SETTLED','DECLINED','REVERSED','FLAGGED')),
    decline_reason      VARCHAR(100),
    reference_id        VARCHAR(100) UNIQUE,              -- external reference
    -- Timestamps
    initiated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    settled_at          TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ─────────────────────────────────────────────
-- FRAUD ALERTS  (investigation outcomes)
-- ─────────────────────────────────────────────
CREATE TABLE fraud_alerts (
    alert_id        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    txn_id          UUID        NOT NULL REFERENCES transactions(txn_id),
    alert_type      VARCHAR(50) NOT NULL,                 -- VELOCITY, GEO_ANOMALY, etc.
    fraud_score     NUMERIC(5,4),                         -- ML score 0-1
    risk_score      NUMERIC(5,4),
    status          VARCHAR(20) NOT NULL DEFAULT 'OPEN'
                    CHECK (status IN ('OPEN','CONFIRMED_FRAUD','FALSE_POSITIVE','INVESTIGATING')),
    investigator    VARCHAR(100),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ
);

-- ─────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────
CREATE INDEX idx_txn_account_id        ON transactions(account_id);
CREATE INDEX idx_txn_initiated_at      ON transactions(initiated_at DESC);
CREATE INDEX idx_txn_status            ON transactions(status);
CREATE INDEX idx_txn_card_id           ON transactions(card_id);
CREATE INDEX idx_accounts_customer_id  ON accounts(customer_id);
CREATE INDEX idx_fraud_alerts_txn_id   ON fraud_alerts(txn_id);

-- ─────────────────────────────────────────────
-- ENABLE LOGICAL REPLICATION (for Debezium CDC)
-- ─────────────────────────────────────────────
ALTER TABLE transactions  REPLICA IDENTITY FULL;
ALTER TABLE accounts      REPLICA IDENTITY FULL;
ALTER TABLE customers     REPLICA IDENTITY FULL;
ALTER TABLE cards         REPLICA IDENTITY FULL;
ALTER TABLE fraud_alerts  REPLICA IDENTITY FULL;

-- ─────────────────────────────────────────────
-- AUTO-UPDATE updated_at TRIGGER
-- ─────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_customers_updated_at   BEFORE UPDATE ON customers   FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_accounts_updated_at    BEFORE UPDATE ON accounts    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_cards_updated_at       BEFORE UPDATE ON cards       FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_transactions_updated_at BEFORE UPDATE ON transactions FOR EACH ROW EXECUTE FUNCTION update_updated_at();

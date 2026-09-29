-- ============================================================
--  EXASOL ANALYTICAL SCHEMA
--  Three-layer: RAW → CLEANSED → ANALYTICS
-- ============================================================

-- ─────────────────────────────────────────────
-- LAYER 1: RAW  (direct landing from Kafka)
-- ─────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS RAW;

CREATE OR REPLACE TABLE RAW.TRANSACTIONS (
    TXN_ID                  VARCHAR(36)     NOT NULL,
    ACCOUNT_ID              VARCHAR(36),
    CARD_ID                 VARCHAR(36),
    TXN_TYPE                VARCHAR(30),
    AMOUNT                  DECIMAL(18,4),
    CURRENCY                CHAR(3),
    DIRECTION               CHAR(2),
    MERCHANT_NAME           VARCHAR(200),
    MERCHANT_MCC            CHAR(4),
    MERCHANT_ID             VARCHAR(100),
    CHANNEL                 VARCHAR(20),
    IP_ADDRESS              VARCHAR(45),
    DEVICE_ID               VARCHAR(100),
    DEVICE_FINGERPRINT      VARCHAR(2000),
    COUNTRY_CODE            CHAR(2),
    CITY                    VARCHAR(100),
    LATITUDE                DECIMAL(9,6),
    LONGITUDE               DECIMAL(9,6),
    COUNTERPARTY_ACCOUNT    VARCHAR(30),
    COUNTERPARTY_BANK       VARCHAR(100),
    STATUS                  VARCHAR(20),
    DECLINE_REASON          VARCHAR(100),
    REFERENCE_ID            VARCHAR(100),
    INITIATED_AT            TIMESTAMP,
    SETTLED_AT              TIMESTAMP,
    -- Kafka metadata
    KAFKA_OFFSET            BIGINT,
    KAFKA_PARTITION         INTEGER,
    KAFKA_TOPIC             VARCHAR(200),
    KAFKA_INGESTED_AT       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    DEBEZIUM_OP             CHAR(1),    -- c=create, u=update, d=delete
    CONSTRAINT RAW_TXN_PK PRIMARY KEY (TXN_ID)
);

CREATE OR REPLACE TABLE RAW.ACCOUNTS (
    ACCOUNT_ID      VARCHAR(36)     NOT NULL,
    CUSTOMER_ID     VARCHAR(36),
    ACCOUNT_NUMBER  VARCHAR(30),
    ACCOUNT_TYPE    VARCHAR(20),
    CURRENCY        CHAR(3),
    BALANCE         DECIMAL(18,4),
    CREDIT_LIMIT    DECIMAL(18,4),
    STATUS          VARCHAR(20),
    OPENED_AT       TIMESTAMP,
    UPDATED_AT      TIMESTAMP,
    KAFKA_INGESTED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT RAW_ACC_PK PRIMARY KEY (ACCOUNT_ID)
);

CREATE OR REPLACE TABLE RAW.CUSTOMERS (
    CUSTOMER_ID     VARCHAR(36)     NOT NULL,
    FULL_NAME       VARCHAR(200),
    EMAIL           VARCHAR(200),
    PHONE           VARCHAR(30),
    DATE_OF_BIRTH   DATE,
    COUNTRY_CODE    CHAR(2),
    KYC_STATUS      VARCHAR(20),
    RISK_BAND       VARCHAR(10),
    CREATED_AT      TIMESTAMP,
    UPDATED_AT      TIMESTAMP,
    KAFKA_INGESTED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT RAW_CUST_PK PRIMARY KEY (CUSTOMER_ID)
);

CREATE OR REPLACE TABLE RAW.CARDS (
    CARD_ID              VARCHAR(36)     NOT NULL,
    ACCOUNT_ID           VARCHAR(36),
    CARD_TYPE            VARCHAR(20),
    MASKED_PAN           VARCHAR(19),
    LAST_FOUR            CHAR(4),
    EXPIRY_DATE          DATE,
    NETWORK              VARCHAR(20),
    STATUS               VARCHAR(20),
    ISSUED_AT            TIMESTAMP,
    UPDATED_AT           TIMESTAMP,
    KAFKA_INGESTED_AT   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT RAW_CARD_PK PRIMARY KEY (CARD_ID)
);

CREATE OR REPLACE TABLE RAW.FRAUD_ALERTS (
    ALERT_ID             VARCHAR(36)     NOT NULL,
    TXN_ID               VARCHAR(36),
    ALERT_TYPE           VARCHAR(50),
    FRAUD_SCORE          DECIMAL(6,5),
    RISK_SCORE           DECIMAL(6,5),
    STATUS               VARCHAR(20),
    INVESTIGATOR         VARCHAR(100),
    NOTES                VARCHAR(2000),
    CREATED_AT           TIMESTAMP,
    RESOLVED_AT          TIMESTAMP,
    KAFKA_INGESTED_AT   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT RAW_ALERT_PK PRIMARY KEY (ALERT_ID)
);

-- ─────────────────────────────────────────────
-- LAYER 2: CLEANSED  (deduplicated, typed, conformed)
-- ─────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS CLEANSED;

CREATE OR REPLACE TABLE CLEANSED.FACT_TRANSACTIONS (
    TXN_ID                  VARCHAR(36)     NOT NULL,
    ACCOUNT_ID              VARCHAR(36)     NOT NULL,
    CARD_ID                 VARCHAR(36),
    TXN_TYPE                VARCHAR(30),
    AMOUNT_USD              DECIMAL(18,4),          -- normalised to USD
    ORIGINAL_AMOUNT         DECIMAL(18,4),
    ORIGINAL_CURRENCY       CHAR(3),
    DIRECTION               CHAR(2),
    MERCHANT_NAME           VARCHAR(200),
    MERCHANT_MCC            CHAR(4),
    CHANNEL                 VARCHAR(20),
    IP_ADDRESS              VARCHAR(45),
    DEVICE_ID               VARCHAR(100),
    COUNTRY_CODE            CHAR(2),
    IS_CROSS_BORDER         BOOLEAN,
    STATUS                  VARCHAR(20),
    INITIATED_AT            TIMESTAMP,
    HOUR_OF_DAY             TINYINT,                -- 0-23 for time-of-day features
    DAY_OF_WEEK             TINYINT,                -- 0=Mon, 6=Sun
    IS_WEEKEND              BOOLEAN,
    IS_NIGHT                BOOLEAN,                -- 22:00-06:00
    LOADED_AT               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FACT_TXN_PK PRIMARY KEY (TXN_ID)
);

CREATE OR REPLACE TABLE CLEANSED.DIM_ACCOUNTS (
    ACCOUNT_ID      VARCHAR(36)     NOT NULL,
    CUSTOMER_ID     VARCHAR(36),
    ACCOUNT_TYPE    VARCHAR(20),
    CURRENCY        CHAR(3),
    STATUS          VARCHAR(20),
    DAYS_OPEN       INTEGER,                -- derived: days since opened_at
    LOADED_AT       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT DIM_ACC_PK PRIMARY KEY (ACCOUNT_ID)
);

CREATE OR REPLACE TABLE CLEANSED.DIM_CUSTOMERS (
    CUSTOMER_ID     VARCHAR(36)     NOT NULL,
    COUNTRY_CODE    CHAR(2),
    KYC_STATUS      VARCHAR(20),
    RISK_BAND       VARCHAR(10),
    AGE_YEARS       INTEGER,
    LOADED_AT       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT DIM_CUST_PK PRIMARY KEY (CUSTOMER_ID)
);

-- ─────────────────────────────────────────────
-- LAYER 3: ANALYTICS  (ML-ready feature tables)
-- ─────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS ANALYTICS;

-- Pre-computed feature table (refreshed on each new transaction)
CREATE OR REPLACE TABLE ANALYTICS.FRAUD_FEATURES (
    TXN_ID                      VARCHAR(36)     NOT NULL,
    ACCOUNT_ID                  VARCHAR(36),
    CUSTOMER_ID                 VARCHAR(36),
    AMOUNT_USD                  DECIMAL(18,4),
    TXN_TYPE                    VARCHAR(30),
    CHANNEL                     VARCHAR(20),
    MERCHANT_MCC                CHAR(4),
    -- Velocity (rolling window counts/sums)
    TXN_COUNT_1H                INTEGER,
    TXN_COUNT_6H                INTEGER,
    TXN_COUNT_24H               INTEGER,
    AMOUNT_SUM_1H               DECIMAL(18,4),
    AMOUNT_SUM_6H               DECIMAL(18,4),
    AMOUNT_SUM_24H              DECIMAL(18,4),
    -- Deviation from account history
    ACCOUNT_AVG_AMOUNT_30D      DECIMAL(18,4),
    AMOUNT_VS_AVG_RATIO         DECIMAL(10,4),  -- this_txn / 30d_avg
    -- Geo/device flags
    IS_CROSS_BORDER             BOOLEAN,
    IS_NEW_COUNTRY_30D          BOOLEAN,        -- first txn from this country in 30d
    IS_NEW_DEVICE_30D           BOOLEAN,
    IS_NIGHT_TXN                BOOLEAN,
    IS_WEEKEND_TXN              BOOLEAN,
    -- MCC risk
    MCC_BASE_RISK               DECIMAL(4,3),
    -- Customer risk context
    KYC_STATUS                  VARCHAR(20),
    RISK_BAND                   VARCHAR(10),
    -- Model output (simplified demo populates FRAUD_SCORE + MODEL_VERSION)
    FRAUD_SCORE                 DECIMAL(6,5),   -- 0.00000 – 1.00000
    RISK_SCORE                  DECIMAL(6,5),   -- reserved for future extension
    MODEL_VERSION               VARCHAR(20),
    FRAUD_LABEL                 BOOLEAN,        -- ground truth (post-investigation)
    FEATURE_COMPUTED_AT         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT FRAUD_FEAT_PK PRIMARY KEY (TXN_ID)
);

-- ─────────────────────────────────────────────
-- ANALYTICS: SCORING RESULTS  (audit trail)
-- ─────────────────────────────────────────────
CREATE OR REPLACE TABLE ANALYTICS.SCORING_RESULTS (
    SCORE_ID            DECIMAL(18,0)   IDENTITY PRIMARY KEY,
    TXN_ID              VARCHAR(36)     NOT NULL,
    MODEL_NAME          VARCHAR(100),
    MODEL_VERSION       VARCHAR(20),
    FRAUD_SCORE         DECIMAL(6,5),
    RISK_SCORE          DECIMAL(6,5),   -- reserved for future extension
    THRESHOLD_USED      DECIMAL(4,3),
    TRIGGERED_ALERT     BOOLEAN,
    SCORED_AT           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- MCC RISK REFERENCE  (for feature joins)
-- ─────────────────────────────────────────────
CREATE OR REPLACE TABLE ANALYTICS.MCC_RISK (
    MCC             CHAR(4)         NOT NULL,
    DESCRIPTION     VARCHAR(200),
    CATEGORY        VARCHAR(100),
    BASE_RISK_SCORE DECIMAL(4,3),
    CONSTRAINT MCC_RISK_PK PRIMARY KEY (MCC)
);

INSERT INTO ANALYTICS.MCC_RISK VALUES
('5411','Grocery Stores',            'Retail',        0.050),
('5812','Restaurants',               'Food & Dining', 0.050),
('5541','Service Stations',          'Auto',          0.080),
('6011','ATM',                       'Cash Access',   0.120),
('7995','Gambling/Betting',          'High Risk',     0.750),
('6051','Non-Financial FX',          'Finance',       0.650),
('4829','Wire Transfers',            'Finance',       0.600),
('5933','Pawn Shops',                'High Risk',     0.700),
('4511','Airlines',                  'Travel',        0.150),
('7011','Hotels',                    'Travel',        0.150),
('5999','Misc Retail',               'Retail',        0.200),
('5816','Digital Goods',             'Digital',       0.300);

COMMIT;

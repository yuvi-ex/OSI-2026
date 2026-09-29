-- ============================================================
--  EXASOL: REFRESH ML TRAINING FEATURES
--  Run after 06_exasol_kafka_connector_merge.sql
--  Purpose:
--    1. Build CLEANSED dimensions/facts from RAW
--    2. Populate ANALYTICS.FRAUD_FEATURES
--    3. Backfill FRAUD_LABEL from RAW.FRAUD_ALERTS
-- ============================================================

-- ─────────────────────────────────────────────
-- STEP 1a: Load customer dimension
-- ─────────────────────────────────────────────
MERGE INTO CLEANSED.DIM_CUSTOMERS t
USING (
    SELECT
        CUSTOMER_ID,
        COUNTRY_CODE,
        KYC_STATUS,
        RISK_BAND,
        CAST(FLOOR(DAYS_BETWEEN(DATE_OF_BIRTH, CURRENT_DATE) / 365.25) AS INTEGER) AS AGE_YEARS
    FROM RAW.CUSTOMERS
) src
ON t.CUSTOMER_ID = src.CUSTOMER_ID
WHEN MATCHED THEN UPDATE SET
    COUNTRY_CODE = src.COUNTRY_CODE,
    KYC_STATUS = src.KYC_STATUS,
    RISK_BAND = src.RISK_BAND,
    AGE_YEARS = src.AGE_YEARS,
    LOADED_AT = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN INSERT VALUES (
    src.CUSTOMER_ID, src.COUNTRY_CODE, src.KYC_STATUS, src.RISK_BAND,
    src.AGE_YEARS, CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- STEP 1b: Load account dimension
-- ─────────────────────────────────────────────
MERGE INTO CLEANSED.DIM_ACCOUNTS t
USING (
    SELECT
        ACCOUNT_ID,
        CUSTOMER_ID,
        ACCOUNT_TYPE,
        CURRENCY,
        STATUS,
        DAYS_BETWEEN(CAST(OPENED_AT AS DATE), CURRENT_DATE) AS DAYS_OPEN
    FROM RAW.ACCOUNTS
) src
ON t.ACCOUNT_ID = src.ACCOUNT_ID
WHEN MATCHED THEN UPDATE SET
    CUSTOMER_ID = src.CUSTOMER_ID,
    ACCOUNT_TYPE = src.ACCOUNT_TYPE,
    CURRENCY = src.CURRENCY,
    STATUS = src.STATUS,
    DAYS_OPEN = src.DAYS_OPEN,
    LOADED_AT = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN INSERT VALUES (
    src.ACCOUNT_ID, src.CUSTOMER_ID, src.ACCOUNT_TYPE, src.CURRENCY,
    src.STATUS, src.DAYS_OPEN, CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- STEP 1c: Load transaction fact table
-- ─────────────────────────────────────────────
MERGE INTO CLEANSED.FACT_TRANSACTIONS t
USING (
    SELECT
        r.TXN_ID,
        r.ACCOUNT_ID,
        r.CARD_ID,
        r.TXN_TYPE,
        r.AMOUNT                                             AS AMOUNT_USD,
        r.AMOUNT                                             AS ORIGINAL_AMOUNT,
        r.CURRENCY                                           AS ORIGINAL_CURRENCY,
        r.DIRECTION,
        r.MERCHANT_NAME,
        r.MERCHANT_MCC,
        r.CHANNEL,
        r.IP_ADDRESS,
        r.DEVICE_ID,
        r.COUNTRY_CODE,
        CASE WHEN r.COUNTRY_CODE != c.COUNTRY_CODE THEN TRUE ELSE FALSE END AS IS_CROSS_BORDER,
        r.STATUS,
        r.INITIATED_AT,
        EXTRACT(HOUR FROM r.INITIATED_AT)                   AS HOUR_OF_DAY,
        MOD(DAYS_BETWEEN(DATE '2000-01-03', CAST(r.INITIATED_AT AS DATE)), 7) AS DAY_OF_WEEK,
        CASE WHEN MOD(DAYS_BETWEEN(DATE '2000-01-03', CAST(r.INITIATED_AT AS DATE)), 7) >= 5
             THEN TRUE ELSE FALSE END                       AS IS_WEEKEND,
        CASE WHEN EXTRACT(HOUR FROM r.INITIATED_AT) >= 22
              OR EXTRACT(HOUR FROM r.INITIATED_AT) < 6
             THEN TRUE ELSE FALSE END                       AS IS_NIGHT
    FROM RAW.TRANSACTIONS r
    LEFT JOIN RAW.ACCOUNTS a ON r.ACCOUNT_ID = a.ACCOUNT_ID
    LEFT JOIN RAW.CUSTOMERS c ON a.CUSTOMER_ID = c.CUSTOMER_ID
    WHERE COALESCE(r.DEBEZIUM_OP, 'c') != 'd'
) src
ON t.TXN_ID = src.TXN_ID
WHEN MATCHED THEN UPDATE SET
    ACCOUNT_ID = src.ACCOUNT_ID,
    CARD_ID = src.CARD_ID,
    TXN_TYPE = src.TXN_TYPE,
    AMOUNT_USD = src.AMOUNT_USD,
    ORIGINAL_AMOUNT = src.ORIGINAL_AMOUNT,
    ORIGINAL_CURRENCY = src.ORIGINAL_CURRENCY,
    DIRECTION = src.DIRECTION,
    MERCHANT_NAME = src.MERCHANT_NAME,
    MERCHANT_MCC = src.MERCHANT_MCC,
    CHANNEL = src.CHANNEL,
    IP_ADDRESS = src.IP_ADDRESS,
    DEVICE_ID = src.DEVICE_ID,
    COUNTRY_CODE = src.COUNTRY_CODE,
    IS_CROSS_BORDER = src.IS_CROSS_BORDER,
    STATUS = src.STATUS,
    INITIATED_AT = src.INITIATED_AT,
    HOUR_OF_DAY = src.HOUR_OF_DAY,
    DAY_OF_WEEK = src.DAY_OF_WEEK,
    IS_WEEKEND = src.IS_WEEKEND,
    IS_NIGHT = src.IS_NIGHT,
    LOADED_AT = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN INSERT VALUES (
    src.TXN_ID, src.ACCOUNT_ID, src.CARD_ID, src.TXN_TYPE,
    src.AMOUNT_USD, src.ORIGINAL_AMOUNT, src.ORIGINAL_CURRENCY,
    src.DIRECTION, src.MERCHANT_NAME, src.MERCHANT_MCC, src.CHANNEL,
    src.IP_ADDRESS, src.DEVICE_ID, src.COUNTRY_CODE, src.IS_CROSS_BORDER,
    src.STATUS, src.INITIATED_AT, src.HOUR_OF_DAY, src.DAY_OF_WEEK,
    src.IS_WEEKEND, src.IS_NIGHT, CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────────
-- STEP 2a: Compute fraud features
-- ─────────────────────────────────────────────
MERGE INTO ANALYTICS.FRAUD_FEATURES f
USING (
    WITH base AS (
        SELECT
            t.TXN_ID,
            t.ACCOUNT_ID,
            a.CUSTOMER_ID,
            t.AMOUNT_USD,
            t.TXN_TYPE,
            t.CHANNEL,
            t.MERCHANT_MCC,
            t.IS_CROSS_BORDER,
            t.IS_NIGHT        AS IS_NIGHT,
            t.IS_WEEKEND      AS IS_WEEKEND,
            t.INITIATED_AT,
            t.DEVICE_ID,
            t.COUNTRY_CODE,
            c.KYC_STATUS,
            c.RISK_BAND
        FROM CLEANSED.FACT_TRANSACTIONS t
        JOIN CLEANSED.DIM_ACCOUNTS a ON t.ACCOUNT_ID = a.ACCOUNT_ID
        JOIN CLEANSED.DIM_CUSTOMERS c ON a.CUSTOMER_ID = c.CUSTOMER_ID
    ),
    velocity AS (
        SELECT
            b.TXN_ID,
            COUNT(CASE WHEN h.INITIATED_AT >= b.INITIATED_AT - INTERVAL '1' HOUR
                            AND h.INITIATED_AT <  b.INITIATED_AT
                            AND h.TXN_ID != b.TXN_ID THEN 1 END) AS TXN_COUNT_1H,
            COUNT(CASE WHEN h.INITIATED_AT >= b.INITIATED_AT - INTERVAL '6' HOUR
                            AND h.INITIATED_AT <  b.INITIATED_AT
                            AND h.TXN_ID != b.TXN_ID THEN 1 END) AS TXN_COUNT_6H,
            COUNT(CASE WHEN h.INITIATED_AT >= b.INITIATED_AT - INTERVAL '24' HOUR
                            AND h.INITIATED_AT <  b.INITIATED_AT
                            AND h.TXN_ID != b.TXN_ID THEN 1 END) AS TXN_COUNT_24H,
            SUM(CASE WHEN h.INITIATED_AT >= b.INITIATED_AT - INTERVAL '1' HOUR
                          AND h.INITIATED_AT <  b.INITIATED_AT
                          AND h.TXN_ID != b.TXN_ID THEN h.AMOUNT_USD ELSE 0 END) AS AMOUNT_SUM_1H,
            SUM(CASE WHEN h.INITIATED_AT >= b.INITIATED_AT - INTERVAL '6' HOUR
                          AND h.INITIATED_AT <  b.INITIATED_AT
                          AND h.TXN_ID != b.TXN_ID THEN h.AMOUNT_USD ELSE 0 END) AS AMOUNT_SUM_6H,
            SUM(CASE WHEN h.INITIATED_AT >= b.INITIATED_AT - INTERVAL '24' HOUR
                          AND h.INITIATED_AT <  b.INITIATED_AT
                          AND h.TXN_ID != b.TXN_ID THEN h.AMOUNT_USD ELSE 0 END) AS AMOUNT_SUM_24H
        FROM base b
        JOIN CLEANSED.FACT_TRANSACTIONS h ON b.ACCOUNT_ID = h.ACCOUNT_ID
        GROUP BY b.TXN_ID
    ),
    history AS (
        SELECT
            b.TXN_ID,
            AVG(h.AMOUNT_USD) AS ACCOUNT_AVG_AMOUNT_30D
        FROM base b
        JOIN CLEANSED.FACT_TRANSACTIONS h
            ON  b.ACCOUNT_ID   = h.ACCOUNT_ID
            AND h.INITIATED_AT >= b.INITIATED_AT - INTERVAL '30' DAY
            AND h.INITIATED_AT <  b.INITIATED_AT
            AND h.TXN_ID       != b.TXN_ID
        GROUP BY b.TXN_ID
    ),
    geo_device AS (
        SELECT
            b.TXN_ID,
            CASE WHEN COUNT(DISTINCT CASE WHEN h.INITIATED_AT >= b.INITIATED_AT - INTERVAL '30' DAY
                                           AND h.INITIATED_AT <  b.INITIATED_AT
                                           AND h.COUNTRY_CODE = b.COUNTRY_CODE THEN 1 END) = 0
                 THEN TRUE ELSE FALSE END AS IS_NEW_COUNTRY_30D,
            CASE WHEN COUNT(DISTINCT CASE WHEN h.INITIATED_AT >= b.INITIATED_AT - INTERVAL '30' DAY
                                           AND h.INITIATED_AT <  b.INITIATED_AT
                                           AND h.DEVICE_ID = b.DEVICE_ID THEN 1 END) = 0
                 THEN TRUE ELSE FALSE END AS IS_NEW_DEVICE_30D
        FROM base b
        LEFT JOIN CLEANSED.FACT_TRANSACTIONS h ON b.ACCOUNT_ID = h.ACCOUNT_ID AND h.TXN_ID != b.TXN_ID
        GROUP BY b.TXN_ID
    )
    SELECT
        b.TXN_ID,
        b.ACCOUNT_ID,
        b.CUSTOMER_ID,
        b.AMOUNT_USD,
        b.TXN_TYPE,
        b.CHANNEL,
        b.MERCHANT_MCC,
        v.TXN_COUNT_1H,
        v.TXN_COUNT_6H,
        v.TXN_COUNT_24H,
        v.AMOUNT_SUM_1H,
        v.AMOUNT_SUM_6H,
        v.AMOUNT_SUM_24H,
        COALESCE(h.ACCOUNT_AVG_AMOUNT_30D, b.AMOUNT_USD)     AS ACCOUNT_AVG_AMOUNT_30D,
        CASE WHEN COALESCE(h.ACCOUNT_AVG_AMOUNT_30D, 0) > 0
             THEN b.AMOUNT_USD / h.ACCOUNT_AVG_AMOUNT_30D
             ELSE 1.0 END                                     AS AMOUNT_VS_AVG_RATIO,
        b.IS_CROSS_BORDER,
        COALESCE(gd.IS_NEW_COUNTRY_30D, TRUE)                 AS IS_NEW_COUNTRY_30D,
        COALESCE(gd.IS_NEW_DEVICE_30D, TRUE)                  AS IS_NEW_DEVICE_30D,
        b.IS_NIGHT                                            AS IS_NIGHT_TXN,
        b.IS_WEEKEND                                          AS IS_WEEKEND_TXN,
        COALESCE(m.BASE_RISK_SCORE, 0.2)                      AS MCC_BASE_RISK,
        b.KYC_STATUS,
        b.RISK_BAND
    FROM base b
    LEFT JOIN velocity     v  ON b.TXN_ID = v.TXN_ID
    LEFT JOIN history      h  ON b.TXN_ID = h.TXN_ID
    LEFT JOIN geo_device   gd ON b.TXN_ID = gd.TXN_ID
    LEFT JOIN ANALYTICS.MCC_RISK m ON b.MERCHANT_MCC = m.MCC
) src
ON f.TXN_ID = src.TXN_ID
WHEN MATCHED THEN UPDATE SET
    ACCOUNT_ID = src.ACCOUNT_ID,
    CUSTOMER_ID = src.CUSTOMER_ID,
    AMOUNT_USD = src.AMOUNT_USD,
    TXN_TYPE = src.TXN_TYPE,
    CHANNEL = src.CHANNEL,
    MERCHANT_MCC = src.MERCHANT_MCC,
    TXN_COUNT_1H = src.TXN_COUNT_1H,
    TXN_COUNT_6H = src.TXN_COUNT_6H,
    TXN_COUNT_24H = src.TXN_COUNT_24H,
    AMOUNT_SUM_1H = src.AMOUNT_SUM_1H,
    AMOUNT_SUM_6H = src.AMOUNT_SUM_6H,
    AMOUNT_SUM_24H = src.AMOUNT_SUM_24H,
    ACCOUNT_AVG_AMOUNT_30D = src.ACCOUNT_AVG_AMOUNT_30D,
    AMOUNT_VS_AVG_RATIO = src.AMOUNT_VS_AVG_RATIO,
    IS_CROSS_BORDER = src.IS_CROSS_BORDER,
    IS_NEW_COUNTRY_30D = src.IS_NEW_COUNTRY_30D,
    IS_NEW_DEVICE_30D = src.IS_NEW_DEVICE_30D,
    IS_NIGHT_TXN = src.IS_NIGHT_TXN,
    IS_WEEKEND_TXN = src.IS_WEEKEND_TXN,
    MCC_BASE_RISK = src.MCC_BASE_RISK,
    KYC_STATUS = src.KYC_STATUS,
    RISK_BAND = src.RISK_BAND,
    FEATURE_COMPUTED_AT = CURRENT_TIMESTAMP
WHEN NOT MATCHED THEN INSERT (
    TXN_ID, ACCOUNT_ID, CUSTOMER_ID, AMOUNT_USD, TXN_TYPE, CHANNEL,
    MERCHANT_MCC, TXN_COUNT_1H, TXN_COUNT_6H, TXN_COUNT_24H,
    AMOUNT_SUM_1H, AMOUNT_SUM_6H, AMOUNT_SUM_24H,
    ACCOUNT_AVG_AMOUNT_30D, AMOUNT_VS_AVG_RATIO,
    IS_CROSS_BORDER, IS_NEW_COUNTRY_30D, IS_NEW_DEVICE_30D,
    IS_NIGHT_TXN, IS_WEEKEND_TXN, MCC_BASE_RISK, KYC_STATUS, RISK_BAND
) VALUES (
    src.TXN_ID, src.ACCOUNT_ID, src.CUSTOMER_ID, src.AMOUNT_USD, src.TXN_TYPE, src.CHANNEL,
    src.MERCHANT_MCC, src.TXN_COUNT_1H, src.TXN_COUNT_6H, src.TXN_COUNT_24H,
    src.AMOUNT_SUM_1H, src.AMOUNT_SUM_6H, src.AMOUNT_SUM_24H,
    src.ACCOUNT_AVG_AMOUNT_30D, src.AMOUNT_VS_AVG_RATIO,
    src.IS_CROSS_BORDER, src.IS_NEW_COUNTRY_30D, src.IS_NEW_DEVICE_30D,
    src.IS_NIGHT_TXN, src.IS_WEEKEND_TXN, src.MCC_BASE_RISK, src.KYC_STATUS, src.RISK_BAND
);

COMMIT;

-- ─────────────────────────────────────────────
-- STEP 2b: Backfill ground-truth labels from fraud alerts
-- ─────────────────────────────────────────────
MERGE INTO ANALYTICS.FRAUD_FEATURES f
USING (
    SELECT
        TXN_ID,
        CASE
            WHEN MAX(CASE WHEN STATUS = 'CONFIRMED_FRAUD' THEN 1 ELSE 0 END) = 1 THEN TRUE
            WHEN MAX(CASE WHEN STATUS = 'FALSE_POSITIVE' THEN 1 ELSE 0 END) = 1 THEN FALSE
            ELSE NULL
        END AS FRAUD_LABEL
    FROM RAW.FRAUD_ALERTS
    GROUP BY TXN_ID
) src
ON f.TXN_ID = src.TXN_ID
WHEN MATCHED THEN UPDATE SET
    FRAUD_LABEL = src.FRAUD_LABEL;

COMMIT;

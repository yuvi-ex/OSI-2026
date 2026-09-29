-- ============================================================
--  OPTIONAL: MERGE KAFKA_STAGE INTO RAW
--  The official Exasol Kafka connector imports append-only rows.
--  This script keeps the latest row per business key and applies
--  deletes by removing the current RAW record when the latest
--  Debezium event is a delete.
-- ============================================================

MERGE INTO RAW.ACCOUNTS t
USING (
    SELECT ACCOUNT_ID, CUSTOMER_ID, ACCOUNT_NUMBER, ACCOUNT_TYPE, CURRENCY, BALANCE,
           CREDIT_LIMIT, STATUS,
           CAST(REPLACE(REPLACE(OPENED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP) AS OPENED_AT,
           CAST(REPLACE(REPLACE(UPDATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP) AS UPDATED_AT,
           KAFKA_RECORD_TS
    FROM (
        SELECT s.*,
               ROW_NUMBER() OVER (
                   PARTITION BY ACCOUNT_ID
                   ORDER BY COALESCE(
                                KAFKA_RECORD_TS,
                                CAST(REPLACE(REPLACE(UPDATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP),
                                CAST(REPLACE(REPLACE(OPENED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP)
                            ) DESC,
                            KAFKA_PARTITION DESC,
                            KAFKA_OFFSET DESC
               ) AS RN
        FROM KAFKA_STAGE.ACCOUNTS s
    )
    WHERE RN = 1
      AND COALESCE(DELETED_FLAG, 'false') != 'true'
      AND COALESCE(DEBEZIUM_OP, 'c') != 'd'
) s
ON t.ACCOUNT_ID = s.ACCOUNT_ID
WHEN MATCHED THEN UPDATE SET
    t.CUSTOMER_ID = s.CUSTOMER_ID,
    t.ACCOUNT_NUMBER = s.ACCOUNT_NUMBER,
    t.ACCOUNT_TYPE = s.ACCOUNT_TYPE,
    t.CURRENCY = s.CURRENCY,
    t.BALANCE = s.BALANCE,
    t.CREDIT_LIMIT = s.CREDIT_LIMIT,
    t.STATUS = s.STATUS,
    t.OPENED_AT = s.OPENED_AT,
    t.UPDATED_AT = s.UPDATED_AT,
    t.KAFKA_INGESTED_AT = s.KAFKA_RECORD_TS
WHEN NOT MATCHED THEN INSERT (
    ACCOUNT_ID, CUSTOMER_ID, ACCOUNT_NUMBER, ACCOUNT_TYPE, CURRENCY, BALANCE,
    CREDIT_LIMIT, STATUS, OPENED_AT, UPDATED_AT, KAFKA_INGESTED_AT
) VALUES (
    s.ACCOUNT_ID, s.CUSTOMER_ID, s.ACCOUNT_NUMBER, s.ACCOUNT_TYPE, s.CURRENCY, s.BALANCE,
    s.CREDIT_LIMIT, s.STATUS, s.OPENED_AT, s.UPDATED_AT, s.KAFKA_RECORD_TS
);

DELETE FROM RAW.ACCOUNTS t
WHERE EXISTS (
    SELECT 1
    FROM (
        SELECT ACCOUNT_ID, DELETED_FLAG, DEBEZIUM_OP,
               ROW_NUMBER() OVER (
                   PARTITION BY ACCOUNT_ID
                   ORDER BY COALESCE(
                                KAFKA_RECORD_TS,
                                CAST(REPLACE(REPLACE(UPDATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP),
                                CAST(REPLACE(REPLACE(OPENED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP)
                            ) DESC,
                            KAFKA_PARTITION DESC,
                            KAFKA_OFFSET DESC
               ) AS RN
        FROM KAFKA_STAGE.ACCOUNTS
    ) s
    WHERE s.RN = 1
      AND t.ACCOUNT_ID = s.ACCOUNT_ID
      AND (COALESCE(s.DELETED_FLAG, 'false') = 'true' OR COALESCE(s.DEBEZIUM_OP, 'c') = 'd')
);

MERGE INTO RAW.CUSTOMERS t
USING (
    SELECT CUSTOMER_ID, FULL_NAME, EMAIL, PHONE,
           CAST(DATE_OF_BIRTH AS DATE) AS DATE_OF_BIRTH,
           COUNTRY_CODE, KYC_STATUS, RISK_BAND,
           CAST(REPLACE(REPLACE(CREATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP) AS CREATED_AT,
           CAST(REPLACE(REPLACE(UPDATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP) AS UPDATED_AT,
           KAFKA_RECORD_TS
    FROM (
        SELECT s.*,
               ROW_NUMBER() OVER (
                   PARTITION BY CUSTOMER_ID
                   ORDER BY COALESCE(
                                KAFKA_RECORD_TS,
                                CAST(REPLACE(REPLACE(UPDATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP),
                                CAST(REPLACE(REPLACE(CREATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP)
                            ) DESC,
                            KAFKA_PARTITION DESC,
                            KAFKA_OFFSET DESC
               ) AS RN
        FROM KAFKA_STAGE.CUSTOMERS s
    )
    WHERE RN = 1
      AND COALESCE(DELETED_FLAG, 'false') != 'true'
      AND COALESCE(DEBEZIUM_OP, 'c') != 'd'
) s
ON t.CUSTOMER_ID = s.CUSTOMER_ID
WHEN MATCHED THEN UPDATE SET
    t.FULL_NAME = s.FULL_NAME,
    t.EMAIL = s.EMAIL,
    t.PHONE = s.PHONE,
    t.DATE_OF_BIRTH = s.DATE_OF_BIRTH,
    t.COUNTRY_CODE = s.COUNTRY_CODE,
    t.KYC_STATUS = s.KYC_STATUS,
    t.RISK_BAND = s.RISK_BAND,
    t.CREATED_AT = s.CREATED_AT,
    t.UPDATED_AT = s.UPDATED_AT,
    t.KAFKA_INGESTED_AT = s.KAFKA_RECORD_TS
WHEN NOT MATCHED THEN INSERT (
    CUSTOMER_ID, FULL_NAME, EMAIL, PHONE, DATE_OF_BIRTH, COUNTRY_CODE,
    KYC_STATUS, RISK_BAND, CREATED_AT, UPDATED_AT, KAFKA_INGESTED_AT
) VALUES (
    s.CUSTOMER_ID, s.FULL_NAME, s.EMAIL, s.PHONE, s.DATE_OF_BIRTH, s.COUNTRY_CODE,
    s.KYC_STATUS, s.RISK_BAND, s.CREATED_AT, s.UPDATED_AT, s.KAFKA_RECORD_TS
);

DELETE FROM RAW.CUSTOMERS t
WHERE EXISTS (
    SELECT 1
    FROM (
        SELECT CUSTOMER_ID, DELETED_FLAG, DEBEZIUM_OP,
               ROW_NUMBER() OVER (
                   PARTITION BY CUSTOMER_ID
                   ORDER BY COALESCE(
                                KAFKA_RECORD_TS,
                                CAST(REPLACE(REPLACE(UPDATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP),
                                CAST(REPLACE(REPLACE(CREATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP)
                            ) DESC,
                            KAFKA_PARTITION DESC,
                            KAFKA_OFFSET DESC
               ) AS RN
        FROM KAFKA_STAGE.CUSTOMERS
    ) s
    WHERE s.RN = 1
      AND t.CUSTOMER_ID = s.CUSTOMER_ID
      AND (COALESCE(s.DELETED_FLAG, 'false') = 'true' OR COALESCE(s.DEBEZIUM_OP, 'c') = 'd')
);

MERGE INTO RAW.CARDS t
USING (
    SELECT CARD_ID, ACCOUNT_ID, CARD_TYPE, MASKED_PAN, LAST_FOUR,
           CAST(EXPIRY_DATE AS DATE) AS EXPIRY_DATE,
           NETWORK, STATUS,
           CAST(REPLACE(REPLACE(ISSUED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP) AS ISSUED_AT,
           CAST(REPLACE(REPLACE(UPDATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP) AS UPDATED_AT,
           KAFKA_RECORD_TS
    FROM (
        SELECT s.*,
               ROW_NUMBER() OVER (
                   PARTITION BY CARD_ID
                   ORDER BY COALESCE(
                                KAFKA_RECORD_TS,
                                CAST(REPLACE(REPLACE(UPDATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP),
                                CAST(REPLACE(REPLACE(ISSUED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP)
                            ) DESC,
                            KAFKA_PARTITION DESC,
                            KAFKA_OFFSET DESC
               ) AS RN
        FROM KAFKA_STAGE.CARDS s
    )
    WHERE RN = 1
      AND COALESCE(DELETED_FLAG, 'false') != 'true'
      AND COALESCE(DEBEZIUM_OP, 'c') != 'd'
) s
ON t.CARD_ID = s.CARD_ID
WHEN MATCHED THEN UPDATE SET
    t.ACCOUNT_ID = s.ACCOUNT_ID,
    t.CARD_TYPE = s.CARD_TYPE,
    t.MASKED_PAN = s.MASKED_PAN,
    t.LAST_FOUR = s.LAST_FOUR,
    t.EXPIRY_DATE = s.EXPIRY_DATE,
    t.NETWORK = s.NETWORK,
    t.STATUS = s.STATUS,
    t.ISSUED_AT = s.ISSUED_AT,
    t.UPDATED_AT = s.UPDATED_AT,
    t.KAFKA_INGESTED_AT = s.KAFKA_RECORD_TS
WHEN NOT MATCHED THEN INSERT (
    CARD_ID, ACCOUNT_ID, CARD_TYPE, MASKED_PAN, LAST_FOUR, EXPIRY_DATE,
    NETWORK, STATUS, ISSUED_AT, UPDATED_AT, KAFKA_INGESTED_AT
) VALUES (
    s.CARD_ID, s.ACCOUNT_ID, s.CARD_TYPE, s.MASKED_PAN, s.LAST_FOUR, s.EXPIRY_DATE,
    s.NETWORK, s.STATUS, s.ISSUED_AT, s.UPDATED_AT, s.KAFKA_RECORD_TS
);

DELETE FROM RAW.CARDS t
WHERE EXISTS (
    SELECT 1
    FROM (
        SELECT CARD_ID, DELETED_FLAG, DEBEZIUM_OP,
               ROW_NUMBER() OVER (
                   PARTITION BY CARD_ID
                   ORDER BY COALESCE(
                                KAFKA_RECORD_TS,
                                CAST(REPLACE(REPLACE(UPDATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP),
                                CAST(REPLACE(REPLACE(ISSUED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP)
                            ) DESC,
                            KAFKA_PARTITION DESC,
                            KAFKA_OFFSET DESC
               ) AS RN
        FROM KAFKA_STAGE.CARDS
    ) s
    WHERE s.RN = 1
      AND t.CARD_ID = s.CARD_ID
      AND (COALESCE(s.DELETED_FLAG, 'false') = 'true' OR COALESCE(s.DEBEZIUM_OP, 'c') = 'd')
);

MERGE INTO RAW.FRAUD_ALERTS t
USING (
    SELECT ALERT_ID, TXN_ID, ALERT_TYPE, FRAUD_SCORE, RISK_SCORE, STATUS,
           INVESTIGATOR, NOTES,
           CAST(REPLACE(REPLACE(CREATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP) AS CREATED_AT,
           CAST(REPLACE(REPLACE(RESOLVED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP) AS RESOLVED_AT,
           KAFKA_RECORD_TS
    FROM (
        SELECT s.*,
               ROW_NUMBER() OVER (
                   PARTITION BY ALERT_ID
                   ORDER BY COALESCE(
                                KAFKA_RECORD_TS,
                                CAST(REPLACE(REPLACE(RESOLVED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP),
                                CAST(REPLACE(REPLACE(CREATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP)
                            ) DESC,
                            KAFKA_PARTITION DESC,
                            KAFKA_OFFSET DESC
               ) AS RN
        FROM KAFKA_STAGE.FRAUD_ALERTS s
    )
    WHERE RN = 1
      AND COALESCE(DELETED_FLAG, 'false') != 'true'
      AND COALESCE(DEBEZIUM_OP, 'c') != 'd'
) s
ON t.ALERT_ID = s.ALERT_ID
WHEN MATCHED THEN UPDATE SET
    t.TXN_ID = s.TXN_ID,
    t.ALERT_TYPE = s.ALERT_TYPE,
    t.FRAUD_SCORE = s.FRAUD_SCORE,
    t.RISK_SCORE = s.RISK_SCORE,
    t.STATUS = s.STATUS,
    t.INVESTIGATOR = s.INVESTIGATOR,
    t.NOTES = s.NOTES,
    t.CREATED_AT = s.CREATED_AT,
    t.RESOLVED_AT = s.RESOLVED_AT,
    t.KAFKA_INGESTED_AT = s.KAFKA_RECORD_TS
WHEN NOT MATCHED THEN INSERT (
    ALERT_ID, TXN_ID, ALERT_TYPE, FRAUD_SCORE, RISK_SCORE, STATUS,
    INVESTIGATOR, NOTES, CREATED_AT, RESOLVED_AT, KAFKA_INGESTED_AT
) VALUES (
    s.ALERT_ID, s.TXN_ID, s.ALERT_TYPE, s.FRAUD_SCORE, s.RISK_SCORE, s.STATUS,
    s.INVESTIGATOR, s.NOTES, s.CREATED_AT, s.RESOLVED_AT, s.KAFKA_RECORD_TS
);

DELETE FROM RAW.FRAUD_ALERTS t
WHERE EXISTS (
    SELECT 1
    FROM (
        SELECT ALERT_ID, DELETED_FLAG, DEBEZIUM_OP,
               ROW_NUMBER() OVER (
                   PARTITION BY ALERT_ID
                   ORDER BY COALESCE(
                                KAFKA_RECORD_TS,
                                CAST(REPLACE(REPLACE(RESOLVED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP),
                                CAST(REPLACE(REPLACE(CREATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP)
                            ) DESC,
                            KAFKA_PARTITION DESC,
                            KAFKA_OFFSET DESC
               ) AS RN
        FROM KAFKA_STAGE.FRAUD_ALERTS
    ) s
    WHERE s.RN = 1
      AND t.ALERT_ID = s.ALERT_ID
      AND (COALESCE(s.DELETED_FLAG, 'false') = 'true' OR COALESCE(s.DEBEZIUM_OP, 'c') = 'd')
);

MERGE INTO RAW.TRANSACTIONS t
USING (
    SELECT TXN_ID, ACCOUNT_ID, CARD_ID, TXN_TYPE, AMOUNT, CURRENCY, DIRECTION,
           MERCHANT_NAME, MERCHANT_MCC, MERCHANT_ID, CHANNEL, IP_ADDRESS,
           DEVICE_ID, DEVICE_FINGERPRINT, COUNTRY_CODE, CITY, LATITUDE,
           LONGITUDE, COUNTERPARTY_ACCOUNT, COUNTERPARTY_BANK, STATUS,
           DECLINE_REASON, REFERENCE_ID,
           CAST(REPLACE(REPLACE(INITIATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP) AS INITIATED_AT,
           CAST(REPLACE(REPLACE(SETTLED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP) AS SETTLED_AT,
           DEBEZIUM_OP, KAFKA_RECORD_TS, KAFKA_PARTITION, KAFKA_OFFSET
    FROM (
        SELECT s.*,
               ROW_NUMBER() OVER (
                   PARTITION BY TXN_ID
                   ORDER BY COALESCE(
                                KAFKA_RECORD_TS,
                                CAST(REPLACE(REPLACE(UPDATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP),
                                CAST(REPLACE(REPLACE(SETTLED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP),
                                CAST(REPLACE(REPLACE(INITIATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP)
                            ) DESC,
                            KAFKA_PARTITION DESC,
                            KAFKA_OFFSET DESC
               ) AS RN
        FROM KAFKA_STAGE.TRANSACTIONS s
    )
    WHERE RN = 1
      AND COALESCE(DELETED_FLAG, 'false') != 'true'
      AND COALESCE(DEBEZIUM_OP, 'c') != 'd'
) s
ON t.TXN_ID = s.TXN_ID
WHEN MATCHED THEN UPDATE SET
    t.ACCOUNT_ID = s.ACCOUNT_ID,
    t.CARD_ID = s.CARD_ID,
    t.TXN_TYPE = s.TXN_TYPE,
    t.AMOUNT = s.AMOUNT,
    t.CURRENCY = s.CURRENCY,
    t.DIRECTION = s.DIRECTION,
    t.MERCHANT_NAME = s.MERCHANT_NAME,
    t.MERCHANT_MCC = s.MERCHANT_MCC,
    t.MERCHANT_ID = s.MERCHANT_ID,
    t.CHANNEL = s.CHANNEL,
    t.IP_ADDRESS = s.IP_ADDRESS,
    t.DEVICE_ID = s.DEVICE_ID,
    t.DEVICE_FINGERPRINT = s.DEVICE_FINGERPRINT,
    t.COUNTRY_CODE = s.COUNTRY_CODE,
    t.CITY = s.CITY,
    t.LATITUDE = s.LATITUDE,
    t.LONGITUDE = s.LONGITUDE,
    t.COUNTERPARTY_ACCOUNT = s.COUNTERPARTY_ACCOUNT,
    t.COUNTERPARTY_BANK = s.COUNTERPARTY_BANK,
    t.STATUS = s.STATUS,
    t.DECLINE_REASON = s.DECLINE_REASON,
    t.REFERENCE_ID = s.REFERENCE_ID,
    t.INITIATED_AT = s.INITIATED_AT,
    t.SETTLED_AT = s.SETTLED_AT,
    t.KAFKA_OFFSET = s.KAFKA_OFFSET,
    t.KAFKA_PARTITION = s.KAFKA_PARTITION,
    t.KAFKA_TOPIC = 'banking_avro.public.transactions',
    t.KAFKA_INGESTED_AT = s.KAFKA_RECORD_TS,
    t.DEBEZIUM_OP = s.DEBEZIUM_OP
WHEN NOT MATCHED THEN INSERT (
    TXN_ID, ACCOUNT_ID, CARD_ID, TXN_TYPE, AMOUNT, CURRENCY, DIRECTION,
    MERCHANT_NAME, MERCHANT_MCC, MERCHANT_ID, CHANNEL, IP_ADDRESS,
    DEVICE_ID, DEVICE_FINGERPRINT, COUNTRY_CODE, CITY, LATITUDE,
    LONGITUDE, COUNTERPARTY_ACCOUNT, COUNTERPARTY_BANK, STATUS,
    DECLINE_REASON, REFERENCE_ID, INITIATED_AT, SETTLED_AT, KAFKA_OFFSET,
    KAFKA_PARTITION, KAFKA_TOPIC, KAFKA_INGESTED_AT, DEBEZIUM_OP
) VALUES (
    s.TXN_ID, s.ACCOUNT_ID, s.CARD_ID, s.TXN_TYPE, s.AMOUNT, s.CURRENCY, s.DIRECTION,
    s.MERCHANT_NAME, s.MERCHANT_MCC, s.MERCHANT_ID, s.CHANNEL, s.IP_ADDRESS,
    s.DEVICE_ID, s.DEVICE_FINGERPRINT, s.COUNTRY_CODE, s.CITY, s.LATITUDE,
    s.LONGITUDE, s.COUNTERPARTY_ACCOUNT, s.COUNTERPARTY_BANK, s.STATUS,
    s.DECLINE_REASON, s.REFERENCE_ID, s.INITIATED_AT, s.SETTLED_AT, s.KAFKA_OFFSET,
    s.KAFKA_PARTITION, 'banking_avro.public.transactions', s.KAFKA_RECORD_TS, s.DEBEZIUM_OP
);

DELETE FROM RAW.TRANSACTIONS t
WHERE EXISTS (
    SELECT 1
    FROM (
        SELECT TXN_ID, DELETED_FLAG, DEBEZIUM_OP,
               ROW_NUMBER() OVER (
                   PARTITION BY TXN_ID
                   ORDER BY COALESCE(
                                KAFKA_RECORD_TS,
                                CAST(REPLACE(REPLACE(UPDATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP),
                                CAST(REPLACE(REPLACE(SETTLED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP),
                                CAST(REPLACE(REPLACE(INITIATED_AT, 'T', ' '), 'Z', '') AS TIMESTAMP)
                            ) DESC,
                            KAFKA_PARTITION DESC,
                            KAFKA_OFFSET DESC
               ) AS RN
        FROM KAFKA_STAGE.TRANSACTIONS
    ) s
    WHERE s.RN = 1
      AND t.TXN_ID = s.TXN_ID
      AND (COALESCE(s.DELETED_FLAG, 'false') = 'true' OR COALESCE(s.DEBEZIUM_OP, 'c') = 'd')
);

COMMIT;

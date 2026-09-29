-- ============================================================
--  OPTIONAL: EXASOL KAFKA CONNECTOR LANDING TABLES
--  These tables are append-only and are meant for the official
--  Exasol Kafka Connector Extension (BucketFS / UDF based).
-- ============================================================

CREATE SCHEMA IF NOT EXISTS KAFKA_STAGE;

CREATE OR REPLACE TABLE KAFKA_STAGE.TRANSACTIONS (
    TXN_ID                  VARCHAR(36),
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
    INITIATED_AT            VARCHAR(40),
    SETTLED_AT              VARCHAR(40),
    UPDATED_AT              VARCHAR(40),
    DEBEZIUM_OP             CHAR(1),
    DELETED_FLAG            VARCHAR(5),
    KAFKA_RECORD_TS         TIMESTAMP,
    KAFKA_PARTITION         DECIMAL(18,0),
    KAFKA_OFFSET            DECIMAL(36,0)
);

CREATE OR REPLACE TABLE KAFKA_STAGE.ACCOUNTS (
    ACCOUNT_ID              VARCHAR(36),
    CUSTOMER_ID             VARCHAR(36),
    ACCOUNT_NUMBER          VARCHAR(30),
    ACCOUNT_TYPE            VARCHAR(20),
    CURRENCY                CHAR(3),
    BALANCE                 DECIMAL(18,4),
    CREDIT_LIMIT            DECIMAL(18,4),
    STATUS                  VARCHAR(20),
    OPENED_AT               VARCHAR(40),
    UPDATED_AT              VARCHAR(40),
    DEBEZIUM_OP             CHAR(1),
    DELETED_FLAG            VARCHAR(5),
    KAFKA_RECORD_TS         TIMESTAMP,
    KAFKA_PARTITION         DECIMAL(18,0),
    KAFKA_OFFSET            DECIMAL(36,0)
);

CREATE OR REPLACE TABLE KAFKA_STAGE.CUSTOMERS (
    CUSTOMER_ID             VARCHAR(36),
    FULL_NAME               VARCHAR(200),
    EMAIL                   VARCHAR(200),
    PHONE                   VARCHAR(30),
    DATE_OF_BIRTH           DATE,
    COUNTRY_CODE            CHAR(2),
    KYC_STATUS              VARCHAR(20),
    RISK_BAND               VARCHAR(10),
    CREATED_AT              VARCHAR(40),
    UPDATED_AT              VARCHAR(40),
    DEBEZIUM_OP             CHAR(1),
    DELETED_FLAG            VARCHAR(5),
    KAFKA_RECORD_TS         TIMESTAMP,
    KAFKA_PARTITION         DECIMAL(18,0),
    KAFKA_OFFSET            DECIMAL(36,0)
);

CREATE OR REPLACE TABLE KAFKA_STAGE.CARDS (
    CARD_ID                 VARCHAR(36),
    ACCOUNT_ID              VARCHAR(36),
    CARD_TYPE               VARCHAR(20),
    MASKED_PAN              VARCHAR(19),
    LAST_FOUR               CHAR(4),
    EXPIRY_DATE             DATE,
    NETWORK                 VARCHAR(20),
    STATUS                  VARCHAR(20),
    ISSUED_AT               VARCHAR(40),
    UPDATED_AT              VARCHAR(40),
    DEBEZIUM_OP             CHAR(1),
    DELETED_FLAG            VARCHAR(5),
    KAFKA_RECORD_TS         TIMESTAMP,
    KAFKA_PARTITION         DECIMAL(18,0),
    KAFKA_OFFSET            DECIMAL(36,0)
);

CREATE OR REPLACE TABLE KAFKA_STAGE.FRAUD_ALERTS (
    ALERT_ID                VARCHAR(36),
    TXN_ID                  VARCHAR(36),
    ALERT_TYPE              VARCHAR(50),
    FRAUD_SCORE             DECIMAL(6,5),
    RISK_SCORE              DECIMAL(6,5),
    STATUS                  VARCHAR(20),
    INVESTIGATOR            VARCHAR(100),
    NOTES                   VARCHAR(2000),
    CREATED_AT              VARCHAR(40),
    RESOLVED_AT             VARCHAR(40),
    DEBEZIUM_OP             CHAR(1),
    DELETED_FLAG            VARCHAR(5),
    KAFKA_RECORD_TS         TIMESTAMP,
    KAFKA_PARTITION         DECIMAL(18,0),
    KAFKA_OFFSET            DECIMAL(36,0)
);

COMMIT;

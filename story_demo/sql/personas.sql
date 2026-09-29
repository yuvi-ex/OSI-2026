-- ===========================================================================
--  Persona-scoped access for the agentic demo.
--
--  The security boundary is the DATABASE, not the agent and not the prompt.
--  Each persona is a real Exasol user holding SELECT on one row-filtered view
--  and nothing else. An agent connecting as that user cannot see another
--  unit's rows even if it writes perfect SQL and even if the prompt is
--  compromised -- there is no grant to exploit.
-- ===========================================================================

-- --- who owns which account -------------------------------------------------
CREATE TABLE IF NOT EXISTS FRAUD_DEMO.ACCOUNT_UNITS (
    ACCOUNT_ID     VARCHAR(36) PRIMARY KEY,
    BUSINESS_UNIT  VARCHAR(20) NOT NULL
);
DELETE FROM FRAUD_DEMO.ACCOUNT_UNITS;
-- The story customer belongs to the US retail book; everyone seeded with the
-- original demo data belongs to the EU book.
INSERT INTO FRAUD_DEMO.ACCOUNT_UNITS
SELECT ACCOUNT_ID,
       CASE WHEN ACCOUNT_ID = 'e1e0a000-0000-4000-8000-000000000002'
            THEN 'RETAIL_US' ELSE 'RETAIL_EU' END
FROM RAW.ACCOUNTS;

-- --- which database user may see which unit ---------------------------------
CREATE TABLE IF NOT EXISTS FRAUD_DEMO.USER_ENTITLEMENTS (
    DB_USER        VARCHAR(128) NOT NULL,
    BUSINESS_UNIT  VARCHAR(20)  NOT NULL
);
DELETE FROM FRAUD_DEMO.USER_ENTITLEMENTS;
INSERT INTO FRAUD_DEMO.USER_ENTITLEMENTS VALUES
    ('FRAUD_ANALYST_US', 'RETAIL_US'),
    ('FRAUD_ANALYST_EU', 'RETAIL_EU'),
    ('FRAUD_LEAD',       'RETAIL_US'),
    ('FRAUD_LEAD',       'RETAIL_EU');

-- --- the row filter ---------------------------------------------------------
-- CURRENT_USER is evaluated by the engine for whoever is connected. There is
-- no parameter for the caller to tamper with and nothing the agent can pass.
CREATE OR REPLACE VIEW FRAUD_DEMO.V_SCORED_TRANSACTIONS AS
SELECT  t.TXN_ID,
        t.MERCHANT_NAME,
        t.MERCHANT_MCC,
        t.CHANNEL,
        t.COUNTRY_CODE,
        t.CITY,
        t.DEVICE_ID,
        t.STATUS,
        t.INITIATED_AT,
        f.AMOUNT_USD,
        f.TXN_COUNT_1H,
        f.AMOUNT_VS_AVG_RATIO,
        f.MCC_BASE_RISK,
        f.IS_CROSS_BORDER,
        f.IS_NEW_COUNTRY_30D,
        f.IS_NEW_DEVICE_30D,
        f.FRAUD_SCORE,
        CASE WHEN f.FRAUD_SCORE >= 0.70 THEN 'BLOCK'
             WHEN f.FRAUD_SCORE >= 0.30 THEN 'REVIEW'
             ELSE 'APPROVE' END              AS DECISION,
        u.BUSINESS_UNIT
FROM    ANALYTICS.FRAUD_FEATURES f
JOIN    RAW.TRANSACTIONS  t ON t.TXN_ID = f.TXN_ID
JOIN    FRAUD_DEMO.ACCOUNT_UNITS   u ON u.ACCOUNT_ID = f.ACCOUNT_ID
JOIN    FRAUD_DEMO.USER_ENTITLEMENTS e
          ON e.BUSINESS_UNIT = u.BUSINESS_UNIT
         AND e.DB_USER       = CURRENT_USER;

-- --- the customers a persona may see ---------------------------------------
CREATE OR REPLACE VIEW FRAUD_DEMO.V_CUSTOMERS AS
SELECT  c.CUSTOMER_ID, c.FULL_NAME, c.COUNTRY_CODE, c.KYC_STATUS, c.RISK_BAND,
        a.ACCOUNT_ID, a.ACCOUNT_NUMBER, a.ACCOUNT_TYPE, a.BALANCE, a.CREDIT_LIMIT,
        u.BUSINESS_UNIT
FROM    RAW.CUSTOMERS c
JOIN    RAW.ACCOUNTS  a ON a.CUSTOMER_ID = c.CUSTOMER_ID
JOIN    FRAUD_DEMO.ACCOUNT_UNITS   u ON u.ACCOUNT_ID = a.ACCOUNT_ID
JOIN    FRAUD_DEMO.USER_ENTITLEMENTS e
          ON e.BUSINESS_UNIT = u.BUSINESS_UNIT
         AND e.DB_USER       = CURRENT_USER;

-- --- who asked what ---------------------------------------------------------
-- Names the human's database identity, not the agent. The agent has no
-- identity of its own -- that is the point.
CREATE OR REPLACE VIEW FRAUD_DEMO.V_AUDIT AS
SELECT  SESSION_ID, USER_NAME, CLIENT, LOGIN_TIME, STATUS
FROM    SYS.EXA_DBA_SESSIONS
ORDER BY LOGIN_TIME DESC;

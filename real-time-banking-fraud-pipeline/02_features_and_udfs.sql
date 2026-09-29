-- ============================================================
--  EXASOL: FRAUD SCORING UDF + SCORING QUERY
--  Run after 07_refresh_analytics_features.sql
-- ============================================================
--
-- 07_refresh_analytics_features.sql owns:
--   1. RAW -> CLEANSED dimension / fact refresh
--   2. ANALYTICS.FRAUD_FEATURES refresh
--   3. FRAUD_LABEL backfill from fraud alerts
--
-- This file now owns only:
--   1. Python fraud scoring UDF creation
--   2. Batch scoring into ANALYTICS.FRAUD_FEATURES
--   3. Demo query for top-risk transactions

-- ─────────────────────────────────────────────
-- STEP 1: SIMPLE ML DEMO
-- One fraud-scoring UDF + one batch scoring query
-- ─────────────────────────────────────────────

-- 1a. FRAUD SCORE UDF  (requires one demo fraud model in BucketFS)
CREATE OR REPLACE PYTHON3 SCALAR SCRIPT ANALYTICS.FRAUD_SCORE_UDF (
    AMOUNT_USD              DOUBLE,
    TXN_COUNT_1H            DOUBLE,
    TXN_COUNT_24H           DOUBLE,
    AMOUNT_SUM_1H           DOUBLE,
    AMOUNT_SUM_24H          DOUBLE,
    AMOUNT_VS_AVG_RATIO     DOUBLE,
    IS_CROSS_BORDER         BOOLEAN,
    IS_NEW_COUNTRY_30D      BOOLEAN,
    IS_NEW_DEVICE_30D       BOOLEAN,
    IS_NIGHT_TXN            BOOLEAN,
    IS_WEEKEND_TXN          BOOLEAN,
    MCC_BASE_RISK           DOUBLE
)
RETURNS DOUBLE
AS
import sys
sys.path.append('/buckets/bfsdefault/drivers/')

import pickle
import numpy as np

MODEL_CACHE = {}

def get_model_package():
    if 'fraud' not in MODEL_CACHE:
        with open('/buckets/bfsdefault/default/drivers/models/fraud_model.pkl', 'rb') as f:
            MODEL_CACHE['fraud'] = pickle.load(f)
    return MODEL_CACHE['fraud']

def run(ctx):
    model_package = get_model_package()

    features = np.array([[
        ctx.AMOUNT_USD         or 0,
        ctx.TXN_COUNT_1H       or 0,
        ctx.TXN_COUNT_24H      or 0,
        ctx.AMOUNT_SUM_1H      or 0,
        ctx.AMOUNT_SUM_24H     or 0,
        ctx.AMOUNT_VS_AVG_RATIO or 1.0,
        1 if ctx.IS_CROSS_BORDER    else 0,
        1 if ctx.IS_NEW_COUNTRY_30D else 0,
        1 if ctx.IS_NEW_DEVICE_30D  else 0,
        1 if ctx.IS_NIGHT_TXN       else 0,
        1 if ctx.IS_WEEKEND_TXN     else 0,
        ctx.MCC_BASE_RISK      or 0.1
    ]], dtype=float)

    if isinstance(model_package, dict):
        model = model_package['model']
        scaler = model_package.get('scaler')
    else:
        model = model_package
        scaler = None

    if scaler is not None:
        features = scaler.transform(features)

    prob = float(model.predict_proba(features)[0][1])
    return round(prob, 5)
/

-- 1b. BATCH SCORING QUERY
-- Populates FRAUD_SCORE and MODEL_VERSION back into the feature table
UPDATE ANALYTICS.FRAUD_FEATURES
SET
    FRAUD_SCORE = ANALYTICS.FRAUD_SCORE_UDF(
        AMOUNT_USD, TXN_COUNT_1H, TXN_COUNT_24H,
        AMOUNT_SUM_1H, AMOUNT_SUM_24H, AMOUNT_VS_AVG_RATIO,
        IS_CROSS_BORDER, IS_NEW_COUNTRY_30D, IS_NEW_DEVICE_30D,
        IS_NIGHT_TXN, IS_WEEKEND_TXN, MCC_BASE_RISK
    ),
    MODEL_VERSION = 'LOGREG_DEMO_v1'
WHERE FRAUD_SCORE IS NULL OR MODEL_VERSION IS NULL;

COMMIT;

-- 1c. DEMO QUERY
-- Show the highest-risk transactions after scoring
SELECT
    TXN_ID,
    ACCOUNT_ID,
    AMOUNT_USD,
    CHANNEL,
    MERCHANT_MCC,
    FRAUD_SCORE,
    MODEL_VERSION
FROM ANALYTICS.FRAUD_FEATURES
WHERE FRAUD_SCORE IS NOT NULL
ORDER BY FRAUD_SCORE DESC, FEATURE_COMPUTED_AT DESC
LIMIT 10;

COMMIT;

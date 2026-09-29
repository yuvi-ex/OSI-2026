# Fraud Features Guide

## Purpose

`ANALYTICS.FRAUD_FEATURES` is the ML-ready transaction feature table used by the Exasol fraud demo.

Think of it as:

- one row per transaction
- raw transaction context plus derived fraud indicators
- optional ground-truth label from investigations
- model output written back into the same table

The table is defined in `01_exasol_schema.sql`, refreshed by `07_refresh_analytics_features.sql`, and scored by `02_features_and_udfs.sql`.

## How To Read The Table

The easiest way to read a row is:

1. identify the transaction
2. look at the behavior features
3. look at the risk flags
4. look at the fraud score

In practice:

- `TXN_ID` tells you which transaction is being scored
- `AMOUNT_USD`, `CHANNEL`, `MERCHANT_MCC` describe the transaction itself
- velocity and deviation columns explain why it may be unusual
- risk flags show suspicious patterns like cross-border or new device usage
- `FRAUD_SCORE` is the model output

## Recommended Demo Query

Use this query during demos:

```sql
SELECT
    TXN_ID,
    AMOUNT_USD,
    CHANNEL,
    MERCHANT_MCC,
    TXN_COUNT_1H,
    TXN_COUNT_24H,
    AMOUNT_VS_AVG_RATIO,
    IS_CROSS_BORDER,
    IS_NEW_DEVICE_30D,
    FRAUD_SCORE,
    MODEL_VERSION
FROM ANALYTICS.FRAUD_FEATURES
WHERE FRAUD_SCORE IS NOT NULL
ORDER BY FRAUD_SCORE DESC, FEATURE_COMPUTED_AT DESC
LIMIT 10;
```

This keeps only the fields that help explain the score quickly.

## Column Groups

### Identity

- `TXN_ID`: transaction identifier
- `ACCOUNT_ID`: account linked to the transaction
- `CUSTOMER_ID`: customer linked to the transaction

### Transaction Context

- `AMOUNT_USD`: transaction amount
- `TXN_TYPE`: purchase, transfer, withdrawal, etc.
- `CHANNEL`: channel such as `ONLINE`, `MOBILE`, `ATM`, `API`
- `MERCHANT_MCC`: merchant category code
- `KYC_STATUS`: customer KYC state
- `RISK_BAND`: customer risk band

These columns describe what happened and who it happened to.

### Velocity Features

- `TXN_COUNT_1H`: prior transaction count in the last hour
- `TXN_COUNT_6H`: prior transaction count in the last 6 hours
- `TXN_COUNT_24H`: prior transaction count in the last 24 hours
- `AMOUNT_SUM_1H`: amount spent in the prior hour
- `AMOUNT_SUM_6H`: amount spent in the prior 6 hours
- `AMOUNT_SUM_24H`: amount spent in the prior 24 hours

These columns answer:

- “Is this transaction part of an unusual burst of activity?”

### Deviation Features

- `ACCOUNT_AVG_AMOUNT_30D`: account's historical average amount
- `AMOUNT_VS_AVG_RATIO`: current amount divided by historical average

These columns answer:

- “Is this transaction much larger than normal for this account?”

### Risk Flags

- `IS_CROSS_BORDER`: transaction country differs from expected customer country context
- `IS_NEW_COUNTRY_30D`: this country has not been seen recently for this account
- `IS_NEW_DEVICE_30D`: this device has not been seen recently
- `IS_NIGHT_TXN`: happened during the night window
- `IS_WEEKEND_TXN`: happened on a weekend
- `MCC_BASE_RISK`: built-in risk weight for the merchant category

These are the easiest columns to explain to an audience because they map directly to common fraud signals.

### ML / Outcome Columns

- `FRAUD_SCORE`: model output from `0` to `1`
- `MODEL_VERSION`: which model generated the score
- `FRAUD_LABEL`: known investigated outcome if available
- `FEATURE_COMPUTED_AT`: when the feature row was last refreshed

## How The Model Is Trained And Used In Exasol

The project uses a simple fraud model lifecycle:

1. build and refresh `ANALYTICS.FRAUD_FEATURES`
2. train one fraud model in Python using those features
3. upload the model artifact to BucketFS
4. load the model inside an Exasol Python UDF
5. write `FRAUD_SCORE` back into `ANALYTICS.FRAUD_FEATURES`

Important clarification:

- feature engineering and feature refresh happen in Exasol
- fraud scoring happens in Exasol
- model training happens in Python
- the training data can come from Exasol itself

### Training Data Source

The training script is [train_pipeline.py](../train_pipeline.py).

It reads the same feature columns that exist in `ANALYTICS.FRAUD_FEATURES`:

- `AMOUNT_USD`
- `TXN_COUNT_1H`
- `TXN_COUNT_24H`
- `AMOUNT_SUM_1H`
- `AMOUNT_SUM_24H`
- `AMOUNT_VS_AVG_RATIO`
- `IS_CROSS_BORDER`
- `IS_NEW_COUNTRY_30D`
- `IS_NEW_DEVICE_30D`
- `IS_NIGHT_TXN`
- `IS_WEEKEND_TXN`
- `MCC_BASE_RISK`

The label is:

- `FRAUD_LABEL`

When you run the training script, it tries to load labeled rows from Exasol:

```sql
SELECT <feature columns>, FRAUD_LABEL
FROM ANALYTICS.FRAUD_FEATURES
WHERE FRAUD_LABEL IS NOT NULL;
```

If there are not enough labeled fraud examples yet, the script can fall back to:

- `hybrid`: real Exasol rows plus synthetic rows
- `synthetic`: synthetic rows only

That makes the demo workable even when the real warehouse is still small.

### Model Training

The current model is a simple logistic regression model.

The main Python libraries used are:

- `pandas`: dataframe handling and feature preparation
- `numpy`: numeric arrays and synthetic data generation
- `scikit-learn`: `LogisticRegression`, `StandardScaler`, train/test split, and evaluation metrics
- `pyexasol`: reading labeled training data from Exasol
- Python `pickle`: serializing the trained artifact into `fraud_model.pkl`

The training pipeline does this:

- coerces numeric and boolean feature columns into model-friendly values
- clips extreme values like `AMOUNT_USD` and `AMOUNT_VS_AVG_RATIO`
- splits the data into train and test sets
- standardizes the features with `StandardScaler`
- trains `LogisticRegression`
- evaluates the model with ROC-AUC and a classification report

The output artifact is:

- `models/fraud_model.pkl`

That pickle file contains:

- the trained logistic regression model
- the fitted scaler
- the feature column list
- the model name `LOGREG_DEMO_v1`

So the full training story is:

1. `train_pipeline.py` reads labeled rows from `ANALYTICS.FRAUD_FEATURES`
2. it prepares the feature matrix with `pandas` and `numpy`
3. it scales the features with `StandardScaler`
4. it trains a `scikit-learn` `LogisticRegression` model
5. it serializes the model package with `pickle` into `fraud_model.pkl`

### Upload To BucketFS

After training, upload the model to BucketFS so Exasol can read it.

The UDF expects this path:

- `/buckets/bfsdefault/default/drivers/models/fraud_model.pkl`

So the uploaded object should be:

- `models/fraud_model.pkl`

### How Exasol Uses The Model

The scoring UDF is defined in [02_features_and_udfs.sql](../02_features_and_udfs.sql).

`ANALYTICS.FRAUD_SCORE_UDF` does the following for each feature row:

- loads `fraud_model.pkl` from BucketFS
- builds a feature vector from the Exasol row
- converts booleans like `IS_CROSS_BORDER` into `0/1`
- applies the saved scaler
- runs `predict_proba(...)`
- returns the fraud probability as a value between `0` and `1`

Then the batch scoring step updates the table:

```sql
UPDATE ANALYTICS.FRAUD_FEATURES
SET
    FRAUD_SCORE = ANALYTICS.FRAUD_SCORE_UDF(...),
    MODEL_VERSION = 'LOGREG_DEMO_v1'
WHERE FRAUD_SCORE IS NULL OR MODEL_VERSION IS NULL;
```

That is why `ANALYTICS.FRAUD_FEATURES` is both:

- the model input table
- and the table where the final fraud score is stored


## Demo Risk Thresholds

The dashboard classifies `FRAUD_SCORE` into simple demo-friendly buckets:

- `High Risk`: `FRAUD_SCORE >= 0.65`
- `Needs Review`: `FRAUD_SCORE >= 0.35` and `< 0.65`
- `Low Risk`: `FRAUD_SCORE < 0.35`

These thresholds are currently used in the demo UI to highlight risky rows in the risk score board.

Interpret them as:

- `High Risk`: investigate first
- `Needs Review`: suspicious enough for analyst review
- `Low Risk`: lower-priority transaction in the current ranking

## How To Explain A High-Scoring Row

Example explanation:

- `TXN_COUNT_1H` is high
- `AMOUNT_VS_AVG_RATIO` is high
- `IS_CROSS_BORDER = TRUE`
- `IS_NEW_DEVICE_30D = TRUE`
- `MCC_BASE_RISK` is high

That means:

- the customer is suddenly very active
- the amount is unusual for their normal behavior
- the location and device are not familiar
- the merchant category is inherently risky

So a higher `FRAUD_SCORE` is easy to justify.

## Helpful Queries

### Top suspicious transactions

```sql
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
ORDER BY FRAUD_SCORE DESC
LIMIT 10;
```

### Compare model output with known labels

```sql
SELECT
    TXN_ID,
    FRAUD_SCORE,
    FRAUD_LABEL,
    MODEL_VERSION
FROM ANALYTICS.FRAUD_FEATURES
WHERE FRAUD_LABEL IS NOT NULL
ORDER BY FRAUD_SCORE DESC;
```

### Show why a row is suspicious

```sql
SELECT
    TXN_ID,
    AMOUNT_USD,
    TXN_COUNT_1H,
    TXN_COUNT_24H,
    AMOUNT_VS_AVG_RATIO,
    IS_CROSS_BORDER,
    IS_NEW_COUNTRY_30D,
    IS_NEW_DEVICE_30D,
    IS_NIGHT_TXN,
    MCC_BASE_RISK,
    FRAUD_SCORE
FROM ANALYTICS.FRAUD_FEATURES
ORDER BY FRAUD_SCORE DESC
LIMIT 10;
```

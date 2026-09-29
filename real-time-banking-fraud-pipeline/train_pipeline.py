"""
============================================================
  SIMPLE FRAUD MODEL TRAINING PIPELINE
  Trains one fraud-scoring model for the Exasol demo
  Output: fraud_model.pkl -> upload to Exasol BucketFS
============================================================
"""

import argparse
import json
import os
import pickle
import ssl
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")


FEATURE_COLS = [
    "AMOUNT_USD", "TXN_COUNT_1H", "TXN_COUNT_24H",
    "AMOUNT_SUM_1H", "AMOUNT_SUM_24H", "AMOUNT_VS_AVG_RATIO",
    "IS_CROSS_BORDER", "IS_NEW_COUNTRY_30D", "IS_NEW_DEVICE_30D",
    "IS_NIGHT_TXN", "IS_WEEKEND_TXN", "MCC_BASE_RISK"
]
LABEL_COL = "FRAUD_LABEL"
BOOL_COLS = [
    "IS_CROSS_BORDER",
    "IS_NEW_COUNTRY_30D",
    "IS_NEW_DEVICE_30D",
    "IS_NIGHT_TXN",
    "IS_WEEKEND_TXN",
]
NUMERIC_COLS = [
    "AMOUNT_USD",
    "TXN_COUNT_1H",
    "TXN_COUNT_24H",
    "AMOUNT_SUM_1H",
    "AMOUNT_SUM_24H",
    "AMOUNT_VS_AVG_RATIO",
    "MCC_BASE_RISK",
]
TRUTHY_VALUES = {"1", "TRUE", "T", "Y", "YES"}
DEFAULT_SYNTHETIC_ROWS = 5_000
DEFAULT_FRAUD_RATE = 0.04
DEFAULT_MIN_LABELED_ROWS = 2_000
DEFAULT_MIN_POSITIVE_LABELS = 50
MODEL_NAME = "LOGREG_DEMO_v1"


def parse_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def parse_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train one Exasol demo fraud model from Exasol or synthetic data."
    )
    parser.add_argument(
        "--source",
        choices=["auto", "exasol", "hybrid", "synthetic"],
        default=os.getenv("TRAINING_SOURCE", "auto"),
        help="auto=prefer Exasol and fall back as needed, hybrid=blend Exasol with synthetic, "
             "exasol=real data only, synthetic=synthetic only",
    )
    parser.add_argument("--dsn", default=os.getenv("EXASOL_DSN"), help="Exasol DSN")
    parser.add_argument("--user", default=os.getenv("EXASOL_USER"), help="Exasol user")
    parser.add_argument("--password", default=os.getenv("EXASOL_PASSWORD"), help="Exasol password")
    parser.add_argument(
        "--synthetic-rows",
        type=int,
        default=parse_int_env("SYNTHETIC_TRAINING_ROWS", DEFAULT_SYNTHETIC_ROWS),
        help="Synthetic row count for pure synthetic mode",
    )
    parser.add_argument(
        "--synthetic-fraud-rate",
        type=float,
        default=parse_float_env("SYNTHETIC_FRAUD_RATE", DEFAULT_FRAUD_RATE),
        help="Fraud rate used when generating synthetic data",
    )
    parser.add_argument(
        "--min-labeled-rows",
        type=int,
        default=parse_int_env("MIN_LABELED_ROWS", DEFAULT_MIN_LABELED_ROWS),
        help="Minimum labeled rows before real-data-only training is considered sufficient",
    )
    parser.add_argument(
        "--min-positive-labels",
        type=int,
        default=parse_int_env("MIN_POSITIVE_LABELS", DEFAULT_MIN_POSITIVE_LABELS),
        help="Minimum confirmed fraud labels before real-data-only training is considered sufficient",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("MODEL_OUTPUT_DIR", "models"),
        help="Directory to write model artifacts into",
    )
    return parser.parse_args()


def coerce_binary_series(series: pd.Series) -> pd.Series:
    return series.map(
        lambda value: value if isinstance(value, bool) else str(value).strip().upper() in TRUTHY_VALUES
    ).astype(int)


def load_from_exasol(dsn: str, user: str, password: str) -> pd.DataFrame:
    """Load labelled feature data from Exasol."""
    import pyexasol

    conn = pyexasol.connect(
        dsn=dsn,
        user=user,
        password=password,
        encryption=True,
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
    )
    stmt = conn.execute(
        "SELECT {} FROM ANALYTICS.FRAUD_FEATURES WHERE FRAUD_LABEL IS NOT NULL".format(
            ", ".join(FEATURE_COLS + [LABEL_COL])
        )
    )
    df = pd.DataFrame(stmt.fetchall(), columns=stmt.column_names())
    conn.close()
    return df


def load_synthetic(n_samples: int = DEFAULT_SYNTHETIC_ROWS, fraud_rate: float = DEFAULT_FRAUD_RATE) -> pd.DataFrame:
    """Generate synthetic training data for the demo when real labels are sparse."""
    np.random.seed(42)
    n_fraud = int(n_samples * fraud_rate)
    n_legit = n_samples - n_fraud

    def sample_legit(n):
        return pd.DataFrame({
            "AMOUNT_USD": np.random.lognormal(4.5, 1.0, n),
            "TXN_COUNT_1H": np.random.poisson(1.5, n),
            "TXN_COUNT_24H": np.random.poisson(4.0, n),
            "AMOUNT_SUM_1H": np.random.lognormal(4.5, 1.0, n),
            "AMOUNT_SUM_24H": np.random.lognormal(6.0, 1.2, n),
            "AMOUNT_VS_AVG_RATIO": np.random.lognormal(0.0, 0.5, n).clip(0.1, 5.0),
            "IS_CROSS_BORDER": np.random.binomial(1, 0.05, n),
            "IS_NEW_COUNTRY_30D": np.random.binomial(1, 0.04, n),
            "IS_NEW_DEVICE_30D": np.random.binomial(1, 0.06, n),
            "IS_NIGHT_TXN": np.random.binomial(1, 0.15, n),
            "IS_WEEKEND_TXN": np.random.binomial(1, 0.28, n),
            "MCC_BASE_RISK": np.random.choice([0.05, 0.08, 0.15, 0.20], n),
            "FRAUD_LABEL": np.zeros(n, dtype=int),
        })

    def sample_fraud(n):
        return pd.DataFrame({
            "AMOUNT_USD": np.random.lognormal(6.5, 1.5, n),
            "TXN_COUNT_1H": np.random.poisson(8.0, n),
            "TXN_COUNT_24H": np.random.poisson(18.0, n),
            "AMOUNT_SUM_1H": np.random.lognormal(7.0, 1.5, n),
            "AMOUNT_SUM_24H": np.random.lognormal(9.0, 1.5, n),
            "AMOUNT_VS_AVG_RATIO": np.random.lognormal(2.0, 0.8, n).clip(1.0, 20.0),
            "IS_CROSS_BORDER": np.random.binomial(1, 0.55, n),
            "IS_NEW_COUNTRY_30D": np.random.binomial(1, 0.60, n),
            "IS_NEW_DEVICE_30D": np.random.binomial(1, 0.65, n),
            "IS_NIGHT_TXN": np.random.binomial(1, 0.45, n),
            "IS_WEEKEND_TXN": np.random.binomial(1, 0.35, n),
            "MCC_BASE_RISK": np.random.choice([0.60, 0.65, 0.70, 0.75], n),
            "FRAUD_LABEL": np.ones(n, dtype=int),
        })

    df = pd.concat([sample_legit(n_legit), sample_fraud(n_fraud)], ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    print(f"Synthetic dataset: {len(df):,} rows | fraud rate: {df['FRAUD_LABEL'].mean():.2%}")
    return df


def label_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"rows": 0, "positives": 0, "negatives": 0, "fraud_rate": 0.0}

    labels = coerce_binary_series(df[LABEL_COL])
    positives = int(labels.sum())
    rows = int(len(df))
    negatives = rows - positives
    return {
        "rows": rows,
        "positives": positives,
        "negatives": negatives,
        "fraud_rate": positives / rows if rows else 0.0,
    }


def print_dataset_summary(title: str, df: pd.DataFrame):
    stats = label_summary(df)
    print(
        f"{title}: {stats['rows']:,} rows | "
        f"positives={stats['positives']:,} | "
        f"negatives={stats['negatives']:,} | "
        f"fraud rate={stats['fraud_rate']:.2%}"
    )


def validate_real_dataset(df: pd.DataFrame, min_rows: int, min_positive: int) -> tuple[bool, str]:
    stats = label_summary(df)
    if stats["rows"] == 0:
        return False, "no labeled rows found in ANALYTICS.FRAUD_FEATURES"
    if stats["positives"] == 0:
        return False, "no confirmed fraud labels found in ANALYTICS.FRAUD_FEATURES"
    if stats["negatives"] == 0:
        return False, "no non-fraud labels found in ANALYTICS.FRAUD_FEATURES"
    if stats["rows"] < min_rows:
        return False, f"only {stats['rows']:,} labeled rows found; need at least {min_rows:,}"
    if stats["positives"] < min_positive:
        return False, (
            f"only {stats['positives']:,} positive fraud labels found; "
            f"need at least {min_positive:,}"
        )
    return True, "sufficient labeled history"


def combine_real_and_synthetic(
    real_df: pd.DataFrame,
    min_rows: int,
    min_positive: int,
    synthetic_fraud_rate: float,
) -> tuple[pd.DataFrame, dict]:
    stats = label_summary(real_df)
    deficit_rows = max(0, min_rows - stats["rows"])
    deficit_positive = max(0, min_positive - stats["positives"])

    if stats["positives"] == 0:
        deficit_positive = max(deficit_positive, 1)
    if stats["negatives"] == 0:
        deficit_rows = max(deficit_rows, 1)

    if deficit_positive > 0:
        rows_for_positive_balance = int(np.ceil(deficit_positive / max(synthetic_fraud_rate, 0.0001)))
        deficit_rows = max(deficit_rows, rows_for_positive_balance)

    if deficit_rows <= 0:
        return real_df.copy(), {"real_rows": stats["rows"], "synthetic_rows": 0}

    synthetic_df = load_synthetic(n_samples=deficit_rows, fraud_rate=synthetic_fraud_rate)
    hybrid_df = pd.concat([real_df, synthetic_df], ignore_index=True)
    hybrid_df = hybrid_df.sample(frac=1, random_state=42).reset_index(drop=True)
    return hybrid_df, {"real_rows": stats["rows"], "synthetic_rows": len(synthetic_df)}


def resolve_training_data(args):
    metadata = {
        "requested_source": args.source,
        "effective_source": None,
        "real_rows": 0,
        "synthetic_rows": 0,
        "notes": [],
    }

    real_df = pd.DataFrame(columns=FEATURE_COLS + [LABEL_COL])
    can_try_exasol = bool(args.dsn and args.user and args.password)

    if args.source == "synthetic":
        df = load_synthetic(args.synthetic_rows, args.synthetic_fraud_rate)
        metadata["effective_source"] = "synthetic"
        metadata["synthetic_rows"] = len(df)
        return df, metadata

    if args.source in {"exasol", "hybrid", "auto"}:
        if not can_try_exasol:
            message = "missing EXASOL_DSN / EXASOL_USER / EXASOL_PASSWORD"
            if args.source == "exasol":
                raise SystemExit(f"Cannot train from Exasol: {message}")
            metadata["notes"].append(f"Exasol load skipped: {message}")
        else:
            try:
                real_df = load_from_exasol(args.dsn, args.user, args.password)
                metadata["real_rows"] = len(real_df)
                print_dataset_summary("Exasol labeled dataset", real_df)
            except Exception as exc:
                if args.source == "exasol":
                    raise
                metadata["notes"].append(f"Exasol load failed: {exc}")
                real_df = pd.DataFrame(columns=FEATURE_COLS + [LABEL_COL])

    if args.source == "exasol":
        valid, reason = validate_real_dataset(real_df, args.min_labeled_rows, args.min_positive_labels)
        if not valid:
            raise SystemExit(
                "Exasol dataset is not ready for real-data-only training: "
                f"{reason}. Run 07_refresh_analytics_features.sql or use --source hybrid."
            )
        metadata["effective_source"] = "exasol"
        return real_df, metadata

    if args.source == "hybrid":
        df, mix = combine_real_and_synthetic(
            real_df,
            min_rows=args.min_labeled_rows,
            min_positive=args.min_positive_labels,
            synthetic_fraud_rate=args.synthetic_fraud_rate,
        )
        metadata["effective_source"] = "hybrid"
        metadata.update(mix)
        return df, metadata

    valid, reason = validate_real_dataset(real_df, args.min_labeled_rows, args.min_positive_labels)
    if valid:
        metadata["effective_source"] = "exasol"
        metadata["notes"].append("Using Exasol labeled history directly.")
        return real_df, metadata

    if len(real_df) > 0:
        metadata["notes"].append(f"Exasol data insufficient for standalone training: {reason}")
        df, mix = combine_real_and_synthetic(
            real_df,
            min_rows=args.min_labeled_rows,
            min_positive=args.min_positive_labels,
            synthetic_fraud_rate=args.synthetic_fraud_rate,
        )
        metadata["effective_source"] = "hybrid"
        metadata.update(mix)
        return df, metadata

    metadata["notes"].append(f"Falling back to synthetic data: {reason}")
    df = load_synthetic(args.synthetic_rows, args.synthetic_fraud_rate)
    metadata["effective_source"] = "synthetic"
    metadata["synthetic_rows"] = len(df)
    return df, metadata


def preprocess(df: pd.DataFrame):
    df = df.copy()

    for col in NUMERIC_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in BOOL_COLS:
        df[col] = coerce_binary_series(df[col])

    df[LABEL_COL] = coerce_binary_series(df[LABEL_COL])
    df["AMOUNT_USD"] = df["AMOUNT_USD"].clip(0, 1_000_000)
    df["AMOUNT_VS_AVG_RATIO"] = df["AMOUNT_VS_AVG_RATIO"].clip(0, 50)

    X = df[FEATURE_COLS].fillna(0).astype(float).values
    y = df[LABEL_COL].values
    return X, y


def train_fraud_model(X_train, y_train, X_test, y_test):
    print("\nTraining simple fraud model (Logistic Regression)...")

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = LogisticRegression(
        C=1.0,
        class_weight="balanced",
        max_iter=1000,
        random_state=42,
    )
    model.fit(X_train_scaled, y_train)

    probs = model.predict_proba(X_test_scaled)[:, 1]
    preds = (probs >= 0.5).astype(int)

    auc = roc_auc_score(y_test, probs)
    print(f"\n   ROC-AUC: {auc:.4f}")
    print(f"\n   Classification Report:\n{classification_report(y_test, preds)}")

    coef_df = pd.DataFrame({
        "feature": FEATURE_COLS,
        "coefficient": model.coef_[0],
    }).sort_values("coefficient", ascending=False)
    print("\n   Most influential features:")
    print(coef_df.head(6).to_string(index=False))

    model_package = {
        "model": model,
        "scaler": scaler,
        "feature_columns": FEATURE_COLS,
        "model_name": MODEL_NAME,
    }
    return model_package, auc


def save_model(model_package: dict, training_report: dict, output_dir: str = "models"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    artifact_path = output_path / "fraud_model.pkl"
    with artifact_path.open("wb") as model_file:
        pickle.dump(model_package, model_file)
    print(f"   Saved: {artifact_path}")

    versioned_path = output_path / f"fraud_model_{timestamp}.pkl"
    with versioned_path.open("wb") as model_file:
        pickle.dump(model_package, model_file)

    report_path = output_path / "training_report.json"
    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(training_report, report_file, indent=2)
    print(f"   Saved: {report_path}")

    print(f"\nModel saved to {output_path}/")
    print("\nNext step: Upload to Exasol BucketFS:")
    print(f"   curl -X PUT -T {artifact_path} \\")
    print("     http://YOUR_EXASOL_HOST:2580/models/fraud_model.pkl")


def main():
    args = parse_args()

    print("=" * 60)
    print("  SIMPLE FRAUD MODEL TRAINING PIPELINE")
    print("=" * 60)

    df, source_metadata = resolve_training_data(args)
    print_dataset_summary("Training dataset", df)

    for note in source_metadata["notes"]:
        print(f"   Note: {note}")

    X, y = preprocess(df)
    if len(np.unique(y)) < 2:
        raise SystemExit("Training dataset must contain both fraud and non-fraud examples.")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        stratify=y,
        random_state=42,
    )
    print(f"\n   Train: {len(X_train):,} | Test: {len(X_test):,}")

    fraud_model, fraud_auc = train_fraud_model(X_train, y_train, X_test, y_test)

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    print(f"  Fraud Model ROC-AUC : {fraud_auc:.4f}")

    dataset_stats = label_summary(df)
    training_report = {
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "requested_source": source_metadata["requested_source"],
        "effective_source": source_metadata["effective_source"],
        "model_name": MODEL_NAME,
        "real_rows": source_metadata["real_rows"],
        "synthetic_rows": source_metadata["synthetic_rows"],
        "dataset_rows": dataset_stats["rows"],
        "positive_labels": dataset_stats["positives"],
        "negative_labels": dataset_stats["negatives"],
        "fraud_rate": dataset_stats["fraud_rate"],
        "fraud_model_auc": float(fraud_auc),
        "feature_columns": FEATURE_COLS,
        "notes": source_metadata["notes"],
    }

    save_model(
        fraud_model,
        training_report=training_report,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()

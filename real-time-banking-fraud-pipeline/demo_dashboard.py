from __future__ import annotations

import html
import os
import ssl
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from uuid import uuid4

import pandas as pd
import psycopg2
import psycopg2.extras
import pyexasol
import streamlit as st


ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"
REFRESH_SQL_PATH = ROOT / "07_refresh_analytics_features.sql"

IMPORT_TRANSACTIONS_SQL = """
IMPORT INTO KAFKA_STAGE.TRANSACTIONS
FROM SCRIPT KAFKA_EXTENSION.KAFKA_CONSUMER WITH
  BOOTSTRAP_SERVERS   = '192.168.64.1:39092'
  SCHEMA_REGISTRY_URL = 'http://192.168.64.1:8081'
  RECORD_VALUE_FORMAT = 'avro'
  RECORD_FIELDS       = 'value.txn_id,value.account_id,value.card_id,value.txn_type,value.amount,value.currency,value.direction,value.merchant_name,value.merchant_mcc,value.merchant_id,value.channel,value.ip_address,value.device_id,value.device_fingerprint,value.country_code,value.city,value.latitude,value.longitude,value.counterparty_account,value.counterparty_bank,value.status,value.decline_reason,value.reference_id,value.initiated_at,value.settled_at,value.updated_at,value.__op,value.__deleted,timestamp'
  TOPIC_NAME          = 'banking_avro.public.transactions'
  TABLE_NAME          = 'KAFKA_STAGE.TRANSACTIONS'
  GROUP_ID            = 'exasol-kafka-transactions'
  CONSUME_ALL_OFFSETS = 'true'
"""

MERGE_TRANSACTIONS_SQL = """
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
)
"""

DELETE_TRANSACTIONS_SQL = """
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
)
"""

SCORE_ONE_TXN_SQL = """
UPDATE ANALYTICS.FRAUD_FEATURES
SET
    FRAUD_SCORE = ANALYTICS.FRAUD_SCORE_UDF(
        AMOUNT_USD,
        TXN_COUNT_1H,
        TXN_COUNT_24H,
        AMOUNT_SUM_1H,
        AMOUNT_SUM_24H,
        AMOUNT_VS_AVG_RATIO,
        IS_CROSS_BORDER,
        IS_NEW_COUNTRY_30D,
        IS_NEW_DEVICE_30D,
        IS_NIGHT_TXN,
        IS_WEEKEND_TXN,
        MCC_BASE_RISK
    ),
    MODEL_VERSION = 'LOGREG_DEMO_v1'
WHERE TXN_ID = '{txn_id}'
"""


@dataclass
class PostgresConfig:
    host: str
    port: int
    database: str
    user: str
    password: str


@dataclass
class ExasolConfig:
    dsn: str
    user: str
    password: str


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value)


load_env_file(ENV_PATH)


def get_postgres_config() -> PostgresConfig:
    use_external = os.getenv("USE_EXTERNAL_POSTGRES", "false").lower() == "true"
    if use_external:
        return PostgresConfig(
            host=os.getenv("EXTERNAL_POSTGRES_HOST", "host.docker.internal"),
            port=int(os.getenv("EXTERNAL_POSTGRES_PORT", "5432")),
            database=os.getenv("EXTERNAL_POSTGRES_DB", ""),
            user=os.getenv("EXTERNAL_POSTGRES_USER", ""),
            password=os.getenv("EXTERNAL_POSTGRES_PASSWORD", ""),
        )

    return PostgresConfig(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "banking"),
        user=os.getenv("POSTGRES_USER", ""),
        password=os.getenv("POSTGRES_PASSWORD", ""),
    )


def get_exasol_config() -> ExasolConfig:
    return ExasolConfig(
        dsn=os.getenv("EXASOL_DSN", ""),
        user=os.getenv("EXASOL_USER", ""),
        password=os.getenv("EXASOL_PASSWORD", ""),
    )


def pg_connect():
    cfg = get_postgres_config()
    return psycopg2.connect(
        host=cfg.host,
        port=cfg.port,
        dbname=cfg.database,
        user=cfg.user,
        password=cfg.password,
    )


def exa_connect():
    cfg = get_exasol_config()
    return pyexasol.connect(
        dsn=cfg.dsn,
        user=cfg.user,
        password=cfg.password,
        encryption=True,
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
    )


def fetch_postgres_dataframe(query: str, params: tuple | None = None) -> pd.DataFrame:
    with pg_connect() as conn:
        return pd.read_sql_query(query, conn, params=params)


def fetch_exasol_dataframe(query: str) -> pd.DataFrame:
    with exa_connect() as conn:
        stmt = conn.execute(query)
        rows = stmt.fetchall()
        columns = [name.lower() for name in stmt.column_names()]
        return pd.DataFrame(rows, columns=columns)


def execute_exasol(query: str) -> None:
    with exa_connect() as conn:
        conn.execute(query)


def iter_sql_statements(path: Path) -> Iterable[str]:
    current: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("--"):
            continue
        current.append(line)
        if stripped.endswith(";"):
            statement = "\n".join(current).strip()
            if statement:
                yield statement[:-1]
            current = []
    if current:
        statement = "\n".join(current).strip()
        if statement:
            yield statement


def run_refresh_analytics() -> None:
    with exa_connect() as conn:
        for statement in iter_sql_statements(REFRESH_SQL_PATH):
            conn.execute(statement)


def load_account_options() -> pd.DataFrame:
    query = """
    SELECT
        a.account_id::text AS account_id,
        c.customer_id::text AS customer_id,
        c.full_name,
        a.account_number,
        a.account_type,
        c.country_code,
        card.card_id::text AS card_id,
        card.masked_pan
    FROM accounts a
    JOIN customers c ON c.customer_id = a.customer_id
    LEFT JOIN LATERAL (
        SELECT card_id, masked_pan
        FROM cards
        WHERE account_id = a.account_id
          AND status = 'ACTIVE'
        ORDER BY issued_at DESC
        LIMIT 1
    ) card ON TRUE
    WHERE a.status = 'ACTIVE'
    ORDER BY c.full_name, a.account_number
    """
    return fetch_postgres_dataframe(query)


def load_mcc_options() -> pd.DataFrame:
    query = """
    SELECT mcc, description
    FROM mcc_codes
    ORDER BY mcc
    """
    return fetch_postgres_dataframe(query)


def insert_transaction(
    txn_id: str,
    reference_id: str,
    account_id: str,
    card_id: str | None,
    amount: float,
    merchant_name: str,
    merchant_mcc: str,
    channel: str,
    country_code: str,
    city: str,
) -> None:
    query = """
    INSERT INTO public.transactions (
        txn_id,
        account_id,
        card_id,
        txn_type,
        amount,
        currency,
        direction,
        merchant_name,
        merchant_mcc,
        channel,
        country_code,
        city,
        status,
        reference_id,
        initiated_at,
        settled_at
    ) VALUES (
        %s, %s, %s, 'PURCHASE', %s, 'USD', 'DR',
        %s, %s, %s, %s, %s, 'SETTLED', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
    )
    """
    with pg_connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                query,
                (
                    txn_id,
                    account_id,
                    card_id,
                    amount,
                    merchant_name,
                    merchant_mcc,
                    channel,
                    country_code,
                    city,
                    reference_id,
                ),
            )
        conn.commit()


def sync_transaction(reference_id: str, txn_id: str) -> None:
    stage_found = False
    for _ in range(6):
        execute_exasol(IMPORT_TRANSACTIONS_SQL)
        stage_df = fetch_exasol_dataframe(
            f"""
            SELECT txn_id
            FROM KAFKA_STAGE.TRANSACTIONS
            WHERE reference_id = '{reference_id}'
            """
        )
        if not stage_df.empty:
            stage_found = True
            break
        time.sleep(2)

    if not stage_found:
        raise RuntimeError("The transaction did not appear in KAFKA_STAGE.TRANSACTIONS in time.")

    execute_exasol(MERGE_TRANSACTIONS_SQL)
    execute_exasol(DELETE_TRANSACTIONS_SQL)
    run_refresh_analytics()
    execute_exasol(SCORE_ONE_TXN_SQL.format(txn_id=txn_id))


def query_pipeline_state(reference_id: str, txn_id: str) -> dict[str, pd.DataFrame]:
    postgres_df = fetch_postgres_dataframe(
        """
        SELECT
            txn_id::text AS txn_id,
            reference_id,
            amount,
            channel,
            status,
            updated_at
        FROM public.transactions
        WHERE reference_id = %s
        ORDER BY updated_at DESC
        """,
        (reference_id,),
    )

    stage_df = fetch_exasol_dataframe(
        f"""
        SELECT
            txn_id,
            reference_id,
            kafka_partition,
            kafka_offset,
            debezium_op
        FROM KAFKA_STAGE.TRANSACTIONS
        WHERE reference_id = '{reference_id}'
        ORDER BY kafka_offset DESC
        """
    )

    raw_df = fetch_exasol_dataframe(
        f"""
        SELECT
            txn_id,
            reference_id,
            amount,
            channel,
            kafka_offset,
            kafka_topic
        FROM RAW.TRANSACTIONS
        WHERE reference_id = '{reference_id}'
        """
    )

    feature_df = fetch_exasol_dataframe(
        f"""
        SELECT
            txn_id,
            account_id,
            customer_id,
            amount_usd,
            channel,
            amount_vs_avg_ratio,
            is_cross_border,
            is_new_device_30d,
            fraud_score,
            model_version
        FROM ANALYTICS.FRAUD_FEATURES
        WHERE txn_id = '{txn_id}'
        """
    )

    return {
        "postgres": postgres_df,
        "stage": stage_df,
        "raw": raw_df,
        "features": feature_df,
    }


def load_top_scores() -> pd.DataFrame:
    return fetch_exasol_dataframe(
        """
        SELECT
            txn_id,
            amount_usd,
            channel,
            merchant_mcc,
            txn_count_1h,
            txn_count_24h,
            amount_vs_avg_ratio,
            is_cross_border,
            is_new_device_30d,
            fraud_score,
            model_version
        FROM ANALYTICS.FRAUD_FEATURES
        WHERE fraud_score IS NOT NULL
        ORDER BY fraud_score DESC, feature_computed_at DESC
        LIMIT 10
        """
    )


def load_recent_transactions(limit: int = 20) -> pd.DataFrame:
    return fetch_postgres_dataframe(
        """
        SELECT
            txn_id::text AS txn_id,
            reference_id,
            amount,
            channel,
            updated_at
        FROM public.transactions
        WHERE reference_id IS NOT NULL
        ORDER BY updated_at DESC
        LIMIT %s
        """,
        (limit,),
    )


def connection_status() -> tuple[bool, bool]:
    postgres_ok = False
    exasol_ok = False
    try:
        _ = fetch_postgres_dataframe("SELECT 1 AS ok")
        postgres_ok = True
    except Exception:
        postgres_ok = False

    try:
        _ = fetch_exasol_dataframe("SELECT 1 AS ok")
        exasol_ok = True
    except Exception:
        exasol_ok = False

    return postgres_ok, exasol_ok


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Space+Grotesk:wght@500;700&display=swap');

        :root {
            --bg-top: #f4efe3;
            --bg-bottom: #f8fbff;
            --ink: #112235;
            --muted: #5d6e84;
            --teal: #0f766e;
            --teal-soft: #d7f3ef;
            --sand: #fff7ea;
            --amber: #c57d1f;
            --line: rgba(17, 34, 53, 0.10);
            --card: rgba(255, 255, 255, 0.82);
            --shadow: 0 18px 45px rgba(24, 48, 76, 0.10);
        }

        html, body, [class*="css"]  {
            font-family: "IBM Plex Sans", sans-serif;
            color: var(--ink);
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(223, 244, 238, 0.9), transparent 28%),
                radial-gradient(circle at top right, rgba(255, 236, 210, 0.75), transparent 24%),
                linear-gradient(180deg, var(--bg-top) 0%, var(--bg-bottom) 55%, #ffffff 100%);
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1280px;
        }

        h1, h2, h3 {
            font-family: "Space Grotesk", sans-serif;
            letter-spacing: -0.03em;
            color: var(--ink);
        }

        [data-testid="stSidebar"],
        [data-testid="collapsedControl"],
        [data-testid="stToolbar"],
        [data-testid="stHeaderActionElements"],
        #MainMenu,
        header[data-testid="stHeader"] {
            display: none;
        }

        .hero-shell {
            background:
                linear-gradient(135deg, rgba(9, 33, 48, 0.96) 0%, rgba(17, 42, 73, 0.94) 55%, rgba(147, 76, 31, 0.90) 100%);
            border-radius: 28px;
            padding: 1.8rem 1.9rem;
            box-shadow: var(--shadow);
            color: #f7fbff;
            margin-bottom: 1.35rem;
            overflow: hidden;
            position: relative;
        }

        .hero-shell::after {
            content: "";
            position: absolute;
            inset: auto -40px -40px auto;
            width: 220px;
            height: 220px;
            background: radial-gradient(circle, rgba(255,255,255,0.17), transparent 65%);
        }

        .hero-eyebrow {
            text-transform: uppercase;
            letter-spacing: 0.16em;
            font-size: 0.72rem;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.70);
            margin-bottom: 0.8rem;
        }

        .hero-title {
            font-family: "Space Grotesk", sans-serif;
            font-size: 2.2rem;
            line-height: 1.02;
            font-weight: 700;
            max-width: 13ch;
            margin-bottom: 0.7rem;
        }

        .hero-copy {
            max-width: 58rem;
            font-size: 1rem;
            line-height: 1.6;
            color: rgba(247, 251, 255, 0.82);
        }

        .signal-grid,
        .stage-grid {
            display: grid;
            gap: 0.85rem;
            margin-top: 1.15rem;
        }

        .signal-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .stage-grid {
            grid-template-columns: repeat(4, minmax(0, 1fr));
        }

        .signal-card,
        .stage-card,
        .note-card {
            border-radius: 22px;
            border: 1px solid var(--line);
            box-shadow: var(--shadow);
        }

        .signal-card {
            background: rgba(255, 255, 255, 0.10);
            border-color: rgba(255, 255, 255, 0.10);
            padding: 1rem;
            backdrop-filter: blur(8px);
        }

        .signal-label,
        .stage-label,
        .mini-kicker {
            text-transform: uppercase;
            letter-spacing: 0.12em;
            font-size: 0.68rem;
            font-weight: 700;
            margin-bottom: 0.35rem;
        }

        .signal-label {
            color: rgba(255, 255, 255, 0.62);
        }

        .signal-value {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.2rem;
            font-weight: 700;
        }

        .signal-meta {
            color: rgba(255, 255, 255, 0.70);
            font-size: 0.88rem;
            margin-top: 0.2rem;
        }

        .section-shell {
            margin: 0.1rem 0 1rem;
        }

        .section-kicker {
            text-transform: uppercase;
            letter-spacing: 0.16em;
            font-size: 0.7rem;
            font-weight: 700;
            color: var(--teal);
            margin-bottom: 0.25rem;
        }

        .section-title {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.5rem;
            margin: 0;
        }

        .section-copy {
            color: var(--muted);
            max-width: 64rem;
            margin-top: 0.3rem;
            line-height: 1.6;
        }

        .note-card {
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.82) 0%, rgba(250, 252, 255, 0.95) 100%);
            padding: 1.15rem 1.15rem;
        }

        .note-card.dark {
            background: linear-gradient(180deg, rgba(11, 34, 53, 0.96) 0%, rgba(19, 45, 69, 0.95) 100%);
            border-color: rgba(255, 255, 255, 0.08);
            color: #f6fbff;
        }

        .note-card p,
        .note-card ul {
            margin: 0.45rem 0 0;
            line-height: 1.55;
            color: inherit;
        }

        .stage-card {
            padding: 1rem;
            background: rgba(255, 255, 255, 0.84);
        }

        .stage-card.live {
            border-color: rgba(15, 118, 110, 0.30);
            background: linear-gradient(180deg, rgba(228, 250, 247, 0.96) 0%, rgba(255, 255, 255, 0.98) 100%);
        }

        .stage-card.waiting {
            opacity: 0.78;
        }

        .stage-step {
            font-family: "Space Grotesk", sans-serif;
            font-size: 1.15rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }

        .stage-detail {
            color: var(--muted);
            font-size: 0.92rem;
            line-height: 1.45;
        }

        .status-pill {
            display: inline-block;
            border-radius: 999px;
            padding: 0.2rem 0.65rem;
            font-size: 0.76rem;
            font-weight: 700;
            margin-top: 0.65rem;
        }

        .status-pill.live {
            background: rgba(15, 118, 110, 0.14);
            color: var(--teal);
        }

        .status-pill.waiting {
            background: rgba(197, 125, 31, 0.14);
            color: var(--amber);
        }

        .stForm {
            background: rgba(255, 255, 255, 0.74);
            border: 1px solid var(--line);
            border-radius: 26px;
            padding: 1.3rem 1.2rem 0.85rem;
            box-shadow: var(--shadow);
        }

        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid var(--line);
            border-radius: 22px;
            padding: 0.9rem 1rem;
            box-shadow: var(--shadow);
        }

        div[data-testid="stDataFrame"] {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid var(--line);
            border-radius: 22px;
            box-shadow: var(--shadow);
        }

        div[data-baseweb="tab-list"] {
            gap: 0.5rem;
            margin-bottom: 0.8rem;
        }

        button[data-baseweb="tab"] {
            border-radius: 999px;
            padding: 0.45rem 1rem;
            background: rgba(255, 255, 255, 0.66);
        }

        button[kind="primary"] {
            border: none;
            border-radius: 999px;
            background: linear-gradient(135deg, #0f766e 0%, #194f73 100%);
            color: #ffffff;
            font-weight: 700;
            box-shadow: 0 12px 24px rgba(15, 118, 110, 0.22);
        }

        .tiny-note {
            color: var(--muted);
            font-size: 0.92rem;
            margin-top: 0.35rem;
            line-height: 1.5;
        }

        @media (max-width: 1100px) {
            .signal-grid,
            .stage-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 720px) {
            .signal-grid,
            .stage-grid {
                grid-template-columns: 1fr;
            }

            .hero-title {
                font-size: 1.7rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(kicker: str, title: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="section-shell">
            <div class="section-kicker">{html.escape(kicker)}</div>
            <h2 class="section-title">{html.escape(title)}</h2>
            <div class="section-copy">{html.escape(copy)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero(postgres_ok: bool, exasol_ok: bool, account_count: int, mcc_count: int) -> None:
    st.markdown(
        f"""
        <section class="hero-shell">
            <div class="hero-eyebrow">Live Demo Control Surface</div>
            <div class="hero-title">Create a transaction and walk it from CDC to fraud scoring.</div>
            <div class="hero-copy">
                This screen is built for customer demos: generate a banking event in PostgreSQL, let Debezium stream it into Kafka,
                then land, enrich, and score it inside Exasol without leaving the story.
            </div>
            <div class="signal-grid">
                <div class="signal-card">
                    <div class="signal-label">PostgreSQL</div>
                    <div class="signal-value">{"Connected" if postgres_ok else "Check connection"}</div>
                    <div class="signal-meta">Source OLTP system for insert and CDC</div>
                </div>
                <div class="signal-card">
                    <div class="signal-label">Exasol</div>
                    <div class="signal-value">{"Connected" if exasol_ok else "Awaiting access"}</div>
                    <div class="signal-meta">Warehouse, feature engineering, and in-database scoring</div>
                </div>
                <div class="signal-card">
                    <div class="signal-label">Active Accounts</div>
                    <div class="signal-value">{account_count}</div>
                    <div class="signal-meta">Ready-to-demo customer accounts from PostgreSQL</div>
                </div>
                <div class="signal-card">
                    <div class="signal-label">Merchant Codes</div>
                    <div class="signal-value">{mcc_count}</div>
                    <div class="signal-meta">Available MCC options for the demo transaction</div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_account_summary(selected_account) -> None:
    st.markdown(
        f"""
        <div class="note-card">
            <div class="mini-kicker">Selected Account</div>
            <h3 style="margin:0;">{html.escape(selected_account.full_name)}</h3>
            <p><strong>Account</strong>: {html.escape(selected_account.account_number)}</p>
            <p><strong>Type</strong>: {html.escape(selected_account.account_type)}</p>
            <p><strong>Card</strong>: {html.escape(selected_account.masked_pan or "No active card")}</p>
            <p><strong>Country</strong>: {html.escape(selected_account.country_code or "US")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="note-card dark">
            <div class="mini-kicker">What the audience should notice</div>
            <p>The insert is operational. The score is analytical. The point of the demo is the handoff between the two.</p>
            <ul>
                <li>PostgreSQL creates the event.</li>
                <li>Debezium and Kafka carry the change in Avro.</li>
                <li>Exasol lands, enriches, and scores the transaction.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def score_metric_value(feature_df: pd.DataFrame) -> str:
    score_value = parse_score_value(feature_df)
    if score_value is not None:
        return f"{score_value:.5f}"
    return "Pending"


def reset_draft_ids() -> None:
    st.session_state["draft_txn_id"] = str(uuid4())
    st.session_state["draft_reference_id"] = f"UI-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def initialize_form_state() -> None:
    if st.session_state.pop("pending_reset_ids", False):
        reset_draft_ids()
        return

    if "draft_txn_id" not in st.session_state:
        st.session_state["draft_txn_id"] = str(uuid4())
    if "draft_reference_id" not in st.session_state:
        st.session_state["draft_reference_id"] = f"UI-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def parse_score_value(feature_df: pd.DataFrame) -> float | None:
    if feature_df.empty:
        return None

    raw_score = feature_df.iloc[0].get("fraud_score")
    return parse_numeric_value(raw_score)


def parse_numeric_value(raw_value) -> float | None:
    if pd.isna(raw_value):
        return None

    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def classify_risk_level(raw_score) -> str:
    score_value = parse_numeric_value(raw_score)
    if score_value is None:
        return "Pending"
    if score_value >= 0.65:
        return "High Risk"
    if score_value >= 0.35:
        return "Needs Review"
    return "Low Risk"


def style_risk_scoreboard(top_scores: pd.DataFrame):
    display_df = top_scores.copy()
    display_df["risk_level"] = display_df["fraud_score"].apply(classify_risk_level)

    def row_styles(row: pd.Series) -> list[str]:
        risk_level = row.get("risk_level", "")
        if risk_level == "High Risk":
            base_style = "background-color: rgba(194, 65, 12, 0.16);"
        elif risk_level == "Needs Review":
            base_style = "background-color: rgba(245, 158, 11, 0.12);"
        else:
            base_style = ""

        styles = [base_style] * len(row)
        if "risk_level" in row.index:
            risk_idx = list(row.index).index("risk_level")
            if risk_level == "High Risk":
                styles[risk_idx] = base_style + "font-weight: 700; color: #9a3412;"
            elif risk_level == "Needs Review":
                styles[risk_idx] = base_style + "font-weight: 700; color: #a16207;"
            elif risk_level == "Low Risk":
                styles[risk_idx] = "font-weight: 700; color: #166534;"
        return styles

    return display_df.style.apply(row_styles, axis=1).format(
        {
            "amount_usd": lambda v: f"${float(v):,.2f}" if parse_numeric_value(v) is not None else v,
            "fraud_score": lambda v: f"{float(v):.5f}" if parse_numeric_value(v) is not None else v,
            "amount_vs_avg_ratio": lambda v: f"{float(v):.2f}x" if parse_numeric_value(v) is not None else v,
        }
    )


st.set_page_config(
    page_title="Banking Fraud Demo Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_styles()

postgres_ok, exasol_ok = connection_status()

accounts_df = pd.DataFrame()
mcc_df = pd.DataFrame()
if postgres_ok:
    accounts_df = load_account_options()
    mcc_df = load_mcc_options()

render_hero(postgres_ok, exasol_ok, len(accounts_df.index), len(mcc_df.index))

if not postgres_ok:
    st.error("PostgreSQL is not reachable. Check Docker, .env, and your local ports before using the dashboard.")
    st.stop()

if accounts_df.empty:
    st.error("No active accounts were found in PostgreSQL.")
    st.stop()

account_options = {
    f"{row.full_name} | {row.account_type} | {row.account_number} | {row.masked_pan or 'No active card'}": row
    for row in accounts_df.itertuples(index=False)
}
mcc_options = {
    f"{row.mcc} - {row.description}": row.mcc
    for row in mcc_df.itertuples(index=False)
}

initialize_form_state()

first_account_label = next(iter(account_options))
if "selected_account_label" not in st.session_state or st.session_state["selected_account_label"] not in account_options:
    st.session_state["selected_account_label"] = first_account_label

selected_account = account_options[st.session_state["selected_account_label"]]
control_tab, trace_tab, leaderboard_tab = st.tabs(["Control Center", "Pipeline Trace", "Risk Score Board"])

with control_tab:
    render_section_header(
        "Create Event",
        "Generate a transaction for the live storyline",
        "Use one form to create a banking event in PostgreSQL. You can also trigger the Exasol-side import, merge, feature refresh, and scoring steps immediately after the insert.",
    )
    form_col, note_col = st.columns([1.7, 1], gap="large")

    with form_col:
        with st.form("insert-transaction-form"):
            selected_label = st.selectbox(
                "Account / Card",
                list(account_options.keys()),
                key="selected_account_label",
                help="Choose the customer account that will originate the demo transaction.",
            )
            selected_account = account_options[selected_label]

            col_a, col_b, col_c = st.columns(3)
            txn_id = col_a.text_input("Transaction ID", key="draft_txn_id")
            reference_id = col_b.text_input("Reference ID", key="draft_reference_id")
            amount = col_c.number_input("Amount (USD)", min_value=1.0, value=149.99, step=1.0)

            col_d, col_e, col_f = st.columns(3)
            merchant_name = col_d.text_input("Merchant Name", value="Demo Merchant")
            merchant_mcc_label = col_e.selectbox(
                "Merchant MCC",
                list(mcc_options.keys()),
                index=min(10, len(mcc_options) - 1),
            )
            channel = col_f.selectbox(
                "Channel",
                ["ONLINE", "POS", "ATM", "MOBILE", "API", "BRANCH", "UNKNOWN"],
                index=0,
            )

            col_g, col_h = st.columns(2)
            country_code = col_g.text_input("Country Code", value=selected_account.country_code or "US")
            city = col_h.text_input("City", value="Austin")

            auto_sync = st.checkbox(
                "Run Exasol import, merge, analytics refresh, and scoring after insert",
                value=True,
            )
            submitted = st.form_submit_button("Create Demo Transaction")

    with note_col:
        render_account_summary(selected_account)
        st.markdown(
            """
            <div class="tiny-note">
                For the best live demo, keep this screen open next to Kafka UI. Insert here, show the event arrive in Kafka,
                then return to the pipeline trace to show landing, merge, and scoring.
            </div>
            """,
            unsafe_allow_html=True,
        )

    if submitted:
        st.session_state["last_txn_id"] = txn_id
        st.session_state["last_reference_id"] = reference_id

        try:
            insert_transaction(
                txn_id=txn_id,
                reference_id=reference_id,
                account_id=selected_account.account_id,
                card_id=selected_account.card_id or None,
                amount=float(amount),
                merchant_name=merchant_name,
                merchant_mcc=mcc_options[merchant_mcc_label],
                channel=channel,
                country_code=country_code,
                city=city,
            )
            st.success(f"Inserted transaction {txn_id} into PostgreSQL.")
            st.session_state["pending_reset_ids"] = True

            if auto_sync:
                if not exasol_ok:
                    st.error("Exasol is not reachable, so the dashboard cannot continue the pipeline sync.")
                else:
                    with st.status("Running pipeline steps...", expanded=True) as status:
                        status.write("Waiting for Debezium / Kafka and importing the transaction into Exasol stage...")
                        sync_transaction(reference_id, txn_id)
                        status.write("Merged the transaction into the Exasol RAW layer.")
                        status.write("Refreshed analytics features.")
                        status.write("Scored the transaction with ANALYTICS.FRAUD_SCORE_UDF.")
                        status.update(label="Pipeline run completed", state="complete")
            st.rerun()
        except Exception as exc:
            st.error(f"Demo action failed: {exc}")


last_txn_id = st.session_state.get("last_txn_id")
last_reference_id = st.session_state.get("last_reference_id")

with trace_tab:
    render_section_header(
        "Trace Event",
        "Show how one transaction moves across the pipeline",
        "Use this section after the insert to prove that the same transaction exists in the source system, Kafka stage import layer, Exasol RAW layer, and Exasol analytical fraud feature layer.",
    )

    recent_transactions_df = load_recent_transactions()
    if (
        (not last_txn_id or not last_reference_id)
        and not recent_transactions_df.empty
        and pd.notna(recent_transactions_df.iloc[0]["reference_id"])
    ):
        st.session_state["last_txn_id"] = recent_transactions_df.iloc[0]["txn_id"]
        st.session_state["last_reference_id"] = recent_transactions_df.iloc[0]["reference_id"]
        last_txn_id = st.session_state["last_txn_id"]
        last_reference_id = st.session_state["last_reference_id"]

    if not recent_transactions_df.empty:
        lookup_options = {}
        for row in recent_transactions_df.itertuples(index=False):
            updated_label = str(row.updated_at)
            label = (
                f"{row.reference_id} | {row.txn_id[:8]}... | ${float(row.amount):.2f} | "
                f"{row.channel} | {updated_label}"
            )
            lookup_options[label] = (row.txn_id, row.reference_id)

        option_labels = list(lookup_options.keys())
        default_index = 0
        for idx, label in enumerate(option_labels):
            txn_value, ref_value = lookup_options[label]
            if txn_value == last_txn_id and ref_value == last_reference_id:
                default_index = idx
                break

        lookup_col, action_col = st.columns([4, 1], gap="small")
        selected_lookup_label = lookup_col.selectbox(
            "Recent tracked transactions",
            option_labels,
            index=default_index,
            help="Switch the trace view to a previously created transaction.",
        )
        if action_col.button("Load Trace", use_container_width=True):
            selected_txn_id, selected_reference_id = lookup_options[selected_lookup_label]
            st.session_state["last_txn_id"] = selected_txn_id
            st.session_state["last_reference_id"] = selected_reference_id
            st.rerun()

    if last_txn_id and last_reference_id:
        try:
            state = query_pipeline_state(last_reference_id, last_txn_id)
            st.markdown(
                """
                <div class="tiny-note" style="margin-bottom:0.9rem;">
                    Use the metrics and tables below as the live proof points: source insert, Kafka stage import, Exasol RAW merge, and final fraud score.
                </div>
                """,
                unsafe_allow_html=True,
            )

            metrics = st.columns(4)
            metrics[0].metric("PostgreSQL Rows", len(state["postgres"]))
            metrics[1].metric("Kafka Stage Rows", len(state["stage"]))
            metrics[2].metric("Exasol RAW Rows", len(state["raw"]))
            metrics[3].metric("Exasol Fraud Score", score_metric_value(state["features"]))

            details_tabs = st.tabs(["PostgreSQL", "Kafka Stage", "Exasol RAW", "Exasol Analytical Fraud Features"])
            with details_tabs[0]:
                st.dataframe(state["postgres"], use_container_width=True, hide_index=True)
            with details_tabs[1]:
                st.dataframe(state["stage"], use_container_width=True, hide_index=True)
            with details_tabs[2]:
                st.dataframe(state["raw"], use_container_width=True, hide_index=True)
            with details_tabs[3]:
                st.dataframe(state["features"], use_container_width=True, hide_index=True)
        except Exception as exc:
            st.warning(f"Could not load pipeline state for the tracked transaction: {exc}")
    else:
        st.info("Create a transaction from the Control Center tab to start tracking it here.")


with leaderboard_tab:
    render_section_header(
        "Explain the Score",
        "Show the highest-risk transactions in the analytics layer",
        "This table is useful at the end of the demo when you want to pivot from data movement to business impact and model-driven prioritization.",
    )
    if exasol_ok:
        try:
            top_scores = load_top_scores()
            high_risk_count = top_scores["fraud_score"].apply(classify_risk_level).eq("High Risk").sum() if not top_scores.empty else 0
            review_count = top_scores["fraud_score"].apply(classify_risk_level).eq("Needs Review").sum() if not top_scores.empty else 0
            low_risk_count = top_scores["fraud_score"].apply(classify_risk_level).eq("Low Risk").sum() if not top_scores.empty else 0

            leaderboard_metrics = st.columns(3)
            leaderboard_metrics[0].metric("High Risk Rows", int(high_risk_count))
            leaderboard_metrics[1].metric("Needs Review Rows", int(review_count))
            leaderboard_metrics[2].metric("Low Risk Rows", int(low_risk_count))

            st.markdown(
                """
                <div class="tiny-note" style="margin-bottom:0.9rem;">
                    High risk rows are highlighted more strongly. Review rows are highlighted lightly so you can distinguish them from the lower-risk baseline.
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.dataframe(style_risk_scoreboard(top_scores), use_container_width=True, hide_index=True)
        except Exception as exc:
            st.warning(f"Could not load top scored transactions: {exc}")
    else:
        st.info("Connect Exasol to view the scored transactions table.")

"""
Pipeline plumbing for the story demo.

Everything that talks to Postgres, Kafka or Exasol lives here so the Streamlit
app stays presentation code. Reuses the proven SQL from demo_dashboard.py rather
than reinventing it -- with one important change, see TUNED_IMPORT below.
"""
from __future__ import annotations

import os, re, ssl, time, uuid, pickle
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import psycopg2
import psycopg2.extras
import pyexasol

ROOT = Path(__file__).resolve().parent.parent
REFRESH_SQL = ROOT / "07_refresh_analytics_features.sql"
IMPORTS_SQL = ROOT / "05_exasol_kafka_connector_import_avro.sql"
MERGES_SQL  = ROOT / "06_exasol_kafka_connector_merge.sql"
MODEL_PATH = ROOT / "models" / "fraud_model.pkl"

# The persona created by seed_story_persona.py
ACCOUNT_ID = "e1e0a000-0000-4000-8000-000000000002"
CARD_ID    = "e1e0a000-0000-4000-8000-000000000003"
PERSONA    = "Elena Fischer"
ACCOUNT_NO = "ACC-90000001"
HOME_DEVICE, HOME_CITY, HOME_COUNTRY = "DEV-ELENA-IPHONE-13", "Austin", "US"

STORY_REF_PREFIX = "STORY-"


def _load_env() -> None:
    for line in (ROOT / ".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


_load_env()

_dash = (ROOT / "demo_dashboard.py").read_text()


def _const(name: str) -> str:
    return re.search(rf'^{name} = """(.*?)"""', _dash, re.S | re.M).group(1)


BASE_IMPORT   = _const("IMPORT_TRANSACTIONS_SQL")
MERGE_SQL     = _const("MERGE_TRANSACTIONS_SQL")
DELETE_SQL    = _const("DELETE_TRANSACTIONS_SQL")
SCORE_ONE_SQL = _const("SCORE_ONE_TXN_SQL")

# --- the single most important line in this demo -----------------------------
# The connector defaults to POLL_TIMEOUT_MS=30000 and MIN_RECORDS_PER_RUN=100.
# Importing one transaction therefore sits in an empty poll waiting for 99 more
# that never arrive: measured at 62 SECONDS per import, 92s when idle.
# Dropping the poll window takes the whole pipeline from 62.96s to 3.32s.
# Below ~400ms there is no further gain -- the remaining ~2.6s is JVM startup
# inside the UDF sandbox.
TUNED_IMPORT = BASE_IMPORT.rstrip().rstrip(";") + """
  POLL_TIMEOUT_MS     = '400'
  MIN_RECORDS_PER_RUN = '1'
  MAX_RECORDS_PER_RUN = '5000'
"""

FEATURE_COLS = [
    "AMOUNT_USD", "TXN_COUNT_1H", "TXN_COUNT_24H",
    "AMOUNT_SUM_1H", "AMOUNT_SUM_24H", "AMOUNT_VS_AVG_RATIO",
    "IS_CROSS_BORDER", "IS_NEW_COUNTRY_30D", "IS_NEW_DEVICE_30D",
    "IS_NIGHT_TXN", "IS_WEEKEND_TXN", "MCC_BASE_RISK",
]

# Human labels, for the attribution panel. The audience should never read a
# column name.
FEATURE_LABELS = {
    "AMOUNT_USD":          "Amount",
    "TXN_COUNT_1H":        "Transactions in the last hour",
    "TXN_COUNT_24H":       "Transactions in the last 24 hours",
    "AMOUNT_SUM_1H":       "Spend in the last hour",
    "AMOUNT_SUM_24H":      "Spend in the last 24 hours",
    "AMOUNT_VS_AVG_RATIO": "Size vs her normal spend",
    "IS_CROSS_BORDER":     "Outside her home country",
    "IS_NEW_COUNTRY_30D":  "Country never seen before",
    "IS_NEW_DEVICE_30D":   "Device never seen before",
    "IS_NIGHT_TXN":        "Middle of the night",
    "IS_WEEKEND_TXN":      "Weekend",
    "MCC_BASE_RISK":       "Merchant category risk",
}


def pg_connect():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"), port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DB"), user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
    )


def exa_connect():
    return pyexasol.connect(
        dsn=os.getenv("EXASOL_DSN"), user=os.getenv("EXASOL_USER"),
        password=os.getenv("EXASOL_PASSWORD"), encryption=True,
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
    )


def _tune(stmt: str) -> str:
    """Apply the fast-poll settings to any connector IMPORT statement."""
    return stmt.rstrip().rstrip(";") + (
        "\n  POLL_TIMEOUT_MS     = '400'"
        "\n  MIN_RECORDS_PER_RUN = '1'"
        "\n  MAX_RECORDS_PER_RUN = '5000'\n"
    )


def _split(path: Path):
    txt = re.sub(r"--[^\n]*", "", path.read_text())
    return [s.strip() for s in txt.split(";") if s.strip()]


def entity_import_statements():
    """
    All five topic imports (transactions, accounts, customers, cards, alerts),
    tuned.

    The story persona needs more than the transactions topic: ANALYTICS's base
    CTE inner-joins DIM_ACCOUNTS and DIM_CUSTOMERS, so a new customer whose
    account row has not been imported has *all* of their transactions silently
    dropped from the feature table. That is not an error anywhere -- the rows
    simply never appear.
    """
    return [_tune(s) for s in _split(IMPORTS_SQL) if s.upper().startswith("IMPORT")]


def entity_merge_statements():
    return _split(MERGES_SQL)


def exa_connect_as(user: str, password: str):
    """
    Connect as a persona rather than SYS.

    This is the whole security model: the agent's reach is decided by which
    database user its MCP server authenticated as, not by anything in a prompt.
    """
    return pyexasol.connect(
        dsn=os.getenv("EXASOL_DSN"), user=user, password=password, encryption=True,
        websocket_sslopt={"cert_reqs": ssl.CERT_NONE},
    )


def refresh_statements():
    txt = re.sub(r"--[^\n]*", "", REFRESH_SQL.read_text())
    return [s.strip() for s in txt.split(";") if s.strip()]


@dataclass
class Hop:
    name: str
    ms: float


@dataclass
class Result:
    txn_id: str
    reference_id: str
    label: str = ""
    hops: list = field(default_factory=list)
    features: dict = field(default_factory=dict)
    score: float | None = None
    kafka_offset: int | None = None
    kafka_partition: int | None = None
    staged: bool = False

    @property
    def total_ms(self) -> float:
        return sum(h.ms for h in self.hops)

    @property
    def analytics_ms(self) -> float:
        """Merge + features + score. The import hop is JVM startup, not analysis."""
        return sum(h.ms for h in self.hops if h.name in ("raw", "features", "score"))

    @property
    def verdict(self) -> str:
        if self.score is None:
            return "PENDING"
        if self.score >= 0.70:
            return "BLOCK"
        if self.score >= 0.30:
            return "REVIEW"
        return "APPROVE"


def insert_transaction(cur, amount, merchant, mcc, channel, country, city, device,
                       initiated_at=None):
    txn_id = str(uuid.uuid4())
    ref = f"{STORY_REF_PREFIX}{uuid.uuid4().hex[:10]}"
    when = initiated_at or datetime.now()
    cur.execute("""
        INSERT INTO transactions (txn_id, account_id, card_id, txn_type, amount, currency,
                                  direction, merchant_name, merchant_mcc, channel, device_id,
                                  country_code, city, status, reference_id, initiated_at, settled_at)
        VALUES (%s,%s,%s,'PURCHASE',%s,'USD','DR',%s,%s,%s,%s,%s,%s,'SETTLED',%s,%s,%s)
    """, (txn_id, ACCOUNT_ID, CARD_ID, amount, merchant, mcc, channel, device,
          country, city, ref, when, when))
    return txn_id, ref


def run_event(amount, merchant, mcc, channel, country, city, device,
              on_stage=None, label="") -> Result:
    """
    Insert one transaction and walk it all the way to a score, timing each hop.

    `on_stage(name, state, ms)` is called as each stage starts and finishes so
    the UI can light up progressively instead of freezing until the end.
    """
    def emit(name, state, ms=None):
        if on_stage:
            on_stage(name, state, ms)

    pg, ex = pg_connect(), exa_connect()
    cur = pg.cursor()
    try:
        emit("postgres", "running")
        t = time.time()
        txn_id, ref = insert_transaction(cur, amount, merchant, mcc, channel,
                                         country, city, device)
        pg.commit()
        res = Result(txn_id=txn_id, reference_id=ref, label=label or (
            f"${amount:,.2f} · {merchant} · {channel} · {country}"
            + (" · unrecognised device" if device != HOME_DEVICE else " · her own device")))
        ms = (time.time() - t) * 1000
        res.hops.append(Hop("postgres", ms)); emit("postgres", "done", ms)

        emit("kafka", "running")
        t = time.time()
        for _ in range(15):
            stage_import(ex)
            row = ex.execute(
                f"SELECT KAFKA_PARTITION, KAFKA_OFFSET FROM KAFKA_STAGE.TRANSACTIONS "
                f"WHERE REFERENCE_ID = '{ref}'"
            ).fetchall()
            if row:
                res.staged = True
                res.kafka_partition, res.kafka_offset = int(row[0][0]), int(row[0][1])
                break
            time.sleep(0.25)
        ms = (time.time() - t) * 1000
        res.hops.append(Hop("kafka", ms)); emit("kafka", "done", ms)

        emit("raw", "running")
        t = time.time()
        ex.execute(MERGE_SQL); ex.execute(DELETE_SQL)
        ms = (time.time() - t) * 1000
        res.hops.append(Hop("raw", ms)); emit("raw", "done", ms)

        emit("features", "running")
        t = time.time()
        for s in refresh_statements():
            ex.execute(s)
        ms = (time.time() - t) * 1000
        res.hops.append(Hop("features", ms)); emit("features", "done", ms)

        emit("score", "running")
        t = time.time()
        ex.execute(SCORE_ONE_SQL.format(txn_id=txn_id))
        ms = (time.time() - t) * 1000
        res.hops.append(Hop("score", ms)); emit("score", "done", ms)

        import runlog
        cols = ", ".join(FEATURE_COLS)
        row = ex.execute(
            f"SELECT {cols}, FRAUD_SCORE FROM ANALYTICS.FRAUD_FEATURES WHERE TXN_ID='{txn_id}'"
        ).fetchall()
        if row:
            vals = row[0]
            res.features = {c: vals[i] for i, c in enumerate(FEATURE_COLS)}
            res.score = float(vals[-1])
        try:
            runlog.log_event(res)
        except Exception:
            pass
        return res
    finally:
        cur.close(); pg.close(); ex.close()


# Rows deleted in Postgres reach RAW (the merge script applies Debezium deletes)
# but NOTHING removes them from CLEANSED or ANALYTICS -- the refresh only ever
# MERGEs. Left alone, every deleted transaction lingers in the velocity windows
# forever, so TXN_COUNT_1H creeps up on every rehearsal and the same demo scores
# higher each time it is run. These two statements are the fix.
PRUNE_ORPHANS = [
    """DELETE FROM RAW.FRAUD_ALERTS a
       WHERE NOT EXISTS (SELECT 1 FROM RAW.TRANSACTIONS r WHERE r.TXN_ID = a.TXN_ID)""",
    """DELETE FROM CLEANSED.FACT_TRANSACTIONS c
       WHERE NOT EXISTS (SELECT 1 FROM RAW.TRANSACTIONS r WHERE r.TXN_ID = c.TXN_ID)""",
    """DELETE FROM ANALYTICS.FRAUD_FEATURES a
       WHERE NOT EXISTS (SELECT 1 FROM RAW.TRANSACTIONS r WHERE r.TXN_ID = a.TXN_ID)""",
]


def reset_story():
    """
    Put the demo back to its opening state: the 30-day history survives, every
    transaction the story created is removed, all the way down to ANALYTICS.

    Returns (rows_removed_in_postgres, orphans_pruned_in_exasol).
    """
    pg, ex = pg_connect(), exa_connect()
    cur = pg.cursor()
    try:
        # Sweep STORY- rows on EVERY account, not just the persona's. An earlier
        # version scoped this to ACCOUNT_ID, so test transactions fired against
        # other customers during development were orphaned -- they survived every
        # reset and turned up later as "fraud" in another analyst's book.
        # Review alerts first: fraud_alerts.txn_id references transactions.
        cur.execute(
            """DELETE FROM fraud_alerts WHERE txn_id IN
               (SELECT txn_id FROM transactions WHERE reference_id LIKE %s)""",
            (STORY_REF_PREFIX + "%",))
        cur.execute(
            "DELETE FROM transactions WHERE reference_id LIKE %s",
            (STORY_REF_PREFIX + "%",))
        removed = cur.rowcount
        pg.commit()

        # Let the deletes travel: Debezium -> Kafka -> stage -> RAW. Wait for
        # them rather than making a fixed number of passes: a connector pass
        # takes ~2.6s (JVM start), which happened to give Debezium time to
        # publish, but a host-staging pass takes milliseconds and finished
        # before the deletes arrived -- leaving yesterday's rehearsal inside
        # every velocity window.
        for _ in range(40):
            stage_import(ex)
            stage_import(ex, ALERTS_IMPORT, **ALERTS_HOST)
            ex.execute(MERGE_SQL)
            ex.execute(DELETE_SQL)
            for stmt in ALERT_MERGES:
                ex.execute(stmt)
            left = ex.execute(
                "SELECT COUNT(*) FROM RAW.TRANSACTIONS WHERE REFERENCE_ID LIKE "
                + _lit(STORY_REF_PREFIX + "%")).fetchone()[0]
            if not left:
                break
            time.sleep(0.5)

        pruned = 0
        for stmt in PRUNE_ORPHANS:
            ex.execute(stmt)
            pruned += ex.last_statement().rowcount() or 0

        for stmt in refresh_statements():
            ex.execute(stmt)
        return removed, pruned
    finally:
        cur.close(); pg.close(); ex.close()


def sync_history(passes: int = 2):
    """
    Full sync: import every entity topic, merge them all into RAW, rebuild
    features. Used after seeding the persona, and as the repair step if the
    layers ever drift apart.
    """
    ex = exa_connect()
    try:
        for _ in range(passes):
            for stmt in entity_import_statements():
                ex.execute(stmt)
        for stmt in entity_merge_statements():
            ex.execute(stmt)
        for stmt in refresh_statements():
            ex.execute(stmt)
    finally:
        ex.close()


_model_cache = {}


def attribution(features: dict):
    """
    Exact per-feature contribution for the logistic-regression score.

    contribution_i = coefficient_i * scaled_value_i, and
    sigmoid(sum(contributions) + intercept) reproduces the UDF's score to ~1e-6.
    So this is arithmetic, not an approximation or a SHAP-style estimate.
    """
    if "pkg" not in _model_cache:
        with MODEL_PATH.open("rb") as f:
            _model_cache["pkg"] = pickle.load(f)
    pkg = _model_cache["pkg"]
    model, scaler, cols = pkg["model"], pkg["scaler"], pkg["feature_columns"]

    vals = np.array([[float(features.get(c) or 0) for c in cols]])
    scaled = scaler.transform(vals)[0]
    contribs = scaled * model.coef_[0]
    logit = float(contribs.sum() + model.intercept_[0])
    recomputed = 1.0 / (1.0 + np.exp(-logit))

    items = [
        {"column": c, "label": FEATURE_LABELS.get(c, c),
         "value": features.get(c), "contribution": float(contribs[i])}
        for i, c in enumerate(cols)
    ]
    items.sort(key=lambda d: -abs(d["contribution"]))
    return {"items": items, "intercept": float(model.intercept_[0]),
            "logit": logit, "recomputed_score": float(recomputed),
            "model_name": pkg.get("model_name", "model")}


def connection_health():
    out = {}
    try:
        pg = pg_connect(); c = pg.cursor()
        # Only the seeded history, not whatever the story has just created --
        # otherwise the masthead count creeps up during the demo.
        c.execute("SELECT count(*) FROM transactions WHERE account_id=%s "
                  "AND reference_id LIKE 'HIST-%%'", (ACCOUNT_ID,))
        out["postgres"] = {"ok": True, "history_rows": c.fetchone()[0]}
        pg.close()
    except Exception as e:
        out["postgres"] = {"ok": False, "error": str(e)[:120]}
    try:
        ex = exa_connect()
        n = ex.execute("SELECT count(*) FROM ANALYTICS.FRAUD_FEATURES").fetchall()[0][0]
        out["exasol"] = {"ok": True, "scored_rows": int(n)}
        ex.close()
    except Exception as e:
        out["exasol"] = {"ok": False, "error": str(e)[:120]}
    return out


# ---------------------------------------------------------------------------
# Reading the Kafka topic directly, so the demo can show genuine events rather
# than describing them. Uses assign() at an explicit offset -- never subscribe()
# -- so there is no consumer group coordination and the connector's own
# consumption is untouched.
# ---------------------------------------------------------------------------
# The IMPORT addresses are the ones Exasol reaches the broker on, which need
# not be reachable from this host -- DEMO_KAFKA_* overrides them for the reader.
KAFKA_BOOTSTRAP = os.getenv("DEMO_KAFKA_BOOTSTRAP") or re.search(
    r"BOOTSTRAP_SERVERS\s*=\s*'([^']+)'", BASE_IMPORT).group(1)
SCHEMA_REGISTRY = os.getenv("DEMO_SCHEMA_REGISTRY") or re.search(
    r"SCHEMA_REGISTRY_URL\s*=\s*'([^']+)'", BASE_IMPORT).group(1)
KAFKA_TOPIC = re.search(r"TOPIC_NAME\s*=\s*'([^']+)'", BASE_IMPORT).group(1)

_kafka = {}


def _consumer():
    from confluent_kafka import Consumer
    if "c" not in _kafka:
        _kafka["c"] = Consumer({
            "bootstrap.servers": KAFKA_BOOTSTRAP,
            "group.id": "story-demo-tail",
            "enable.auto.commit": False,
            "socket.timeout.ms": 4000,
        })
    return _kafka["c"]


def _deserializer():
    from confluent_kafka.schema_registry import SchemaRegistryClient
    from confluent_kafka.schema_registry.avro import AvroDeserializer
    if "d" not in _kafka:
        _kafka["d"] = AvroDeserializer(SchemaRegistryClient({"url": SCHEMA_REGISTRY}))
    return _kafka["d"]


# ---------------------------------------------------------------------------
# Staging fallback. The official path is Exasol's own Kafka connector (the
# IMPORT above), which needs Exasol to reach the broker. Where it cannot --
# a host firewall between a local Exasol VM and Docker, for example -- this app reads the same topic on localhost and writes the same
# rows into KAFKA_STAGE.TRANSACTIONS, partition and offset included. Because
# the connector resumes from the offsets stored in that table, either path can
# take over from the other with nothing skipped or duplicated.
#
# DEMO_STAGE_MODE: auto (default: connector, fall back on E-KCE-24) |
#                  connector (never fall back) | host (always use this path)
# ---------------------------------------------------------------------------
STAGE_MODE = os.getenv("DEMO_STAGE_MODE", "auto").lower()


def _vm_can_reach_broker() -> bool:
    """
    The connector only reports E-KCE-24 after a ~60s timeout -- far too long
    for a first click on stage. The VM's traffic arrives at this host exactly
    like a connection to the IMPORT's own address from here would, so a
    2-second probe of that address predicts the outcome.
    """
    import socket, struct
    host, port = re.search(r"BOOTSTRAP_SERVERS\s*=\s*'([^':]+):(\d+)'", BASE_IMPORT).groups()
    if host in ("localhost", "127.0.0.1") or "." not in host:
        return True     # a Docker service name or loopback: nothing to predict
    # Kafka ApiVersions v0 (api_key 18, correlation 1, client "demo"). A blocked
    # path accepts the TCP connection and then closes it without answering.
    body = struct.pack(">hhih", 18, 0, 1, 4) + b"demo"
    try:
        with socket.create_connection((host, int(port)), timeout=2) as sock:
            sock.settimeout(2)
            sock.sendall(struct.pack(">i", len(body)) + body)
            return len(sock.recv(4)) == 4
    except OSError:
        return False


_stage = {"host": STAGE_MODE == "host"
          or (STAGE_MODE == "auto" and not _vm_can_reach_broker())}

STAGE_FIELDS = [
    "txn_id", "account_id", "card_id", "txn_type", "amount", "currency", "direction",
    "merchant_name", "merchant_mcc", "merchant_id", "channel", "ip_address", "device_id",
    "device_fingerprint", "country_code", "city", "latitude", "longitude",
    "counterparty_account", "counterparty_bank", "status", "decline_reason",
    "reference_id", "initiated_at", "settled_at", "updated_at", "__op", "__deleted",
]


def staging_via_host() -> bool:
    """True once the fallback is in use, so the UI can say so."""
    return _stage["host"]


def host_stage(ex, max_wait: float = 2.0, topic: str | None = None,
               table: str = "KAFKA_STAGE.TRANSACTIONS", fields=None) -> int:
    """Copy messages past the staged offsets from Kafka into a KAFKA_STAGE table."""
    from confluent_kafka import Consumer, TopicPartition
    from confluent_kafka.serialization import SerializationContext, MessageField
    topic, fields = topic or KAFKA_TOPIC, fields or STAGE_FIELDS
    staged = dict(ex.execute(
        f"SELECT KAFKA_PARTITION, MAX(KAFKA_OFFSET) FROM {table} "
        "GROUP BY KAFKA_PARTITION").fetchall())
    staged = {int(p): int(o) for p, o in staged.items()}
    c = Consumer({"bootstrap.servers": KAFKA_BOOTSTRAP, "group.id": "story-demo-stage",
                  "enable.auto.commit": False, "socket.timeout.ms": 4000})
    try:
        md = c.list_topics(topic, timeout=5).topics[topic]
        assign, want = [], 0
        for p in md.partitions:
            lo, hi = c.get_watermark_offsets(TopicPartition(topic, p), timeout=5)
            start = max(lo, staged.get(p, -1) + 1)
            if hi > start:
                assign.append(TopicPartition(topic, p, start))
                want += hi - start
        if not assign:
            return 0
        c.assign(assign)
        deser, rows, deadline = _deserializer(), [], time.time() + max_wait
        while len(rows) < want and time.time() < deadline:
            m = c.poll(0.2)
            if m is None or m.error() or m.value() is None:
                continue
            v = deser(m.value(), SerializationContext(topic, MessageField.VALUE)) or {}
            vals = [v.get(f) for f in fields]
            rows.append("(" + ", ".join(
                "NULL" if x is None else (repr(x) if isinstance(x, (int, float))
                                          and not isinstance(x, bool)
                                          else "'" + str(x).replace("'", "''") + "'")
                for x in vals)
                + f", FROM_POSIX_TIME({m.timestamp()[1] / 1000:.3f}),"
                  f" {m.partition()}, {m.offset()})")
    finally:
        c.close()
    for i in range(0, len(rows), 200):
        ex.execute(f"INSERT INTO {table} VALUES " + ", ".join(rows[i:i + 200]))
    return len(rows)


def stage_import(ex, stmt: str | None = None, **host) -> None:
    """One pass of Kafka -> KAFKA_STAGE, by the connector when it can reach Kafka."""
    if not _stage["host"]:
        try:
            ex.execute(stmt or TUNED_IMPORT)
            return
        except Exception as exc:
            if STAGE_MODE == "connector" or "E-KCE-24" not in str(exc):
                raise
            _stage["host"] = True   # the VM cannot reach the broker; stop paying the timeout
    host_stage(ex, **host)


# ---------------------------------------------------------------------------
# Human review. A payment scored into the REVIEW band is held, and an alert is
# opened where analysts actually work -- the operational database. Their
# decision is an ordinary UPDATE in PostgreSQL, so it travels the same road as
# the payment did: Debezium -> Kafka -> Exasol, where the analytics refresh
# turns CONFIRMED_FRAUD / FALSE_POSITIVE into FRAUD_LABEL -- the column the
# model is retrained on (train_pipeline.py --source exasol).
# ---------------------------------------------------------------------------
ALERTS_IMPORT = next(s for s in entity_import_statements() if "KAFKA_STAGE.FRAUD_ALERTS" in s)
ALERTS_TOPIC = re.search(r"TOPIC_NAME\s*=\s*'([^']+)'", ALERTS_IMPORT).group(1)
ALERT_FIELDS = ["alert_id", "txn_id", "alert_type", "fraud_score", "risk_score", "status",
                "investigator", "notes", "created_at", "resolved_at", "__op", "__deleted"]
ALERT_MERGES = [s for s in entity_merge_statements() if "RAW.FRAUD_ALERTS" in s]
ALERTS_HOST = dict(topic=ALERTS_TOPIC, table="KAFKA_STAGE.FRAUD_ALERTS", fields=ALERT_FIELDS)

# The "needs review" preset: a wire to a new payee, from her own phone, at
# home. Nothing is wrong except the size and the category -- exactly the case
# a model should not decide alone. When velocity is already high (many clicks
# without a reset), even a small wire scores BLOCK, so lower-risk categories
# are tried as well.
REVIEW_PRESET = dict(merchant="Summit Wire Transfer", mcc="4829", channel="MOBILE",
                     country="US", city="Austin")
REVIEW_PROFILES = [  # (merchant, mcc, base risk) -- the wire is preferred
    ("Summit Wire Transfer", "4829", 0.60),
    ("PixelStore Digital", "5816", 0.30),
    ("Metro Electronics", "5045", 0.20),
]
REVIEW_BAND = (0.32, 0.68)       # inside REVIEW (0.30-0.70) with a little margin


def borderline_payment(target: float = 0.5):
    """
    The payment the model is least sure about *right now*, or None.

    The score is steep in amount and depends on velocity (a $450 wire is REVIEW
    as the first payment of the hour and BLOCK as the third), so a fixed preset
    only lands in REVIEW if the presenter clicks in one particular order. This
    reproduces the features the refresh will compute for the new payment --
    same windows as 07_refresh_analytics_features.sql -- asks the real UDF for
    every candidate amount and category in one statement, and picks the one
    closest to `target`. The score shown afterwards is still the one the
    pipeline computes; this only chooses the payment. Returns None when nothing
    lands in the review band -- the caller asks for a reset rather than firing
    a payment that would be BLOCKED.
    """
    now = datetime.now()
    ts = f"TIMESTAMP '{now:%Y-%m-%d %H:%M:%S}'"
    ex = exa_connect()
    try:
        c1h, s1h, c24h, s24h, avg30 = ex.execute(f"""
            SELECT COUNT(CASE WHEN INITIATED_AT >= {ts} - INTERVAL '1' HOUR THEN 1 END),
                   COALESCE(SUM(CASE WHEN INITIATED_AT >= {ts} - INTERVAL '1' HOUR
                                     THEN AMOUNT_USD END), 0),
                   COUNT(CASE WHEN INITIATED_AT >= {ts} - INTERVAL '24' HOUR THEN 1 END),
                   COALESCE(SUM(CASE WHEN INITIATED_AT >= {ts} - INTERVAL '24' HOUR
                                     THEN AMOUNT_USD END), 0),
                   AVG(CASE WHEN INITIATED_AT >= {ts} - INTERVAL '30' DAY
                            THEN AMOUNT_USD END)
            FROM CLEANSED.FACT_TRANSACTIONS
            WHERE ACCOUNT_ID = '{ACCOUNT_ID}' AND INITIATED_AT < {ts}""").fetchone()
        avg30 = float(avg30 or 30.0)
        night = "TRUE" if now.hour >= 22 or now.hour < 6 else "FALSE"
        weekend = "TRUE" if now.weekday() >= 5 else "FALSE"
        amounts = (list(range(10, 100, 5)) + list(range(100, 1000, 25))
                   + list(range(1000, 9001, 250)))
        # One statement over one row set: a single UDF invocation for every
        # candidate. (A UNION ALL of per-candidate SELECTs started one Python VM
        # per branch and took ~30s.)
        values = ", ".join(f"({x}, {i})" for i, (_, _, _) in enumerate(REVIEW_PROFILES)
                           for x in amounts)
        risk = " ".join(f"WHEN {i} THEN {r}" for i, (_, _, r) in enumerate(REVIEW_PROFILES))
        scored = [(float(a), int(i), float(sc)) for a, i, sc in ex.execute(f"""
            SELECT A, P, ANALYTICS.FRAUD_SCORE_UDF(A, {c1h}, {c24h}, {float(s1h)} + 0,
                   {float(s24h)} + 0, A / {avg30}, FALSE, FALSE, FALSE, {night}, {weekend},
                   CASE P {risk} END)
            FROM (VALUES {values}) AS C(A, P)""").fetchall()]
        lo, hi = REVIEW_BAND
        for i, (merchant, mcc, _) in enumerate(REVIEW_PROFILES):   # prefer the wire
            inside = [(a, sc) for a, p, sc in scored if p == i and lo <= sc <= hi]
            if inside:
                a, sc = min(inside, key=lambda r: abs(r[1] - target))
                return {**REVIEW_PRESET, "merchant": merchant, "mcc": mcc,
                        "amount": a, "expected": sc}
        return None
    finally:
        ex.close()


def open_review(txn_id: str, score: float) -> str:
    """Hold the payment and open an alert for an analyst. Returns the alert id."""
    pg = pg_connect()
    cur = pg.cursor()
    try:
        cur.execute("UPDATE transactions SET status = 'FLAGGED' WHERE txn_id = %s", (txn_id,))
        cur.execute("""
            INSERT INTO fraud_alerts (txn_id, alert_type, fraud_score, status, notes)
            VALUES (%s, 'MODEL_REVIEW', %s, 'OPEN',
                    'Score in the review band: held for an analyst')
            RETURNING alert_id""", (txn_id, round(float(score), 4)))
        alert_id = str(cur.fetchone()[0])
        pg.commit()
        return alert_id
    finally:
        cur.close(); pg.close()


def resolve_review(txn_id: str, confirm_fraud: bool, investigator: str = "Demo analyst") -> dict:
    """
    Record the analyst's decision in PostgreSQL, then follow it into Exasol.

    Returns what Exasol ended up holding -- the alert status, the payment
    status and the FRAUD_LABEL -- and how long the round trip took.
    """
    alert_status = "CONFIRMED_FRAUD" if confirm_fraud else "FALSE_POSITIVE"
    pg = pg_connect()
    cur = pg.cursor()
    try:
        cur.execute("""
            UPDATE fraud_alerts
               SET status = %s, investigator = %s, resolved_at = now(),
                   notes = %s
             WHERE txn_id = %s AND status = 'OPEN'""",
                    (alert_status, investigator,
                     "Analyst confirmed fraud" if confirm_fraud else "Analyst cleared the payment",
                     txn_id))
        if confirm_fraud:
            cur.execute("""UPDATE transactions SET status = 'DECLINED',
                           decline_reason = 'ANALYST_CONFIRMED_FRAUD' WHERE txn_id = %s""",
                        (txn_id,))
        else:
            cur.execute("""UPDATE transactions SET status = 'SETTLED', decline_reason = NULL
                           WHERE txn_id = %s""", (txn_id,))
        pg.commit()
    finally:
        cur.close(); pg.close()

    ex = exa_connect()
    try:
        t = time.time()
        for _ in range(15):
            stage_import(ex)
            stage_import(ex, ALERTS_IMPORT, **ALERTS_HOST)
            if ex.execute(f"""SELECT 1 FROM KAFKA_STAGE.FRAUD_ALERTS
                              WHERE TXN_ID = '{txn_id}' AND STATUS = '{alert_status}'""").fetchall():
                break
            time.sleep(0.25)
        ex.execute(MERGE_SQL); ex.execute(DELETE_SQL)
        for stmt in ALERT_MERGES:
            ex.execute(stmt)
        for stmt in refresh_statements():
            ex.execute(stmt)
        row = ex.execute(f"""
            SELECT a.STATUS AS ALERT_STATUS, r.STATUS AS TXN_STATUS, f.FRAUD_LABEL
            FROM RAW.TRANSACTIONS r
            LEFT JOIN RAW.FRAUD_ALERTS a ON a.TXN_ID = r.TXN_ID
            LEFT JOIN ANALYTICS.FRAUD_FEATURES f ON f.TXN_ID = r.TXN_ID
            WHERE r.TXN_ID = '{txn_id}'""").fetchone()
        return {"alert_status": row[0] if row else None,
                "txn_status": row[1] if row else None,
                "label": row[2] if row else None,
                "ms": (time.time() - t) * 1000}
    finally:
        ex.close()


def review_queue(limit: int = 6):
    """Story alerts, newest first, from the operational database where they are worked."""
    pg = pg_connect()
    cur = pg.cursor()
    try:
        cur.execute("""
            SELECT a.txn_id::text, t.merchant_name, t.amount, a.fraud_score, a.status,
                   a.investigator, t.status
            FROM fraud_alerts a JOIN transactions t ON t.txn_id = a.txn_id
            WHERE t.reference_id LIKE %s
            ORDER BY a.created_at DESC LIMIT %s""", (STORY_REF_PREFIX + "%", limit))
        return [dict(zip(("txn_id", "merchant", "amount", "score", "status", "investigator",
                          "txn_status"), r)) for r in cur.fetchall()]
    finally:
        cur.close(); pg.close()


def topic_stats():
    """Messages currently on the topic, and how many partitions carry them."""
    from confluent_kafka import TopicPartition
    try:
        c = _consumer()
        md = c.list_topics(KAFKA_TOPIC, timeout=5)
        t = md.topics.get(KAFKA_TOPIC)
        if t is None or t.error is not None:
            return {"ok": False, "messages": None, "partitions": 0}
        total = 0
        for p in t.partitions:
            lo, hi = c.get_watermark_offsets(TopicPartition(KAFKA_TOPIC, p),
                                             timeout=5, cached=False)
            total += max(0, hi - lo)
        return {"ok": True, "messages": total, "partitions": len(t.partitions),
                "topic": KAFKA_TOPIC}
    except Exception:
        _kafka.pop("c", None)
        return {"ok": False, "messages": None, "partitions": 0, "topic": KAFKA_TOPIC}


def topic_tail(limit: int = 6):
    """The newest `limit` events actually on the topic, decoded from Avro."""
    from confluent_kafka import TopicPartition
    from confluent_kafka.serialization import SerializationContext, MessageField
    try:
        c, deser = _consumer(), _deserializer()
        md = c.list_topics(KAFKA_TOPIC, timeout=5)
        t = md.topics.get(KAFKA_TOPIC)
        if t is None or t.error is not None:
            return []
        assign = []
        for p in t.partitions:
            lo, hi = c.get_watermark_offsets(TopicPartition(KAFKA_TOPIC, p),
                                             timeout=5, cached=False)
            if hi > lo:
                assign.append(TopicPartition(KAFKA_TOPIC, p, max(lo, hi - limit)))
        if not assign:
            return []
        c.assign(assign)
        out, deadline = [], time.time() + 2.5
        while len(out) < limit * len(assign) and time.time() < deadline:
            m = c.poll(0.2)
            if m is None or m.error():
                continue
            try:
                v = deser(m.value(), SerializationContext(KAFKA_TOPIC, MessageField.VALUE))
            except Exception:
                v = None
            out.append({"partition": m.partition(), "offset": m.offset(),
                        "ts": m.timestamp()[1], "payload": v,
                        "op": (v or {}).get("__op")})
        c.unassign()
        out.sort(key=lambda r: r["ts"] or 0, reverse=True)
        return out[:limit]
    except Exception:
        _kafka.pop("c", None)
        return []


SCORED_SQL = """SELECT  t.MERCHANT_NAME,
        f.AMOUNT_USD,
        f.TXN_COUNT_1H          AS TXN_LAST_HOUR,
        f.AMOUNT_VS_AVG_RATIO   AS VS_30D_AVERAGE,
        f.MCC_BASE_RISK         AS MERCHANT_RISK,
        f.FRAUD_SCORE,
        CASE WHEN f.FRAUD_SCORE >= 0.70 THEN 'BLOCK'
             WHEN f.FRAUD_SCORE >= 0.30 THEN 'REVIEW'
             ELSE 'APPROVE' END AS DECISION,
        CASE WHEN f.FRAUD_LABEL = TRUE  THEN 'CONFIRMED FRAUD'
             WHEN f.FRAUD_LABEL = FALSE THEN 'CLEARED' END AS ANALYST
FROM    ANALYTICS.FRAUD_FEATURES f
JOIN    RAW.TRANSACTIONS t ON t.TXN_ID = f.TXN_ID
WHERE   f.ACCOUNT_ID = '{account}'
  AND   f.FRAUD_SCORE IS NOT NULL
ORDER BY t.INITIATED_AT DESC
LIMIT 8"""


def scored_rows(limit: int = 8):
    """Run the analytical query the demo is really about, and return rows."""
    ex = exa_connect()
    try:
        sql = SCORED_SQL.format(account=ACCOUNT_ID)
        return sql, ex.execute(sql).fetchall()
    finally:
        ex.close()


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------
# Written by the application, never by the agent. The MCP server refuses every
# write, so there is no path from the agent to its own audit log -- it cannot
# add, alter or erase a line about itself. The identity recorded is read back
# from the engine through the agent's own session, so it is what the DATABASE
# believed, not a variable this process was holding.

def _lit(v) -> str:
    """A SQL string literal. Doubling the quote is the whole escape in Exasol."""
    return "'" + str(v).replace("'", "''") + "'"


def write_audit(db_user: str, question: str, entries):
    """
    entries: iterable of (sql_text, rows_returned, duration_ms).

    A single multi-row INSERT rather than pyexasol's import_from_iterable --
    that path parses the server version string, and Exasol Personal reports
    "2026.2.0-nano.3", which is not a valid PEP 440 version, so it raises
    before sending anything. Audit batches are a handful of rows; one statement
    is plenty.
    """
    if not entries:
        return 0
    vals = ", ".join(
        "(CURRENT_TIMESTAMP, {}, {}, {}, {}, {})".format(
            _lit(db_user), _lit((question or "")[:500]), _lit((sql or "")[:2000]),
            int(n), round(float(ms), 1))
        for sql, n, ms in entries)
    ex = exa_connect()
    try:
        ex.execute("INSERT INTO FRAUD_DEMO.AGENT_AUDIT "
                   "(ASKED_AT, DB_USER, QUESTION, SQL_TEXT, ROWS_RETURNED, DURATION_MS) "
                   "VALUES " + vals)
        ex.commit()
        return len(list(entries))
    finally:
        ex.close()


def read_audit(limit: int = 12):
    """The whole trail, for the SYS-side view of who asked what."""
    ex = exa_connect()
    try:
        return ex.execute(f"""SELECT ASKED_AT, DB_USER, SQL_TEXT, ROWS_RETURNED, DURATION_MS
                              FROM FRAUD_DEMO.AGENT_AUDIT
                              ORDER BY ASKED_AT DESC LIMIT {limit}""").fetchall()
    finally:
        ex.close()

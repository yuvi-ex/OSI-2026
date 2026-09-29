#!/usr/bin/env bash
# ============================================================
#  deploy.sh  –  Bootstrap the full banking pipeline
# ============================================================
set -euo pipefail

CONNECT_URL="http://localhost:8083"
CONNECT_TIMEOUT=120
PYTHON_BIN="python3"
USE_EXTERNAL_POSTGRES="${USE_EXTERNAL_POSTGRES:-false}"
EXTERNAL_POSTGRES_CONTAINER="${EXTERNAL_POSTGRES_CONTAINER:-}"
EXTERNAL_POSTGRES_PSQL_USER="${EXTERNAL_POSTGRES_PSQL_USER:-}"
POSTGRES_DB="${POSTGRES_DB:-banking}"
POSTGRES_USER="${POSTGRES_USER:-}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
DEBEZIUM_REPLICATION_USER="${DEBEZIUM_REPLICATION_USER:-}"
DEBEZIUM_REPLICATION_PASSWORD="${DEBEZIUM_REPLICATION_PASSWORD:-}"
EXTERNAL_POSTGRES_HOST="${EXTERNAL_POSTGRES_HOST:-host.docker.internal}"
EXTERNAL_POSTGRES_PORT="${EXTERNAL_POSTGRES_PORT:-5432}"
EXTERNAL_POSTGRES_DB="${EXTERNAL_POSTGRES_DB:-}"
EXTERNAL_POSTGRES_USER="${EXTERNAL_POSTGRES_USER:-}"
EXTERNAL_POSTGRES_PASSWORD="${EXTERNAL_POSTGRES_PASSWORD:-}"
EXPECTED_SOURCE_TABLES=5
DEBEZIUM_CONFIG_FILE="debezium-connector.avro.json"
DEBEZIUM_CONNECTOR_NAME="banking-postgres-cdc-avro"
RENDERED_DEBEZIUM_CONFIG=""

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1 && command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
fi

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[$(date +%H:%M:%S)] $1${NC}"; }
warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] ⚠  $1${NC}"; }
err()  { echo -e "${RED}[$(date +%H:%M:%S)] ✗  $1${NC}"; exit 1; }

cleanup() {
    if [[ -n "$RENDERED_DEBEZIUM_CONFIG" && -f "$RENDERED_DEBEZIUM_CONFIG" ]]; then
        rm -f "$RENDERED_DEBEZIUM_CONFIG"
    fi
}
trap cleanup EXIT

render_connector_config() {
    local template_file="$1"
    local output_file="$2"
    local database_host="$3"
    local database_port="$4"
    local database_user="$5"
    local database_password="$6"
    local database_name="$7"

    "$PYTHON_BIN" - "$template_file" "$output_file" "$database_host" "$database_port" "$database_user" "$database_password" "$database_name" <<'PY'
import pathlib
import sys

template_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])

replacements = {
    "__DATABASE_HOST__": sys.argv[3],
    "__DATABASE_PORT__": sys.argv[4],
    "__DATABASE_USER__": sys.argv[5],
    "__DATABASE_PASSWORD__": sys.argv[6],
    "__DATABASE_DBNAME__": sys.argv[7],
}

content = template_path.read_text(encoding="utf-8")
for needle, value in replacements.items():
    content = content.replace(needle, value)
output_path.write_text(content, encoding="utf-8")
PY
}

# ─── 1. Start Docker stack ────────────────────────────────
log "Starting Docker Compose stack..."
SERVICES=(zookeeper kafka schema-registry kafka-connect kafka-ui)
if [[ "$USE_EXTERNAL_POSTGRES" == "true" ]]; then
    DEBEZIUM_CONFIG_FILE="debezium-connector.external.avro.json"
    [[ -n "$EXTERNAL_POSTGRES_CONTAINER" ]] || err "EXTERNAL_POSTGRES_CONTAINER must be set for external PostgreSQL mode."
    [[ -n "$EXTERNAL_POSTGRES_PSQL_USER" ]] || err "EXTERNAL_POSTGRES_PSQL_USER must be set for external PostgreSQL mode."
    [[ -n "$EXTERNAL_POSTGRES_DB" ]] || err "EXTERNAL_POSTGRES_DB must be set for external PostgreSQL mode."
    [[ -n "$EXTERNAL_POSTGRES_USER" ]] || err "EXTERNAL_POSTGRES_USER must be set for external PostgreSQL mode."
    [[ -n "$EXTERNAL_POSTGRES_PASSWORD" ]] || err "EXTERNAL_POSTGRES_PASSWORD must be set for external PostgreSQL mode."
else
    [[ -n "$POSTGRES_USER" ]] || err "POSTGRES_USER must be set. Copy .env.example to .env and fill in your values."
    [[ -n "$POSTGRES_PASSWORD" ]] || err "POSTGRES_PASSWORD must be set. Copy .env.example to .env and fill in your values."
    [[ -n "$DEBEZIUM_REPLICATION_USER" ]] || err "DEBEZIUM_REPLICATION_USER must be set. Copy .env.example to .env and fill in your values."
    [[ -n "$DEBEZIUM_REPLICATION_PASSWORD" ]] || err "DEBEZIUM_REPLICATION_PASSWORD must be set. Copy .env.example to .env and fill in your values."
    SERVICES=(postgres "${SERVICES[@]}")
fi
docker compose up -d "${SERVICES[@]}"

# ─── 2. Wait for Kafka Connect ────────────────────────────
log "Waiting for Kafka Connect REST API ($CONNECT_TIMEOUT s)..."
elapsed=0
until curl -sf "$CONNECT_URL/connectors" > /dev/null 2>&1; do
    sleep 5
    elapsed=$((elapsed+5))
    [ $elapsed -ge $CONNECT_TIMEOUT ] && err "Kafka Connect did not start in time."
    echo -n "."
done
echo ""
log "Kafka Connect is ready."

# ─── 3. Validate PostgreSQL source ────────────────────────
REGISTER_DEBEZIUM="true"
if [[ "$USE_EXTERNAL_POSTGRES" == "true" ]]; then
    log "Using external PostgreSQL container: $EXTERNAL_POSTGRES_CONTAINER"
    if ! docker ps --format '{{.Names}}' | grep -Fx "$EXTERNAL_POSTGRES_CONTAINER" > /dev/null; then
        warn "External PostgreSQL container '$EXTERNAL_POSTGRES_CONTAINER' is not running. Debezium registration is skipped."
        REGISTER_DEBEZIUM="false"
    else
        WAL_LEVEL=$(docker exec "$EXTERNAL_POSTGRES_CONTAINER" \
            psql -U "$EXTERNAL_POSTGRES_PSQL_USER" -d "$EXTERNAL_POSTGRES_DB" -Atc "SHOW wal_level;" 2>/dev/null || echo "UNKNOWN")
        TABLE_COUNT=$(docker exec "$EXTERNAL_POSTGRES_CONTAINER" \
            psql -U "$EXTERNAL_POSTGRES_PSQL_USER" -d "$EXTERNAL_POSTGRES_DB" -Atc \
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name IN ('customers','accounts','cards','transactions','fraud_alerts');" 2>/dev/null || echo "0")

        if [[ "$WAL_LEVEL" != "logical" ]]; then
            warn "External PostgreSQL wal_level is '$WAL_LEVEL'. Debezium needs 'logical', so connector registration is skipped."
            REGISTER_DEBEZIUM="false"
        fi

        if [[ "$TABLE_COUNT" != "$EXPECTED_SOURCE_TABLES" ]]; then
            warn "Expected banking source tables were not found in ${EXTERNAL_POSTGRES_DB}. Connector registration is skipped until 01_schema.sql and 02_seed.sql are loaded."
            REGISTER_DEBEZIUM="false"
        fi
    fi
else
    log "Using Compose-managed PostgreSQL."
fi

# ─── 4. Register Debezium CDC connector ───────────────────
if [[ "$REGISTER_DEBEZIUM" == "true" ]]; then
    log "Registering Debezium PostgreSQL connector..."
    RENDERED_DEBEZIUM_CONFIG="$(mktemp)"
    if [[ "$USE_EXTERNAL_POSTGRES" == "true" ]]; then
        render_connector_config \
            "$DEBEZIUM_CONFIG_FILE" \
            "$RENDERED_DEBEZIUM_CONFIG" \
            "$EXTERNAL_POSTGRES_HOST" \
            "$EXTERNAL_POSTGRES_PORT" \
            "$EXTERNAL_POSTGRES_USER" \
            "$EXTERNAL_POSTGRES_PASSWORD" \
            "$EXTERNAL_POSTGRES_DB"
    else
        render_connector_config \
            "$DEBEZIUM_CONFIG_FILE" \
            "$RENDERED_DEBEZIUM_CONFIG" \
            "postgres" \
            "5432" \
            "$DEBEZIUM_REPLICATION_USER" \
            "$DEBEZIUM_REPLICATION_PASSWORD" \
            "$POSTGRES_DB"
    fi
    STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
        -X POST "$CONNECT_URL/connectors" \
        -H "Content-Type: application/json" \
        -d @"$RENDERED_DEBEZIUM_CONFIG" || true)

    if [[ "$STATUS" == "201" ]]; then
        log "Debezium connector registered (201 Created)."
    elif [[ "$STATUS" == "409" ]]; then
        warn "Debezium connector already exists (409 Conflict). Skipping."
    else
        err "Failed to register Debezium connector. HTTP $STATUS"
    fi

    sleep 5
    CONNECTOR_STATE=$(curl -sf "$CONNECT_URL/connectors/$DEBEZIUM_CONNECTOR_NAME/status" \
        | "$PYTHON_BIN" -c "import sys,json; d=json.load(sys.stdin); print(d['connector']['state'])" 2>/dev/null || echo "UNKNOWN")
    log "Connector state: $CONNECTOR_STATE"
    if [[ "$CONNECTOR_STATE" != "RUNNING" ]]; then
        CONNECTOR_TRACE=$(curl -sf "$CONNECT_URL/connectors/$DEBEZIUM_CONNECTOR_NAME/status" \
            | "$PYTHON_BIN" -c "import sys,json; d=json.load(sys.stdin); tasks=d.get('tasks') or [{}]; trace=tasks[0].get('trace',''); print(trace.splitlines()[0] if trace else '')" 2>/dev/null || true)
        warn "Connector is not RUNNING yet. ${CONNECTOR_TRACE:-Check Kafka Connect and PostgreSQL logical replication settings.}"
    fi
else
    warn "Debezium connector registration skipped."
fi

# ─── 5. List active Kafka topics ──────────────────────────
log "Checking Kafka topics..."
sleep 3
docker exec banking-kafka kafka-topics \
    --bootstrap-server localhost:9092 \
    --list | grep -E "^banking_avro\." || warn "No banking Avro topics yet — CDC may still be initialising."

# ─── 6. Print access URLs ─────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║         BANKING PIPELINE DEPLOYED ✅                 ║"
echo "╠══════════════════════════════════════════════════════╣"
if [[ "$USE_EXTERNAL_POSTGRES" == "true" ]]; then
echo "║  PostgreSQL    : external container                  ║"
echo "║                  $EXTERNAL_POSTGRES_CONTAINER / $EXTERNAL_POSTGRES_DB           ║"
else
echo "║  PostgreSQL    : localhost:5432                      ║"
echo "║                  db=$POSTGRES_DB                     ║"
fi
echo "║  Kafka Broker  : localhost:29092                     ║"
echo "║  Kafka Connect : http://localhost:8083               ║"
echo "║  Kafka UI      : http://localhost:8080               ║"
echo "║  Schema Reg.   : http://localhost:8081               ║"
echo "║  CDC Format    : Avro + Schema Registry              ║"
echo "║  Exasol Sync   : official Kafka connector            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Next steps:"
if [[ "$USE_EXTERNAL_POSTGRES" == "true" ]]; then
echo "  1. External PostgreSQL prerequisites:"
echo "     - Container: $EXTERNAL_POSTGRES_CONTAINER"
echo "     - Database : $EXTERNAL_POSTGRES_DB"
echo "     - PSQL user: $EXTERNAL_POSTGRES_PSQL_USER"
echo "     - Required : wal_level=logical"
echo "     - Load schema with:"
echo "       docker exec -i $EXTERNAL_POSTGRES_CONTAINER psql -U $EXTERNAL_POSTGRES_PSQL_USER -d $EXTERNAL_POSTGRES_DB < 01_schema.sql"
echo "       docker exec -i $EXTERNAL_POSTGRES_CONTAINER psql -U $EXTERNAL_POSTGRES_PSQL_USER -d $EXTERNAL_POSTGRES_DB < 02_seed.sql"
else
echo "  1. Local PostgreSQL is ready on localhost:5432."
fi
echo ""

echo "  2. In Exasol, run:"
echo "       01_exasol_schema.sql"
echo "       03_exasol_kafka_connector_schema.sql"
echo "  3. Upload the official kafka-connector-extension JAR to BucketFS."
echo "     If Exasol runs in Docker, prepare its network access with:"
echo "       bash prepare_exasol_docker.sh"
echo "     Then run:"
echo "       04_exasol_kafka_connector_udfs.sql"
echo "       05_exasol_kafka_connector_import_avro.sql"
echo "       06_exasol_kafka_connector_merge.sql"
echo "  4. Re-run 05_exasol_kafka_connector_import_avro.sql and"
echo "     06_exasol_kafka_connector_merge.sql whenever you want"
echo "     to pull the latest Kafka changes into Exasol."
echo ""
if [[ "$USE_EXTERNAL_POSTGRES" == "true" ]]; then
echo "  5. Train ML models:"
else
echo "  5. Train ML models:"
fi
echo "     pip install -r requirements.txt && python train_pipeline.py"
echo ""
echo "  6. Upload model to Exasol BucketFS:"
echo "     curl -X PUT -T models/fraud_model.pkl \\"
echo "       http://YOUR_EXASOL_HOST:2580/models/fraud_model.pkl"
echo ""
echo "  7. Run feature + UDF SQL in Exasol:"
echo "     Execute 02_features_and_udfs.sql in EXAplus"

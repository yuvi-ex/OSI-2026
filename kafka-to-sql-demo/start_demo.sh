#!/usr/bin/env bash
# Start the demo on http://localhost:8502.
#
# Run from anywhere. The folder may be called story_demo/ or kafka-to-sql-demo/;
# it must sit inside a checkout of real-time-banking-fraud-pipeline (the app
# reuses that repo's .venv, .env and demo_dashboard.py).
#
# The demo reads Kafka and Schema Registry on localhost (always reachable from
# this machine). If Exasol cannot reach the broker -- a host firewall between a
# local Exasol VM and Docker, for example -- pipeline.py detects it in two
# seconds and stages the topic from the host instead; the Live tab then says so.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR/.."
APP="$(basename "$DIR")/app.py"

pkill -f "streamlit run $APP" 2>/dev/null || true

export DEMO_KAFKA_BOOTSTRAP="${DEMO_KAFKA_BOOTSTRAP:-localhost:29092}"
export DEMO_SCHEMA_REGISTRY="${DEMO_SCHEMA_REGISTRY:-http://localhost:8081}"

exec ./.venv/bin/streamlit run "$APP" --server.port 8502 \
  --server.headless true --browser.gatherUsageStats false

#!/usr/bin/env bash
set -euo pipefail

EXASOL_CONTAINER_NAME="${EXASOL_CONTAINER_NAME:-exasol-db}"
KAFKA_CONTAINER_NAME="${KAFKA_CONTAINER_NAME:-banking-kafka}"
SCHEMA_REGISTRY_CONTAINER_NAME="${SCHEMA_REGISTRY_CONTAINER_NAME:-banking-schema-registry}"

log() {
    printf '[%s] %s\n' "$(date +%H:%M:%S)" "$1"
}

err() {
    printf '[%s] %s\n' "$(date +%H:%M:%S)" "$1" >&2
    exit 1
}

require_running_container() {
    local name="$1"
    docker ps --format '{{.Names}}' | grep -Fx "$name" >/dev/null || err "Container '$name' is not running."
}

require_running_container "$EXASOL_CONTAINER_NAME"
require_running_container "$KAFKA_CONTAINER_NAME"
require_running_container "$SCHEMA_REGISTRY_CONTAINER_NAME"

KAFKA_NETWORK_NAME="${KAFKA_NETWORK_NAME:-$(docker inspect -f '{{range $name, $conf := .NetworkSettings.Networks}}{{println $name}}{{end}}' "$KAFKA_CONTAINER_NAME" | head -n1 | tr -d '\r')}"
[ -n "$KAFKA_NETWORK_NAME" ] || err "Could not determine the Kafka Docker network."

log "Connecting '$EXASOL_CONTAINER_NAME' to '$KAFKA_NETWORK_NAME'..."
docker network connect "$KAFKA_NETWORK_NAME" "$EXASOL_CONTAINER_NAME" >/dev/null 2>&1 || true

KAFKA_IP="$(docker inspect -f '{{range $name, $conf := .NetworkSettings.Networks}}{{if eq $name "'"$KAFKA_NETWORK_NAME"'"}}{{$conf.IPAddress}}{{end}}{{end}}' "$KAFKA_CONTAINER_NAME" | tr -d '\r')"
SCHEMA_REGISTRY_IP="$(docker inspect -f '{{range $name, $conf := .NetworkSettings.Networks}}{{if eq $name "'"$KAFKA_NETWORK_NAME"'"}}{{$conf.IPAddress}}{{end}}{{end}}' "$SCHEMA_REGISTRY_CONTAINER_NAME" | tr -d '\r')"

[ -n "$KAFKA_IP" ] || err "Could not resolve the Kafka container IP on '$KAFKA_NETWORK_NAME'."
[ -n "$SCHEMA_REGISTRY_IP" ] || err "Could not resolve the Schema Registry container IP on '$KAFKA_NETWORK_NAME'."

log "Updating /etc/hosts inside '$EXASOL_CONTAINER_NAME'..."
CURRENT_HOSTS="$(docker exec "$EXASOL_CONTAINER_NAME" cat /etc/hosts)"
FILTERED_HOSTS="$(printf '%s\n' "$CURRENT_HOSTS" | awk '!/([[:space:]]|^)(kafka|schema-registry)$/')"
{
    printf '%s\n' "$FILTERED_HOSTS"
    printf '%s %s\n' "$KAFKA_IP" "kafka"
    printf '%s %s\n' "$SCHEMA_REGISTRY_IP" "schema-registry"
} | docker exec -i "$EXASOL_CONTAINER_NAME" tee /etc/hosts >/dev/null

log "Prepared Exasol container networking."
log "Kafka: $KAFKA_IP (alias: kafka)"
log "Schema Registry: $SCHEMA_REGISTRY_IP (alias: schema-registry)"

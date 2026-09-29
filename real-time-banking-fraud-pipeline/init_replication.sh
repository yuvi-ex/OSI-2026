#!/usr/bin/env bash
set -euo pipefail

DEBEZIUM_REPLICATION_USER="${DEBEZIUM_REPLICATION_USER:?DEBEZIUM_REPLICATION_USER must be set}"
DEBEZIUM_REPLICATION_PASSWORD="${DEBEZIUM_REPLICATION_PASSWORD:?DEBEZIUM_REPLICATION_PASSWORD must be set}"

psql \
  -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  -v app_db="$POSTGRES_DB" \
  -v debezium_user="$DEBEZIUM_REPLICATION_USER" \
  -v debezium_password="$DEBEZIUM_REPLICATION_PASSWORD" <<'SQL'
DO $do$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'debezium_user') THEN
        EXECUTE format(
            'CREATE ROLE %I WITH LOGIN REPLICATION PASSWORD %L',
            :'debezium_user',
            :'debezium_password'
        );
    ELSE
        EXECUTE format(
            'ALTER ROLE %I WITH LOGIN REPLICATION PASSWORD %L',
            :'debezium_user',
            :'debezium_password'
        );
        EXECUTE format('ALTER ROLE %I WITH REPLICATION', :'debezium_user');
    END IF;
END $do$;

DO $do$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO %I', :'app_db', :'debezium_user');
    EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', :'debezium_user');
    EXECUTE format(
        'GRANT SELECT ON TABLE customers, accounts, cards, transactions, fraud_alerts TO %I',
        :'debezium_user'
    );
    EXECUTE format(
        'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO %I',
        :'debezium_user'
    );
END $do$;

DO $do$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'banking_publication') THEN
        CREATE PUBLICATION banking_publication
        FOR TABLE customers, accounts, cards, transactions, fraud_alerts;
    END IF;
END $do$;
SQL

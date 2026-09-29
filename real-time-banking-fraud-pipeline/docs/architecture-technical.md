# Technical Architecture

## Purpose

This project is an end-to-end banking analytics pipeline that demonstrates:

- change data capture from PostgreSQL
- event streaming through Kafka
- schema-managed Avro messages through Schema Registry
- ingestion into Exasol for analytical processing
- feature engineering and in-database ML scoring

The repo uses the official Exasol Kafka connector via BucketFS-hosted UDFs for Kafka-to-Exasol ingestion.

The current recommended showcase path is:

`PostgreSQL -> Debezium -> Kafka -> Schema Registry -> Exasol -> features -> ML scoring`

## Runtime Architecture

### Source and CDC

- `postgres` is the transactional source system.
- `01_schema.sql` creates the OLTP tables: `customers`, `accounts`, `cards`, `transactions`, `fraud_alerts`.
- `02_seed.sql` loads demo data.
- `init_replication.sh` creates the `debezium` replication user and the `banking_publication`.
- Debezium reads changes from PostgreSQL logical replication using `pgoutput`.

### Streaming Layer

- `kafka` stores CDC events in topics.
- `kafka-connect` hosts the Debezium connector.
- `schema-registry` stores Avro schemas for Kafka topics.
- `kafka-ui` provides visibility into topics, messages, offsets, schemas, and connector state.

### Analytical Layer

- Exasol is the analytical target.
- `01_exasol_schema.sql` creates three layers:
  - `RAW`: landed source-like records
  - `CLEANSED`: typed and conformed dimensions/facts
  - `ANALYTICS`: feature tables and scoring outputs

### ML Layer

- `07_refresh_analytics_features.sql` refreshes `CLEANSED` dimensions / facts and rebuilds `ANALYTICS.FRAUD_FEATURES`.
- `02_features_and_udfs.sql` defines a single Python UDF for fraud scoring and applies batch scoring inside Exasol.
- `train_pipeline.py` trains one simple logistic regression fraud model for the demo.
- The model artifact is uploaded to BucketFS and loaded by the Exasol Python UDF.

## Service Responsibilities

### PostgreSQL

Used as the operational banking system.

Why it exists:

- it is the mutable source of truth
- it generates WAL changes for CDC
- it gives the pipeline realistic inserts, updates, and deletes

Important configuration:

- `wal_level=logical`
- replication slots enabled
- `REPLICA IDENTITY FULL` on CDC tables

## Zookeeper

Used only because this Kafka image set still expects it.

Why it exists:

- cluster coordination for the Kafka broker in this stack

## Kafka

Used as the event backbone.

Why it exists:

- decouples source capture from downstream consumers
- stores ordered event streams durably
- supports multiple consumers of the same change stream

Topic family used in this repo:

- `banking_avro.public.*`

## Kafka Connect

Used as the connector runtime.

Why it exists:

- hosts the Debezium PostgreSQL connector
- exposes a REST API for connector registration and status
- centralizes connector execution instead of running custom polling code in the source DB

In this project, Debezium is not a separate service. It runs inside Kafka Connect.

## Debezium

Used for CDC from PostgreSQL into Kafka.

Why it exists:

- captures inserts, updates, and deletes from PostgreSQL WAL
- supports initial snapshots plus ongoing streaming
- preserves source metadata such as operation type and source table

Connector behavior in this repo:

- source tables limited to the five banking tables
- `ExtractNewRecordState` unwrap transform simplifies the emitted payload
- delete handling rewrites deletes into normal records with delete markers
- heartbeat messages are emitted periodically

## Schema Registry

Used only for the Avro mode.

Why it exists:

- stores schema versions centrally
- lets producers and consumers agree on Avro structure
- avoids embedding full schemas into every message

Without it, Avro mode would not be practical for the Exasol consumer side.

## Kafka UI

Used for monitoring and demos.

Why it exists:

- inspect topics and messages
- verify schemas in Schema Registry
- inspect Kafka Connect connector state
- show the pipeline visually during a customer demo

## Official Exasol Kafka Connector

Used as the supported Kafka-to-Exasol path in this repo.

Why it exists:

- it is the official Exasol-supported pattern
- Exasol itself pulls from Kafka using BucketFS-hosted Java UDFs
- it aligns better with an Exasol-centered architecture for customer showcase work

Files involved:

- `03_exasol_kafka_connector_schema.sql`
- `04_exasol_kafka_connector_udfs.sql`
- `05_exasol_kafka_connector_import_avro.sql`
- `06_exasol_kafka_connector_merge.sql`
- `prepare_exasol_docker.sh`

## Detailed Flow

### 1. Database initialization

When `docker compose up` starts PostgreSQL:

- the source schema is created
- seed data is loaded
- replication user/publication are created

At that point, the OLTP source is ready for Debezium.

### 2. Connector registration

`deploy.sh` starts the stack, waits for Kafka Connect, and registers the Debezium connector.

Connector file selection depends on:

- `USE_EXTERNAL_POSTGRES`

Examples:

- `debezium-connector.avro.json`
- `debezium-connector.external.avro.json`

### 3. CDC capture

Debezium performs:

- an initial snapshot of the selected source tables
- continued streaming from the WAL afterward

Each change is published to Kafka.

In Avro mode:

- key and value are serialized with `io.confluent.connect.avro.AvroConverter`
- schemas are registered in Schema Registry

### 4. Kafka topic usage

The most important topics are:

- `banking_avro.public.customers`
- `banking_avro.public.accounts`
- `banking_avro.public.cards`
- `banking_avro.public.transactions`
- `banking_avro.public.fraud_alerts`

Debezium also emits a heartbeat topic.

### 5. Exasol ingest

- `prepare_exasol_docker.sh` attaches the Exasol container to the Kafka network and injects `kafka` / `schema-registry` name resolution when Exasol itself runs in Docker
- `04_exasol_kafka_connector_udfs.sql` registers the connector JAR from BucketFS
- `05_exasol_kafka_connector_import_avro.sql` imports Avro topic data into `KAFKA_STAGE.*`
- `06_exasol_kafka_connector_merge.sql` converts string timestamps, deduplicates by business key, and merges the latest state into `RAW.*`

This path is append-only at the staging layer and stateful at the merge layer.

### 6. Warehouse modeling

After `RAW.*` is populated:

- customer and account dimensions are derived into `CLEANSED`
- transactions are normalized into `CLEANSED.FACT_TRANSACTIONS`
- feature vectors are created in `ANALYTICS.FRAUD_FEATURES`

Feature examples:

- transaction velocity over 1h, 6h, 24h
- amount vs historical average
- cross-border flag
- new device / new country flags
- night / weekend indicators
- MCC base risk

### 7. ML scoring

Two simple ML steps exist:

- offline training of one fraud model in `train_pipeline.py`
- online inference inside Exasol via one Python UDF

The fraud UDF:

- loads `fraud_model.pkl` from BucketFS
- returns a `FRAUD_SCORE`
- the batch scoring SQL writes `MODEL_VERSION`
- requires the BucketFS model artifact to be present before scoring runs

## Why The Layers Exist

### RAW

Purpose:

- preserve landed source state with minimal business transformation
- keep Kafka metadata available
- provide a stable reload boundary

### KAFKA_STAGE

Purpose:

- absorb append-only imported topic rows from the official connector
- isolate connector-specific typing behavior from the warehouse model

### CLEANSED

Purpose:

- type normalization
- conformed dimensions
- consistent derived business fields

### ANALYTICS

Purpose:

- ML-ready feature storage
- scoring/audit outputs
- reusable analytical model layer

## Configuration Switches

### `USE_EXTERNAL_POSTGRES`

- `false`: use the Compose-managed PostgreSQL
- `true`: reuse an existing PostgreSQL container

## Recommended Customer Showcase Mode

For the strongest architecture story, use:

```bash
bash deploy.sh
bash prepare_exasol_docker.sh
```

Then in Exasol run:

1. `01_exasol_schema.sql`
2. `03_exasol_kafka_connector_schema.sql`
3. `04_exasol_kafka_connector_udfs.sql`
4. `05_exasol_kafka_connector_import_avro.sql`
5. `06_exasol_kafka_connector_merge.sql`
6. `07_refresh_analytics_features.sql`
7. `02_features_and_udfs.sql`

That gives the cleanest narrative:

- CDC from OLTP
- governed streaming with Avro schemas
- Exasol-native Kafka ingestion
- in-database feature engineering and fraud scoring

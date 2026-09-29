-- ============================================================
--  OPTIONAL: OFFICIAL EXASOL KAFKA CONNECTOR UDFS
--  Source: https://docs.exasol.com/saas/loading_data/connect_sources/kafka_integration.htm
--  BucketFS JAR path for this project:
--    /buckets/bfsdefault/default/drivers/exasol-kafka-connector-extension-1.7.16.jar
-- ============================================================

CREATE SCHEMA IF NOT EXISTS KAFKA_EXTENSION;
OPEN SCHEMA KAFKA_EXTENSION;

CREATE OR REPLACE JAVA SET SCRIPT KAFKA_CONSUMER(...) EMITS (...) AS
  %scriptclass com.exasol.cloudetl.kafka.KafkaConsumerQueryGenerator;
  %jar /buckets/bfsdefault/default/drivers/exasol-kafka-connector-extension-1.7.16.jar;
/

CREATE OR REPLACE JAVA SET SCRIPT KAFKA_IMPORT(...) EMITS (...) AS
  %scriptclass com.exasol.cloudetl.kafka.KafkaTopicDataImporter;
  %jar /buckets/bfsdefault/default/drivers/exasol-kafka-connector-extension-1.7.16.jar;
/

CREATE OR REPLACE JAVA SET SCRIPT KAFKA_METADATA(
  params VARCHAR(2000),
  kafka_partition DECIMAL(18, 0),
  kafka_offset DECIMAL(36, 0)
)
EMITS (partition_index DECIMAL(18, 0), max_offset DECIMAL(36, 0)) AS
  %scriptclass com.exasol.cloudetl.kafka.KafkaTopicMetadataReader;
  %jar /buckets/bfsdefault/default/drivers/exasol-kafka-connector-extension-1.7.16.jar;
/

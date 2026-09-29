-- ============================================================
--  OPTIONAL: IMPORT AVRO TOPICS INTO KAFKA_STAGE
--  Use this file when Debezium publishes Avro and registers
--  schemas in Schema Registry.
-- ============================================================

IMPORT INTO KAFKA_STAGE.TRANSACTIONS
FROM SCRIPT KAFKA_EXTENSION.KAFKA_CONSUMER WITH
  BOOTSTRAP_SERVERS   = '192.168.64.1:39092'
  SCHEMA_REGISTRY_URL = 'http://192.168.64.1:8081'
  RECORD_VALUE_FORMAT = 'avro'
  RECORD_FIELDS       = 'value.txn_id,value.account_id,value.card_id,value.txn_type,value.amount,value.currency,value.direction,value.merchant_name,value.merchant_mcc,value.merchant_id,value.channel,value.ip_address,value.device_id,value.device_fingerprint,value.country_code,value.city,value.latitude,value.longitude,value.counterparty_account,value.counterparty_bank,value.status,value.decline_reason,value.reference_id,value.initiated_at,value.settled_at,value.updated_at,value.__op,value.__deleted,timestamp'
  TOPIC_NAME          = 'banking_avro.public.transactions'
  TABLE_NAME          = 'KAFKA_STAGE.TRANSACTIONS'
  GROUP_ID            = 'exasol-kafka-transactions'
  CONSUME_ALL_OFFSETS = 'true';

IMPORT INTO KAFKA_STAGE.ACCOUNTS
FROM SCRIPT KAFKA_EXTENSION.KAFKA_CONSUMER WITH
  BOOTSTRAP_SERVERS   = '192.168.64.1:39092'
  SCHEMA_REGISTRY_URL = 'http://192.168.64.1:8081'
  RECORD_VALUE_FORMAT = 'avro'
  RECORD_FIELDS       = 'value.account_id,value.customer_id,value.account_number,value.account_type,value.currency,value.balance,value.credit_limit,value.status,value.opened_at,value.updated_at,value.__op,value.__deleted,timestamp'
  TOPIC_NAME          = 'banking_avro.public.accounts'
  TABLE_NAME          = 'KAFKA_STAGE.ACCOUNTS'
  GROUP_ID            = 'exasol-kafka-accounts'
  CONSUME_ALL_OFFSETS = 'true';

IMPORT INTO KAFKA_STAGE.CUSTOMERS
FROM SCRIPT KAFKA_EXTENSION.KAFKA_CONSUMER WITH
  BOOTSTRAP_SERVERS   = '192.168.64.1:39092'
  SCHEMA_REGISTRY_URL = 'http://192.168.64.1:8081'
  RECORD_VALUE_FORMAT = 'avro'
  RECORD_FIELDS       = 'value.customer_id,value.full_name,value.email,value.phone,value.date_of_birth,value.country_code,value.kyc_status,value.risk_band,value.created_at,value.updated_at,value.__op,value.__deleted,timestamp'
  TOPIC_NAME          = 'banking_avro.public.customers'
  TABLE_NAME          = 'KAFKA_STAGE.CUSTOMERS'
  GROUP_ID            = 'exasol-kafka-customers'
  CONSUME_ALL_OFFSETS = 'true';

IMPORT INTO KAFKA_STAGE.CARDS
FROM SCRIPT KAFKA_EXTENSION.KAFKA_CONSUMER WITH
  BOOTSTRAP_SERVERS   = '192.168.64.1:39092'
  SCHEMA_REGISTRY_URL = 'http://192.168.64.1:8081'
  RECORD_VALUE_FORMAT = 'avro'
  RECORD_FIELDS       = 'value.card_id,value.account_id,value.card_type,value.masked_pan,value.last_four,value.expiry_date,value.network,value.status,value.issued_at,value.updated_at,value.__op,value.__deleted,timestamp'
  TOPIC_NAME          = 'banking_avro.public.cards'
  TABLE_NAME          = 'KAFKA_STAGE.CARDS'
  GROUP_ID            = 'exasol-kafka-cards'
  CONSUME_ALL_OFFSETS = 'true';

IMPORT INTO KAFKA_STAGE.FRAUD_ALERTS
FROM SCRIPT KAFKA_EXTENSION.KAFKA_CONSUMER WITH
  BOOTSTRAP_SERVERS   = '192.168.64.1:39092'
  SCHEMA_REGISTRY_URL = 'http://192.168.64.1:8081'
  RECORD_VALUE_FORMAT = 'avro'
  RECORD_FIELDS       = 'value.alert_id,value.txn_id,value.alert_type,value.fraud_score,value.risk_score,value.status,value.investigator,value.notes,value.created_at,value.resolved_at,value.__op,value.__deleted,timestamp'
  TOPIC_NAME          = 'banking_avro.public.fraud_alerts'
  TABLE_NAME          = 'KAFKA_STAGE.FRAUD_ALERTS'
  GROUP_ID            = 'exasol-kafka-fraud-alerts'
  CONSUME_ALL_OFFSETS = 'true';

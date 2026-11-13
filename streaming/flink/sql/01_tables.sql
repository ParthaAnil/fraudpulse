-- FraudPulse stream tables: payments (with event time) and user and merchant state (CDC).
-- Every Flink SQL session loads this file first: sql-client.sh -i /opt/flink/sql/01_tables.sql

SET 'execution.runtime-mode' = 'streaming';
SET 'table.local-time-zone' = 'UTC';
-- A Kafka partition or CDC topic with no new data for 5 s must not hold back event time.
SET 'table.exec.source.idle-timeout' = '5 s';
SET 'sql-client.execution.result-mode' = 'tableau';

-- Payments, in event time. The answer-key fields are deliberately not declared, so the
-- rules cannot read them (Avro skips fields the reader does not ask for).
CREATE TABLE payments (
  transaction_id STRING,
  user_id STRING,
  merchant_id STRING,
  amount_paise BIGINT,
  city STRING,
  latitude DOUBLE,
  longitude DOUBLE,
  device_id STRING,
  event_time TIMESTAMP(3),
  -- The same instant as a time-zone-aware timestamp, to line up with Kafka's own timestamps.
  payment_time AS CAST(event_time AS TIMESTAMP_LTZ(3)),
  -- Wait up to 2 s for late payments (the generator sends them at most 1.5 s late).
  WATERMARK FOR payment_time AS payment_time - INTERVAL '2' SECOND
) WITH (
  'connector' = 'kafka',
  'topic' = 'payments.transactions',
  'properties.bootstrap.servers' = 'kafka:29092',
  'scan.startup.mode' = 'latest-offset',
  'value.format' = 'avro-confluent',
  'value.avro-confluent.url' = 'http://schema-registry:8081'
);

-- Users from the payments core, as a versioned table: every change kept with its time.
CREATE TABLE users (
  user_id STRING,
  home_city STRING,
  kyc_level STRING,
  segment STRING,
  changed_at TIMESTAMP_LTZ(3) METADATA FROM 'timestamp' VIRTUAL,
  PRIMARY KEY (user_id) NOT ENFORCED,
  WATERMARK FOR changed_at AS changed_at
) WITH (
  'connector' = 'kafka',
  'topic' = 'cdc.payments_core.public.users',
  'properties.bootstrap.servers' = 'kafka:29092',
  'scan.startup.mode' = 'earliest-offset',
  'value.format' = 'debezium-avro-confluent',
  'value.debezium-avro-confluent.url' = 'http://schema-registry:8081'
);

-- Merchants from the merchant app, versioned the same way.
CREATE TABLE merchants (
  merchant_id STRING,
  category_code STRING,
  status STRING,
  changed_at TIMESTAMP_LTZ(3) METADATA FROM 'timestamp' VIRTUAL,
  PRIMARY KEY (merchant_id) NOT ENFORCED,
  WATERMARK FOR changed_at AS changed_at
) WITH (
  'connector' = 'kafka',
  'topic' = 'cdc.merchants.merchants.merchants',
  'properties.bootstrap.servers' = 'kafka:29092',
  'scan.startup.mode' = 'earliest-offset',
  'value.format' = 'debezium-avro-confluent',
  'value.debezium-avro-confluent.url' = 'http://schema-registry:8081'
);

-- Each payment with the user's and merchant's details as they were when it happened.
CREATE VIEW enriched_payments AS
SELECT
  p.transaction_id, p.user_id, p.merchant_id, p.amount_paise, p.city,
  p.latitude, p.longitude, p.device_id, p.event_time, p.payment_time,
  u.home_city AS user_home_city,
  u.kyc_level AS user_kyc_level,
  m.category_code AS merchant_category,
  m.status AS merchant_status
FROM payments AS p
LEFT JOIN users FOR SYSTEM_TIME AS OF p.payment_time AS u
  ON p.user_id = u.user_id
LEFT JOIN merchants FOR SYSTEM_TIME AS OF p.payment_time AS m
  ON p.merchant_id = m.merchant_id;

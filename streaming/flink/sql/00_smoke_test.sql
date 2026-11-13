-- Smoke test: can Flink read payments from Kafka through Schema Registry?
-- Run with: make flink-smoke
SET 'sql-client.execution.result-mode' = 'tableau';
SET 'execution.runtime-mode' = 'batch';

-- Only the columns the rules need. The answer-key fields (injected_fraud_type, scenario_id)
-- are deliberately absent: Avro skips fields the reader does not ask for, so the fraud job
-- cannot see them at all.
CREATE TABLE payments (
  transaction_id STRING,
  user_id STRING,
  amount_paise BIGINT,
  city STRING,
  event_time TIMESTAMP(3)
) WITH (
  'connector' = 'kafka',
  'topic' = 'payments.transactions',
  'properties.bootstrap.servers' = 'kafka:29092',
  'scan.startup.mode' = 'earliest-offset',
  'scan.bounded.mode' = 'latest-offset',
  'value.format' = 'avro-confluent',
  'value.avro-confluent.url' = 'http://schema-registry:8081'
);

SELECT city, COUNT(*) AS payments, SUM(amount_paise) / 100 AS rupees,
       MIN(event_time) AS first_payment, MAX(event_time) AS last_payment
FROM payments GROUP BY city ORDER BY payments DESC LIMIT 5;

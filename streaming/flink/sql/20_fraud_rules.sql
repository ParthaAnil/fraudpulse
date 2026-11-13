-- The fraud rules job: three rules on enriched payments. Alerts go to fraud.alerts and
-- invalid payments to payments.dlq, both exactly once. Submit with: make flink-job
-- (submit-fraud-job.sh puts the contents of ingestion/schemas/fraud_alert.avsc into the sink).

SET 'pipeline.name' = 'fraudpulse-fraud-rules';
-- Exactly-once alerts become visible to readers only when a checkpoint commits them, so
-- checkpoint often: every 2 s instead of the cluster's default 10 s.
SET 'execution.checkpointing.interval' = '2 s';
-- Forget a user's rule state after 7 days without activity, so memory cannot grow forever.
SET 'table.exec.state.ttl' = '7 d';

CREATE TABLE fraud_alerts (
  alert_id STRING NOT NULL,
  rule STRING NOT NULL,
  user_id STRING NOT NULL,
  transaction_id STRING NOT NULL,
  payment_time TIMESTAMP(3) NOT NULL,
  detected_at TIMESTAMP(3) NOT NULL,
  amount_paise BIGINT NOT NULL,
  city STRING NOT NULL,
  merchant_id STRING NOT NULL,
  reason STRING NOT NULL,
  user_home_city STRING,
  user_kyc_level STRING,
  merchant_category STRING
) WITH (
  'connector' = 'kafka',
  'topic' = 'fraud.alerts',
  'properties.bootstrap.servers' = 'kafka:29092',
  'key.format' = 'raw',
  'key.fields' = 'user_id',
  'value.format' = 'avro-confluent',
  'value.avro-confluent.url' = 'http://schema-registry:8081',
  'value.avro-confluent.schema' = '@FRAUD_ALERT_SCHEMA@',
  'value.fields-include' = 'ALL',
  'sink.delivery-guarantee' = 'exactly-once',
  'sink.transactional-id-prefix' = 'fraudpulse-alerts',
  'properties.transaction.timeout.ms' = '600000'
);

CREATE TABLE payments_dlq (
  transaction_id STRING,
  user_id STRING,
  merchant_id STRING,
  amount_paise BIGINT,
  event_time TIMESTAMP(3),
  problem STRING,
  detected_at TIMESTAMP(3)
) WITH (
  'connector' = 'kafka',
  'topic' = 'payments.dlq',
  'properties.bootstrap.servers' = 'kafka:29092',
  'value.format' = 'json',
  'sink.delivery-guarantee' = 'exactly-once',
  'sink.transactional-id-prefix' = 'fraudpulse-dlq',
  'properties.transaction.timeout.ms' = '600000'
);

CREATE TEMPORARY VIEW valid_payments AS
SELECT * FROM enriched_payments
WHERE amount_paise > 0 AND user_id IS NOT NULL AND merchant_id IS NOT NULL;

CREATE TEMPORARY VIEW velocity_alerts AS
SELECT 'VELOCITY' AS rule, transaction_id, user_id, payment_time, amount_paise, city, merchant_id,
       CONCAT(CAST(payments_last_minute AS STRING), ' payments within 60 s') AS reason,
       user_home_city, user_kyc_level, merchant_category
FROM (
  SELECT *,
         COUNT(*) OVER (PARTITION BY user_id ORDER BY payment_time
                        RANGE BETWEEN INTERVAL '1' MINUTE PRECEDING AND CURRENT ROW)
           AS payments_last_minute
  FROM valid_payments
)
WHERE payments_last_minute = 6;

CREATE TEMPORARY VIEW travel_alerts AS
SELECT 'IMPOSSIBLE_TRAVEL' AS rule, transaction_id, user_id, payment_time, amount_paise, city,
       merchant_id,
       CONCAT(prev_city, ' to ', city, ': ', CAST(CAST(km AS INT) AS STRING), ' km in ',
              CAST(seconds / 60 AS STRING), ' min') AS reason,
       user_home_city, user_kyc_level, merchant_category
FROM (
  SELECT *,
         2 * 6371 * ASIN(SQRT(
           POWER(SIN(RADIANS(latitude - prev_lat) / 2), 2)
           + COS(RADIANS(prev_lat)) * COS(RADIANS(latitude))
             * POWER(SIN(RADIANS(longitude - prev_lon) / 2), 2))) AS km,
         TIMESTAMPDIFF(SECOND, prev_time, payment_time) AS seconds
  FROM (
    SELECT *,
           LAG(city) OVER by_user AS prev_city,
           LAG(latitude) OVER by_user AS prev_lat,
           LAG(longitude) OVER by_user AS prev_lon,
           CAST(LAG(event_time) OVER by_user AS TIMESTAMP_LTZ(3)) AS prev_time
    FROM valid_payments
    WINDOW by_user AS (PARTITION BY user_id ORDER BY payment_time)
  )
)
WHERE prev_city IS NOT NULL AND km > 50 AND km * 3600 > 900 * GREATEST(seconds, 1);

CREATE TEMPORARY VIEW spike_alerts AS
SELECT 'AMOUNT_SPIKE' AS rule, transaction_id, user_id, payment_time, amount_paise, city,
       merchant_id,
       CONCAT(CAST(amount_paise * history / history_sum AS STRING), 'x the average of the last ',
              CAST(history AS STRING), ' payments') AS reason,
       user_home_city, user_kyc_level, merchant_category
FROM (
  SELECT *,
         COUNT(*) OVER last_21 - 1 AS history,
         SUM(amount_paise) OVER last_21 - amount_paise AS history_sum
  FROM valid_payments
  WINDOW last_21 AS (PARTITION BY user_id ORDER BY payment_time
                     ROWS BETWEEN 20 PRECEDING AND CURRENT ROW)
)
WHERE history >= 3 AND amount_paise * history >= 10 * history_sum;

EXECUTE STATEMENT SET
BEGIN
  INSERT INTO fraud_alerts
  SELECT CONCAT(rule, ':', transaction_id), rule, user_id, transaction_id,
         CAST(payment_time AS TIMESTAMP(3)), CAST(CURRENT_TIMESTAMP AS TIMESTAMP(3)),
         amount_paise, city, merchant_id, reason,
         user_home_city, user_kyc_level, merchant_category
  FROM (
    SELECT * FROM velocity_alerts
    UNION ALL SELECT * FROM travel_alerts
    UNION ALL SELECT * FROM spike_alerts
  );

  INSERT INTO payments_dlq
  SELECT transaction_id, user_id, merchant_id, amount_paise, event_time,
         CASE
           WHEN amount_paise IS NULL OR amount_paise <= 0 THEN 'amount must be above 0'
           ELSE 'missing user_id or merchant_id'
         END,
         CAST(CURRENT_TIMESTAMP AS TIMESTAMP(3))
  FROM payments
  WHERE amount_paise IS NULL OR amount_paise <= 0 OR user_id IS NULL OR merchant_id IS NULL;
END;

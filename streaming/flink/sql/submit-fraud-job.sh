#!/bin/bash
# Submits the fraud rules job to Flink, unless it is already running.
# Runs inside the Flink JobManager container: make flink-job
set -euo pipefail
cd /opt/flink

JOB=fraudpulse-fraud-rules
if ./bin/flink list --running 2>/dev/null | grep -q ": ${JOB} (RUNNING)"; then
  echo "${JOB} is already running"
  exit 0
fi

# fraud_alert.avsc is the single source of truth for the alert contract. Put it on one line,
# double every ' (that is how a quote is written inside a SQL string), and insert it.
# (sed would misread a & or | in the schema; fraud_alert.avsc contains neither.)
schema=$(tr -d '\n' < /opt/flink/schemas/fraud_alert.avsc | sed "s/'/''/g")
sed "s|@FRAUD_ALERT_SCHEMA@|${schema}|" /opt/flink/sql/20_fraud_rules.sql > /tmp/20_fraud_rules.sql

./bin/sql-client.sh -i /opt/flink/sql/01_tables.sql -f /tmp/20_fraud_rules.sql

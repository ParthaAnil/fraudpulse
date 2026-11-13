#!/bin/bash
# Replication role and publication for Debezium CDC. Read-only: it can never change data.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname "$POSTGRES_DB" \
     -v cdc_password="$DEBEZIUM_PG_PASSWORD" <<'EOSQL'
CREATE ROLE debezium WITH LOGIN REPLICATION PASSWORD :'cdc_password';
GRANT CONNECT ON DATABASE payments_core TO debezium;
GRANT USAGE ON SCHEMA public TO debezium;
GRANT SELECT ON users, accounts TO debezium;

-- The list of tables whose changes are published to Debezium.
CREATE PUBLICATION fraudpulse_cdc FOR TABLE users, accounts;
-- Log the whole old row on UPDATE and DELETE, so CDC events carry a "before" image.
-- Flink reads CDC as a changelog and needs the old version to replace it.
ALTER TABLE users REPLICA IDENTITY FULL;
ALTER TABLE accounts REPLICA IDENTITY FULL;
EOSQL

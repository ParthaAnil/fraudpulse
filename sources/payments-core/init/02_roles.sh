#!/bin/bash
# Least-privilege role for applications (the generator's seeding, later the API).
# The password comes from the environment, so it is never written in Git.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v app_password="$PAYMENTS_APP_PASSWORD" <<'EOSQL'
CREATE ROLE payments_app LOGIN PASSWORD :'app_password';

GRANT CONNECT ON DATABASE payments_core TO payments_app;
GRANT USAGE ON SCHEMA public TO payments_app;

-- Read, add and change rows. No DELETE, and no creating or dropping tables.
GRANT SELECT, INSERT, UPDATE ON users, accounts TO payments_app;
EOSQL

#!/bin/bash
# Read-only replication user for Debezium CDC. It can never change merchant data.
set -euo pipefail

MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket -uroot <<EOSQL
CREATE USER 'debezium'@'%' IDENTIFIED BY '${DEBEZIUM_MYSQL_PASSWORD}';

-- Read rows for the first snapshot (this database only).
GRANT SELECT ON merchants.* TO 'debezium'@'%';
-- Read the binlog. MySQL only offers these two as server-wide permissions.
GRANT REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO 'debezium'@'%';
EOSQL

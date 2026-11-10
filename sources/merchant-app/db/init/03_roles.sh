#!/bin/bash
# Least-privilege user for the merchant app. Passwords come from the environment.
set -euo pipefail

# MYSQL_PWD hands the root password to the client without putting it on the command line.
MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql --protocol=socket -uroot <<EOSQL
CREATE USER 'merchant_app'@'%' IDENTIFIED BY '${MERCHANT_APP_PASSWORD}';

-- The app onboards and updates merchants. It only reads the category lists.
GRANT SELECT, INSERT, UPDATE ON merchants.merchants       TO 'merchant_app'@'%';
GRANT SELECT                 ON merchants.categories      TO 'merchant_app'@'%';
GRANT SELECT                 ON merchants.category_groups TO 'merchant_app'@'%';
EOSQL

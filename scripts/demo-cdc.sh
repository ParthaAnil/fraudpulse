#!/bin/bash
# Makes one change in each source database, the way the applications would,
# so a CDC event for each appears in Kafka. Running it again flips both back.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Postgres: flipping the KYC level of user U0000002 (as payments_app)"
docker compose exec -T payments-core-db psql -q -U payments_app -d payments_core -c \
  "UPDATE users SET kyc_level = CASE kyc_level WHEN 'FULL' THEN 'MIN' ELSE 'FULL' END
   WHERE user_id = 'U0000002'"

echo "MySQL: flipping merchant M000001 between ACTIVE and SUSPENDED (through the API)"
read -r version status < <(curl -fsS http://127.0.0.1:8001/merchants/M000001 \
  | python3 -c 'import json, sys; m = json.load(sys.stdin); print(m["version"], m["status"])')
if [ "$status" = "ACTIVE" ]; then next=SUSPENDED; else next=ACTIVE; fi
curl -fsS -o /dev/null -X PATCH http://127.0.0.1:8001/merchants/M000001/status \
  -H 'Content-Type: application/json' -d "{\"status\": \"$next\", \"version\": $version}"
echo "  M000001: $status -> $next (version $version -> $((version + 1)))"

echo
echo "Now open http://localhost:8080 -> Topics, and look at the newest messages in:"
echo "  cdc.payments_core.public.users"
echo "  cdc.merchants.merchants.merchants"

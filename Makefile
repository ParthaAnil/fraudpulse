# FraudPulse: everyday commands. Run `make` or `make help` to list them.

# Recipe lines start with ">" instead of an invisible tab, so copy-paste cannot break them.
.RECIPEPREFIX = >
.DEFAULT_GOAL := help
.PHONY: help env up down clean ps logs test demo-cdc flink-sql flink-smoke flink-preview flink-job dlq-test

COMPOSE := docker compose
SECRETS := POSTGRES_PASSWORD PAYMENTS_APP_PASSWORD MYSQL_ROOT_PASSWORD \
           MERCHANT_APP_PASSWORD DEBEZIUM_PG_PASSWORD DEBEZIUM_MYSQL_PASSWORD

help: ## List the commands
> @grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  make %-9s %s\n", $$1, $$2}'

env: ## Create .env with random passwords (never overwrites an existing one)
> @if [ -f .env ]; then echo ".env exists, keeping it"; else \
>   for name in $(SECRETS); do printf '%s=%s\n' "$$name" "$$(openssl rand -hex 24)"; done > .env; \
>   echo "created .env with $(words $(SECRETS)) random passwords"; fi

up: env ## Build and start everything
> $(COMPOSE) up -d --build
> @echo "Kafka UI: http://localhost:8080   Merchant API: http://localhost:8001/docs"

down: ## Stop everything, keep the data
> $(COMPOSE) down

clean: ## Stop everything and DELETE all data (volumes)
> $(COMPOSE) down -v

ps: ## Show container status
> $(COMPOSE) ps -a

logs: ## Follow the generator's output (Ctrl+C to stop following)
> $(COMPOSE) logs -f generator

test: ## Lint and unit-test the generator
> cd generator && .venv/bin/ruff check . && .venv/bin/pytest -q

demo-cdc: ## Change one user and one merchant, to see CDC events in Kafka UI
> @bash scripts/demo-cdc.sh

flink-sql: ## Open the Flink SQL client (type QUIT; to leave)
> $(COMPOSE) exec flink-jobmanager ./bin/sql-client.sh -i /opt/flink/sql/01_tables.sql

flink-smoke: ## Check that Flink can read payments through Schema Registry
> $(COMPOSE) exec flink-jobmanager ./bin/sql-client.sh -f /opt/flink/sql/00_smoke_test.sql

flink-preview: ## Show 10 live payments enriched with user and merchant details
> $(COMPOSE) exec flink-jobmanager ./bin/sql-client.sh -i /opt/flink/sql/01_tables.sql -f /opt/flink/sql/10_preview_enrichment.sql

flink-job: ## Submit the fraud rules job (skipped if it is already running)
> $(COMPOSE) exec flink-jobmanager bash /opt/flink/sql/submit-fraud-job.sh

dlq-test: ## Send one invalid payment (amount 0) to check it reaches payments.dlq
> generator/.venv/bin/python scripts/send-bad-payment.py

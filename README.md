# FraudPulse

A real-time payments fraud and analytics platform, built end to end with free tools.

FraudPulse ingests UPI-style payment events through Kafka, catches fraud within
seconds with Flink, keeps a replayable history in an Iceberg lakehouse built with
Spark, models a star-schema warehouse in Snowflake with dbt, and gives analysts a
React console to review alerts. Everything runs locally first and moves to AWS and
Snowflake only in the final phase.

The full design is in [docs/design-document.pdf](docs/design-document.pdf).

## Architecture

```
Sources ──► Kafka ──┬──► Flink (fraud rules) ──► fraud.alerts ──► API ──► Console
                    │
                    └──► S3 / Iceberg (Bronze → Silver, Spark) ──► Snowflake (dbt marts) ──► Superset
```

- **Real-time path (seconds):** is this payment fraud?
- **Batch path (daily):** business questions, answered from the warehouse.

## Build status

| Phase | What it delivers | Status |
|---|---|---|
| 1. Sources and ingestion | Generator, Postgres, MySQL, Kafka, Debezium CDC | Done |
| 2. Real-time fraud detection | Flink rules, alerts API, Live alerts screen | Not started |
| 3. Lakehouse | MinIO + Iceberg, Bronze and Silver with Spark | Not started |
| 4. Warehouse modelling | dbt star schema and tests | Not started |
| 5. Orchestration and quality | Airflow, Great Expectations, reconciliation | Not started |
| 6. Platform, CI/CD, observability | k3d, Helm, GitHub Actions, Prometheus, Grafana | Not started |
| 7. Cloud deployment | Terraform, AWS, Snowflake, Superset | Not started |

## How to run

You need Docker with Docker Compose, `make` and `openssl` (on Windows, use WSL2 with Ubuntu).
The full stack uses about 5 GB of RAM.

```bash
make up        # creates .env with random passwords, builds and starts everything
make ps        # container status
make demo-cdc  # change a user and a merchant, and watch the CDC events
make down      # stop, keep the data
make clean     # stop and delete all data
make help      # every command
```

Then open:

- Kafka UI: http://localhost:8080 (topics, messages, schemas, connectors)
- Merchant API docs: http://localhost:8001/docs

What `make up` starts:

| Service | What it does |
|---|---|
| `payments-core-db` | Postgres 16: users and accounts |
| `merchant-db`, `merchant-app` | MySQL 8.4 and the FastAPI merchant onboarding API |
| `kafka`, `schema-registry` | Kafka (KRaft) and Avro schemas with BACKWARD compatibility |
| `kafka-connect` | Debezium CDC from both databases into `cdc.*` topics |
| `payments-seed`, `merchants-seed` | Load 5,000 users and 500 merchants (safe to rerun) |
| `generator` | Streams payments with injected fraud into `payments.transactions` |
| `kafka-ui` | A web view of all of it |

All ports listen on `127.0.0.1` only. Each application connects to its database with its own
least-privilege user, and Debezium's users are read-only.

To work on the generator itself:

```bash
cd generator
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
make -C .. test
```

## Repository layout

```
generator/              Python generator: fake payments with injected fraud, seed commands, tests
sources/payments-core/  Postgres schema, roles and CDC publication
sources/merchant-app/   FastAPI + MySQL merchant onboarding app
ingestion/schemas/      Avro schemas (single source of truth for event shapes)
ingestion/debezium/     Kafka Connect image and CDC connector configs
scripts/                Helper scripts (CDC demo)
docs/                   Design document and architecture decision records (ADRs)
```

## Measured results

Filled in as each phase is built and measured.

| Metric | Value |
|---|---|
| Events per second | – |
| Fraud alert latency (p99) | – |
| Rule precision / recall | – |
| Rows processed | – |
| Daily cloud cost | – |

## Data

All data is synthetic. Real payment data is private, so a generator creates payments
with known, injected fraud. Knowing the true answer lets us measure how well the
fraud rules work.

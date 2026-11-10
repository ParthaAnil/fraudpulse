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
| 1. Sources and ingestion | Generator, Postgres, MySQL, Kafka, Debezium CDC | In progress |
| 2. Real-time fraud detection | Flink rules, alerts API, Live alerts screen | Not started |
| 3. Lakehouse | MinIO + Iceberg, Bronze and Silver with Spark | Not started |
| 4. Warehouse modelling | dbt star schema and tests | Not started |
| 5. Orchestration and quality | Airflow, Great Expectations, reconciliation | Not started |
| 6. Platform, CI/CD, observability | k3d, Helm, GitHub Actions, Prometheus, Grafana | Not started |
| 7. Cloud deployment | Terraform, AWS, Snowflake, Superset | Not started |

## Repository layout

```
generator/              Python transaction generator (fake payments + injected fraud)
sources/payments-core/  Postgres: users, accounts, balances
sources/merchant-app/   FastAPI + MySQL merchant onboarding app
ingestion/schemas/      Avro schemas (single source of truth for event shapes)
ingestion/debezium/     CDC connector configs
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

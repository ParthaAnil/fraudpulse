# 0001. Store money as whole-number paise

- **Status:** Accepted
- **Date:** 2026-11-10
- **Phase:** 1 (Sources and ingestion)

## Context

Money amounts travel through many systems in FraudPulse: the Python generator,
Kafka (Avro), Flink, Spark, Iceberg and Snowflake. Each one could represent
decimal numbers differently.

- **Floating-point numbers are inexact.** Most decimal amounts cannot be stored
  exactly as a `double`: `0.1 + 0.2` gives `0.30000000000000004`. Summed over
  millions of payments, totals drift. Our reconciliation check (rupee totals must
  match across Bronze, Silver and Snowflake) would fail by tiny amounts.
- **Avro's `decimal` type is exact but awkward.** It is stored as raw bytes, which
  Kafka UI and many libraries display or handle inconsistently.
- **We saw silent data loss in testing.** Writing the decimal `499.99` into an
  Avro `long` field did not raise an error: the encoder silently wrote `499`
  (₹4.99 instead of ₹499.99). Only Avro's strict validation caught it.

## Decision

Store every money amount as a 64-bit whole number of **paise**
(1 rupee = 100 paise), in a field whose name ends in `_paise`
(for example `amount_paise`, `balance_paise`).

- ₹499.99 is stored as `49999`.
- Convert to rupees only when displaying (console, dashboards).
- The generator creates amounts as integers, and its tests run every generated
  record through Avro strict validation.

## Consequences

Good:

- Exact arithmetic everywhere. Reconciliation totals match to the paisa.
- A simple type (`long` in Avro, `BIGINT` in SQL) that every tool supports.
- The `_paise` suffix makes the unit obvious, so nobody reads `49999` as ₹49,999.

Costs:

- Display code must divide by 100.
- Fractions of a paisa (for example a percentage fee) need an explicit rounding
  rule. If we ever need that, it gets its own ADR.
- None in practice from size limits: a `long` holds up to about 9.2 × 10^18 paise.

## Alternatives considered

- **`double` (floating point):** rejected, because it is inexact.
- **Avro `decimal(18, 2)`:** exact, but stored as bytes that are hard to read in
  tools and awkward in Python and Flink. Rejected for now.

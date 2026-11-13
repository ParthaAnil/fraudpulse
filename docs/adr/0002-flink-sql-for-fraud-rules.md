# 0002. Write the fraud rules in Flink SQL

- **Status:** Accepted
- **Date:** 2026-11-13
- **Phase:** 2 (Real-time fraud detection)

## Context

Phase 2 needs a stateful stream job that reads payments and two CDC streams, joins each
payment with the user's and merchant's state at the time of the payment, applies three
rules (velocity, impossible travel, amount spike), and writes alerts exactly once.
Flink offers three ways to write it:

- **Flink SQL:** declarative; reads Avro, Schema Registry and Debezium CDC formats out of
  the box; supports event-time windows, temporal joins and `MATCH_RECOGNIZE` patterns.
- **Java DataStream API:** full control over keyed state, timers and side outputs, but
  needs Java and Maven, a second language in a Python project.
- **PyFlink:** stays in Python, but Avro and Schema Registry support is clumsy, it is
  slower, and debugging crosses between Python and Java.

## Decision

Write the job in **Flink SQL**.

- Event time comes from `payment.event_time`, with a **2-second watermark delay**. The
  generator sends some normal payments up to 1.5 seconds late, so every late payment
  still arrives before its watermark.
- User and merchant details come from the CDC topics through **event-time temporal joins**.
- State has a time-to-live, so memory cannot grow forever.
- Alerts go to `fraud.alerts` with an exactly-once Kafka sink. The alert ID is
  `RULE:transaction_id`, so replays produce the same ID.

To measure the rules honestly, payments also carry a `scenario_id` (payment schema
version 2). Recall is counted per fraud scenario, not per payment, because a velocity
rule can only fire from the 6th payment of a burst onwards.

## Consequences

Good:

- The rules are short and readable, close to how an analyst would describe them.
- No second programming language; the formats we already use are built in.
- Streaming SQL is widely used in industry, so the skill transfers.

Costs:

- Less low-level control than the DataStream API. Records that fail to parse cannot be
  sent to a side output; bad records are mainly stopped earlier, by Schema Registry.
- A 2-second watermark delay is added to every alert's latency, inside the 5-second target.
- Avro enums are awkward to write from SQL, so `fraud_alert.rule` is a string.

## Alternatives considered

- **Java DataStream API:** rejected for now; it would double the time for Phase 2.
  It can replace a single rule later if SQL is not enough.
- **PyFlink:** rejected because of weak Avro and Schema Registry support.

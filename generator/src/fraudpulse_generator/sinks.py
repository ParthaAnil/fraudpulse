"""Where generated payments go: the terminal (StdoutSink) or Kafka (KafkaSink)."""

import json
import sys
from pathlib import Path
from typing import Protocol, TextIO

from confluent_kafka import KafkaError, Message, Producer
from confluent_kafka.schema_registry import Schema, SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import MessageField, SerializationContext, StringSerializer
from fastavro import parse_schema
from fastavro.validation import validate

from fraudpulse_generator.payments import Payment

TOPIC = "payments.transactions"
# This file is generator/src/fraudpulse_generator/sinks.py: the repository is 3 folders up.
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCHEMA_PATH = REPO_ROOT / "ingestion" / "schemas" / "payment.avsc"


class Sink(Protocol):
    def send(self, payment: Payment) -> None: ...

    def close(self) -> int: ...  # returns how many payments could not be delivered


class StdoutSink:
    """Writes one JSON object per line: easy to read, and easy to pipe into other tools."""

    def __init__(self, out: TextIO = sys.stdout) -> None:
        self._out = out

    def send(self, payment: Payment) -> None:
        self._out.write(json.dumps(payment.to_record()) + "\n")

    def close(self) -> int:
        self._out.flush()
        return 0


class KafkaSink:
    """Sends payments to Kafka as Avro, keyed by user_id, after checking each one strictly."""

    def __init__(
        self,
        bootstrap_servers: str,
        schema_registry_url: str,
        schema_path: Path,
        topic: str = TOPIC,
    ) -> None:
        schema_str = schema_path.read_text(encoding="utf-8")
        self._topic = topic
        self._parsed_schema = parse_schema(json.loads(schema_str))

        # Register the schema now, so a missing registry or an incompatible change fails at
        # startup, not on the first payment.
        registry = SchemaRegistryClient({"url": schema_registry_url})
        self.schema_id = registry.register_schema(f"{topic}-value", Schema(schema_str, "AVRO"))
        self._value_serializer = AvroSerializer(registry, schema_str)
        self._key_serializer = StringSerializer("utf_8")

        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "enable.idempotence": True,  # retries never create duplicate payments
                "acks": "all",  # a payment counts as sent only once Kafka has stored it
                "linger.ms": 20,  # wait up to 20 ms to send payments in batches
                "compression.type": "lz4",
                "message.timeout.ms": 30_000,  # give up on a payment after 30 s, and report it
            }
        )
        # Fail fast if Kafka is unreachable or the topic does not exist.
        metadata = self._producer.list_topics(topic, timeout=10)
        topic_error = metadata.topics[topic].error
        if topic_error is not None:
            raise RuntimeError(f"topic {topic!r}: {topic_error.str()}")
        self.delivered = 0
        self.failed = 0

    def send(self, payment: Payment) -> None:
        record = payment.to_record()
        validate(record, self._parsed_schema, strict=True)  # ADR 0001: never truncate silently
        key = self._key_serializer(
            payment.user_id, SerializationContext(self._topic, MessageField.KEY)
        )
        value = self._value_serializer(
            record, SerializationContext(self._topic, MessageField.VALUE)
        )
        while True:
            try:
                self._producer.produce(
                    self._topic, key=key, value=value, on_delivery=self._on_delivery
                )
                break
            except BufferError:
                # The local send queue is full: wait for Kafka to accept some payments.
                self._producer.poll(1)
        self._producer.poll(0)  # run the delivery callbacks of payments that have finished

    def close(self) -> int:
        not_sent = self._producer.flush(30)
        failures = self.failed + not_sent
        print(f"kafka: delivered {self.delivered}, failed {failures}", file=sys.stderr)
        return failures

    def _on_delivery(self, err: KafkaError | None, msg: Message) -> None:
        if err is None:
            self.delivered += 1
        else:
            self.failed += 1
            print(f"kafka: delivery failed: {err}", file=sys.stderr)

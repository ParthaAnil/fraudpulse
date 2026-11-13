"""Sends one invalid payment (amount 0) to payments.transactions, to test the DLQ path.

Schema Registry accepts it, because Avro checks types, not business rules (a long can be 0).
The Flink job must route it to payments.dlq instead of the fraud rules.
Run with: make dlq-test
"""

import time
import uuid
from pathlib import Path

from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import MessageField, SerializationContext

TOPIC = "payments.transactions"
SCHEMA = Path(__file__).resolve().parents[1] / "ingestion" / "schemas" / "payment.avsc"

registry = SchemaRegistryClient({"url": "http://localhost:8081"})
# Use the registered schema version; never register a new one from a test script.
serialize = AvroSerializer(
    registry, SCHEMA.read_text(), conf={"auto.register.schemas": False, "use.latest.version": True}
)
payment = {
    "transaction_id": str(uuid.uuid4()),
    "event_time": int(time.time() * 1000),
    "user_id": "U0000001",
    "payer_upi_id": "test@fpbank",
    "merchant_id": "M000001",
    "payee_upi_id": "m000001@fpmerchant",
    "amount_paise": 0,  # the problem: not a real payment
    "currency": "INR",
    "payment_method": "UPI_QR",
    "status": "SUCCESS",
    "city": "Pune",
    "latitude": 18.5204,
    "longitude": 73.8567,
    "device_id": "dev-dlq-test",
    "injected_fraud_type": None,
    "scenario_id": None,
}
producer = Producer({"bootstrap.servers": "localhost:9092"})
value = serialize(payment, SerializationContext(TOPIC, MessageField.VALUE))
producer.produce(TOPIC, key=payment["user_id"].encode(), value=value)
producer.flush(10)
print(f"sent invalid payment {payment['transaction_id']} (amount 0); look for it in payments.dlq")

"""Payment events. Field names match ingestion/schemas/payment.avsc."""

import math
import random
import uuid
from dataclasses import asdict, dataclass

from fraudpulse_generator.geo import City
from fraudpulse_generator.population import RUPEE, Merchant, User

PAYMENT_METHODS = ("UPI_QR", "UPI_INTENT", "UPI_COLLECT")
PAYMENT_METHOD_WEIGHTS = (60, 35, 5)
FAILURE_RATE = 0.02  # about 2 in 100 payments fail (wrong PIN, bank down, ...)


@dataclass
class Payment:
    transaction_id: str
    event_time: int  # milliseconds since 1970-01-01 UTC
    user_id: str
    payer_upi_id: str
    merchant_id: str
    payee_upi_id: str
    amount_paise: int
    currency: str
    payment_method: str
    status: str
    city: str
    latitude: float
    longitude: float
    device_id: str
    injected_fraud_type: str | None  # the answer key: None means a normal payment
    scenario_id: str | None = None  # shared by all fraudulent payments of one scenario

    def to_record(self) -> dict:
        """The plain dictionary that the Avro serializer writes to Kafka."""
        return asdict(self)


def make_payment(
    rng: random.Random,
    user: User,
    merchant: Merchant,
    city: City,
    event_time_ms: int,
    amount_paise: int,
    *,
    device_id: str | None = None,
    fraud_type: str | None = None,
    scenario_id: str | None = None,
) -> Payment:
    """Build one payment. Refuses amounts that are not a positive whole number of paise."""
    # ADR 0001: a decimal here would be silently cut by the Avro encoder, so stop it early.
    if type(amount_paise) is not int or amount_paise <= 0:
        raise ValueError(f"amount_paise must be a positive int, got {amount_paise!r}")
        # The answer key must be consistent: a fraud label always comes with its scenario, and back.
    if (fraud_type is None) != (scenario_id is None):
        raise ValueError("fraud_type and scenario_id must be given together")
    return Payment(
        # Built from the seeded rng (not uuid.uuid4()) so the same seed gives the same IDs.
        transaction_id=str(uuid.UUID(int=rng.getrandbits(128), version=4)),
        event_time=event_time_ms,
        user_id=user.user_id,
        payer_upi_id=user.upi_id,
        merchant_id=merchant.merchant_id,
        payee_upi_id=merchant.upi_id,
        amount_paise=amount_paise,
        currency="INR",
        payment_method=rng.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS)[0],
        status="FAILED" if rng.random() < FAILURE_RATE else "SUCCESS",
        city=city.name,
        latitude=city.latitude,
        longitude=city.longitude,
        device_id=device_id or user.device_id,
        injected_fraud_type=fraud_type,
        scenario_id=scenario_id,
    )


def normal_amount(rng: random.Random, user: User) -> int:
    """An everyday amount for this user: near their typical amount, never above 4x it."""
    amount = rng.lognormvariate(math.log(user.typical_amount_paise), 0.5)
    return max(1 * RUPEE, min(round(amount), 4 * user.typical_amount_paise))

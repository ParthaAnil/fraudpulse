"""The stream as a whole: ordered, valid, repeatable, and with a clean answer key."""

from collections import defaultdict
from itertools import islice

import pytest
from fastavro.validation import validate

from fraudpulse_generator.engine import PaymentStream, StreamConfig

from .conftest import START_MS


def take(users, merchants, count, **config):
    stream = PaymentStream(users, merchants, StreamConfig(**config), START_MS)
    return list(islice(stream, count))


@pytest.fixture(scope="module")
def payments(users, merchants):
    return take(users, merchants, 20_000)


def test_payments_come_out_in_event_time_order(payments):
    times = [p.event_time for p in payments]
    assert times == sorted(times)


def test_every_payment_passes_strict_avro_validation(payments, payment_schema):
    for payment in payments:
        validate(payment.to_record(), payment_schema, strict=True)


def test_transaction_ids_are_unique(payments):
    assert len({p.transaction_id for p in payments}) == len(payments)


def test_fraud_share_is_close_to_the_target(payments):
    fraud = sum(p.injected_fraud_type is not None for p in payments)
    assert 0.015 <= fraud / len(payments) <= 0.025


def test_normal_payments_never_trip_the_velocity_rule(payments):
    by_user = defaultdict(list)
    for p in payments:
        if p.injected_fraud_type is None:
            by_user[p.user_id].append(p.event_time)
    for times in by_user.values():
        for i, t in enumerate(times):
            in_last_minute = [s for s in times[: i + 1] if t - s < 60_000]
            assert len(in_last_minute) <= 5


def test_same_seed_gives_the_same_stream(users, merchants):
    first = [p.transaction_id for p in take(users, merchants, 500)]
    again = [p.transaction_id for p in take(users, merchants, 500)]
    other = [p.transaction_id for p in take(users, merchants, 500, seed=7)]
    assert first == again
    assert first != other


def test_zero_fraud_rate_gives_only_normal_payments(users, merchants):
    stream = take(users, merchants, 2_000, fraud_rate=0.0)
    assert all(p.injected_fraud_type is None for p in stream)


@pytest.mark.parametrize(
    "config", [{"rate_per_second": 0}, {"fraud_rate": 0.5}, {"fraud_rate": -0.1}]
)
def test_invalid_config_is_refused(users, merchants, config):
    with pytest.raises(ValueError):
        PaymentStream(users, merchants, StreamConfig(**config), START_MS)

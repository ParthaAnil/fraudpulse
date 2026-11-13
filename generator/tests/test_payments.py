"""The money guard from ADR 0001, and payments that match payment.avsc."""

import pytest
from fastavro.validation import validate

from fraudpulse_generator.geo import CITY_BY_NAME
from fraudpulse_generator.payments import make_payment, normal_amount

from .conftest import START_MS


@pytest.mark.parametrize("bad_amount", [499.99, "49999", True, 0, -100, None])
def test_money_guard_refuses_anything_but_positive_whole_paise(rng, users, merchants, bad_amount):
    with pytest.raises(ValueError):
        make_payment(rng, users[0], merchants[0], CITY_BY_NAME["Pune"], START_MS, bad_amount)


def test_payment_passes_strict_avro_validation(rng, users, merchants, payment_schema):
    payment = make_payment(rng, users[0], merchants[0], CITY_BY_NAME["Pune"], START_MS, 49_999)
    assert validate(payment.to_record(), payment_schema, strict=True)
    assert payment.injected_fraud_type is None


def test_normal_amounts_stay_below_four_times_typical(rng, users):
    for user in users:
        for _ in range(20):
            amount = normal_amount(rng, user)
            assert type(amount) is int
            assert 0 < amount <= 4 * user.typical_amount_paise

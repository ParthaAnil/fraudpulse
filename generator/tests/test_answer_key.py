"""The answer key: every fraudulent payment has a label and a scenario_id, nothing else does."""

import pytest

from fraudpulse_generator.engine import PaymentStream, StreamConfig
from fraudpulse_generator.fraud import FRAUD_PATTERNS
from fraudpulse_generator.geo import CITY_BY_NAME
from fraudpulse_generator.payments import make_payment

from .conftest import START_MS


@pytest.mark.parametrize(
    "labels", [{"fraud_type": "VELOCITY"}, {"scenario_id": "4f0a3c1e-0000-4000-8000-000000000000"}]
)
def test_fraud_label_and_scenario_id_come_together(rng, users, merchants, labels):
    with pytest.raises(ValueError):
        make_payment(rng, users[0], merchants[0], CITY_BY_NAME["Pune"], START_MS, 100, **labels)


def test_each_scenario_shares_one_new_scenario_id(rng, users, merchants):
    seen = set()
    for pattern in FRAUD_PATTERNS.values():
        for user in users[:20]:
            scenario = pattern(rng, user, merchants, CITY_BY_NAME[user.home_city], START_MS)
            fraud = [p for p in scenario.payments if p.injected_fraud_type is not None]
            ids = {p.scenario_id for p in fraud}
            assert len(ids) == 1 and None not in ids  # one id for the whole scenario
            assert ids.isdisjoint(seen)  # and a new one every time
            seen |= ids
            for p in scenario.payments:
                if p.injected_fraud_type is None:
                    assert p.scenario_id is None  # e.g. the real user paying at home


def test_scenario_ids_match_the_fraud_labels_in_the_stream(users, merchants):
    stream = PaymentStream(users, merchants, StreamConfig(), START_MS)
    for _, p in zip(range(10_000), stream, strict=False):
        assert (p.injected_fraud_type is None) == (p.scenario_id is None)

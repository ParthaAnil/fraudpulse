"""Each fraud pattern must clearly cross the line of the rule it is built for."""

from fraudpulse_generator.fraud import (
    MAX_TRAVEL_SPEED_KMH,
    amount_spike,
    impossible_travel,
    velocity_burst,
)
from fraudpulse_generator.geo import CITY_BY_NAME, distance_km

from .conftest import START_MS


def test_velocity_burst_is_more_than_five_payments_within_a_minute(rng, users, merchants):
    for user in users[:50]:
        scenario = velocity_burst(rng, user, merchants, CITY_BY_NAME[user.home_city], START_MS)
        times = [p.event_time for p in scenario.payments]
        assert len(times) > 5
        assert max(times) - min(times) < 60_000
        assert all(p.injected_fraud_type == "VELOCITY" for p in scenario.payments)
        assert scenario.user_free_at_ms >= max(times) + 60_000


def test_impossible_travel_is_at_least_twice_jet_speed(rng, users, merchants):
    for user in users[:50]:
        home = CITY_BY_NAME[user.home_city]
        at_home, far_away = impossible_travel(rng, user, merchants, home, START_MS).payments
        km = distance_km(home, CITY_BY_NAME[far_away.city])
        hours = (far_away.event_time - at_home.event_time) / 3_600_000
        assert km / hours >= 2 * MAX_TRAVEL_SPEED_KMH * 0.999
        assert at_home.injected_fraud_type is None  # the real user at home is not fraud
        assert far_away.injected_fraud_type == "IMPOSSIBLE_TRAVEL"
        assert far_away.device_id != at_home.device_id  # the fraudster's own phone


def test_amount_spike_is_well_above_ten_times_typical(rng, users, merchants):
    for user in users[:50]:
        scenario = amount_spike(rng, user, merchants, CITY_BY_NAME[user.home_city], START_MS)
        (spike,) = scenario.payments
        assert spike.amount_paise >= 15 * user.typical_amount_paise - 1
        assert spike.injected_fraud_type == "AMOUNT_SPIKE"

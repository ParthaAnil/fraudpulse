"""The three fraud patterns the generator injects, one per rule in the design doc.

Each pattern returns a Scenario: the payments to send, labelled in `injected_fraud_type`
(the answer key), and the time when this user may make normal payments again. All the
fraudulent payments of one scenario share a `scenario_id`, so recall can be measured per
scenario ("did we catch this burst?") instead of per payment.
"""

import random
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from fraudpulse_generator.geo import CITIES, City, distance_km
from fraudpulse_generator.payments import Payment, make_payment, normal_amount
from fraudpulse_generator.population import Merchant, User

# Velocity rule: more than 5 payments by one user within 1 minute.
VELOCITY_BURST_SIZE = (6, 10)
VELOCITY_BURST_SECONDS = 50  # the whole burst fits well inside one minute

# Impossible-travel rule: two cities too far apart for the time between payments.
MAX_TRAVEL_SPEED_KMH = 900  # about a passenger jet; anything faster is impossible
FAR_CITY_MIN_KM = 1_000
TRAVEL_GAP_MINUTES = (2, 30)

# Amount-spike rule: 10x the user's running average.
SPIKE_MULTIPLIER = (15, 40)  # well above 10x, because normal amounts are capped at 4x

MS_PER_SECOND = 1_000
MS_PER_MINUTE = 60_000
MS_PER_HOUR = 3_600_000


@dataclass
class Scenario:
    payments: list[Payment]
    user_free_at_ms: int  # no normal payments for this user before this time


def velocity_burst(
    rng: random.Random, user: User, merchants: Sequence[Merchant], city: City, start_ms: int
) -> Scenario:
    """Many small payments in under a minute, as if a stolen phone is being drained."""
    scenario_id = _new_scenario_id(rng)
    count = rng.randint(*VELOCITY_BURST_SIZE)
    offsets_ms = sorted(
        round(rng.uniform(0, VELOCITY_BURST_SECONDS) * MS_PER_SECOND) for _ in range(count)
    )
    payments = [
        make_payment(
            rng, user, rng.choice(merchants), city, start_ms + offset,
            normal_amount(rng, user), fraud_type="VELOCITY", scenario_id=scenario_id,
        )
        for offset in offsets_ms
    ]
    # Wait one more minute, so normal payments cannot fall inside the burst's window.
    return Scenario(payments, user_free_at_ms=payments[-1].event_time + MS_PER_MINUTE)


def impossible_travel(
    rng: random.Random, user: User, merchants: Sequence[Merchant], city: City, start_ms: int
) -> Scenario:
    """A normal payment at home, then one from a far city minutes later, on another phone."""
    scenario_id = _new_scenario_id(rng)
    far_city = _pick_far_city(rng, city)
    km = distance_km(city, far_city)
    # Keep the implied speed at least twice the fastest real travel, so it is clearly impossible.
    max_gap_minutes = min(TRAVEL_GAP_MINUTES[1], km / (2 * MAX_TRAVEL_SPEED_KMH) * 60)
    gap_ms = round(rng.uniform(TRAVEL_GAP_MINUTES[0], max_gap_minutes) * MS_PER_MINUTE)

    at_home = make_payment(
        rng, user, rng.choice(merchants), city, start_ms, normal_amount(rng, user)
    )
    far_away = make_payment(
        rng, user, rng.choice(merchants), far_city, start_ms + gap_ms,
        normal_amount(rng, user),
        device_id=f"dev-{rng.getrandbits(48):012x}",  # the fraudster's phone
        fraud_type="IMPOSSIBLE_TRAVEL",
        scenario_id=scenario_id,
    )
    # The real user's next payment comes from home. Wait until a trip back would be possible,
    # otherwise that next payment would look like a second impossible jump.
    travel_back_ms = round(km / MAX_TRAVEL_SPEED_KMH * MS_PER_HOUR)
    return Scenario([at_home, far_away], user_free_at_ms=far_away.event_time + travel_back_ms)


def amount_spike(
    rng: random.Random, user: User, merchants: Sequence[Merchant], city: City, start_ms: int
) -> Scenario:
    """One payment far bigger than anything this user normally pays."""
    amount = round(user.typical_amount_paise * rng.uniform(*SPIKE_MULTIPLIER))
    spike = make_payment(
        rng, user, rng.choice(merchants), city, start_ms, amount,
        fraud_type="AMOUNT_SPIKE", scenario_id=_new_scenario_id(rng),
    )
    return Scenario([spike], user_free_at_ms=start_ms)


FraudPattern = Callable[[random.Random, User, Sequence[Merchant], City, int], Scenario]

FRAUD_PATTERNS: dict[str, FraudPattern] = {
    "VELOCITY": velocity_burst,
    "IMPOSSIBLE_TRAVEL": impossible_travel,
    "AMOUNT_SPIKE": amount_spike,
}


def _new_scenario_id(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def _pick_far_city(rng: random.Random, city: City) -> City:
    far = [c for c in CITIES if distance_km(city, c) >= FAR_CITY_MIN_KM]
    if far:
        return rng.choice(far)
    return max(CITIES, key=lambda c: distance_km(city, c))  # fallback: the farthest city

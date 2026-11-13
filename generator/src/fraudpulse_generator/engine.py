"""Mixes normal payments and injected fraud into one stream, ordered by event time.

A small share of normal payments can arrive late (out of order), as on real networks, so
that the stream processor's watermarks have something to do.
"""

import heapq
import itertools
import random
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from fraudpulse_generator.fraud import FRAUD_PATTERNS
from fraudpulse_generator.geo import CITY_BY_NAME
from fraudpulse_generator.payments import Payment, make_payment, normal_amount
from fraudpulse_generator.population import Merchant, User

# A user's normal payments are at least 15 seconds apart, so normal traffic never reaches
# the velocity rule (more than 5 in a minute) by accident.
NORMAL_GAP_MS = 15_000
LOCAL_MERCHANT_SHARE = 0.8  # most people pay shops in their own city
FREE_USER_ATTEMPTS = 20
# A late payment is sent this long after it happened. Flink allows 2 s of lateness (Phase 2).
LATENESS_MS = (200, 1_500)


@dataclass(frozen=True)
class StreamConfig:
    rate_per_second: float = 20.0
    fraud_rate: float = 0.02  # target share of all payments that are fraud
    seed: int = 42
    late_ratio: float = 0.0  # share of normal payments that arrive out of order


class PaymentStream:
    """An endless, repeatable stream of payments. Loop over it to get them in time order."""

    def __init__(
        self,
        users: Sequence[User],
        merchants: Sequence[Merchant],
        config: StreamConfig,
        start_ms: int,
    ) -> None:
        if not users or not merchants:
            raise ValueError("need at least one user and one merchant")
        if config.rate_per_second <= 0:
            raise ValueError("rate_per_second must be above 0")
        if not 0 <= config.fraud_rate < 0.5:
            raise ValueError("fraud_rate must be at least 0 and below 0.5")
        if not 0 <= config.late_ratio < 0.5:
            raise ValueError("late_ratio must be at least 0 and below 0.5")
        self._users = users
        self._merchants = merchants
        self._config = config
        self._rng = random.Random(config.seed + 2)  # noqa: S311 (fake data: repeatable)
        self._clock_ms = float(start_ms)
        self._step_ms = 1000 / config.rate_per_second
        self._free_at: dict[str, int] = {}  # user_id -> earliest time of their next payment
        # A heap of (send time, tiebreak, payment). Send time = event time, unless it is late.
        self._pending: list[tuple[int, int, Payment]] = []
        self._tiebreak = itertools.count()
        self._planned_total = 0
        self._planned_fraud = 0
        self._local_merchants: dict[str, list[Merchant]] = {}
        for merchant in merchants:
            self._local_merchants.setdefault(merchant.city, []).append(merchant)

    def __iter__(self) -> Iterator[Payment]:
        while True:
            now = round(self._clock_ms)
            if self._planned_fraud < self._config.fraud_rate * self._planned_total:
                self._start_fraud(now)
            else:
                self._add_normal(now)
            self._clock_ms += self._step_ms
            # Hand out everything due to be sent by now, in send order.
            while self._pending and self._pending[0][0] <= now:
                yield heapq.heappop(self._pending)[2]

    def _add_normal(self, now: int) -> None:
        user = self._free_user(now)
        if user is None:
            return  # everyone we tried is busy at this instant; skip a beat
        city = CITY_BY_NAME[user.home_city]
        payment = make_payment(
            self._rng, user, self._pick_merchant(city.name), city, now,
            normal_amount(self._rng, user),
        )
        self._free_at[user.user_id] = now + NORMAL_GAP_MS
        delay_ms = 0
        if self._config.late_ratio and self._rng.random() < self._config.late_ratio:
            delay_ms = self._rng.randint(*LATENESS_MS)
        self._schedule([payment], delay_ms)

    def _start_fraud(self, now: int) -> None:
        user = self._free_user(now)
        if user is None:
            return
        fraud_type = self._rng.choice(list(FRAUD_PATTERNS))
        scenario = FRAUD_PATTERNS[fraud_type](
            self._rng, user, self._merchants, CITY_BY_NAME[user.home_city], now
        )
        self._free_at[user.user_id] = max(scenario.user_free_at_ms, now + NORMAL_GAP_MS)
        self._schedule(scenario.payments)

    def _schedule(self, payments: list[Payment], delay_ms: int = 0) -> None:
        for payment in payments:
            send_at = payment.event_time + delay_ms
            heapq.heappush(self._pending, (send_at, next(self._tiebreak), payment))
            self._planned_total += 1
            if payment.injected_fraud_type is not None:
                self._planned_fraud += 1

    def _free_user(self, now: int) -> User | None:
        """A random user who is not in the middle of something, or None if none was found."""
        for _ in range(FREE_USER_ATTEMPTS):
            user = self._rng.choice(self._users)
            if self._free_at.get(user.user_id, 0) <= now:
                return user
        return None

    def _pick_merchant(self, city_name: str) -> Merchant:
        local = self._local_merchants.get(city_name)
        if local and self._rng.random() < LOCAL_MERCHANT_SHARE:
            return self._rng.choice(local)
        return self._rng.choice(self._merchants)

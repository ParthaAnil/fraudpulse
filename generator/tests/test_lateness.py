"""Late (out-of-order) payments: some arrive late, never too late, and never fraud."""

from itertools import islice

import pytest

from fraudpulse_generator.cli import _parse_args
from fraudpulse_generator.engine import LATENESS_MS, PaymentStream, StreamConfig

from .conftest import START_MS


def take(users, merchants, count, late_ratio):
    config = StreamConfig(late_ratio=late_ratio)
    return list(islice(PaymentStream(users, merchants, config, START_MS), count))


def test_late_payments_arrive_out_of_order_but_never_beyond_the_limit(users, merchants):
    newest_seen = 0
    out_of_order = 0
    for p in take(users, merchants, 5_000, late_ratio=0.1):
        if p.event_time < newest_seen:
            out_of_order += 1
            assert newest_seen - p.event_time <= LATENESS_MS[1]
        newest_seen = max(newest_seen, p.event_time)
    assert out_of_order > 0


def test_fraud_payments_are_never_sent_late(users, merchants):
    newest_seen = 0
    for p in take(users, merchants, 5_000, late_ratio=0.3):
        if p.injected_fraud_type is not None:
            assert p.event_time >= newest_seen
        newest_seen = max(newest_seen, p.event_time)


def test_no_late_ratio_means_strict_event_time_order(users, merchants):
    times = [p.event_time for p in take(users, merchants, 5_000, late_ratio=0.0)]
    assert times == sorted(times)


@pytest.mark.parametrize("late_ratio", [-0.1, 0.5])
def test_invalid_late_ratio_is_refused(users, merchants, late_ratio):
    with pytest.raises(ValueError):
        PaymentStream(users, merchants, StreamConfig(late_ratio=late_ratio), START_MS)


def test_late_ratio_option_is_parsed():
    assert _parse_args(["run", "--late-ratio", "0.02"]).late_ratio == 0.02


def test_late_ratio_option_rejects_out_of_range():
    with pytest.raises(SystemExit):
        _parse_args(["run", "--late-ratio", "0.9"])

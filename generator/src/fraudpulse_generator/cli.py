"""Command line for the generator.

    fraudpulse-gen run --count 20 --fast        # 20 payments, as fast as possible
    fraudpulse-gen run --rate 5 --duration 60   # real time: 5 payments a second for a minute
"""

import argparse
import os
import sys
import time
from collections import Counter

from fraudpulse_generator.engine import PaymentStream, StreamConfig
from fraudpulse_generator.population import make_merchants, make_users
from fraudpulse_generator.sinks import Sink, StdoutSink


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        users = make_users(args.users, seed=args.seed)
        merchants = make_merchants(args.merchants, seed=args.seed)
        config = StreamConfig(
            rate_per_second=args.rate, fraud_rate=args.fraud_rate, seed=args.seed
        )
        start_ms = int(time.time() * 1000)
        stream = PaymentStream(users, merchants, config, start_ms)
    except ValueError as e:
        print(f"fraudpulse-gen: error: {e}", file=sys.stderr)
        return 2

    sink: Sink = StdoutSink()
    counts: Counter[str] = Counter()
    try:
        _run(stream, sink, counts, args, start_ms)
    except KeyboardInterrupt:
        pass  # Ctrl+C: stop cleanly and still print the summary
    except BrokenPipeError:
        # The reader stopped early (for example `| head`). That is fine, not an error.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0
    finally:
        sink.close()
    _print_summary(counts)
    return 0


def _run(
    stream: PaymentStream,
    sink: Sink,
    counts: Counter[str],
    args: argparse.Namespace,
    start_ms: int,
) -> None:
    started = time.monotonic()
    for payment in stream:
        elapsed_ms = payment.event_time - start_ms
        if args.duration is not None and elapsed_ms >= args.duration * 1000:
            break
        if not args.fast:
            # Real time: wait until the wall clock reaches this payment's event time.
            delay = elapsed_ms / 1000 - (time.monotonic() - started)
            if delay > 0:
                time.sleep(delay)
        sink.send(payment)
        counts[payment.injected_fraud_type or "NORMAL"] += 1
        if args.count is not None and counts.total() >= args.count:
            break


def _print_summary(counts: Counter[str]) -> None:
    total = counts.total()
    fraud = total - counts["NORMAL"]
    share = fraud / total if total else 0.0
    # Summary goes to stderr, so stdout stays pure JSON for whatever reads it.
    print(
        f"sent {total} payments, {fraud} injected fraud ({share:.1%}): {dict(counts)}",
        file=sys.stderr,
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fraudpulse-gen", description="Synthetic UPI payments with injected fraud."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="generate payments")
    run.add_argument(
        "--rate", type=_positive_float, default=20.0, help="payments per second (default 20)"
    )
    run.add_argument(
        "--fraud-rate", type=_fraction, default=0.02,
        help="share of payments that are fraud, 0 to 0.5 (default 0.02)",
    )
    run.add_argument("--users", type=_positive_int, default=5000, help="default 5000")
    run.add_argument("--merchants", type=_positive_int, default=500, help="default 500")
    run.add_argument("--seed", type=int, default=42, help="same seed, same data (default 42)")
    run.add_argument("--count", type=_positive_int, help="stop after this many payments")
    run.add_argument(
        "--duration", type=_positive_float, help="stop after this many seconds of event time"
    )
    run.add_argument(
        "--fast", action="store_true", help="do not wait for the clock; go as fast as possible"
    )
    args = parser.parse_args(argv)
    if args.fast and args.count is None and args.duration is None:
        parser.error("--fast needs --count or --duration, otherwise it never stops")
    return args


def _positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number: {text!r}") from None
    if value <= 0:
        raise argparse.ArgumentTypeError(f"must be above 0, got {value}")
    return value


def _positive_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if not value > 0:
        raise argparse.ArgumentTypeError(f"must be above 0, got {value}")
    return value


def _fraction(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if not 0 <= value < 0.5:
        raise argparse.ArgumentTypeError(f"must be at least 0 and below 0.5, got {value}")
    return value

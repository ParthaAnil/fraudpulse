"""Command line for the generator.

    fraudpulse-gen run --count 20 --fast           # 20 payments to the terminal, at once
    fraudpulse-gen run --rate 5 --duration 60      # real time: 5 payments a second for a minute
    fraudpulse-gen run --sink kafka --rate 20      # real time, into Kafka
"""

import argparse
import math
import os
import signal
import sys
import time
from collections import Counter
from pathlib import Path

from confluent_kafka import KafkaException

from fraudpulse_generator.engine import PaymentStream, StreamConfig
from fraudpulse_generator.population import make_merchants, make_users
from fraudpulse_generator.sinks import DEFAULT_SCHEMA_PATH, KafkaSink, Sink, StdoutSink


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        users = make_users(args.users, seed=args.seed)
        merchants = make_merchants(args.merchants, seed=args.seed)
        config = StreamConfig(
            rate_per_second=args.rate,
            fraud_rate=args.fraud_rate,
            seed=args.seed,
            late_ratio=args.late_ratio,
        )
        start_ms = int(time.time() * 1000)
        stream = PaymentStream(users, merchants, config, start_ms)
    except ValueError as e:
        print(f"fraudpulse-gen: error: {e}", file=sys.stderr)
        return 2

    try:
        sink = _make_sink(args)
    except Exception as e:  # any startup failure (file, registry, Kafka) is one clear line
        print(f"fraudpulse-gen: error: cannot start the {args.sink} sink: {e}", file=sys.stderr)
        return 1
        # `docker stop` sends SIGTERM. Treat it like Ctrl+C, so queued payments are still flushed.
    signal.signal(signal.SIGTERM, _stop_like_ctrl_c)    

    counts: Counter[str] = Counter()
    error: Exception | None = None
    pipe_closed = False
    try:
        _run(stream, sink, counts, args, start_ms)
    except KeyboardInterrupt:
        pass  # Ctrl+C: stop cleanly and still print the summary
    except BrokenPipeError:
        # The reader stopped early (for example `| head`). That is fine, not an error.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        pipe_closed = True
    except (KafkaException, ValueError) as e:
        error = e
    failures = sink.close()
    if pipe_closed:
        return 0
    _print_summary(counts)
    if error is not None:
        print(f"fraudpulse-gen: error: {error}", file=sys.stderr)
    return 1 if error is not None or failures else 0

def _stop_like_ctrl_c(signum: int, frame: object) -> None:
    raise KeyboardInterrupt


def _make_sink(args: argparse.Namespace) -> Sink:
    if args.sink == "kafka":
        return KafkaSink(args.bootstrap_servers, args.schema_registry, Path(args.schema))
    return StdoutSink()


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
    run.add_argument(
        "--late-ratio", type=_fraction, default=0.0,
        help="share of normal payments sent out of order, 0 to 0.5 (default 0)",
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
    run.add_argument(
        "--sink", choices=("stdout", "kafka"), default="stdout",
        help="where payments go (default stdout)",
    )
    run.add_argument(
        "--bootstrap-servers",
        default=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        help="Kafka address (default localhost:9092)",
    )
    run.add_argument(
        "--schema-registry",
        default=os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:8081"),
        help="Schema Registry URL (default http://localhost:8081)",
    )
    run.add_argument(
        "--schema",
        default=os.environ.get("PAYMENT_SCHEMA_PATH", str(DEFAULT_SCHEMA_PATH)),
        help="path to payment.avsc",
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
    if not (value > 0 and math.isfinite(value)):
        raise argparse.ArgumentTypeError(f"must be a normal number above 0, got {value}")
    return value


def _fraction(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if not 0 <= value < 0.5:
        raise argparse.ArgumentTypeError(f"must be at least 0 and below 0.5, got {value}")
    return value

"""Where generated payments go. The Kafka sink is added in Step 6."""

import json
import sys
from typing import Protocol, TextIO

from fraudpulse_generator.payments import Payment


class Sink(Protocol):
    def send(self, payment: Payment) -> None: ...

    def close(self) -> None: ...


class StdoutSink:
    """Writes one JSON object per line: easy to read, and easy to pipe into other tools."""

    def __init__(self, out: TextIO = sys.stdout) -> None:
        self._out = out

    def send(self, payment: Payment) -> None:
        self._out.write(json.dumps(payment.to_record()) + "\n")

    def close(self) -> None:
        self._out.flush()

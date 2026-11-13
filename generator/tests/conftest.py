"""Shared test helpers: the real payment schema, and small seeded populations."""

import json
import random

import pytest
from fastavro import parse_schema

from fraudpulse_generator.population import make_merchants, make_users
from fraudpulse_generator.sinks import DEFAULT_SCHEMA_PATH

START_MS = 1_793_000_000_000  # a fixed start time, so every run is identical


@pytest.fixture(scope="session")
def payment_schema():
    """ingestion/schemas/payment.avsc, the same file the Kafka sink uses."""
    return parse_schema(json.loads(DEFAULT_SCHEMA_PATH.read_text(encoding="utf-8")))


@pytest.fixture(scope="session")
def users():
    return make_users(200)


@pytest.fixture(scope="session")
def merchants():
    return make_merchants(50)


@pytest.fixture
def rng():
    return random.Random(1)  # noqa: S311 (tests need repeatable randomness)

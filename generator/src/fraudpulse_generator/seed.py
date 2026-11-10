"""Loads the generator's users, and one account each, into the Postgres payments core.

    fraudpulse-seed --users 5000

Connects as the least-privilege role payments_app. The password is read from the
PAYMENTS_APP_PASSWORD environment variable, never from the command line.
"""

import argparse
import os
import random
import sys
from collections.abc import Sequence

import psycopg

from fraudpulse_generator.population import RUPEE, User, make_users

INSERT_USER = """
    INSERT INTO users
        (user_id, full_name, phone, email, upi_id, home_city, kyc_level, segment)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (user_id) DO NOTHING
"""

INSERT_ACCOUNT = """
    INSERT INTO accounts (account_id, user_id, balance_paise)
    VALUES (%s, %s, %s)
    ON CONFLICT (account_id) DO NOTHING
"""


def seed_users(conn: psycopg.Connection, users: Sequence[User], seed: int) -> tuple[int, int]:
    """Insert users and accounts. Returns how many of each were new. Safe to run again."""
    rng = random.Random(seed + 3)  # noqa: S311 (fake data: repeatable)
    user_rows = [
        (u.user_id, u.full_name, u.phone, u.email, u.upi_id, u.home_city, u.kyc_level, u.segment)
        for u in users
    ]
    # One account per user, A0000123 for U0000123, with Rs 100 to Rs 50,000 in it.
    account_rows = [
        (f"A{u.user_id[1:]}", u.user_id, rng.randint(100, 50_000) * RUPEE) for u in users
    ]
    # One transaction: either every row is saved, or (on any error) none are.
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(INSERT_USER, user_rows)
        new_users = cur.rowcount
        cur.executemany(INSERT_ACCOUNT, account_rows)
        new_accounts = cur.rowcount
    return new_users, new_accounts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="fraudpulse-seed", description="Load fake users and accounts into Postgres."
    )
    parser.add_argument("--users", type=int, default=5000, help="default 5000")
    parser.add_argument("--seed", type=int, default=42, help="same seed, same users (default 42)")
    args = parser.parse_args(argv)

    password = os.environ.get("PAYMENTS_APP_PASSWORD")
    if not password:
        print("fraudpulse-seed: error: PAYMENTS_APP_PASSWORD is not set", file=sys.stderr)
        return 2
    try:
        users = make_users(args.users, seed=args.seed)
    except ValueError as e:
        print(f"fraudpulse-seed: error: {e}", file=sys.stderr)
        return 2

    try:
        with psycopg.connect(
            host=os.environ.get("PAYMENTS_DB_HOST", "127.0.0.1"),
            port=int(os.environ.get("PAYMENTS_DB_PORT", "5432")),
            dbname="payments_core",
            user="payments_app",
            password=password,
            connect_timeout=10,
        ) as conn:
            new_users, new_accounts = seed_users(conn, users, args.seed)
    except psycopg.Error as e:
        print(f"fraudpulse-seed: database error: {e}", file=sys.stderr)
        return 1

    print(f"added {new_users} users and {new_accounts} accounts ({len(users)} requested)")
    return 0

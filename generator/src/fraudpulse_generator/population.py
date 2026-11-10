"""Fake users and merchants.

Field names match ingestion/schemas/user.avsc and merchant.avsc. The same seed always
produces the same people, so every run of the generator is reproducible.
"""

import math
import random
import re
from dataclasses import dataclass

from faker import Faker

from fraudpulse_generator.geo import CITIES

RUPEE = 100  # paise in one rupee (ADR 0001: money is stored as whole-number paise)

SEGMENTS = ("RETAIL", "PREMIUM", "SMALL_BUSINESS")
SEGMENT_WEIGHTS = (80, 15, 5)

# The usual (median) payment size for each segment.
SEGMENT_MEDIAN_AMOUNT = {
    "RETAIL": 300 * RUPEE,
    "PREMIUM": 1_500 * RUPEE,
    "SMALL_BUSINESS": 3_000 * RUPEE,
}

# (category_code, group_code). The merchant app stores the same codes in its tables.
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("GROCERY", "DAILY_NEEDS"),
    ("PHARMACY", "DAILY_NEEDS"),
    ("RESTAURANT", "FOOD"),
    ("FOOD_DELIVERY", "FOOD"),
    ("FUEL", "TRANSPORT"),
    ("TAXI", "TRANSPORT"),
    ("ELECTRONICS", "SHOPPING"),
    ("CLOTHING", "SHOPPING"),
    ("TRAVEL", "TRAVEL"),
    ("UTILITIES", "BILLS"),
)

_CITY_WEIGHTS = [city.weight for city in CITIES]


@dataclass
class User:
    user_id: str
    full_name: str
    phone: str
    email: str | None
    upi_id: str
    home_city: str
    kyc_level: str
    segment: str
    # Generator-only traits (not stored anywhere): how this user normally behaves.
    typical_amount_paise: int
    device_id: str


@dataclass
class Merchant:
    merchant_id: str
    legal_name: str
    display_name: str
    upi_id: str
    category_code: str
    city: str
    contact_email: str | None


def make_users(count: int, seed: int = 42) -> list[User]:
    """Create `count` fake users. The same seed always gives the same users."""
    if not 0 < count < 100_000:
        raise ValueError("count must be between 1 and 99,999 (phone numbers have 5 digits)")
    rng = random.Random(seed)  # noqa: S311 (fake data: repeatable, not security)
    fake = Faker("en_IN")
    fake.seed_instance(seed)

    users = []
    for n in range(1, count + 1):
        first, last = fake.first_name(), fake.last_name()
        handle = f"{_slug(first)}.{_slug(last)}{n}"  # the number keeps every handle unique
        segment = rng.choices(SEGMENTS, weights=SEGMENT_WEIGHTS)[0]
        users.append(
            User(
                user_id=f"U{n:07d}",
                full_name=f"{first} {last}",
                # Real Indian mobiles start with 6-9; starting with 0 makes it clearly fake.
                phone=f"+91 00000 {n:05d}",
                email=f"{handle}@example.com" if rng.random() < 0.7 else None,
                upi_id=f"{handle}@fpbank",
                home_city=rng.choices(CITIES, weights=_CITY_WEIGHTS)[0].name,
                kyc_level="FULL" if rng.random() < 0.85 else "MIN",
                segment=segment,
                typical_amount_paise=_typical_amount(rng, segment),
                device_id=f"dev-{rng.getrandbits(48):012x}",
            )
        )
    return users


def make_merchants(count: int, seed: int = 42) -> list[Merchant]:
    """Create `count` fake merchants. The same seed always gives the same merchants."""
    if not 0 < count < 1_000_000:
        raise ValueError("count must be between 1 and 999,999 (merchant IDs have 6 digits)")
    rng = random.Random(seed + 1)  # noqa: S311 (a different random stream from the users)
    fake = Faker("en_IN")
    fake.seed_instance(seed + 1)

    merchants = []
    for n in range(1, count + 1):
        merchant_id = f"M{n:06d}"
        category_code, _group = rng.choice(CATEGORIES)
        display_name = f"{fake.last_name()} {category_code.replace('_', ' ').title()}"
        merchants.append(
            Merchant(
                merchant_id=merchant_id,
                legal_name=f"{display_name} Private Limited",
                display_name=display_name,
                upi_id=f"{merchant_id.lower()}@fpmerchant",
                category_code=category_code,
                city=rng.choices(CITIES, weights=_CITY_WEIGHTS)[0].name,
                contact_email=f"{merchant_id.lower()}@example.com",
            )
        )
    return merchants


def _typical_amount(rng: random.Random, segment: str) -> int:
    """A user's usual payment size: most near the segment median, a few much higher or lower."""
    median = SEGMENT_MEDIAN_AMOUNT[segment]
    amount = rng.lognormvariate(math.log(median), 0.6)
    return max(10 * RUPEE, round(amount))  # at least ₹10; round() gives whole paise


def _slug(text: str) -> str:
    """Only lower-case letters and digits, so it is safe inside a UPI handle or an email."""
    return re.sub(r"[^a-z0-9]", "", text.lower())

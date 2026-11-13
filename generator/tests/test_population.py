"""Fake users and merchants: repeatable, clearly fake, and shaped like the schemas."""

import pytest

from fraudpulse_generator.population import CATEGORIES, make_users


def test_same_seed_gives_same_users():
    assert make_users(50, seed=42) == make_users(50, seed=42)


def test_different_seed_gives_different_users():
    assert make_users(50, seed=42) != make_users(50, seed=7)


def test_user_ids_and_upi_ids_are_unique(users):
    assert len({u.user_id for u in users}) == len(users)
    assert len({u.upi_id for u in users}) == len(users)


def test_personal_data_is_clearly_fake(users):
    for user in users:
        assert user.phone.startswith("+91 00000 ")  # real Indian mobiles start with 6-9
        assert user.email is None or user.email.endswith("@example.com")
        assert user.upi_id.endswith("@fpbank")


def test_typical_amounts_are_whole_positive_paise(users):
    for user in users:
        assert type(user.typical_amount_paise) is int
        assert user.typical_amount_paise >= 10 * 100  # at least Rs 10


def test_merchant_categories_are_known_codes(merchants):
    known = {code for code, _group in CATEGORIES}
    for merchant in merchants:
        assert merchant.category_code in known
        assert merchant.merchant_id.startswith("M") and len(merchant.merchant_id) == 7


@pytest.mark.parametrize("count", [0, -1, 100_000])
def test_user_count_out_of_range_is_refused(count):
    with pytest.raises(ValueError):
        make_users(count)

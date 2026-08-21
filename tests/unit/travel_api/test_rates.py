"""Unit tests for the deterministic city/tier catalog and rate table."""

import datetime

import pytest
from travel_api.domain.errors import CityNotFoundError
from travel_api.domain.rates import (
    PER_DIEM_TABLE,
    POLICY_EFFECTIVE_DATE,
    get_city_tier,
    is_domestic_city,
)


@pytest.mark.parametrize(
    ("city", "expected_tier"),
    [
        ("Tokyo", "domestic_tier1"),
        ("Osaka", "domestic_tier1"),
        ("Sapporo", "domestic_tier1"),
        ("Sendai", "domestic_tier2"),
        ("Kyoto", "domestic_tier2"),
        ("New York", "international_tier_a"),
        ("London", "international_tier_a"),
        ("Singapore", "international_tier_b"),
        ("Hong Kong", "international_tier_b"),
        ("Bangkok", "international_tier_c"),
    ],
)
def test_get_city_tier_known_cities(city, expected_tier):
    assert get_city_tier(city) == expected_tier


def test_get_city_tier_strips_whitespace():
    assert get_city_tier("  Osaka  ") == "domestic_tier1"


def test_get_city_tier_unknown_city_raises():
    with pytest.raises(CityNotFoundError) as excinfo:
        get_city_tier("Atlantis")
    assert excinfo.value.error_code == "city_not_found"
    assert "Atlantis" in excinfo.value.message


def test_is_domestic_city():
    assert is_domestic_city("Tokyo") is True
    assert is_domestic_city("New York") is False


def test_per_diem_table_has_all_five_tiers():
    assert set(PER_DIEM_TABLE) == {
        "domestic_tier1",
        "domestic_tier2",
        "international_tier_a",
        "international_tier_b",
        "international_tier_c",
    }


def test_per_diem_table_values_match_policy_numbers():
    # Mirrors data/policies/04-per-diem-meals.md; a stronger cross-file check
    # lives in tests/contract/data/test_per_diem_rates_match_policy.py.
    assert PER_DIEM_TABLE["domestic_tier1"] == {"meal_allowance": 3000, "lodging_cap": 15000}
    assert PER_DIEM_TABLE["domestic_tier2"] == {"meal_allowance": 2500, "lodging_cap": 12000}
    assert PER_DIEM_TABLE["international_tier_a"] == {
        "meal_allowance": 6000,
        "lodging_cap": 25000,
    }
    assert PER_DIEM_TABLE["international_tier_b"] == {
        "meal_allowance": 5000,
        "lodging_cap": 20000,
    }
    assert PER_DIEM_TABLE["international_tier_c"] == {
        "meal_allowance": 4000,
        "lodging_cap": 18000,
    }


def test_policy_effective_date():
    assert datetime.date(2026, 4, 1) == POLICY_EFFECTIVE_DATE

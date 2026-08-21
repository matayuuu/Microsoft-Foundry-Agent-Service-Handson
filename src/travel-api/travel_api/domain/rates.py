"""Deterministic city/tier catalog and per-diem/lodging rate table.

These numbers intentionally mirror data/policies/03-hotels.md and
data/policies/04-per-diem-meals.md exactly. A contract test
(tests/contract/data/test_per_diem_rates_match_policy.py) parses the
Markdown tables and asserts they stay in sync with this module, so the two
never drift apart even though they live in separately-owned packages
(data/** vs src/travel-api/**).
"""

from __future__ import annotations

import datetime

from travel_api.domain.errors import CityNotFoundError

# Policy effective date (see data/policies/*.md front matter: effective_date).
POLICY_EFFECTIVE_DATE = datetime.date(2026, 4, 1)

DOMESTIC_TIER1_CITIES: frozenset[str] = frozenset(
    {"Tokyo", "Osaka", "Nagoya", "Yokohama", "Fukuoka", "Sapporo"}
)
DOMESTIC_TIER2_CITIES: frozenset[str] = frozenset({"Sendai", "Hiroshima", "Kobe", "Kyoto", "Naha"})
INTERNATIONAL_TIER_A_CITIES: frozenset[str] = frozenset(
    {"New York", "San Francisco", "London", "Paris"}
)
INTERNATIONAL_TIER_B_CITIES: frozenset[str] = frozenset({"Singapore", "Hong Kong", "Sydney"})
INTERNATIONAL_TIER_C_CITIES: frozenset[str] = frozenset(
    {"Bangkok", "Seoul", "Taipei", "Sao Paulo", "Dubai"}
)

_TIER_BY_CITY: dict[str, str] = {
    **{city: "domestic_tier1" for city in DOMESTIC_TIER1_CITIES},
    **{city: "domestic_tier2" for city in DOMESTIC_TIER2_CITIES},
    **{city: "international_tier_a" for city in INTERNATIONAL_TIER_A_CITIES},
    **{city: "international_tier_b" for city in INTERNATIONAL_TIER_B_CITIES},
    **{city: "international_tier_c" for city in INTERNATIONAL_TIER_C_CITIES},
}

# Meal allowance (JPY/day) and lodging cap (JPY/night) per tier.
# Source of truth cross-checked against data/policies/04-per-diem-meals.md.
PER_DIEM_TABLE: dict[str, dict[str, int]] = {
    "domestic_tier1": {"meal_allowance": 3000, "lodging_cap": 15000},
    "domestic_tier2": {"meal_allowance": 2500, "lodging_cap": 12000},
    "international_tier_a": {"meal_allowance": 6000, "lodging_cap": 25000},
    "international_tier_b": {"meal_allowance": 5000, "lodging_cap": 20000},
    "international_tier_c": {"meal_allowance": 4000, "lodging_cap": 18000},
}

# Flat day-trip (no overnight stay) meal allowance, JPY.
DAY_TRIP_MEAL_ALLOWANCE: dict[str, int] = {
    "domestic": 1500,
    "international": 3000,
}

CURRENCY = "JPY"


def normalize_city(city: str) -> str:
    return city.strip()


def get_city_tier(city: str) -> str:
    """Return the deterministic tier id for a known city.

    Raises CityNotFoundError for any city outside the workshop's fixed
    catalog. This is a simulation limitation, not an attempt to model every
    real city, so the error message steers callers toward the known city
    list rather than guessing a tier.
    """
    normalized = normalize_city(city)
    tier = _TIER_BY_CITY.get(normalized)
    if tier is None:
        known = ", ".join(sorted(_TIER_BY_CITY))
        raise CityNotFoundError(f"Unknown city '{city}'. This simulation only recognizes: {known}.")
    return tier


def is_domestic_city(city: str) -> bool:
    return get_city_tier(city).startswith("domestic")

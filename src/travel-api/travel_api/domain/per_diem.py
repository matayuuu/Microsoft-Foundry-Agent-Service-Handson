"""Per-diem domain rule: GET /per-diem?city=&date=."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from travel_api.domain.errors import DateBeforeEffectiveError
from travel_api.domain.rates import (
    CURRENCY,
    PER_DIEM_TABLE,
    POLICY_EFFECTIVE_DATE,
    get_city_tier,
    normalize_city,
)


@dataclass(frozen=True)
class PerDiemResult:
    city: str
    date: datetime.date
    tier: str
    currency: str
    meal_allowance: int
    lodging_cap: int


def get_per_diem(*, city: str, on_date: datetime.date) -> PerDiemResult:
    if on_date < POLICY_EFFECTIVE_DATE:
        raise DateBeforeEffectiveError(
            f"Date {on_date.isoformat()} is before the policy effective date "
            f"{POLICY_EFFECTIVE_DATE.isoformat()}. Historical rates are not "
            "available in this simulation."
        )
    tier = get_city_tier(city)
    rates = PER_DIEM_TABLE[tier]
    return PerDiemResult(
        city=normalize_city(city),
        date=on_date,
        tier=tier,
        currency=CURRENCY,
        meal_allowance=rates["meal_allowance"],
        lodging_cap=rates["lodging_cap"],
    )

"""Trip estimate domain rule: POST /trip-estimates.

Also reused by travel_api.domain.preapproval to derive the same deterministic
numbers a preapproval decision is based on.
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass, field

from travel_api.domain.errors import (
    CabinClassNotAllowedError,
    DateBeforeEffectiveError,
    InvalidDateRangeError,
)
from travel_api.domain.rates import (
    CURRENCY,
    DAY_TRIP_MEAL_ALLOWANCE,
    PER_DIEM_TABLE,
    POLICY_EFFECTIVE_DATE,
    get_city_tier,
    normalize_city,
)
from travel_api.domain.routes_catalog import allowed_cabin_classes, get_route

CABIN_CLASSES = ("economy", "premium_economy", "business", "first")

# Domestic total above this JPY amount requires manager preapproval even
# without a cabin-class trigger. See data/policies/09-approval-process.md.
DOMESTIC_MANAGER_APPROVAL_THRESHOLD_JPY = 100_000


@dataclass(frozen=True)
class TripEstimateResult:
    trip_reference_id: str
    origin_city: str
    destination_city: str
    start_date: datetime.date
    end_date: datetime.date
    nights: int
    is_day_trip: bool
    is_domestic: bool
    destination_tier: str
    flight_hours: float
    cabin_class: str
    traveler_count: int
    currency: str
    flight_cost: int
    lodging_cost: int
    meal_cost: int
    total_estimate: int
    manager_preapproval_required: bool
    vp_preapproval_required: bool
    preapproval_reasons: list[str] = field(default_factory=list)


def _reference_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"trip-{digest[:12]}"


def estimate_trip(
    *,
    origin_city: str,
    destination_city: str,
    start_date: datetime.date,
    end_date: datetime.date,
    cabin_class: str = "economy",
    traveler_count: int = 1,
) -> TripEstimateResult:
    if start_date < POLICY_EFFECTIVE_DATE:
        raise DateBeforeEffectiveError(
            f"start_date {start_date.isoformat()} is before the policy effective "
            f"date {POLICY_EFFECTIVE_DATE.isoformat()}."
        )
    if end_date < start_date:
        raise InvalidDateRangeError("end_date must not be before start_date.")

    origin_tier = get_city_tier(origin_city)
    destination_tier = get_city_tier(destination_city)
    is_domestic = origin_tier.startswith("domestic") and destination_tier.startswith("domestic")

    route = get_route(origin_city, destination_city)
    allowed = allowed_cabin_classes(is_domestic=is_domestic, flight_hours=route.flight_hours)
    if cabin_class not in CABIN_CLASSES:
        raise CabinClassNotAllowedError(f"Unknown cabin_class '{cabin_class}'.")
    if cabin_class == "first" or cabin_class not in allowed:
        raise CabinClassNotAllowedError(
            f"Cabin class '{cabin_class}' is not allowed for this route "
            f"(flight_hours={route.flight_hours}, is_domestic={is_domestic}). "
            "See data/policies/02-flights.md; first class requires the "
            "accessibility-exceptions process and is never available via this API."
        )
    fare = route.fares_jpy.get(cabin_class)
    if fare is None:
        raise CabinClassNotAllowedError(
            f"No fare on file for cabin_class '{cabin_class}' on this route."
        )

    nights = (end_date - start_date).days
    is_day_trip = nights == 0
    destination_rates = PER_DIEM_TABLE[destination_tier]

    if is_day_trip:
        meal_bucket = "domestic" if is_domestic else "international"
        meal_cost = DAY_TRIP_MEAL_ALLOWANCE[meal_bucket] * traveler_count
        lodging_cost = 0
    else:
        meal_days = nights + 1
        meal_cost = destination_rates["meal_allowance"] * meal_days * traveler_count
        lodging_cost = destination_rates["lodging_cap"] * nights * traveler_count

    flight_cost = fare * traveler_count
    total_estimate = flight_cost + lodging_cost + meal_cost

    reasons: list[str] = []
    if not is_domestic:
        reasons.append("international_travel")
    if is_domestic and total_estimate > DOMESTIC_MANAGER_APPROVAL_THRESHOLD_JPY:
        reasons.append("domestic_total_exceeds_100000_jpy")
    if cabin_class == "business":
        reasons.append("business_class_requested")

    vp_required = cabin_class == "business"
    manager_required = bool(reasons)

    reference_id = _reference_id(
        normalize_city(origin_city),
        normalize_city(destination_city),
        start_date.isoformat(),
        end_date.isoformat(),
        cabin_class,
        str(traveler_count),
    )

    return TripEstimateResult(
        trip_reference_id=reference_id,
        origin_city=normalize_city(origin_city),
        destination_city=normalize_city(destination_city),
        start_date=start_date,
        end_date=end_date,
        nights=nights,
        is_day_trip=is_day_trip,
        is_domestic=is_domestic,
        destination_tier=destination_tier,
        flight_hours=route.flight_hours,
        cabin_class=cabin_class,
        traveler_count=traveler_count,
        currency=CURRENCY,
        flight_cost=flight_cost,
        lodging_cost=lodging_cost,
        meal_cost=meal_cost,
        total_estimate=total_estimate,
        manager_preapproval_required=manager_required,
        vp_preapproval_required=vp_required,
        preapproval_reasons=reasons,
    )

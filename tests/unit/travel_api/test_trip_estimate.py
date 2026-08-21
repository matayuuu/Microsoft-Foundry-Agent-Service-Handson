"""Unit tests for the POST /trip-estimates domain rule."""

import datetime

import pytest
from travel_api.domain.errors import (
    CabinClassNotAllowedError,
    CityNotFoundError,
    DateBeforeEffectiveError,
    InvalidDateRangeError,
    RouteNotFoundError,
)
from travel_api.domain.trip_estimate import estimate_trip


def test_domestic_short_trip_economy():
    result = estimate_trip(
        origin_city="Tokyo",
        destination_city="Osaka",
        start_date=datetime.date(2026, 5, 11),
        end_date=datetime.date(2026, 5, 12),
        cabin_class="economy",
    )
    assert result.is_domestic is True
    assert result.is_day_trip is False
    assert result.nights == 1
    assert result.destination_tier == "domestic_tier1"
    assert result.flight_cost == 32000
    assert result.lodging_cost == 15000  # 1 night * 15,000
    assert result.meal_cost == 6000  # 2 days (start+end) * 3,000
    assert result.total_estimate == 32000 + 15000 + 6000
    assert result.manager_preapproval_required is False
    assert result.vp_preapproval_required is False
    assert result.preapproval_reasons == []


def test_domestic_day_trip_uses_flat_meal_allowance():
    result = estimate_trip(
        origin_city="Tokyo",
        destination_city="Nagoya",
        start_date=datetime.date(2026, 6, 15),
        end_date=datetime.date(2026, 6, 15),
    )
    assert result.is_day_trip is True
    assert result.nights == 0
    assert result.lodging_cost == 0
    assert result.meal_cost == 1500  # domestic day-trip flat allowance


def test_domestic_trip_over_threshold_requires_manager_preapproval():
    result = estimate_trip(
        origin_city="Tokyo",
        destination_city="Sapporo",
        start_date=datetime.date(2026, 8, 1),
        end_date=datetime.date(2026, 8, 6),  # 5 nights, well over 100,000 JPY
    )
    assert result.total_estimate > 100_000
    assert result.manager_preapproval_required is True
    assert "domestic_total_exceeds_100000_jpy" in result.preapproval_reasons
    assert result.vp_preapproval_required is False


def test_international_trip_always_requires_manager_preapproval():
    result = estimate_trip(
        origin_city="Tokyo",
        destination_city="Hong Kong",
        start_date=datetime.date(2026, 5, 25),
        end_date=datetime.date(2026, 5, 27),
    )
    assert result.is_domestic is False
    assert result.manager_preapproval_required is True
    assert "international_travel" in result.preapproval_reasons


def test_business_class_requires_manager_and_vp_preapproval():
    result = estimate_trip(
        origin_city="Tokyo",
        destination_city="New York",
        start_date=datetime.date(2026, 7, 10),
        end_date=datetime.date(2026, 7, 15),
        cabin_class="business",
    )
    assert result.flight_hours == 13.0
    assert result.manager_preapproval_required is True
    assert result.vp_preapproval_required is True
    assert "business_class_requested" in result.preapproval_reasons


def test_short_haul_international_forbids_business_class():
    # Tokyo-Hong Kong is 5.0h: economy only per policy (<6h).
    with pytest.raises(CabinClassNotAllowedError) as excinfo:
        estimate_trip(
            origin_city="Tokyo",
            destination_city="Hong Kong",
            start_date=datetime.date(2026, 5, 25),
            end_date=datetime.date(2026, 5, 27),
            cabin_class="business",
        )
    assert excinfo.value.error_code == "cabin_class_not_allowed"


def test_mid_haul_international_allows_premium_economy_not_business():
    # Tokyo-Singapore is 7.0h: economy/premium_economy allowed, business not (<10h).
    result = estimate_trip(
        origin_city="Tokyo",
        destination_city="Singapore",
        start_date=datetime.date(2026, 5, 20),
        end_date=datetime.date(2026, 5, 22),
        cabin_class="premium_economy",
    )
    assert result.cabin_class == "premium_economy"

    with pytest.raises(CabinClassNotAllowedError):
        estimate_trip(
            origin_city="Tokyo",
            destination_city="Singapore",
            start_date=datetime.date(2026, 5, 20),
            end_date=datetime.date(2026, 5, 22),
            cabin_class="business",
        )


def test_domestic_route_forbids_non_economy():
    with pytest.raises(CabinClassNotAllowedError):
        estimate_trip(
            origin_city="Tokyo",
            destination_city="Osaka",
            start_date=datetime.date(2026, 5, 11),
            end_date=datetime.date(2026, 5, 12),
            cabin_class="premium_economy",
        )


def test_first_class_is_never_allowed_via_this_api():
    with pytest.raises(CabinClassNotAllowedError):
        estimate_trip(
            origin_city="Tokyo",
            destination_city="New York",
            start_date=datetime.date(2026, 7, 10),
            end_date=datetime.date(2026, 7, 15),
            cabin_class="first",
        )


def test_unknown_city_raises():
    with pytest.raises(CityNotFoundError):
        estimate_trip(
            origin_city="Tokyo",
            destination_city="Atlantis",
            start_date=datetime.date(2026, 5, 1),
            end_date=datetime.date(2026, 5, 2),
        )


def test_unknown_route_raises():
    with pytest.raises(RouteNotFoundError):
        estimate_trip(
            origin_city="Sendai",
            destination_city="Naha",
            start_date=datetime.date(2026, 5, 1),
            end_date=datetime.date(2026, 5, 2),
        )


def test_end_date_before_start_date_raises():
    with pytest.raises(InvalidDateRangeError):
        estimate_trip(
            origin_city="Tokyo",
            destination_city="Osaka",
            start_date=datetime.date(2026, 5, 12),
            end_date=datetime.date(2026, 5, 11),
        )


def test_start_date_before_effective_date_raises():
    with pytest.raises(DateBeforeEffectiveError):
        estimate_trip(
            origin_city="Tokyo",
            destination_city="Osaka",
            start_date=datetime.date(2026, 3, 1),
            end_date=datetime.date(2026, 3, 2),
        )


def test_trip_reference_id_is_deterministic():
    kwargs = dict(
        origin_city="Tokyo",
        destination_city="Osaka",
        start_date=datetime.date(2026, 5, 11),
        end_date=datetime.date(2026, 5, 12),
        cabin_class="economy",
    )
    first = estimate_trip(**kwargs)
    second = estimate_trip(**kwargs)
    assert first.trip_reference_id == second.trip_reference_id

    different = estimate_trip(**{**kwargs, "traveler_count": 2})
    assert different.trip_reference_id != first.trip_reference_id


def test_traveler_count_multiplies_costs():
    single = estimate_trip(
        origin_city="Tokyo",
        destination_city="Osaka",
        start_date=datetime.date(2026, 5, 11),
        end_date=datetime.date(2026, 5, 12),
        traveler_count=1,
    )
    double = estimate_trip(
        origin_city="Tokyo",
        destination_city="Osaka",
        start_date=datetime.date(2026, 5, 11),
        end_date=datetime.date(2026, 5, 12),
        traveler_count=2,
    )
    assert double.flight_cost == single.flight_cost * 2
    assert double.lodging_cost == single.lodging_cost * 2
    assert double.meal_cost == single.meal_cost * 2

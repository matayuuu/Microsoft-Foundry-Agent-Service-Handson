"""Unit tests for the GET /per-diem domain rule."""

import datetime

import pytest
from travel_api.domain.errors import CityNotFoundError, DateBeforeEffectiveError
from travel_api.domain.per_diem import get_per_diem


def test_get_per_diem_domestic_tier1():
    result = get_per_diem(city="Osaka", on_date=datetime.date(2026, 5, 11))
    assert result.tier == "domestic_tier1"
    assert result.currency == "JPY"
    assert result.meal_allowance == 3000
    assert result.lodging_cap == 15000
    assert result.city == "Osaka"


def test_get_per_diem_international_tier_b():
    result = get_per_diem(city="Hong Kong", on_date=datetime.date(2026, 6, 1))
    assert result.tier == "international_tier_b"
    assert result.meal_allowance == 5000
    assert result.lodging_cap == 20000


def test_get_per_diem_unknown_city_raises():
    with pytest.raises(CityNotFoundError):
        get_per_diem(city="Atlantis", on_date=datetime.date(2026, 5, 1))


def test_get_per_diem_date_before_effective_raises():
    with pytest.raises(DateBeforeEffectiveError) as excinfo:
        get_per_diem(city="Tokyo", on_date=datetime.date(2026, 3, 31))
    assert excinfo.value.error_code == "date_before_effective_date"


def test_get_per_diem_on_effective_date_is_allowed():
    result = get_per_diem(city="Tokyo", on_date=datetime.date(2026, 4, 1))
    assert result.tier == "domestic_tier1"

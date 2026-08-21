"""Keep Hosted Agent cabin rules aligned with the Travel Ops API/policy."""

from __future__ import annotations

import datetime
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from travel_api.domain.routes_catalog import _ROUTES, allowed_cabin_classes

REPO_ROOT = Path(__file__).resolve().parents[3]
HOSTED_DOMAIN_PATH = REPO_ROOT / "src" / "hosted-agent" / "domain.py"


def _load_hosted_domain() -> ModuleType:
    module_name = "hosted_agent_domain_policy_contract"
    spec = importlib.util.spec_from_file_location(module_name, HOSTED_DOMAIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


hosted_domain = _load_hosted_domain()


def test_hosted_route_hours_match_travel_api_catalog() -> None:
    expected = {route_key: route.flight_hours for route_key, route in _ROUTES.items()}

    assert expected == hosted_domain._FLIGHT_HOURS_BY_ROUTE


def test_hosted_cabin_eligibility_matches_travel_api_policy() -> None:
    for route_key, route in _ROUTES.items():
        origin, destination = sorted(route_key)
        origin_tier = hosted_domain.get_city_tier(origin)
        destination_tier = hosted_domain.get_city_tier(destination)
        is_domestic = bool(
            origin_tier
            and destination_tier
            and not hosted_domain.is_international_tier(origin_tier)
            and not hosted_domain.is_international_tier(destination_tier)
        )
        expected = allowed_cabin_classes(
            is_domestic=is_domestic,
            flight_hours=route.flight_hours,
        )

        for cabin_class in hosted_domain.CABIN_CLASSES:
            request = hosted_domain.TripRequest(
                origin=origin,
                destination=destination,
                departure_date=datetime.date(2026, 9, 1),
                return_date=datetime.date(2026, 9, 2),
                cabin_class=cabin_class,
                purpose="policy contract test",
            )
            actual = hosted_domain.check_policy(request).cabin_class_allowed

            assert actual is (cabin_class in expected), (
                f"{origin}<->{destination} {cabin_class}: "
                f"hosted={actual}, travel-api allowed={sorted(expected)}"
            )

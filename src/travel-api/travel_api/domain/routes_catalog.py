"""Deterministic flight route catalog (flight hours + round-trip fares).

This is a fixed, small set of representative routes for the workshop
simulation, not a real flight-pricing engine. Unknown origin/destination
pairs raise RouteNotFoundError rather than guessing a fare.
"""

from __future__ import annotations

from dataclasses import dataclass

from travel_api.domain.errors import RouteNotFoundError


@dataclass(frozen=True)
class Route:
    flight_hours: float
    fares_jpy: dict[str, int]  # cabin_class -> round-trip fare in JPY


_ROUTES: dict[frozenset[str], Route] = {
    frozenset({"Tokyo", "Osaka"}): Route(1.0, {"economy": 32000}),
    frozenset({"Tokyo", "Nagoya"}): Route(1.0, {"economy": 26000}),
    frozenset({"Tokyo", "Fukuoka"}): Route(1.9, {"economy": 38000}),
    frozenset({"Tokyo", "Sapporo"}): Route(1.5, {"economy": 40000}),
    frozenset({"Osaka", "Sapporo"}): Route(2.0, {"economy": 42000}),
    frozenset({"Tokyo", "Sendai"}): Route(1.0, {"economy": 24000}),
    frozenset({"Tokyo", "Hiroshima"}): Route(1.3, {"economy": 34000}),
    frozenset({"Tokyo", "Naha"}): Route(2.5, {"economy": 46000}),
    frozenset({"Tokyo", "Hong Kong"}): Route(5.0, {"economy": 70000}),
    frozenset({"Tokyo", "Taipei"}): Route(4.0, {"economy": 60000}),
    frozenset({"Tokyo", "Seoul"}): Route(2.5, {"economy": 45000}),
    frozenset({"Tokyo", "Singapore"}): Route(7.0, {"economy": 90000, "premium_economy": 150000}),
    frozenset({"Tokyo", "Bangkok"}): Route(7.0, {"economy": 75000, "premium_economy": 130000}),
    frozenset({"Tokyo", "San Francisco"}): Route(
        9.5, {"economy": 170000, "premium_economy": 300000}
    ),
    frozenset({"Tokyo", "Sydney"}): Route(9.5, {"economy": 140000, "premium_economy": 230000}),
    frozenset({"Tokyo", "New York"}): Route(
        13.0, {"economy": 180000, "premium_economy": 320000, "business": 620000}
    ),
    frozenset({"Tokyo", "London"}): Route(
        14.0, {"economy": 190000, "premium_economy": 340000, "business": 650000}
    ),
    frozenset({"Tokyo", "Paris"}): Route(
        14.5, {"economy": 195000, "premium_economy": 345000, "business": 660000}
    ),
    frozenset({"Tokyo", "Dubai"}): Route(
        11.0, {"economy": 160000, "premium_economy": 280000, "business": 600000}
    ),
    frozenset({"Tokyo", "Sao Paulo"}): Route(
        24.0, {"economy": 280000, "premium_economy": 480000, "business": 900000}
    ),
}


def get_route(origin_city: str, destination_city: str) -> Route:
    key = frozenset({origin_city.strip(), destination_city.strip()})
    route = _ROUTES.get(key)
    if route is None:
        raise RouteNotFoundError(
            f"No route catalog entry for '{origin_city}' <-> '{destination_city}'. "
            "This simulation only supports a fixed set of representative routes; "
            "use the Contoso Travel Portal for other city pairs."
        )
    return route


def allowed_cabin_classes(*, is_domestic: bool, flight_hours: float) -> frozenset[str]:
    """Cabin classes permitted by policy for a route, per data/policies/02-flights.md."""
    if is_domestic:
        return frozenset({"economy"})
    if flight_hours < 6:
        return frozenset({"economy"})
    if flight_hours < 10:
        return frozenset({"economy", "premium_economy"})
    return frozenset({"economy", "premium_economy", "business"})

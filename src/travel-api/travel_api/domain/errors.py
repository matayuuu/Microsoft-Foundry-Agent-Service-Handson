"""Domain-level error types.

These carry no HTTP concerns; the FastAPI adapter (adapters/api/routes.py) is
responsible for mapping each of these to an HTTP status code.
"""

from __future__ import annotations


class TravelOpsDomainError(Exception):
    """Base class for all deterministic Travel Ops domain errors."""

    error_code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class CityNotFoundError(TravelOpsDomainError):
    """Raised when a city is not in the deterministic city/tier catalog."""

    error_code = "city_not_found"


class RouteNotFoundError(TravelOpsDomainError):
    """Raised when an origin/destination pair is not in the route catalog."""

    error_code = "route_not_found"


class DateBeforeEffectiveError(TravelOpsDomainError):
    """Raised when a requested date predates the policy effective date."""

    error_code = "date_before_effective_date"


class InvalidDateRangeError(TravelOpsDomainError):
    """Raised when end_date is before start_date."""

    error_code = "invalid_date_range"


class CabinClassNotAllowedError(TravelOpsDomainError):
    """Raised when the requested cabin class is not permitted for the route."""

    error_code = "cabin_class_not_allowed"

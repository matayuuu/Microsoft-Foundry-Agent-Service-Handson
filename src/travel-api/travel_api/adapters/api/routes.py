"""Thin FastAPI routes: HTTP request/response translation only.

All actual policy logic lives in travel_api.domain and travel_api.application.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, HTTPException, Query, status

from travel_api.application import use_cases
from travel_api.domain.errors import TravelOpsDomainError

from .schemas import (
    ErrorResponse,
    HealthResponse,
    PerDiemResponse,
    PreapprovalRequest,
    PreapprovalResponse,
    TripEstimateRequest,
    TripEstimateResponse,
)

router = APIRouter()

_ERROR_STATUS_BY_CODE: dict[str, int] = {
    "city_not_found": status.HTTP_404_NOT_FOUND,
    "route_not_found": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "date_before_effective_date": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "invalid_date_range": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "cabin_class_not_allowed": status.HTTP_422_UNPROCESSABLE_CONTENT,
}

_ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Unknown city."},
    422: {"model": ErrorResponse, "description": "Invalid or disallowed request."},
}


def _raise_from_domain_error(error: TravelOpsDomainError) -> None:
    status_code = _ERROR_STATUS_BY_CODE.get(error.error_code, status.HTTP_422_UNPROCESSABLE_CONTENT)
    raise HTTPException(
        status_code=status_code,
        detail={"error_code": error.error_code, "detail": error.message},
    ) from error


@router.get(
    "/health",
    operation_id="getHealth",
    response_model=HealthResponse,
    summary="Liveness/readiness check",
)
def get_health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/per-diem",
    operation_id="getPerDiem",
    response_model=PerDiemResponse,
    responses=_ERROR_RESPONSES,
    summary="Look up the deterministic per-diem meal allowance and lodging cap for a city",
)
def get_per_diem(
    city: str = Query(..., min_length=1, examples=["Osaka"]),
    date: datetime.date = Query(..., description="Trip date (ISO 8601)"),  # noqa: B008
) -> PerDiemResponse:
    try:
        use_case_result = use_cases.get_per_diem(city=city, on_date=date)
    except TravelOpsDomainError as error:
        _raise_from_domain_error(error)
        raise  # pragma: no cover - _raise_from_domain_error always raises
    return PerDiemResponse.from_domain(use_case_result.result, use_case_result.policy_references)


@router.post(
    "/trip-estimates",
    operation_id="createTripEstimate",
    response_model=TripEstimateResponse,
    responses=_ERROR_RESPONSES,
    summary="Produce a deterministic flight/lodging/meal cost estimate for a trip",
)
def create_trip_estimate(payload: TripEstimateRequest) -> TripEstimateResponse:
    try:
        use_case_result = use_cases.estimate_trip(
            origin_city=payload.origin_city,
            destination_city=payload.destination_city,
            start_date=payload.start_date,
            end_date=payload.end_date,
            cabin_class=payload.cabin_class,
            traveler_count=payload.traveler_count,
        )
    except TravelOpsDomainError as error:
        _raise_from_domain_error(error)
        raise  # pragma: no cover
    return TripEstimateResponse.from_domain(
        use_case_result.result, use_case_result.policy_references
    )


@router.post(
    "/preapprovals",
    operation_id="createPreapproval",
    response_model=PreapprovalResponse,
    responses=_ERROR_RESPONSES,
    summary="Simulate a travel preapproval decision (never a real approval)",
)
def create_preapproval(payload: PreapprovalRequest) -> PreapprovalResponse:
    try:
        use_case_result = use_cases.evaluate_preapproval(
            origin_city=payload.origin_city,
            destination_city=payload.destination_city,
            start_date=payload.start_date,
            end_date=payload.end_date,
            cabin_class=payload.cabin_class,
            traveler_count=payload.traveler_count,
            justification=payload.justification,
        )
    except TravelOpsDomainError as error:
        _raise_from_domain_error(error)
        raise  # pragma: no cover
    return PreapprovalResponse.from_domain(
        use_case_result.result, use_case_result.policy_references
    )

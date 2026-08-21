"""Typed request/response schemas for the Travel Ops API HTTP adapter."""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field

from travel_api.application.use_cases import PolicyReference
from travel_api.domain.per_diem import PerDiemResult
from travel_api.domain.preapproval import PreapprovalResult
from travel_api.domain.trip_estimate import TripEstimateResult

CabinClass = Literal["economy", "premium_economy", "business", "first"]


class PolicyReferenceModel(BaseModel):
    id: str = Field(description="Document id from data/manifest.json")
    source_url: str = Field(
        description=(
            "Source URL for the referenced policy document. Contains the "
            "{{WORKSHOP_SOURCE_BASE}} placeholder until bootstrap/setup "
            "tooling substitutes a configured, stable repository base."
        )
    )

    @classmethod
    def from_domain(cls, ref: PolicyReference) -> PolicyReferenceModel:
        return cls(id=ref.id, source_url=ref.source_url)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ErrorResponse(BaseModel):
    error_code: str
    detail: str


class PerDiemResponse(BaseModel):
    city: str
    date: datetime.date
    tier: str
    currency: str
    meal_allowance: int = Field(description="JPY per day")
    lodging_cap: int = Field(description="JPY per night")
    policy_references: list[PolicyReferenceModel]

    @classmethod
    def from_domain(
        cls, result: PerDiemResult, policy_references: tuple[PolicyReference, ...]
    ) -> PerDiemResponse:
        return cls(
            city=result.city,
            date=result.date,
            tier=result.tier,
            currency=result.currency,
            meal_allowance=result.meal_allowance,
            lodging_cap=result.lodging_cap,
            policy_references=[PolicyReferenceModel.from_domain(r) for r in policy_references],
        )


class TripEstimateRequest(BaseModel):
    origin_city: str = Field(min_length=1, examples=["Tokyo"])
    destination_city: str = Field(min_length=1, examples=["New York"])
    start_date: datetime.date
    end_date: datetime.date
    cabin_class: CabinClass = "economy"
    traveler_count: int = Field(default=1, ge=1, le=20)


class TripEstimateResponse(BaseModel):
    trip_reference_id: str = Field(
        description="Deterministic id derived from the request; not a persisted record."
    )
    origin_city: str
    destination_city: str
    start_date: datetime.date
    end_date: datetime.date
    nights: int
    is_day_trip: bool
    is_domestic: bool
    destination_tier: str
    flight_hours: float
    cabin_class: CabinClass
    traveler_count: int
    currency: str
    flight_cost: int
    lodging_cost: int
    meal_cost: int
    total_estimate: int
    manager_preapproval_required: bool
    vp_preapproval_required: bool
    preapproval_reasons: list[str]
    policy_references: list[PolicyReferenceModel]

    @classmethod
    def from_domain(
        cls, result: TripEstimateResult, policy_references: tuple[PolicyReference, ...]
    ) -> TripEstimateResponse:
        return cls(
            trip_reference_id=result.trip_reference_id,
            origin_city=result.origin_city,
            destination_city=result.destination_city,
            start_date=result.start_date,
            end_date=result.end_date,
            nights=result.nights,
            is_day_trip=result.is_day_trip,
            is_domestic=result.is_domestic,
            destination_tier=result.destination_tier,
            flight_hours=result.flight_hours,
            cabin_class=result.cabin_class,  # type: ignore[arg-type]
            traveler_count=result.traveler_count,
            currency=result.currency,
            flight_cost=result.flight_cost,
            lodging_cost=result.lodging_cost,
            meal_cost=result.meal_cost,
            total_estimate=result.total_estimate,
            manager_preapproval_required=result.manager_preapproval_required,
            vp_preapproval_required=result.vp_preapproval_required,
            preapproval_reasons=list(result.preapproval_reasons),
            policy_references=[PolicyReferenceModel.from_domain(r) for r in policy_references],
        )


class PreapprovalRequest(BaseModel):
    origin_city: str = Field(min_length=1, examples=["Tokyo"])
    destination_city: str = Field(min_length=1, examples=["New York"])
    start_date: datetime.date
    end_date: datetime.date
    cabin_class: CabinClass = "economy"
    traveler_count: int = Field(default=1, ge=1, le=20)
    justification: str | None = Field(
        default=None,
        max_length=500,
        description="Optional free-text business justification. Must not contain PII.",
    )
    requester_alias: str | None = Field(
        default=None,
        pattern=r"^employee-\d{3}$",
        description=(
            "Optional opaque synthetic requester id, e.g. 'employee-001'. "
            "Never a real name or email."
        ),
    )


class PreapprovalResponse(BaseModel):
    simulation: Literal[True] = Field(
        default=True,
        description="Always true. This endpoint never grants a real approval.",
    )
    reference_id: str = Field(
        description="Deterministic simulation reference id; not a real approval ticket number."
    )
    decision: Literal[
        "simulated_auto_eligible",
        "simulated_pending_manager_review",
        "simulated_pending_vp_review",
    ]
    disclaimer: str
    justification: str | None
    trip_estimate: TripEstimateResponse
    policy_references: list[PolicyReferenceModel]

    @classmethod
    def from_domain(
        cls, result: PreapprovalResult, policy_references: tuple[PolicyReference, ...]
    ) -> PreapprovalResponse:
        return cls(
            simulation=result.simulation,
            reference_id=result.reference_id,
            decision=result.decision,  # type: ignore[arg-type]
            disclaimer=result.disclaimer,
            justification=result.justification,
            trip_estimate=TripEstimateResponse.from_domain(result.trip_estimate, policy_references),
            policy_references=[PolicyReferenceModel.from_domain(r) for r in policy_references],
        )

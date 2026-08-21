"""Use cases: thin orchestration between the FastAPI adapter and pure domain rules.

Each use case pairs a domain calculation with the fixed set of policy
document references (id + source_url) an agent should cite when explaining
the result. Document ids/source_urls here are intentionally hardcoded to
match data/manifest.json; a contract test
(tests/contract/travel_api/test_policy_references_match_manifest.py) checks
every id referenced here exists in data/manifest.json so the two owned areas
(data/** and src/travel-api/**) cannot silently drift apart.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from travel_api.domain.per_diem import PerDiemResult
from travel_api.domain.per_diem import get_per_diem as _get_per_diem
from travel_api.domain.preapproval import PreapprovalResult
from travel_api.domain.preapproval import evaluate_preapproval as _evaluate_preapproval
from travel_api.domain.trip_estimate import TripEstimateResult
from travel_api.domain.trip_estimate import estimate_trip as _estimate_trip

SOURCE_URL_BASE_PLACEHOLDER = "{{WORKSHOP_SOURCE_BASE}}"


@dataclass(frozen=True)
class PolicyReference:
    id: str
    source_url: str


def _ref(policy_id: str, filename: str) -> PolicyReference:
    return PolicyReference(
        id=policy_id,
        source_url=f"{SOURCE_URL_BASE_PLACEHOLDER}/data/policies/{filename}",
    )


PER_DIEM_REFERENCES = (
    _ref("policy-per-diem-001", "04-per-diem-meals.md"),
    _ref("policy-hotels-001", "03-hotels.md"),
)
TRIP_ESTIMATE_REFERENCES = (
    _ref("policy-per-diem-001", "04-per-diem-meals.md"),
    _ref("policy-hotels-001", "03-hotels.md"),
    _ref("policy-flights-001", "02-flights.md"),
    _ref("policy-approval-process-001", "09-approval-process.md"),
)
PREAPPROVAL_REFERENCES = (
    _ref("policy-approval-process-001", "09-approval-process.md"),
    _ref("policy-flights-001", "02-flights.md"),
    _ref("policy-hotels-001", "03-hotels.md"),
    _ref("policy-per-diem-001", "04-per-diem-meals.md"),
)


@dataclass(frozen=True)
class PerDiemUseCaseResult:
    result: PerDiemResult
    policy_references: tuple[PolicyReference, ...]


@dataclass(frozen=True)
class TripEstimateUseCaseResult:
    result: TripEstimateResult
    policy_references: tuple[PolicyReference, ...]


@dataclass(frozen=True)
class PreapprovalUseCaseResult:
    result: PreapprovalResult
    policy_references: tuple[PolicyReference, ...]


def get_per_diem(*, city: str, on_date: datetime.date) -> PerDiemUseCaseResult:
    result = _get_per_diem(city=city, on_date=on_date)
    return PerDiemUseCaseResult(result=result, policy_references=PER_DIEM_REFERENCES)


def estimate_trip(
    *,
    origin_city: str,
    destination_city: str,
    start_date: datetime.date,
    end_date: datetime.date,
    cabin_class: str = "economy",
    traveler_count: int = 1,
) -> TripEstimateUseCaseResult:
    result = _estimate_trip(
        origin_city=origin_city,
        destination_city=destination_city,
        start_date=start_date,
        end_date=end_date,
        cabin_class=cabin_class,
        traveler_count=traveler_count,
    )
    return TripEstimateUseCaseResult(result=result, policy_references=TRIP_ESTIMATE_REFERENCES)


def evaluate_preapproval(
    *,
    origin_city: str,
    destination_city: str,
    start_date: datetime.date,
    end_date: datetime.date,
    cabin_class: str = "economy",
    traveler_count: int = 1,
    justification: str | None = None,
) -> PreapprovalUseCaseResult:
    result = _evaluate_preapproval(
        origin_city=origin_city,
        destination_city=destination_city,
        start_date=start_date,
        end_date=end_date,
        cabin_class=cabin_class,
        traveler_count=traveler_count,
        justification=justification,
    )
    return PreapprovalUseCaseResult(result=result, policy_references=PREAPPROVAL_REFERENCES)

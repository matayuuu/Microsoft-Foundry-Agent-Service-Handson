"""Preapproval domain rule: POST /preapprovals.

IMPORTANT: this is a workshop simulation. It never grants a real approval and
every decision value is prefixed with `simulated_` so it cannot be mistaken
for a genuine Contoso Travel Portal approval. See
data/policies/09-approval-process.md.
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass

from travel_api.domain.trip_estimate import TripEstimateResult, estimate_trip

DISCLAIMER = (
    "これはハンズオン教材用のシミュレーションであり、実際の承認ではありません。"
    "実際の出張では Contoso Travel Portal を通じて正式な事前承認を得てください。"
)

SIMULATED_AUTO_ELIGIBLE = "simulated_auto_eligible"
SIMULATED_PENDING_MANAGER_REVIEW = "simulated_pending_manager_review"
SIMULATED_PENDING_VP_REVIEW = "simulated_pending_vp_review"


@dataclass(frozen=True)
class PreapprovalResult:
    reference_id: str
    decision: str
    simulation: bool
    disclaimer: str
    justification: str | None
    trip_estimate: TripEstimateResult


def _reference_id(*parts: str) -> str:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"sim-preapproval-{digest[:12]}"


def evaluate_preapproval(
    *,
    origin_city: str,
    destination_city: str,
    start_date: datetime.date,
    end_date: datetime.date,
    cabin_class: str = "economy",
    traveler_count: int = 1,
    justification: str | None = None,
) -> PreapprovalResult:
    estimate = estimate_trip(
        origin_city=origin_city,
        destination_city=destination_city,
        start_date=start_date,
        end_date=end_date,
        cabin_class=cabin_class,
        traveler_count=traveler_count,
    )

    if estimate.vp_preapproval_required:
        decision = SIMULATED_PENDING_VP_REVIEW
    elif estimate.manager_preapproval_required:
        decision = SIMULATED_PENDING_MANAGER_REVIEW
    else:
        decision = SIMULATED_AUTO_ELIGIBLE

    reference_id = _reference_id(
        estimate.origin_city,
        estimate.destination_city,
        start_date.isoformat(),
        end_date.isoformat(),
        cabin_class,
        str(traveler_count),
        justification or "",
    )

    return PreapprovalResult(
        reference_id=reference_id,
        decision=decision,
        simulation=True,
        disclaimer=DISCLAIMER,
        justification=justification,
        trip_estimate=estimate,
    )

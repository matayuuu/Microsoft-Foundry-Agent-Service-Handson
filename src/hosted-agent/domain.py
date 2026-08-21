"""Pure, Azure-free domain logic for the Contoso travel-expense planner workflow.

This module intentionally has **no** dependency on ``agent_framework``,
``azure-*``, or any network/host adapter. Every function here is a plain,
deterministic transformation over plain data so it can be unit tested without
a running event loop, credentials, or a deployed agent.

The rate tables and thresholds below are a small, self-contained *synthetic*
excerpt that mirrors (but does not import) the authoritative numbers in
``data/policies/*.md`` and ``src/travel-api/travel_api/domain/*.py``. The
deployed hosted-agent zip only contains ``src/hosted-agent/**`` so it cannot
reach those other, separately-owned packages at runtime; this module is the
hosted agent's own copy of just enough policy/rate data to run a believable,
fully-simulated planning workflow.

IMPORTANT: Nothing in this module (or the workflow built on top of it) ever
calls a real approval, payment, or booking system. ``ApprovalDecision`` is
always a *simulated recommendation* -- see ``SIMULATION_DISCLAIMER_JA``.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

# ---------------------------------------------------------------------------
# Bundled synthetic policy/rate excerpt
#
# Source of truth mirrored (not imported) from:
#   - data/policies/02-flights.md          (policy-flights-001)
#   - data/policies/03-hotels.md            (policy-hotels-001)
#   - data/policies/04-per-diem-meals.md    (policy-per-diem-001)
#   - data/policies/09-approval-process.md  (policy-approval-process-001)
#   - src/travel-api/travel_api/domain/{rates,routes_catalog,trip_estimate}.py
#
# This is a deliberately small, representative subset for the workshop demo,
# not an attempt to reproduce the full Travel Ops API rate catalog.
# ---------------------------------------------------------------------------

CabinClass = Literal["economy", "premium_economy", "business", "first"]
CABIN_CLASSES: tuple[CabinClass, ...] = ("economy", "premium_economy", "business", "first")

CURRENCY = "JPY"

# Domestic total above this JPY amount requires manager preapproval even
# without a cabin-class trigger. See data/policies/09-approval-process.md
# (policy-approval-process-001).
DOMESTIC_MANAGER_APPROVAL_THRESHOLD_JPY = 100_000

DOMESTIC_TIER1_CITIES: frozenset[str] = frozenset(
    {"Tokyo", "Osaka", "Nagoya", "Fukuoka", "Sapporo"}
)
DOMESTIC_TIER2_CITIES: frozenset[str] = frozenset({"Sendai", "Hiroshima", "Kyoto", "Naha"})
INTERNATIONAL_TIER_A_CITIES: frozenset[str] = frozenset({"New York", "London", "Paris"})
INTERNATIONAL_TIER_B_CITIES: frozenset[str] = frozenset({"Singapore", "Sydney", "Hong Kong"})
INTERNATIONAL_TIER_C_CITIES: frozenset[str] = frozenset({"Bangkok", "Seoul", "Taipei"})

_TIER_BY_CITY: dict[str, str] = {
    **{city: "domestic_tier1" for city in DOMESTIC_TIER1_CITIES},
    **{city: "domestic_tier2" for city in DOMESTIC_TIER2_CITIES},
    **{city: "international_tier_a" for city in INTERNATIONAL_TIER_A_CITIES},
    **{city: "international_tier_b" for city in INTERNATIONAL_TIER_B_CITIES},
    **{city: "international_tier_c" for city in INTERNATIONAL_TIER_C_CITIES},
}

# Meal allowance (JPY/day) and lodging cap (JPY/night) per destination tier.
# Mirrors data/policies/03-hotels.md + 04-per-diem-meals.md (policy-hotels-001,
# policy-per-diem-001).
PER_DIEM_TABLE: dict[str, dict[str, int]] = {
    "domestic_tier1": {"meal_allowance": 3000, "lodging_cap": 15000},
    "domestic_tier2": {"meal_allowance": 2500, "lodging_cap": 12000},
    "international_tier_a": {"meal_allowance": 6000, "lodging_cap": 25000},
    "international_tier_b": {"meal_allowance": 5000, "lodging_cap": 20000},
    "international_tier_c": {"meal_allowance": 4000, "lodging_cap": 18000},
}

DAY_TRIP_MEAL_ALLOWANCE: dict[str, int] = {"domestic": 1500, "international": 3000}

# Simplified illustrative round-trip flight fare (JPY, economy) keyed by
# destination tier, used when planning a cost estimate for a destination
# whose exact city pair is not in the small representative city catalog
# above. This is a coarse average, not a real fare -- the lab explicitly asks
# participants to compare it against the authoritative Travel Ops API
# ``POST /trip-estimates`` result.
ILLUSTRATIVE_FLIGHT_FARE_JPY: dict[str, int] = {
    "domestic_tier1": 32000,
    "domestic_tier2": 40000,
    "international_tier_c": 65000,
    "international_tier_b": 90000,
    "international_tier_a": 185000,
}

# Cabin classes with an additional illustrative fare multiplier, and whether a
# tier's flight is long enough to plausibly offer them. Mirrors the
# allowed_cabin_classes() policy in src/travel-api (policy-flights-001):
# domestic routes are economy-only; first class is never offered by this
# simulation (see policy-approval-process-001 accessibility-exception carve
# out, which this workshop agent does not attempt to model).
_CABIN_FARE_MULTIPLIER: dict[CabinClass, float] = {
    "economy": 1.0,
    "premium_economy": 1.8,
    "business": 3.4,
    "first": 6.0,
}

# One-way scheduled hours for the same representative routes used by the
# Travel Ops API. Cabin eligibility is based on duration, not destination cost
# tier (data/policies/02-flights.md).
_FLIGHT_HOURS_BY_ROUTE: dict[frozenset[str], float] = {
    frozenset({"Tokyo", "Osaka"}): 1.0,
    frozenset({"Tokyo", "Nagoya"}): 1.0,
    frozenset({"Tokyo", "Fukuoka"}): 1.9,
    frozenset({"Tokyo", "Sapporo"}): 1.5,
    frozenset({"Osaka", "Sapporo"}): 2.0,
    frozenset({"Tokyo", "Sendai"}): 1.0,
    frozenset({"Tokyo", "Hiroshima"}): 1.3,
    frozenset({"Tokyo", "Naha"}): 2.5,
    frozenset({"Tokyo", "Hong Kong"}): 5.0,
    frozenset({"Tokyo", "Taipei"}): 4.0,
    frozenset({"Tokyo", "Seoul"}): 2.5,
    frozenset({"Tokyo", "Singapore"}): 7.0,
    frozenset({"Tokyo", "Bangkok"}): 7.0,
    frozenset({"Tokyo", "San Francisco"}): 9.5,
    frozenset({"Tokyo", "Sydney"}): 9.5,
    frozenset({"Tokyo", "New York"}): 13.0,
    frozenset({"Tokyo", "London"}): 14.0,
    frozenset({"Tokyo", "Paris"}): 14.5,
    frozenset({"Tokyo", "Dubai"}): 11.0,
    frozenset({"Tokyo", "Sao Paulo"}): 24.0,
}

SIMULATION_DISCLAIMER_JA = (
    "この結果はハンズオン教材用のシミュレーションです。実際の承認・予約権限は"
    "持ちません。実際の出張では必ず Contoso Travel Portal で正式な事前承認・予約"
    "手続きを行ってください。"
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "origin",
    "destination",
    "departure_date",
    "return_date",
    "cabin_class",
    "purpose",
)


def get_city_tier(city: str) -> str | None:
    """Return the synthetic tier id for a known city, or ``None`` if unknown."""
    return _TIER_BY_CITY.get(city.strip())


def is_international_tier(tier: str) -> bool:
    return tier.startswith("international")


def get_flight_hours(origin: str, destination: str) -> float | None:
    """Return one-way hours for a representative route, or ``None``.

    Unknown routes never gain eligibility for an upgraded cabin class.
    """
    return _FLIGHT_HOURS_BY_ROUTE.get(frozenset({origin.strip(), destination.strip()}))


# ---------------------------------------------------------------------------
# intake_agent: structure the raw request
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TripRequest:
    """A structured, validated trip request produced by intake_agent."""

    origin: str
    destination: str
    departure_date: datetime.date
    return_date: datetime.date
    cabin_class: CabinClass
    purpose: str
    traveler_count: int = 1


@dataclass(frozen=True)
class IntakeResult:
    """Output of intake_agent: either a complete request, or the missing fields."""

    is_complete: bool
    request: TripRequest | None
    missing_fields: tuple[str, ...]
    field_errors: tuple[str, ...] = field(default_factory=tuple)


def _parse_date(value: Any) -> datetime.date | None:
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value.strip())
        except ValueError:
            return None
    return None


def parse_trip_request(raw: dict[str, Any]) -> IntakeResult:
    """Structure a raw (already-parsed JSON) trip request payload.

    Any field in ``REQUIRED_FIELDS`` that is missing, blank, or the wrong
    shape is reported in ``missing_fields``/``field_errors`` and
    ``is_complete`` is ``False`` -- this is the seam the workflow's
    missing-information branch routes on.
    """
    missing: list[str] = []
    errors: list[str] = []

    def _clean_str(key: str) -> str | None:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            missing.append(key)
            return None
        return value.strip()

    origin = _clean_str("origin")
    destination = _clean_str("destination")
    purpose = _clean_str("purpose")

    departure_date = _parse_date(raw.get("departure_date"))
    if "departure_date" not in raw or raw.get("departure_date") in (None, ""):
        missing.append("departure_date")
    elif departure_date is None:
        errors.append("departure_date must be an ISO-8601 date (YYYY-MM-DD)")

    return_date = _parse_date(raw.get("return_date"))
    if "return_date" not in raw or raw.get("return_date") in (None, ""):
        missing.append("return_date")
    elif return_date is None:
        errors.append("return_date must be an ISO-8601 date (YYYY-MM-DD)")

    cabin_class_raw = raw.get("cabin_class")
    cabin_class: CabinClass | None = None
    if not isinstance(cabin_class_raw, str) or not cabin_class_raw.strip():
        missing.append("cabin_class")
    elif cabin_class_raw.strip() not in CABIN_CLASSES:
        errors.append(f"cabin_class must be one of {CABIN_CLASSES}")
    else:
        cabin_class = cabin_class_raw.strip()  # type: ignore[assignment]

    traveler_count_raw = raw.get("traveler_count", 1)
    traveler_count = 1
    if isinstance(traveler_count_raw, bool):
        errors.append("traveler_count must be a positive integer")
    elif isinstance(traveler_count_raw, int) and traveler_count_raw > 0:
        traveler_count = traveler_count_raw
    elif traveler_count_raw not in (None, ""):
        errors.append("traveler_count must be a positive integer")

    if departure_date is not None and return_date is not None and return_date < departure_date:
        errors.append("return_date must not be before departure_date")

    is_complete = not missing and not errors
    request: TripRequest | None = None
    if is_complete:
        assert origin is not None
        assert destination is not None
        assert purpose is not None
        assert departure_date is not None
        assert return_date is not None
        assert cabin_class is not None
        request = TripRequest(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            cabin_class=cabin_class,
            purpose=purpose,
            traveler_count=traveler_count,
        )

    return IntakeResult(
        is_complete=is_complete,
        request=request,
        missing_fields=tuple(missing),
        field_errors=tuple(errors),
    )


# ---------------------------------------------------------------------------
# policy_agent: check bundled synthetic policy excerpts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyCheckResult:
    """Output of policy_agent."""

    is_international: bool
    origin_tier: str | None
    destination_tier: str | None
    cabin_class_allowed: bool
    requires_manager_preapproval: bool
    requires_vp_preapproval: bool
    reasons: tuple[str, ...]
    citations: tuple[str, ...]


def check_policy(request: TripRequest) -> PolicyCheckResult:
    """Check a structured trip request against the bundled policy excerpt.

    This mirrors the reasoning in
    ``src/travel-api/travel_api/domain/trip_estimate.py`` (manager/VP
    preapproval derivation) and ``data/policies/09-approval-process.md``
    (policy-approval-process-001), but total-estimate-driven reasons are
    finalized once the cost plan is known -- see ``decide_approval`` below,
    which combines this result with ``CostPlan``.
    """
    origin_tier = get_city_tier(request.origin)
    destination_tier = get_city_tier(request.destination)

    is_international = bool(
        (origin_tier and is_international_tier(origin_tier))
        or (destination_tier and is_international_tier(destination_tier))
        or origin_tier is None
        or destination_tier is None
    )

    reasons: list[str] = []
    citations: list[str] = ["policy-approval-process-001"]

    flight_hours = get_flight_hours(request.origin, request.destination)
    cabin_class_allowed = False
    if request.cabin_class == "first":
        reasons.append("first_class_requires_accessibility_exception_process")
        citations.append("policy-approval-process-001")
    elif request.cabin_class == "economy":
        cabin_class_allowed = True
    elif not is_international:
        reason_prefix = "business_class" if request.cabin_class == "business" else "premium_economy"
        reasons.append(f"{reason_prefix}_not_allowed_on_domestic_routes")
        citations.append("policy-flights-001")
    elif flight_hours is None:
        reasons.append("route_duration_unknown_upgraded_cabin_not_allowed")
        citations.append("policy-flights-001")
    elif request.cabin_class == "premium_economy":
        cabin_class_allowed = flight_hours >= 6
        if not cabin_class_allowed:
            reasons.append("premium_economy_requires_at_least_6_hours")
        citations.append("policy-flights-001")
    elif request.cabin_class == "business":
        cabin_class_allowed = flight_hours >= 10
        if not cabin_class_allowed:
            reasons.append("business_class_requires_at_least_10_hours")
        citations.append("policy-flights-001")
    else:
        reasons.append("unsupported_cabin_class")
        citations.append("policy-flights-001")

    if is_international:
        reasons.append("international_travel_requires_manager_preapproval")

    vp_required = request.cabin_class == "business" and cabin_class_allowed
    if vp_required:
        reasons.append("business_class_requires_manager_and_vp_preapproval")

    manager_required = is_international or vp_required

    return PolicyCheckResult(
        is_international=is_international,
        origin_tier=origin_tier,
        destination_tier=destination_tier,
        cabin_class_allowed=cabin_class_allowed,
        requires_manager_preapproval=manager_required,
        requires_vp_preapproval=vp_required,
        reasons=tuple(reasons),
        citations=tuple(dict.fromkeys(citations)),
    )


# ---------------------------------------------------------------------------
# planner_agent: build a cost plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CostPlan:
    """Output of planner_agent."""

    nights: int
    is_day_trip: bool
    flight_estimate_jpy: int
    lodging_estimate_jpy: int
    meal_estimate_jpy: int
    total_estimate_jpy: int
    currency: str
    notes: tuple[str, ...]


def _flight_estimate(
    destination_tier: str | None, cabin_class: CabinClass, traveler_count: int
) -> int:
    tier = destination_tier or "international_tier_c"
    base_fare = ILLUSTRATIVE_FLIGHT_FARE_JPY.get(
        tier, ILLUSTRATIVE_FLIGHT_FARE_JPY["international_tier_c"]
    )
    multiplier = _CABIN_FARE_MULTIPLIER.get(cabin_class, 1.0)
    return round(base_fare * multiplier) * traveler_count


def estimate_cost(request: TripRequest, policy: PolicyCheckResult) -> CostPlan:
    """Compute a simplified, illustrative cost plan for a structured request.

    Mirrors the shape of
    ``src/travel-api/travel_api/domain/trip_estimate.py::estimate_trip`` but
    uses the smaller bundled rate table above instead of the full route
    catalog, since the deployed hosted-agent zip cannot import
    ``src/travel-api``.
    """
    nights = (request.return_date - request.departure_date).days
    is_day_trip = nights == 0
    destination_tier = policy.destination_tier or "international_tier_c"
    rates = PER_DIEM_TABLE.get(destination_tier, PER_DIEM_TABLE["international_tier_c"])

    notes: list[str] = []
    if policy.destination_tier is None:
        notes.append(
            "destination city is outside the bundled synthetic city catalog; "
            "using international_tier_c rates as a conservative illustrative default"
        )

    if is_day_trip:
        meal_bucket = "international" if policy.is_international else "domestic"
        meal_cost = DAY_TRIP_MEAL_ALLOWANCE[meal_bucket] * request.traveler_count
        lodging_cost = 0
    else:
        meal_days = nights + 1
        meal_cost = rates["meal_allowance"] * meal_days * request.traveler_count
        lodging_cost = rates["lodging_cap"] * nights * request.traveler_count

    flight_cost = _flight_estimate(
        policy.destination_tier, request.cabin_class, request.traveler_count
    )
    total = flight_cost + lodging_cost + meal_cost

    return CostPlan(
        nights=nights,
        is_day_trip=is_day_trip,
        flight_estimate_jpy=flight_cost,
        lodging_estimate_jpy=lodging_cost,
        meal_estimate_jpy=meal_cost,
        total_estimate_jpy=total,
        currency=CURRENCY,
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# approval_agent: final simulated recommendation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApprovalDecision:
    """Output of approval_agent -- always a *simulated* recommendation."""

    requires_preapproval: bool
    approvers: tuple[str, ...]
    reasons: tuple[str, ...]
    citations: tuple[str, ...]
    recommendation_ja: str
    disclaimer_ja: str = SIMULATION_DISCLAIMER_JA


def _trip_reference_id(request: TripRequest) -> str:
    digest = hashlib.sha256(
        "|".join(
            [
                request.origin,
                request.destination,
                request.departure_date.isoformat(),
                request.return_date.isoformat(),
                request.cabin_class,
                str(request.traveler_count),
            ]
        ).encode("utf-8")
    ).hexdigest()
    return f"sim-trip-{digest[:12]}"


def decide_approval(
    request: TripRequest, policy: PolicyCheckResult, cost_plan: CostPlan
) -> ApprovalDecision:
    """Combine policy + cost signals into one simulated recommendation.

    This is the function the workflow's over-threshold/approval branch
    routes on via ``ApprovalDecision.requires_preapproval``.
    """
    reasons = list(policy.reasons)
    citations = list(policy.citations)

    over_threshold = (
        not policy.is_international
        and cost_plan.total_estimate_jpy > DOMESTIC_MANAGER_APPROVAL_THRESHOLD_JPY
    )
    if over_threshold:
        reasons.append("domestic_total_exceeds_100000_jpy")
        citations.append("policy-approval-process-001")

    requires_preapproval = policy.requires_manager_preapproval or over_threshold

    approvers: list[str] = []
    if requires_preapproval:
        approvers.append("manager")
    if policy.requires_vp_preapproval:
        approvers.append("department_vp")

    ref = _trip_reference_id(request)
    if not policy.cabin_class_allowed:
        recommendation_ja = (
            f"[{ref}] このハンズオン環境では座席クラス '{request.cabin_class}' は"
            "許可されていません。エコノミー、プレミアムエコノミー、または"
            "(対象路線のみ)ビジネスクラスを選択してください。"
        )
    elif requires_preapproval:
        who = "・".join("マネージャー" if a == "manager" else "部門 VP" for a in approvers)
        recommendation_ja = (
            f"[{ref}] 見積総額 {cost_plan.total_estimate_jpy:,} 円のこの出張案は、"
            f"予約前に{who}の事前承認が必要と判定されました(シミュレーション)。"
        )
    else:
        recommendation_ja = (
            f"[{ref}] 見積総額 {cost_plan.total_estimate_jpy:,} 円のこの出張案は、"
            "現行ポリシー上、追加の事前承認なしで手配可能と判定されました"
            "(シミュレーション、事後レビュー対象)。"
        )

    return ApprovalDecision(
        requires_preapproval=requires_preapproval,
        approvers=tuple(approvers),
        reasons=tuple(dict.fromkeys(reasons)),
        citations=tuple(dict.fromkeys(citations)),
        recommendation_ja=recommendation_ja,
    )


# ---------------------------------------------------------------------------
# Structured output shaping
#
# These functions produce the exact JSON-serializable dict the workflow
# yields as its final Responses-protocol output. Keeping the shaping here
# (rather than in the agent_framework-facing workflow module) keeps the
# workflow's terminal executors as thin one-line adapters, per the
# "pure workflow/policy/branching configuration testable without Azure"
# architecture requirement.
# ---------------------------------------------------------------------------


def safe_parse_json_object(text: str) -> dict[str, Any]:
    """Best-effort parse of ``text`` as a JSON object.

    Returns an empty dict (never raises) if ``text`` is not valid JSON or is
    not a JSON object -- callers treat an empty dict as "no usable fields",
    which naturally routes into the missing-information branch.
    """
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def missing_info_response(result: IntakeResult) -> dict[str, Any]:
    """Structured output for the missing-information branch."""
    return {
        "status": "missing_information",
        "missing_fields": list(result.missing_fields),
        "field_errors": list(result.field_errors),
        "message_ja": (
            "出張プランを見積もるには、次の項目が必要です: "
            + "、".join(result.missing_fields + result.field_errors)
            + "。origin(出発地)、destination(目的地)、departure_date、"
            "return_date(YYYY-MM-DD)、cabin_class"
            f"({'/'.join(CABIN_CLASSES)})、purpose(出張目的)を含む "
            "JSON 形式で再度お知らせください。"
        ),
        "disclaimer_ja": SIMULATION_DISCLAIMER_JA,
    }


def _request_dict(request: TripRequest) -> dict[str, Any]:
    payload = asdict(request)
    payload["departure_date"] = request.departure_date.isoformat()
    payload["return_date"] = request.return_date.isoformat()
    return payload


def final_response(
    request: TripRequest,
    policy: PolicyCheckResult,
    cost_plan: CostPlan,
    decision: ApprovalDecision,
) -> dict[str, Any]:
    """Structured output for the sequential workflow's terminal branches.

    ``status`` is either ``"approval_required"`` or ``"auto_within_policy"``
    -- this is the same field the workflow's over-threshold/approval branch
    routes on (see ``ApprovalDecision.requires_preapproval``).
    """
    return {
        "status": "approval_required" if decision.requires_preapproval else "auto_within_policy",
        "request": _request_dict(request),
        "policy_check": {
            "is_international": policy.is_international,
            "origin_tier": policy.origin_tier,
            "destination_tier": policy.destination_tier,
            "cabin_class_allowed": policy.cabin_class_allowed,
            "requires_manager_preapproval": policy.requires_manager_preapproval,
            "requires_vp_preapproval": policy.requires_vp_preapproval,
            "reasons": list(policy.reasons),
            "citations": list(policy.citations),
        },
        "cost_plan": {
            "nights": cost_plan.nights,
            "is_day_trip": cost_plan.is_day_trip,
            "flight_estimate_jpy": cost_plan.flight_estimate_jpy,
            "lodging_estimate_jpy": cost_plan.lodging_estimate_jpy,
            "meal_estimate_jpy": cost_plan.meal_estimate_jpy,
            "total_estimate_jpy": cost_plan.total_estimate_jpy,
            "currency": cost_plan.currency,
            "notes": list(cost_plan.notes),
        },
        "approval_decision": {
            "requires_preapproval": decision.requires_preapproval,
            "approvers": list(decision.approvers),
            "reasons": list(decision.reasons),
            "citations": list(decision.citations),
        },
        "recommendation_ja": decision.recommendation_ja,
        "disclaimer_ja": decision.disclaimer_ja,
    }

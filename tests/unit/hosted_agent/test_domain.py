"""Unit tests for src/hosted-agent/domain.py.

domain.py has zero agent_framework/azure-* imports, so these tests exercise
plain, deterministic Python: no event loop, no credentials, no network.
"""

from __future__ import annotations

import datetime

import domain
import pytest

# ---------------------------------------------------------------------------
# parse_trip_request (intake_agent logic)
# ---------------------------------------------------------------------------


def _complete_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "origin": "Tokyo",
        "destination": "Osaka",
        "departure_date": "2026-05-10",
        "return_date": "2026-05-11",
        "cabin_class": "economy",
        "purpose": "client visit",
    }
    payload.update(overrides)
    return payload


def test_parse_trip_request_complete_payload_is_complete() -> None:
    result = domain.parse_trip_request(_complete_payload())

    assert result.is_complete is True
    assert result.missing_fields == ()
    assert result.field_errors == ()
    assert result.request is not None
    assert result.request.origin == "Tokyo"
    assert result.request.destination == "Osaka"
    assert result.request.departure_date == datetime.date(2026, 5, 10)
    assert result.request.traveler_count == 1


def test_parse_trip_request_reports_all_missing_fields() -> None:
    result = domain.parse_trip_request({"origin": "Tokyo"})

    assert result.is_complete is False
    assert result.request is None
    assert set(result.missing_fields) == {
        "destination",
        "departure_date",
        "return_date",
        "cabin_class",
        "purpose",
    }


def test_parse_trip_request_empty_dict_is_missing_everything() -> None:
    result = domain.parse_trip_request({})

    assert result.is_complete is False
    assert set(result.missing_fields) == set(domain.REQUIRED_FIELDS)


@pytest.mark.parametrize("bad_date", ["not-a-date", "2026/05/10", "05-10-2026"])
def test_parse_trip_request_invalid_date_format_is_a_field_error_not_missing(bad_date: str) -> None:
    result = domain.parse_trip_request(_complete_payload(departure_date=bad_date))

    assert result.is_complete is False
    assert "departure_date" not in result.missing_fields
    assert any("departure_date" in error for error in result.field_errors)


def test_parse_trip_request_return_before_departure_is_field_error() -> None:
    result = domain.parse_trip_request(
        _complete_payload(departure_date="2026-05-10", return_date="2026-05-01")
    )

    assert result.is_complete is False
    assert any("return_date" in error for error in result.field_errors)


def test_parse_trip_request_unknown_cabin_class_is_field_error() -> None:
    result = domain.parse_trip_request(_complete_payload(cabin_class="super-deluxe"))

    assert result.is_complete is False
    assert any("cabin_class" in error for error in result.field_errors)


def test_parse_trip_request_honors_explicit_traveler_count() -> None:
    result = domain.parse_trip_request(_complete_payload(traveler_count=3))

    assert result.is_complete is True
    assert result.request is not None
    assert result.request.traveler_count == 3


@pytest.mark.parametrize("bad_count", [0, -1, "two", True])
def test_parse_trip_request_invalid_traveler_count_is_field_error(bad_count: object) -> None:
    result = domain.parse_trip_request(_complete_payload(traveler_count=bad_count))

    assert result.is_complete is False
    assert any("traveler_count" in error for error in result.field_errors)


def test_safe_parse_json_object_returns_empty_dict_for_garbage() -> None:
    assert domain.safe_parse_json_object("not json at all") == {}
    assert domain.safe_parse_json_object("[1, 2, 3]") == {}
    assert domain.safe_parse_json_object("") == {}


def test_safe_parse_json_object_parses_valid_object() -> None:
    assert domain.safe_parse_json_object('{"a": 1}') == {"a": 1}


# ---------------------------------------------------------------------------
# check_policy (policy_agent logic)
# ---------------------------------------------------------------------------


def _request(**overrides: object) -> domain.TripRequest:
    defaults: dict[str, object] = dict(
        origin="Tokyo",
        destination="Osaka",
        departure_date=datetime.date(2026, 5, 10),
        return_date=datetime.date(2026, 5, 11),
        cabin_class="economy",
        purpose="client visit",
        traveler_count=1,
    )
    defaults.update(overrides)
    return domain.TripRequest(**defaults)  # type: ignore[arg-type]


def test_check_policy_domestic_economy_requires_no_preapproval() -> None:
    policy = domain.check_policy(_request())

    assert policy.is_international is False
    assert policy.requires_manager_preapproval is False
    assert policy.requires_vp_preapproval is False
    assert policy.cabin_class_allowed is True


def test_check_policy_international_always_requires_manager_preapproval() -> None:
    policy = domain.check_policy(_request(destination="London"))

    assert policy.is_international is True
    assert policy.requires_manager_preapproval is True
    assert "international_travel_requires_manager_preapproval" in policy.reasons


def test_check_policy_business_class_requires_manager_and_vp() -> None:
    policy = domain.check_policy(_request(destination="London", cabin_class="business"))

    assert policy.requires_manager_preapproval is True
    assert policy.requires_vp_preapproval is True


def test_check_policy_domestic_business_class_is_not_allowed() -> None:
    policy = domain.check_policy(_request(cabin_class="business"))

    assert policy.cabin_class_allowed is False
    assert "business_class_not_allowed_on_domestic_routes" in policy.reasons


def test_check_policy_domestic_premium_economy_is_not_allowed() -> None:
    policy = domain.check_policy(_request(cabin_class="premium_economy"))

    assert policy.cabin_class_allowed is False
    assert "premium_economy_not_allowed_on_domestic_routes" in policy.reasons


@pytest.mark.parametrize("destination", ["Singapore", "Sydney", "Bangkok"])
def test_check_policy_business_requires_ten_hour_route(destination: str) -> None:
    policy = domain.check_policy(_request(destination=destination, cabin_class="business"))

    assert policy.cabin_class_allowed is False
    assert policy.requires_vp_preapproval is False
    assert "business_class_requires_at_least_10_hours" in policy.reasons


def test_check_policy_premium_economy_requires_six_hour_route() -> None:
    short_route = domain.check_policy(
        _request(destination="Hong Kong", cabin_class="premium_economy")
    )
    medium_route = domain.check_policy(
        _request(destination="Singapore", cabin_class="premium_economy")
    )

    assert short_route.cabin_class_allowed is False
    assert "premium_economy_requires_at_least_6_hours" in short_route.reasons
    assert medium_route.cabin_class_allowed is True


def test_check_policy_unknown_route_disallows_upgraded_cabin() -> None:
    policy = domain.check_policy(_request(destination="Atlantis", cabin_class="business"))

    assert policy.cabin_class_allowed is False
    assert policy.requires_vp_preapproval is False
    assert "route_duration_unknown_upgraded_cabin_not_allowed" in policy.reasons


def test_check_policy_first_class_is_never_allowed() -> None:
    policy = domain.check_policy(_request(destination="London", cabin_class="first"))

    assert policy.cabin_class_allowed is False
    assert "first_class_requires_accessibility_exception_process" in policy.reasons


def test_check_policy_unknown_city_is_treated_as_international_conservatively() -> None:
    policy = domain.check_policy(_request(destination="Atlantis"))

    assert policy.destination_tier is None
    assert policy.is_international is True


def test_check_policy_always_cites_approval_process_policy() -> None:
    policy = domain.check_policy(_request())

    assert "policy-approval-process-001" in policy.citations


# ---------------------------------------------------------------------------
# estimate_cost (planner_agent logic)
# ---------------------------------------------------------------------------


def test_estimate_cost_day_trip_has_no_lodging_cost() -> None:
    request = _request(
        departure_date=datetime.date(2026, 5, 10), return_date=datetime.date(2026, 5, 10)
    )
    policy = domain.check_policy(request)

    cost_plan = domain.estimate_cost(request, policy)

    assert cost_plan.is_day_trip is True
    assert cost_plan.nights == 0
    assert cost_plan.lodging_estimate_jpy == 0
    assert cost_plan.meal_estimate_jpy == domain.DAY_TRIP_MEAL_ALLOWANCE["domestic"]


def test_estimate_cost_overnight_trip_scales_with_nights_and_travelers() -> None:
    request = _request(
        departure_date=datetime.date(2026, 5, 10),
        return_date=datetime.date(2026, 5, 12),
        traveler_count=2,
    )
    policy = domain.check_policy(request)

    cost_plan = domain.estimate_cost(request, policy)

    assert cost_plan.nights == 2
    assert cost_plan.is_day_trip is False
    rates = domain.PER_DIEM_TABLE["domestic_tier1"]
    assert cost_plan.lodging_estimate_jpy == rates["lodging_cap"] * 2 * 2
    assert cost_plan.meal_estimate_jpy == rates["meal_allowance"] * 3 * 2
    assert cost_plan.total_estimate_jpy == (
        cost_plan.flight_estimate_jpy + cost_plan.lodging_estimate_jpy + cost_plan.meal_estimate_jpy
    )


def test_estimate_cost_business_class_flight_is_more_expensive_than_economy() -> None:
    request_economy = _request(destination="London", cabin_class="economy")
    request_business = _request(destination="London", cabin_class="business")
    policy = domain.check_policy(request_economy)

    economy_plan = domain.estimate_cost(request_economy, policy)
    business_plan = domain.estimate_cost(request_business, policy)

    assert business_plan.flight_estimate_jpy > economy_plan.flight_estimate_jpy


def test_estimate_cost_unknown_destination_falls_back_conservatively() -> None:
    request = _request(destination="Atlantis")
    policy = domain.check_policy(request)

    cost_plan = domain.estimate_cost(request, policy)

    assert cost_plan.notes  # a note documents the fallback
    assert cost_plan.total_estimate_jpy > 0


# ---------------------------------------------------------------------------
# decide_approval (approval_agent logic) -- this is the "over-threshold"
# branch condition the workflow routes on.
# ---------------------------------------------------------------------------


def test_decide_approval_low_cost_domestic_trip_needs_no_preapproval() -> None:
    request = _request()
    policy = domain.check_policy(request)
    cost_plan = domain.estimate_cost(request, policy)

    decision = domain.decide_approval(request, policy, cost_plan)

    assert decision.requires_preapproval is False
    assert decision.approvers == ()
    assert domain.SIMULATION_DISCLAIMER_JA in decision.disclaimer_ja


def test_decide_approval_domestic_trip_over_threshold_requires_manager() -> None:
    # Many travelers to push the domestic total comfortably over 100,000 JPY.
    request = _request(traveler_count=5)
    policy = domain.check_policy(request)
    cost_plan = domain.estimate_cost(request, policy)
    assert cost_plan.total_estimate_jpy > domain.DOMESTIC_MANAGER_APPROVAL_THRESHOLD_JPY

    decision = domain.decide_approval(request, policy, cost_plan)

    assert decision.requires_preapproval is True
    assert "manager" in decision.approvers
    assert "domestic_total_exceeds_100000_jpy" in decision.reasons


def test_decide_approval_international_business_requires_manager_and_vp() -> None:
    request = _request(destination="London", cabin_class="business")
    policy = domain.check_policy(request)
    cost_plan = domain.estimate_cost(request, policy)

    decision = domain.decide_approval(request, policy, cost_plan)

    assert decision.requires_preapproval is True
    assert set(decision.approvers) == {"manager", "department_vp"}


def test_decide_approval_never_omits_the_simulation_disclaimer() -> None:
    request = _request()
    policy = domain.check_policy(request)
    cost_plan = domain.estimate_cost(request, policy)

    decision = domain.decide_approval(request, policy, cost_plan)

    assert decision.disclaimer_ja == domain.SIMULATION_DISCLAIMER_JA
    assert (
        "シミュレーション" in decision.recommendation_ja
        or "シミュレーション" in decision.disclaimer_ja
    )


# ---------------------------------------------------------------------------
# Structured output shaping
# ---------------------------------------------------------------------------


def test_missing_info_response_lists_missing_fields_and_disclaimer() -> None:
    intake = domain.parse_trip_request({"origin": "Tokyo"})

    response = domain.missing_info_response(intake)

    assert response["status"] == "missing_information"
    assert set(response["missing_fields"]) == set(intake.missing_fields)
    assert response["disclaimer_ja"] == domain.SIMULATION_DISCLAIMER_JA


def test_final_response_status_matches_approval_decision() -> None:
    request = _request(destination="London", cabin_class="business")
    policy = domain.check_policy(request)
    cost_plan = domain.estimate_cost(request, policy)
    decision = domain.decide_approval(request, policy, cost_plan)

    response = domain.final_response(request, policy, cost_plan, decision)

    assert response["status"] == "approval_required"
    assert response["request"]["departure_date"] == "2026-05-10"
    assert response["approval_decision"]["requires_preapproval"] is True
    assert response["disclaimer_ja"] == domain.SIMULATION_DISCLAIMER_JA


def test_final_response_auto_within_policy_status() -> None:
    request = _request()
    policy = domain.check_policy(request)
    cost_plan = domain.estimate_cost(request, policy)
    decision = domain.decide_approval(request, policy, cost_plan)

    response = domain.final_response(request, policy, cost_plan, decision)

    assert response["status"] == "auto_within_policy"

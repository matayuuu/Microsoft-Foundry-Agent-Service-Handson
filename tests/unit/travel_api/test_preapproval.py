"""Unit tests for the POST /preapprovals domain rule (always a simulation)."""

import datetime

from travel_api.domain.preapproval import (
    SIMULATED_AUTO_ELIGIBLE,
    SIMULATED_PENDING_MANAGER_REVIEW,
    SIMULATED_PENDING_VP_REVIEW,
    evaluate_preapproval,
)


def test_small_domestic_trip_is_auto_eligible():
    result = evaluate_preapproval(
        origin_city="Tokyo",
        destination_city="Osaka",
        start_date=datetime.date(2026, 5, 11),
        end_date=datetime.date(2026, 5, 12),
    )
    assert result.decision == SIMULATED_AUTO_ELIGIBLE
    assert result.simulation is True
    assert "シミュレーション" in result.disclaimer


def test_international_trip_requires_manager_review():
    result = evaluate_preapproval(
        origin_city="Tokyo",
        destination_city="Hong Kong",
        start_date=datetime.date(2026, 5, 25),
        end_date=datetime.date(2026, 5, 27),
    )
    assert result.decision == SIMULATED_PENDING_MANAGER_REVIEW


def test_business_class_requires_vp_review():
    result = evaluate_preapproval(
        origin_city="Tokyo",
        destination_city="New York",
        start_date=datetime.date(2026, 7, 10),
        end_date=datetime.date(2026, 7, 15),
        cabin_class="business",
    )
    assert result.decision == SIMULATED_PENDING_VP_REVIEW


def test_all_decision_values_are_prefixed_simulated():
    for decision in (
        SIMULATED_AUTO_ELIGIBLE,
        SIMULATED_PENDING_MANAGER_REVIEW,
        SIMULATED_PENDING_VP_REVIEW,
    ):
        assert decision.startswith("simulated_")


def test_reference_id_is_deterministic_and_not_a_real_approval_number():
    kwargs = dict(
        origin_city="Tokyo",
        destination_city="Osaka",
        start_date=datetime.date(2026, 5, 11),
        end_date=datetime.date(2026, 5, 12),
    )
    first = evaluate_preapproval(**kwargs)
    second = evaluate_preapproval(**kwargs)
    assert first.reference_id == second.reference_id
    assert first.reference_id.startswith("sim-preapproval-")


def test_justification_is_carried_through_unmodified():
    result = evaluate_preapproval(
        origin_city="Tokyo",
        destination_city="Osaka",
        start_date=datetime.date(2026, 5, 11),
        end_date=datetime.date(2026, 5, 12),
        justification="顧客訪問のため",
    )
    assert result.justification == "顧客訪問のため"

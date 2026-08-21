"""Contract tests for the Travel Ops API HTTP endpoints via FastAPI's TestClient."""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient
from travel_api.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_per_diem_success():
    response = client.get("/per-diem", params={"city": "Osaka", "date": "2026-05-11"})
    assert response.status_code == 200
    body = response.json()
    assert body["tier"] == "domestic_tier1"
    assert body["meal_allowance"] == 3000
    assert body["lodging_cap"] == 15000
    assert body["currency"] == "JPY"
    assert any(ref["id"] == "policy-per-diem-001" for ref in body["policy_references"])


def test_per_diem_unknown_city_returns_404():
    response = client.get("/per-diem", params={"city": "Atlantis", "date": "2026-05-11"})
    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "city_not_found"


def test_per_diem_date_before_effective_returns_422():
    response = client.get("/per-diem", params={"city": "Tokyo", "date": "2026-01-01"})
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "date_before_effective_date"


def test_per_diem_missing_query_params_returns_422():
    response = client.get("/per-diem")
    assert response.status_code == 422


def test_trip_estimate_success():
    response = client.post(
        "/trip-estimates",
        json={
            "origin_city": "Tokyo",
            "destination_city": "New York",
            "start_date": "2026-07-10",
            "end_date": "2026-07-15",
            "cabin_class": "business",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_domestic"] is False
    assert body["manager_preapproval_required"] is True
    assert body["vp_preapproval_required"] is True
    assert body["total_estimate"] == body["flight_cost"] + body["lodging_cost"] + body["meal_cost"]


def test_trip_estimate_disallowed_cabin_class_returns_422():
    response = client.post(
        "/trip-estimates",
        json={
            "origin_city": "Tokyo",
            "destination_city": "Osaka",
            "start_date": "2026-05-11",
            "end_date": "2026-05-12",
            "cabin_class": "business",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "cabin_class_not_allowed"


def test_trip_estimate_unknown_route_returns_422():
    response = client.post(
        "/trip-estimates",
        json={
            "origin_city": "Sendai",
            "destination_city": "Naha",
            "start_date": "2026-05-01",
            "end_date": "2026-05-02",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error_code"] == "route_not_found"


def test_trip_estimate_rejects_invalid_body_shape():
    response = client.post("/trip-estimates", json={"origin_city": "Tokyo"})
    assert response.status_code == 422


def test_preapproval_is_always_a_simulation():
    response = client.post(
        "/preapprovals",
        json={
            "origin_city": "Tokyo",
            "destination_city": "Osaka",
            "start_date": "2026-05-11",
            "end_date": "2026-05-12",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["simulation"] is True
    assert body["decision"].startswith("simulated_")
    assert "シミュレーション" in body["disclaimer"]
    assert body["decision"] == "simulated_auto_eligible"


def test_preapproval_business_class_pending_vp_review():
    response = client.post(
        "/preapprovals",
        json={
            "origin_city": "Tokyo",
            "destination_city": "London",
            "start_date": "2026-09-01",
            "end_date": "2026-09-06",
            "cabin_class": "business",
            "justification": "監査対応のため",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "simulated_pending_vp_review"
    assert body["justification"] == "監査対応のため"


def test_preapproval_requester_alias_must_be_synthetic_pattern():
    response = client.post(
        "/preapprovals",
        json={
            "origin_city": "Tokyo",
            "destination_city": "Osaka",
            "start_date": "2026-05-11",
            "end_date": "2026-05-12",
            "requester_alias": "not-a-valid-alias",
        },
    )
    assert response.status_code == 422


def test_preapproval_never_returns_an_unprefixed_approved_field():
    response = client.post(
        "/preapprovals",
        json={
            "origin_city": "Tokyo",
            "destination_city": "Osaka",
            "start_date": "2026-05-11",
            "end_date": "2026-05-12",
        },
    )
    body = response.json()
    assert "approved" not in body
    assert "is_approved" not in body

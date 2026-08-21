"""Contract tests for the Travel Ops API's OpenAPI 3.1 document.

These require FastAPI (owned by src/travel-api/requirements.txt or its own
pyproject.toml, not the repository root). They skip cleanly instead of
failing when the environment running pytest does not have FastAPI installed
(e.g. the repository-root CI environment, until it deliberately opts in).
"""

import pytest

pytest.importorskip("fastapi")

from travel_api.main import app

EXPECTED_OPERATIONS = {
    ("get", "/health"): "getHealth",
    ("get", "/per-diem"): "getPerDiem",
    ("post", "/trip-estimates"): "createTripEstimate",
    ("post", "/preapprovals"): "createPreapproval",
}


@pytest.fixture(scope="module")
def openapi_schema():
    return app.openapi()


def test_openapi_version_is_3_1(openapi_schema):
    assert openapi_schema["openapi"].startswith("3.1")


def test_all_expected_paths_present(openapi_schema):
    for method, path in EXPECTED_OPERATIONS:
        assert path in openapi_schema["paths"], f"missing path {path}"
        assert method in openapi_schema["paths"][path], f"missing method {method} on {path}"


def test_every_operation_has_an_explicit_operation_id(openapi_schema):
    seen_operation_ids = set()
    for path, methods in openapi_schema["paths"].items():
        for method, operation in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            operation_id = operation.get("operationId")
            assert operation_id, f"{method.upper()} {path} is missing operationId"
            assert operation_id not in seen_operation_ids, f"duplicate operationId {operation_id}"
            seen_operation_ids.add(operation_id)

    for (method, path), expected_id in EXPECTED_OPERATIONS.items():
        actual = openapi_schema["paths"][path][method]["operationId"]
        assert actual == expected_id


def test_trip_estimate_and_preapproval_requests_are_typed(openapi_schema):
    components = openapi_schema["components"]["schemas"]
    assert "TripEstimateRequest" in components
    assert "PreapprovalRequest" in components
    trip_request_props = components["TripEstimateRequest"]["properties"]
    assert set(trip_request_props) >= {
        "origin_city",
        "destination_city",
        "start_date",
        "end_date",
        "cabin_class",
        "traveler_count",
    }


def test_preapproval_response_never_implies_a_real_approval(openapi_schema):
    components = openapi_schema["components"]["schemas"]
    preapproval_response = components["PreapprovalResponse"]
    decision_schema = preapproval_response["properties"]["decision"]
    for value in decision_schema["enum"]:
        assert value.startswith("simulated_"), (
            f"decision value {value!r} does not carry the simulated_ prefix"
        )
    simulation_schema = preapproval_response["properties"]["simulation"]
    assert simulation_schema.get("default") is True

"""Unit tests for scripts/create_toolbox.py.

scripts/ is intentionally not a Python package (see scripts/lib), so the
module under test is loaded directly from its file path via importlib,
matching tests/unit/test_validate_environment.py. No live Travel Ops API,
Azure credential, or azure-ai-projects network call happens in this file:
``fetch_openapi_spec`` is exercised with a stubbed ``httpx.get`` and
``get_existing_default_tools``/the SDK client are simple fakes.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from azure.ai.projects.models import WebSearchToolboxTool
from azure.core.exceptions import ResourceNotFoundError

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "create_toolbox.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("create_toolbox", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


create_toolbox = _load_module()

SAMPLE_SPEC = {
    "openapi": "3.1.0",
    "info": {"title": "Travel Ops API", "version": "1.0.0"},
    "paths": {"/health": {"get": {"operationId": "getHealth", "responses": {"200": {}}}}},
}


# ---------------------------------------------------------------------------
# build_auth_details
# ---------------------------------------------------------------------------


def test_build_auth_details_anonymous_needs_no_audience() -> None:
    auth = create_toolbox.build_auth_details("anonymous", audience=None)

    assert isinstance(auth, create_toolbox.OpenApiAnonymousAuthDetails)


def test_build_auth_details_managed_identity_requires_audience() -> None:
    with pytest.raises(create_toolbox.WorkshopContextError, match="--audience"):
        create_toolbox.build_auth_details("managed_identity", audience=None)


def test_build_auth_details_managed_identity_with_audience() -> None:
    auth = create_toolbox.build_auth_details("managed_identity", audience="api://travel-ops")

    assert isinstance(auth, create_toolbox.OpenApiManagedAuthDetails)
    assert auth.security_scheme.audience == "api://travel-ops"


def test_build_auth_details_rejects_unknown_type() -> None:
    with pytest.raises(create_toolbox.WorkshopContextError, match="unknown --auth-type"):
        create_toolbox.build_auth_details("api-key", audience=None)


# ---------------------------------------------------------------------------
# build_openapi_tool / version_matches_desired_tools
# ---------------------------------------------------------------------------


def test_build_openapi_tool_uses_tool_name_and_spec() -> None:
    auth = create_toolbox.OpenApiAnonymousAuthDetails()

    tool = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api", spec=SAMPLE_SPEC, auth=auth
    )

    assert tool.name == "travel_ops_api"
    assert tool.openapi.name == "travel_ops_api"
    assert tool.openapi.spec == SAMPLE_SPEC


def test_version_matches_desired_tools_true_for_identical_spec() -> None:
    auth = create_toolbox.OpenApiAnonymousAuthDetails()
    tool_a = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api", spec=SAMPLE_SPEC, auth=auth
    )
    tool_b = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api", spec=json.loads(json.dumps(SAMPLE_SPEC)), auth=auth
    )

    assert create_toolbox.version_matches_desired_tools([tool_a], [tool_b])


def test_version_matches_desired_tools_false_when_spec_changes() -> None:
    auth = create_toolbox.OpenApiAnonymousAuthDetails()
    existing = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api", spec=SAMPLE_SPEC, auth=auth
    )
    changed_spec = {**SAMPLE_SPEC, "info": {"title": "Travel Ops API", "version": "2.0.0"}}
    desired = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api", spec=changed_spec, auth=auth
    )

    assert not create_toolbox.version_matches_desired_tools([existing], [desired])


def test_version_matches_desired_tools_false_when_auth_changes() -> None:
    existing = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api",
        spec=SAMPLE_SPEC,
        auth=create_toolbox.OpenApiAnonymousAuthDetails(),
    )
    desired = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api",
        spec=SAMPLE_SPEC,
        auth=create_toolbox.OpenApiManagedAuthDetails(
            security_scheme=create_toolbox.OpenApiManagedSecurityScheme(audience="api://x")
        ),
    )

    assert not create_toolbox.version_matches_desired_tools([existing], [desired])


def test_version_matches_desired_tools_false_when_tool_count_differs() -> None:
    auth = create_toolbox.OpenApiAnonymousAuthDetails()
    tool = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api", spec=SAMPLE_SPEC, auth=auth
    )

    assert not create_toolbox.version_matches_desired_tools([], [tool])


def test_upsert_openapi_tool_preserves_non_openapi_tools() -> None:
    web_search = WebSearchToolboxTool(name="web_search", description="Search the public web.")
    desired = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api",
        spec=SAMPLE_SPEC,
        auth=create_toolbox.OpenApiAnonymousAuthDetails(),
    )

    merged, changed = create_toolbox.upsert_openapi_tool([web_search], desired)

    assert changed
    assert merged == [web_search, desired]


def test_upsert_openapi_tool_replaces_only_same_named_openapi_tool() -> None:
    web_search = WebSearchToolboxTool(name="web_search", description="Search the public web.")
    old = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api",
        spec={**SAMPLE_SPEC, "info": {"title": "Travel Ops API", "version": "0.9.0"}},
        auth=create_toolbox.OpenApiAnonymousAuthDetails(),
    )
    desired = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api",
        spec=SAMPLE_SPEC,
        auth=create_toolbox.OpenApiAnonymousAuthDetails(),
    )

    merged, changed = create_toolbox.upsert_openapi_tool([web_search, old], desired)

    assert changed
    assert merged == [web_search, desired]


def test_upsert_openapi_tool_is_unchanged_when_exact_tool_exists() -> None:
    web_search = WebSearchToolboxTool(name="web_search", description="Search the public web.")
    desired = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api",
        spec=SAMPLE_SPEC,
        auth=create_toolbox.OpenApiAnonymousAuthDetails(),
    )

    merged, changed = create_toolbox.upsert_openapi_tool([web_search, desired], desired)

    assert not changed
    assert merged == [web_search, desired]


# ---------------------------------------------------------------------------
# mcp_endpoints
# ---------------------------------------------------------------------------


def test_mcp_endpoints_shape() -> None:
    endpoints = create_toolbox.mcp_endpoints(
        "https://acct.services.ai.azure.com/api/projects/proj", "contoso-travel-toolbox", "2"
    )

    assert endpoints["consumer"] == (
        "https://acct.services.ai.azure.com/api/projects/proj/toolboxes/contoso-travel-toolbox/mcp?api-version=v1"
    )
    assert endpoints["developer"] == (
        "https://acct.services.ai.azure.com/api/projects/proj/toolboxes/contoso-travel-toolbox"
        "/versions/2/mcp?api-version=v1"
    )


def test_mcp_endpoints_strips_trailing_slash_from_project_endpoint() -> None:
    endpoints = create_toolbox.mcp_endpoints(
        "https://acct.example.com/api/projects/proj/", "tb", "1"
    )

    assert "proj//toolboxes" not in endpoints["consumer"]


# ---------------------------------------------------------------------------
# fetch_openapi_spec (httpx stubbed)
# ---------------------------------------------------------------------------


def test_fetch_openapi_spec_returns_parsed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, timeout: float) -> httpx.Response:
        assert url == "https://travel-api.example.io/openapi.json"
        return httpx.Response(200, json=SAMPLE_SPEC, request=httpx.Request("GET", url))

    monkeypatch.setattr(create_toolbox.httpx, "get", fake_get)

    spec = create_toolbox.fetch_openapi_spec("https://travel-api.example.io", "/openapi.json")

    assert spec == SAMPLE_SPEC


def test_fetch_openapi_spec_raises_on_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, timeout: float) -> httpx.Response:
        raise httpx.ConnectError("boom", request=httpx.Request("GET", url))

    monkeypatch.setattr(create_toolbox.httpx, "get", fake_get)

    with pytest.raises(create_toolbox.WorkshopContextError, match="could not fetch"):
        create_toolbox.fetch_openapi_spec("https://travel-api.example.io", "/openapi.json")


def test_fetch_openapi_spec_rejects_non_openapi_document(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, timeout: float) -> httpx.Response:
        return httpx.Response(200, json={"not": "openapi"}, request=httpx.Request("GET", url))

    monkeypatch.setattr(create_toolbox.httpx, "get", fake_get)

    with pytest.raises(
        create_toolbox.WorkshopContextError, match="does not look like an OpenAPI document"
    ):
        create_toolbox.fetch_openapi_spec("https://travel-api.example.io", "/openapi.json")


# ---------------------------------------------------------------------------
# get_existing_default_tools
# ---------------------------------------------------------------------------


class _FakeToolbox:
    def __init__(self, default_version: str) -> None:
        self.default_version = default_version


class _FakeToolboxVersion:
    def __init__(self, tools: list) -> None:
        self.tools = tools


class _FakeToolboxesOperations:
    def __init__(self, toolbox: _FakeToolbox | None, tools: list) -> None:
        self._toolbox = toolbox
        self._tools = tools

    def get(self, name: str) -> _FakeToolbox:
        if self._toolbox is None:
            raise ResourceNotFoundError("not found")
        return self._toolbox

    def get_version(self, name: str, version: str) -> _FakeToolboxVersion:
        return _FakeToolboxVersion(self._tools)


class _FakeClient:
    def __init__(self, toolbox: _FakeToolbox | None, tools: list) -> None:
        self.toolboxes = _FakeToolboxesOperations(toolbox, tools)


def test_get_existing_default_tools_returns_none_when_toolbox_absent() -> None:
    client = _FakeClient(toolbox=None, tools=[])

    assert create_toolbox.get_existing_default_tools(client, "contoso-travel-toolbox") is None


def test_get_existing_default_tools_returns_version_and_tools() -> None:
    auth = create_toolbox.OpenApiAnonymousAuthDetails()
    tool = create_toolbox.build_openapi_tool(
        tool_name="travel_ops_api", spec=SAMPLE_SPEC, auth=auth
    )
    client = _FakeClient(toolbox=_FakeToolbox(default_version="3"), tools=[tool])

    result = create_toolbox.get_existing_default_tools(client, "contoso-travel-toolbox")

    assert result is not None
    version, tools = result
    assert version == "3"
    assert tools == [tool]

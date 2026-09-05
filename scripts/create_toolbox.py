#!/usr/bin/env python3
"""scripts/create_toolbox.py

Optional SDK path for the ``contoso-travel-toolbox`` Microsoft Foundry toolbox
in notebooks/04-create-toolbox.ipynb. Lab 4 creates the toolbox in the Portal.
This adapter adds the Travel Ops OpenAPI tool while preserving UI-managed
tools, Skills, metadata, and guardrails.

Why a script and not Terraform: per docs/architecture.md, toolbox versions are
a Foundry data-plane object owned by SDK wrappers, not Terraform. The adapter
reuses an unchanged default version and creates a version only when the desired
tool definition changes.

Design, mirroring scripts/validate_environment.py: the OpenAPI tool payload
and the "does a new version need to be created" decision are pure functions
(``build_openapi_tool``, ``version_matches_desired_tools``) that are fully
unit-testable without Azure access or a live Travel Ops API. Only ``main``
performs I/O: reading .workshop/context.json, fetching the live OpenAPI spec
over HTTPS, and calling the azure-ai-projects SDK.

Authentication: az login only, via AzureCliCredential (default) or
DefaultAzureCredential (--credential default). No API keys or connection
strings are read anywhere in this script.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path
from typing import Any

# Make the sibling `lib` package importable regardless of current working
# directory (scripts/ is intentionally not an installed Python package).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    MCPTool,
    OpenApiAnonymousAuthDetails,
    OpenApiAuthDetails,
    OpenApiFunctionDefinition,
    OpenApiManagedAuthDetails,
    OpenApiManagedSecurityScheme,
    OpenApiToolboxTool,
    PromptAgentDefinition,
    ToolboxTool,
    ToolboxVersionObject,
)
from azure.core.exceptions import ResourceNotFoundError
from lib.workshop_context import (
    DEFAULT_CONTEXT_PATH,
    DEFAULT_TOOLBOX_NAME,
    WorkshopContextError,
    build_credential,
    load_context,
    project_endpoint,
    travel_api_base_url,
)

DEFAULT_TOOL_NAME = "travel_ops_api"
DEFAULT_OPENAPI_PATH = "/openapi.json"
DEFAULT_TOOLBOX_CONNECTION_NAME = "contoso-travel-toolbox-mcp"
DEFAULT_TOOLBOX_SERVER_LABEL = "travel_ops"
ARM_ENDPOINT = "https://management.azure.com"
PROJECT_CONNECTION_API_VERSION = "2025-10-01-preview"
CONNECTION_TIMEOUT_SECONDS = 60.0
OPENAPI_FETCH_TIMEOUT_SECONDS = 15.0
OPENAPI_FETCH_MAX_ATTEMPTS = 5
OPENAPI_FETCH_RETRY_DELAY_SECONDS = 3.0


# ---------------------------------------------------------------------------
# Pure logic (unit-testable, no Azure/network access)
# ---------------------------------------------------------------------------


def build_openapi_tool(
    *,
    tool_name: str,
    spec: dict[str, Any],
    auth: OpenApiAuthDetails,
    description: str | None = None,
) -> OpenApiToolboxTool:
    """Build the single OpenAPI toolbox tool wrapping the Travel Ops API spec.

    Kept separate from any Azure call so its shape can be asserted in tests
    without a live project or network access.
    """
    return OpenApiToolboxTool(
        openapi=OpenApiFunctionDefinition(
            name=tool_name,
            description=description
            or "Contoso Travel Ops deterministic mock API (per-diem, trip estimate, preapproval).",
            spec=spec,
            auth=auth,
        ),
        name=tool_name,
        description=description,
    )


def build_auth_details(auth_type: str, *, audience: str | None) -> OpenApiAuthDetails:
    """Build the OpenAPI auth details for the tool.

    Defaults to anonymous auth because the deployed Travel Ops API (see
    src/travel-api/README.md) is a public, unauthenticated deterministic mock
    -- there is no API key or Entra-protected audience to attach. The
    managed_identity path is kept for participants/instructors who front the
    API with their own auth later; it requires --audience because the SDK
    itself requires a security_scheme for that auth type.
    """
    if auth_type == "anonymous":
        return OpenApiAnonymousAuthDetails()
    if auth_type == "managed_identity":
        if not audience:
            raise WorkshopContextError(
                "--auth-type managed_identity requires --audience "
                "(the Entra ID audience/App ID URI the Travel Ops API expects)."
            )
        return OpenApiManagedAuthDetails(
            security_scheme=OpenApiManagedSecurityScheme(audience=audience)
        )
    raise WorkshopContextError(
        f"unknown --auth-type '{auth_type}' (expected 'anonymous' or 'managed_identity')"
    )


def _canonicalize_openapi_value(value: Any) -> Any:
    """Normalize lossless server-side JSON number coercions for comparison."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: _canonicalize_openapi_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonicalize_openapi_value(item) for item in value]
    return value


def _openapi_tool_fingerprint(tool: ToolboxTool) -> tuple[Any, ...] | None:
    """A comparable, order-independent fingerprint of an OpenAPI toolbox tool.

    Used only to decide whether an existing default version already matches
    the desired tool set (idempotency), so we never open a needless new
    version. Returns ``None`` for any non-OpenAPI tool (never treated as a
    match).
    """
    openapi = getattr(tool, "openapi", None)
    if openapi is None:
        return None
    auth = getattr(openapi, "auth", None)
    auth_fingerprint = (
        getattr(auth, "type", None),
        getattr(getattr(auth, "security_scheme", None), "audience", None),
    )
    return (
        openapi.name,
        json.dumps(
            _canonicalize_openapi_value(openapi.spec),
            sort_keys=True,
            separators=(",", ":"),
        ),
        auth_fingerprint,
    )


def version_matches_desired_tools(
    existing_tools: list[ToolboxTool], desired_tools: list[ToolboxTool]
) -> bool:
    """True if ``existing_tools`` already contains exactly the desired tool set.

    Compares OpenAPI tools by (name, spec, auth) fingerprint rather than
    object identity, since the SDK returns freshly-deserialized objects on
    every ``get_version`` call.
    """
    existing_fingerprints = {_openapi_tool_fingerprint(t) for t in existing_tools}
    desired_fingerprints = {_openapi_tool_fingerprint(t) for t in desired_tools}
    return existing_fingerprints == desired_fingerprints


def upsert_openapi_tool(
    existing_tools: list[ToolboxTool], desired_tool: OpenApiToolboxTool
) -> tuple[list[ToolboxTool], bool]:
    """Return a complete toolbox version with ``desired_tool`` added or replaced.

    Toolbox versions are snapshots, not additive patches. Preserve every
    unrelated tool from the current default version and replace only an
    OpenAPI tool with the same function name. ``changed`` is false when the
    current version already contains the exact desired OpenAPI definition.
    """
    desired_fingerprint = _openapi_tool_fingerprint(desired_tool)
    desired_name = desired_tool.openapi.name
    merged: list[ToolboxTool] = []
    found_exact = False

    for tool in existing_tools:
        openapi = getattr(tool, "openapi", None)
        if openapi is None or getattr(openapi, "name", None) != desired_name:
            merged.append(tool)
            continue

        if _openapi_tool_fingerprint(tool) == desired_fingerprint and not found_exact:
            merged.append(tool)
            found_exact = True

    if not found_exact:
        merged.append(desired_tool)

    return merged, not found_exact


def mcp_endpoints(endpoint: str, toolbox_name: str, version: str) -> dict[str, str]:
    """The consumer (default-version) and developer (pinned-version) MCP
    endpoint URLs for a toolbox, per the documented URL format:
    ``{project_endpoint}/toolboxes/{toolbox_name}/mcp?api-version=v1``.
    """
    base = f"{endpoint.rstrip('/')}/toolboxes/{toolbox_name}"
    return {
        "consumer": f"{base}/mcp?api-version=v1",
        "developer": f"{base}/versions/{version}/mcp?api-version=v1",
    }


def set_live_server_url(spec: dict[str, Any], base_url: str) -> dict[str, Any]:
    """Return a copy of ``spec`` targeting the deployed Travel Ops API.

    FastAPI omits ``servers`` by default, but Foundry's OpenAPI tool runtime
    requires it to resolve operation URLs. The live Container App URL from
    workshop context is authoritative for this toolbox version.
    """
    normalized = copy.deepcopy(spec)
    normalized["servers"] = [{"url": base_url.rstrip("/")}]
    return normalized


# ---------------------------------------------------------------------------
# I/O adapters
# ---------------------------------------------------------------------------


def fetch_openapi_spec(
    base_url: str,
    openapi_path: str,
    *,
    max_attempts: int = OPENAPI_FETCH_MAX_ATTEMPTS,
    retry_delay: float = OPENAPI_FETCH_RETRY_DELAY_SECONDS,
) -> dict[str, Any]:
    """Fetch the live OpenAPI 3.1 document from the deployed Travel Ops API.

    Fetched live (never vendored into this repo) so the toolbox always
    reflects the actually-deployed API image, per docs/architecture.md's
    "single source of truth" rule for the Travel Ops API contract.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    url = f"{base_url.rstrip('/')}{openapi_path}"
    response: httpx.Response | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            response = httpx.get(url, timeout=OPENAPI_FETCH_TIMEOUT_SECONDS)
            response.raise_for_status()
            break
        except httpx.HTTPError as exc:
            if attempt >= max_attempts:
                raise WorkshopContextError(
                    f"could not fetch OpenAPI spec from {url} after "
                    f"{max_attempts} attempt(s): {exc}"
                ) from exc
            time.sleep(retry_delay)

    assert response is not None
    try:
        spec = response.json()
    except json.JSONDecodeError as exc:
        raise WorkshopContextError(f"response from {url} was not valid JSON: {exc}") from exc
    if "openapi" not in spec or "paths" not in spec:
        raise WorkshopContextError(
            f"response from {url} does not look like an OpenAPI document (missing openapi/paths)."
        )
    return set_live_server_url(spec, base_url)


def get_existing_default_version(
    client: AIProjectClient, toolbox_name: str
) -> ToolboxVersionObject | None:
    """Read the complete default snapshot so SDK edits preserve Portal settings."""
    try:
        toolbox = client.toolboxes.get(toolbox_name)
    except ResourceNotFoundError:
        return None
    return client.toolboxes.get_version(toolbox_name, toolbox.default_version)


def ensure_toolbox(
    client: AIProjectClient,
    *,
    endpoint: str,
    toolbox_name: str,
    desired_tool: OpenApiToolboxTool,
    description: str | None = None,
    publish: bool = True,
) -> dict[str, Any]:
    """Create or update the toolbox and return a participant-friendly result."""
    existing = get_existing_default_version(client, toolbox_name)
    existing_tools = list(existing.tools) if existing is not None else []
    tools_for_version, changed = upsert_openapi_tool(existing_tools, desired_tool)

    if existing is not None and not changed:
        default_version = existing.version
        return {
            "toolbox_name": toolbox_name,
            "action": "unchanged",
            "default_version": default_version,
            "endpoints": mcp_endpoints(endpoint, toolbox_name, default_version),
        }

    new_version = client.toolboxes.create_version(
        toolbox_name,
        tools=tools_for_version,
        description=(
            description
            if description is not None
            else existing.description
            if existing is not None
            else "Contoso Travel Ops toolbox."
        ),
        skills=copy.deepcopy(existing.skills) if existing is not None else None,
        policies=copy.deepcopy(existing.policies) if existing is not None else None,
        metadata=copy.deepcopy(existing.metadata) if existing is not None else None,
    )
    action = "created"
    if existing is not None and publish:
        client.toolboxes.update(toolbox_name, default_version=new_version.version)
        action = "created_and_published"
    elif existing is not None:
        action = "created_unpublished"

    return {
        "toolbox_name": toolbox_name,
        "action": action,
        "default_version": (
            new_version.version if action != "created_unpublished" else existing.version
        ),
        "new_version": new_version.version,
        "endpoints": mcp_endpoints(endpoint, toolbox_name, new_version.version),
    }


def build_toolbox_connection_payload(
    *,
    connection_name: str,
    toolbox_endpoint: str,
) -> dict[str, Any]:
    """Build the keyless RemoteTool connection used by Prompt Agents."""
    return {
        "name": connection_name,
        "type": "Microsoft.MachineLearningServices/workspaces/connections",
        "properties": {
            "authType": "ProjectManagedIdentity",
            "category": "RemoteTool",
            "target": toolbox_endpoint,
            "isSharedToAll": True,
            "audience": "https://ai.azure.com/",
            "metadata": {
                "ApiType": "Azure",
                "type": "custom_MCP",
            },
        },
    }


def ensure_toolbox_connection(
    *,
    credential: Any,
    project_resource_id: str,
    connection_name: str,
    toolbox_endpoint: str,
) -> dict[str, Any]:
    """Create or update the project-managed Toolbox MCP connection."""
    token = credential.get_token(f"{ARM_ENDPOINT}/.default").token
    response = httpx.put(
        (
            f"{ARM_ENDPOINT}{project_resource_id}/connections/{connection_name}"
            f"?api-version={PROJECT_CONNECTION_API_VERSION}"
        ),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=build_toolbox_connection_payload(
            connection_name=connection_name,
            toolbox_endpoint=toolbox_endpoint,
        ),
        timeout=CONNECTION_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def attach_toolbox_to_agent(
    client: AIProjectClient,
    *,
    agent_name: str,
    connection_name: str,
    toolbox_endpoint: str,
    server_label: str = DEFAULT_TOOLBOX_SERVER_LABEL,
) -> dict[str, str]:
    """Attach the Toolbox MCP endpoint while preserving existing agent tools."""
    agent = client.agents.get(agent_name)
    latest = agent.versions.latest
    definition = copy.deepcopy(latest.definition)
    if not isinstance(definition, PromptAgentDefinition):
        raise WorkshopContextError(
            f"agent '{agent_name}' is not a Prompt Agent and cannot be updated by this notebook"
        )

    existing_tools = list(definition.tools or [])
    if any(
        isinstance(tool, MCPTool) and tool.server_url == toolbox_endpoint for tool in existing_tools
    ):
        return {
            "action": "unchanged",
            "agent_name": agent_name,
            "agent_version": latest.version,
        }

    definition.tools = [
        *existing_tools,
        MCPTool(
            server_label=server_label,
            server_url=toolbox_endpoint,
            project_connection_id=connection_name,
            require_approval="never",
        ),
    ]
    created = client.agents.create_version(
        agent_name=agent_name,
        definition=definition,
    )
    return {
        "action": "attached",
        "agent_name": agent_name,
        "agent_version": created.version,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--context", type=Path, default=DEFAULT_CONTEXT_PATH, help="Path to .workshop/context.json"
    )
    parser.add_argument(
        "--toolbox-name", default=DEFAULT_TOOLBOX_NAME, help="Toolbox name to create/update"
    )
    parser.add_argument(
        "--tool-name", default=DEFAULT_TOOL_NAME, help="Name of the OpenAPI tool inside the toolbox"
    )
    parser.add_argument(
        "--travel-api-url",
        default=None,
        help="Override the Travel Ops API base URL (default: from context.json travel_api_fqdn)",
    )
    parser.add_argument(
        "--openapi-path",
        default=DEFAULT_OPENAPI_PATH,
        help="Path to the OpenAPI document on the API",
    )
    parser.add_argument(
        "--auth-type",
        choices=["anonymous", "managed_identity"],
        default="anonymous",
        help="OpenAPI tool auth type (default: anonymous; API is public/unauthenticated)",
    )
    parser.add_argument(
        "--audience",
        default=None,
        help="Entra ID audience, required when --auth-type managed_identity",
    )
    parser.add_argument("--description", default=None, help="Toolbox version description")
    parser.add_argument(
        "--credential",
        choices=["azure-cli", "default"],
        default="azure-cli",
        help="Credential source (both are az login-only; default: azure-cli)",
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="Create version but do not set it as toolbox default (skip auto-promotion)",
    )
    parser.add_argument(
        "--output", choices=["human", "json"], default="human", help="Output format"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        context = load_context(args.context)
        endpoint = project_endpoint(context)
        base_url = args.travel_api_url or travel_api_base_url(context)
        spec = fetch_openapi_spec(base_url, args.openapi_path)
        auth = build_auth_details(args.auth_type, audience=args.audience)
    except WorkshopContextError as exc:
        print(f"create_toolbox.py: {exc}", file=sys.stderr)
        return 2

    desired_tool = build_openapi_tool(
        tool_name=args.tool_name,
        spec=spec,
        auth=auth,
        description=args.description,
    )

    credential = build_credential(args.credential)
    with AIProjectClient(endpoint=endpoint, credential=credential, allow_preview=True) as client:
        result = ensure_toolbox(
            client,
            endpoint=endpoint,
            toolbox_name=args.toolbox_name,
            desired_tool=desired_tool,
            description=args.description,
            publish=not args.no_publish,
        )

    if args.output == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"toolbox: {result['toolbox_name']}")
        print(f"action:  {result['action']}")
        print(f"default_version: {result['default_version']}")
        print(f"consumer MCP endpoint (default_version):  {result['endpoints']['consumer']}")
        print(f"developer MCP endpoint (this version):    {result['endpoints']['developer']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""scripts/create_toolbox.py

Creates (or updates) the ``contoso-travel-toolbox`` Microsoft Foundry toolbox
used in labs/04-tools-toolbox.md: a v2 toolbox exposing the deployed Travel
Ops API as an OpenAPI tool, on top of the v1 toolbox participants create by
hand in the Toolkit UI.

Why a script and not Terraform: per docs/architecture.md, toolbox versions are
a Foundry data-plane object owned by SDK wrappers, not Terraform -- creating a
version is an explicit, participant-triggered action with its own lifecycle
(new versions on every re-run), not declarative infrastructure.

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
import json
import sys
from pathlib import Path
from typing import Any

# Make the sibling `lib` package importable regardless of current working
# directory (scripts/ is intentionally not an installed Python package).
sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    OpenApiAnonymousAuthDetails,
    OpenApiAuthDetails,
    OpenApiFunctionDefinition,
    OpenApiManagedAuthDetails,
    OpenApiManagedSecurityScheme,
    OpenApiToolboxTool,
    ToolboxTool,
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
OPENAPI_FETCH_TIMEOUT_SECONDS = 15.0


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
        json.dumps(openapi.spec, sort_keys=True),
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


# ---------------------------------------------------------------------------
# I/O adapters
# ---------------------------------------------------------------------------


def fetch_openapi_spec(base_url: str, openapi_path: str) -> dict[str, Any]:
    """Fetch the live OpenAPI 3.1 document from the deployed Travel Ops API.

    Fetched live (never vendored into this repo) so the toolbox always
    reflects the actually-deployed API image, per docs/architecture.md's
    "single source of truth" rule for the Travel Ops API contract.
    """
    url = f"{base_url.rstrip('/')}{openapi_path}"
    try:
        response = httpx.get(url, timeout=OPENAPI_FETCH_TIMEOUT_SECONDS)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise WorkshopContextError(f"could not fetch OpenAPI spec from {url}: {exc}") from exc
    try:
        spec = response.json()
    except json.JSONDecodeError as exc:
        raise WorkshopContextError(f"response from {url} was not valid JSON: {exc}") from exc
    if "openapi" not in spec or "paths" not in spec:
        raise WorkshopContextError(
            f"response from {url} does not look like an OpenAPI document (missing openapi/paths)."
        )
    return spec


def get_existing_default_tools(
    client: AIProjectClient, toolbox_name: str
) -> tuple[str, list[ToolboxTool]] | None:
    """Return (default_version, tools) for an existing toolbox, or ``None`` if
    the toolbox does not exist yet."""
    try:
        toolbox = client.toolboxes.get(toolbox_name)
    except ResourceNotFoundError:
        return None
    version = client.toolboxes.get_version(toolbox_name, toolbox.default_version)
    return toolbox.default_version, list(version.tools)


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
    with AIProjectClient(endpoint=endpoint, credential=credential) as client:
        existing = get_existing_default_tools(client, args.toolbox_name)
        existing_tools = existing[1] if existing is not None else []
        tools_for_version, changed = upsert_openapi_tool(existing_tools, desired_tool)

        if existing is not None and not changed:
            default_version, _ = existing
            result = {
                "toolbox_name": args.toolbox_name,
                "action": "unchanged",
                "default_version": default_version,
                "endpoints": mcp_endpoints(endpoint, args.toolbox_name, default_version),
            }
        else:
            new_version = client.toolboxes.create_version(
                args.toolbox_name,
                tools=tools_for_version,
                description=args.description
                or "Contoso Travel Ops OpenAPI toolbox (v2, SDK-managed).",
            )
            action = "created"
            if existing is not None and not args.no_publish:
                client.toolboxes.update(args.toolbox_name, default_version=new_version.version)
                action = "created_and_published"
            elif existing is not None:
                action = "created_unpublished"
            result = {
                "toolbox_name": args.toolbox_name,
                "action": action,
                "default_version": new_version.version
                if action != "created_unpublished"
                else existing[0],
                "new_version": new_version.version,
                "endpoints": mcp_endpoints(endpoint, args.toolbox_name, new_version.version),
            }

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

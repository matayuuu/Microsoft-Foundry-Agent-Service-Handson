#!/usr/bin/env python3
"""scripts/validate_environment.py

Confirms the deployed workshop environment matches what
``infra/`` + ``scripts/bootstrap_data.py`` were supposed to produce, after
``terraform apply`` and data bootstrap have run. Intended to be the last
step of ``scripts/setup.sh``.

Design: pure dataclasses (``CheckSpec``/``CheckResult``) plus a pure report
formatter are fully unit testable without Azure access. The adapters that
actually call Azure (management-plane ``az`` CLI invocations and data-plane
SDK calls) are isolated in clearly named functions so tests can substitute
fakes for them.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from azure.core.exceptions import AzureError

Status = str  # "pass" | "fail" | "warn"


# ---------------------------------------------------------------------------
# Pure data model + report formatting
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    detail: str

    def __post_init__(self) -> None:
        if self.status not in ("pass", "fail", "warn"):
            raise ValueError(f"invalid status '{self.status}' for check '{self.name}'")


@dataclass(frozen=True)
class CheckSpec:
    """A single validation to run: ``run`` takes no arguments (callers
    close over whatever context they need) and returns a CheckResult."""

    name: str
    run: Callable[[], CheckResult]


@dataclass(frozen=True)
class ValidationReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def overall_status(self) -> Status:
        if any(c.status == "fail" for c in self.checks):
            return "fail"
        if any(c.status == "warn" for c in self.checks):
            return "warn"
        return "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "checks": [
                {"name": c.name, "status": c.status, "detail": c.detail} for c in self.checks
            ],
        }

    def to_markdown(self) -> str:
        lines = [
            "# Environment validation report",
            "",
            f"**Overall status: {self.overall_status}**",
            "",
            "| Check | Status | Detail |",
            "| --- | --- | --- |",
        ]
        for c in self.checks:
            escaped_detail = c.detail.replace("|", "\\|")
            lines.append(f"| {c.name} | {c.status} | {escaped_detail} |")
        return "\n".join(lines) + "\n"


def run_checks(specs: Sequence[CheckSpec]) -> ValidationReport:
    """Runs each CheckSpec in order, always continuing on failure so a
    single broken check does not hide the results of the others.

    Only catches the exception types a check adapter can legitimately raise
    (az CLI/subprocess failures, malformed JSON, missing files, invalid
    inputs, and Azure SDK errors) -- never a bare ``Exception``, so a genuine
    programming bug in a check surfaces as a real crash instead of being
    silently folded into a "failed check" row.
    """
    results: list[CheckResult] = []
    for spec in specs:
        try:
            results.append(spec.run())
        except (RuntimeError, OSError, ValueError, KeyError, AzureError) as exc:
            # still be reported, not raised, so the rest of the report is
            # produced; the exception message is preserved verbatim.
            results.append(
                CheckResult(
                    name=spec.name,
                    status="fail",
                    detail=f"check raised {type(exc).__name__}: {exc}",
                )
            )
    return ValidationReport(checks=results)


# ---------------------------------------------------------------------------
# Pure validators over already-fetched data (no I/O; fully unit testable)
# ---------------------------------------------------------------------------


def validate_terraform_outputs_present(
    outputs: dict[str, Any], required_keys: Sequence[str]
) -> CheckResult:
    missing = [
        key for key in required_keys if key not in outputs or "value" not in outputs.get(key, {})
    ]
    if missing:
        return CheckResult(
            name="terraform-outputs-present",
            status="fail",
            detail=f"missing terraform outputs: {', '.join(missing)}",
        )
    return CheckResult(
        name="terraform-outputs-present",
        status="pass",
        detail=f"all {len(required_keys)} expected terraform outputs are present.",
    )


def validate_role_assignment_present(
    role_assignments: list[dict[str, Any]],
    principal_id: str,
    role_definition_id_suffix: str,
    label: str,
) -> CheckResult:
    """``role_assignments`` is the already-fetched JSON list from
    ``az role assignment list``. Checks that at least one assignment
    matches the given principal and role-definition GUID suffix."""
    for assignment in role_assignments:
        principal = assignment.get("principalId", "")
        role_def_id = assignment.get("roleDefinitionId", "")
        if principal == principal_id and role_def_id.endswith(role_definition_id_suffix):
            return CheckResult(name=label, status="pass", detail="Role assignment found.")
    return CheckResult(
        name=label,
        status="fail",
        detail=f"No role assignment for principal '{principal_id}' with role definition ending "
        f"'{role_definition_id_suffix}' was found.",
    )


def validate_search_index(
    index_fields: list[str],
    expected_fields: Sequence[str],
    label: str,
) -> CheckResult:
    missing = [f for f in expected_fields if f not in index_fields]
    if missing:
        return CheckResult(
            name=label,
            status="fail",
            detail=f"index is missing expected field(s): {', '.join(missing)}",
        )
    return CheckResult(
        name=label, status="pass", detail="All expected fields are present in the index schema."
    )


def validate_search_document_count(document_count: int, minimum: int, label: str) -> CheckResult:
    if document_count < minimum:
        return CheckResult(
            name=label,
            status="fail",
            detail=f"index contains {document_count} document(s); expected at least {minimum}.",
        )
    return CheckResult(
        name=label, status="pass", detail=f"index contains {document_count} document(s)."
    )


def validate_resource_exists(resource_json: Any, label: str) -> CheckResult:
    """``resource_json`` is the already-fetched JSON object from
    ``az resource show --ids <resource_id>`` (``None`` if the CLI returned no
    output, e.g. the resource does not exist)."""
    if not isinstance(resource_json, dict) or "id" not in resource_json:
        return CheckResult(
            name=label,
            status="fail",
            detail="resource was not found (az resource show returned no matching resource).",
        )
    provisioning_state = resource_json.get("properties", {}).get("provisioningState")
    detail = f"resource exists: {resource_json['id']}"
    if provisioning_state:
        detail += f" (provisioningState={provisioning_state})"
    return CheckResult(name=label, status="pass", detail=detail)


def validate_travel_api_health(status_code: int, label: str) -> CheckResult:
    """``status_code`` is the already-fetched HTTP status code from a GET
    against the Travel Ops API's ``/health`` endpoint."""
    if status_code != 200:
        return CheckResult(
            name=label,
            status="fail",
            detail=f"Travel Ops API /health returned HTTP {status_code} (expected 200).",
        )
    return CheckResult(
        name=label, status="pass", detail="Travel Ops API /health returned HTTP 200."
    )


# ---------------------------------------------------------------------------
# Adapters: az CLI + Azure SDK I/O
# ---------------------------------------------------------------------------


def az_cli_json(args: Sequence[str]) -> Any:
    """Runs an `az ... -o json` command and returns the parsed JSON, or
    raises BootstrapError-style RuntimeError with the captured stderr on
    failure. Never swallows a failure silently."""
    completed = subprocess.run(
        ["az", *args, "-o", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"'az {' '.join(args)}' failed: {completed.stderr.strip()}")
    if not completed.stdout.strip():
        return None
    return json.loads(completed.stdout)


def fetch_role_assignments(resource_id: str) -> list[dict[str, Any]]:
    result = az_cli_json(
        ["role", "assignment", "list", "--scope", resource_id, "--include-inherited"]
    )
    return result if isinstance(result, list) else []


def fetch_search_index_fields(search_endpoint: str, index_name: str, credential: Any) -> list[str]:
    from azure.search.documents.indexes import SearchIndexClient

    client = SearchIndexClient(endpoint=search_endpoint, credential=credential)
    index = client.get_index(index_name)
    return [f.name for f in index.fields]


def fetch_search_document_count(search_endpoint: str, index_name: str, credential: Any) -> int:
    from azure.search.documents import SearchClient

    client = SearchClient(endpoint=search_endpoint, index_name=index_name, credential=credential)
    return client.get_document_count()


def build_credential() -> Any:
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


def fetch_resource_by_id(resource_id: str) -> Any:
    """Resource-type-agnostic ARM existence lookup via
    ``az resource show --ids <resource_id>``, reusing the same
    ``az_cli_json`` adapter used by ``fetch_role_assignments``. Works for the
    AI Services account, Search service, and Container App alike, so no
    per-resource-type ``az`` subcommands are needed."""
    return az_cli_json(["resource", "show", "--ids", resource_id])


def fetch_travel_api_health(fqdn: str, timeout: float = 10.0) -> int:
    """GETs ``https://<fqdn>/health`` and returns the HTTP status code.

    A non-2xx response is a meaningful "check failed with this status"
    signal, so ``urllib.error.HTTPError`` is caught here to extract
    ``.code``. Every other failure mode (DNS failure, connection refused,
    timeout, TLS error) is a genuine infrastructure/network fault, so
    ``urllib.error.URLError`` (an ``OSError`` subclass) and other ``OSError``
    subclasses are left to propagate into ``run_checks``'s own exception
    handling rather than being swallowed here."""
    request = urllib.request.Request(f"https://{fqdn}/health", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.getcode())
    except urllib.error.HTTPError as exc:
        return int(exc.code)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

REQUIRED_TERRAFORM_OUTPUTS = (
    "resource_group_name",
    "location",
    "ai_services_account_name",
    "ai_services_endpoint",
    "openai_endpoint",
    "foundry_project_name",
    "foundry_project_id",
    "foundry_project_endpoint",
    "primary_model_deployment_name",
    "optimizer_model_deployment_name",
    "embedding_model_deployment_name",
    "search_service_name",
    "search_service_endpoint",
    "travel_api_fqdn",
    "travel_api_container_app_name",
)

EXPECTED_INDEX_FIELDS = (
    "id",
    "manifest_id",
    "title",
    "content",
    "citation",
    "category",
    "source_path",
    "source_url",
    "blob_url",
    "chunk_index",
    "heading",
    "token_count",
    "content_vector",
)

# Role-definition GUID suffixes must match infra/locals.tf local.role_ids.
FOUNDRY_USER_ROLE_ID = "53ca6127-db72-4b80-b1b0-d745d6d5456d"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument(
        "--terraform-outputs",
        required=True,
        type=Path,
        help="Path to a file containing `terraform output -json` output (a process substitution "
        "or plain file both work).",
    )
    parser.add_argument("--index-name", default="contoso-travel-policy")
    parser.add_argument(
        "--min-documents",
        type=int,
        default=1,
        help="Minimum number of documents the search index must contain to pass.",
    )
    parser.add_argument(
        "--skip-search-checks",
        action="store_true",
        help="Skip Azure AI Search index/document checks (useful before bootstrap_data.py has "
        "run).",
    )
    parser.add_argument("--format", choices=["json", "markdown"], default="markdown")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        outputs_raw = args.terraform_outputs.read_text(encoding="utf-8")
        outputs = json.loads(outputs_raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"validate_environment.py: could not read terraform outputs from "
            f"{args.terraform_outputs}: {exc}",
            file=sys.stderr,
        )
        return 2

    specs: list[CheckSpec] = [
        CheckSpec(
            name="terraform-outputs-present",
            run=lambda: validate_terraform_outputs_present(outputs, REQUIRED_TERRAFORM_OUTPUTS),
        )
    ]

    ai_services_account_name = outputs.get("ai_services_account_name", {}).get("value")
    search_service_endpoint = outputs.get("search_service_endpoint", {}).get("value")
    search_service_name = outputs.get("search_service_name", {}).get("value")
    travel_api_container_app_name = outputs.get("travel_api_container_app_name", {}).get("value")
    travel_api_fqdn = outputs.get("travel_api_fqdn", {}).get("value")

    if ai_services_account_name:
        ai_services_resource_id = (
            f"/subscriptions/{args.subscription}/resourceGroups/{args.resource_group}"
            f"/providers/Microsoft.CognitiveServices/accounts/{ai_services_account_name}"
        )
        specs.append(
            CheckSpec(
                name="rbac-foundry-user-present",
                run=lambda: validate_role_assignment_present(
                    fetch_role_assignments(ai_services_resource_id),
                    principal_id=_signed_in_principal_id(),
                    role_definition_id_suffix=FOUNDRY_USER_ROLE_ID,
                    label="rbac-foundry-user-present",
                ),
            )
        )
        specs.append(
            CheckSpec(
                name="arm-ai-services-account-exists",
                run=lambda: validate_resource_exists(
                    fetch_resource_by_id(ai_services_resource_id),
                    "arm-ai-services-account-exists",
                ),
            )
        )

    if search_service_name:
        search_service_resource_id = (
            f"/subscriptions/{args.subscription}/resourceGroups/{args.resource_group}"
            f"/providers/Microsoft.Search/searchServices/{search_service_name}"
        )
        specs.append(
            CheckSpec(
                name="arm-search-service-exists",
                run=lambda: validate_resource_exists(
                    fetch_resource_by_id(search_service_resource_id),
                    "arm-search-service-exists",
                ),
            )
        )

    if travel_api_container_app_name:
        container_app_resource_id = (
            f"/subscriptions/{args.subscription}/resourceGroups/{args.resource_group}"
            f"/providers/Microsoft.App/containerApps/{travel_api_container_app_name}"
        )
        specs.append(
            CheckSpec(
                name="arm-travel-api-container-app-exists",
                run=lambda: validate_resource_exists(
                    fetch_resource_by_id(container_app_resource_id),
                    "arm-travel-api-container-app-exists",
                ),
            )
        )

    if travel_api_fqdn:
        specs.append(
            CheckSpec(
                name="travel-api-health",
                run=lambda: validate_travel_api_health(
                    fetch_travel_api_health(travel_api_fqdn),
                    "travel-api-health",
                ),
            )
        )

    if not args.skip_search_checks and search_service_endpoint:
        credential = build_credential()

        def _index_fields_check() -> CheckResult:
            fields = fetch_search_index_fields(search_service_endpoint, args.index_name, credential)
            return validate_search_index(fields, EXPECTED_INDEX_FIELDS, "search-index-schema")

        def _document_count_check() -> CheckResult:
            count = fetch_search_document_count(
                search_service_endpoint, args.index_name, credential
            )
            return validate_search_document_count(
                count, args.min_documents, "search-index-document-count"
            )

        specs.append(CheckSpec(name="search-index-schema", run=_index_fields_check))
        specs.append(CheckSpec(name="search-index-document-count", run=_document_count_check))

    report = run_checks(specs)

    rendered = (
        json.dumps(report.to_dict(), indent=2) if args.format == "json" else report.to_markdown()
    )

    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        print(f"validate_environment.py: report written to {args.output}", file=sys.stderr)
    else:
        print(rendered)

    return 0 if report.overall_status != "fail" else 2


_signed_in_principal_id_cache: str | None = None


def _signed_in_principal_id() -> str:
    """Lazily resolves and caches the signed-in identity's Entra object ID
    via the az CLI (falls back to raising if it cannot be resolved -- callers
    must not silently treat an unresolved identity as a passing check)."""
    global _signed_in_principal_id_cache
    if _signed_in_principal_id_cache is not None:
        return _signed_in_principal_id_cache
    result = az_cli_json(["ad", "signed-in-user", "show"])
    if not isinstance(result, dict) or "id" not in result:
        raise RuntimeError(
            "could not resolve the signed-in identity's object id via 'az ad signed-in-user show'"
        )
    _signed_in_principal_id_cache = str(result["id"])
    return _signed_in_principal_id_cache


if __name__ == "__main__":
    raise SystemExit(main())

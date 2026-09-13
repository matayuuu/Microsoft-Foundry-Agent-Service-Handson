#!/usr/bin/env python3
"""Validate the provisioned workshop from canonical non-secret context."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from azure.core.exceptions import AzureError, ServiceRequestError, ServiceResponseError
from azure.identity import AzureCliCredential

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.workshop_context import (
    CUSTOM_TEMPLATE_RESOURCE_OUTPUTS,
    WorkshopContextError,
    participant_object_id,
)

Status = str


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: Status
    detail: str
    retryable: bool = False

    def __post_init__(self) -> None:
        if self.status not in ("pass", "fail", "warn"):
            raise ValueError(f"invalid status '{self.status}' for check '{self.name}'")


@dataclass(frozen=True)
class CheckSpec:
    name: str
    run: Callable[[], CheckResult]


@dataclass(frozen=True)
class ValidationReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def overall_status(self) -> Status:
        if any(check.status == "fail" for check in self.checks):
            return "fail"
        if any(check.status == "warn" for check in self.checks):
            return "warn"
        return "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "checks": [
                {
                    "name": check.name,
                    "status": check.status,
                    "detail": check.detail,
                    "retryable": check.retryable,
                }
                for check in self.checks
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
        for check in self.checks:
            escaped_detail = check.detail.replace("|", "\\|")
            lines.append(f"| {check.name} | {check.status} | {escaped_detail} |")
        return "\n".join(lines) + "\n"


def run_checks(specs: Sequence[CheckSpec]) -> ValidationReport:
    results: list[CheckResult] = []
    for spec in specs:
        try:
            results.append(spec.run())
        except (
            RuntimeError,
            OSError,
            ValueError,
            KeyError,
            AzureError,
            subprocess.TimeoutExpired,
        ) as exc:
            results.append(
                CheckResult(
                    name=spec.name,
                    status="fail",
                    detail=redact_diagnostic(f"check raised {type(exc).__name__}: {exc}"),
                    retryable=is_transient_exception(exc),
                )
            )
    return ValidationReport(checks=results)


REQUIRED_RESOURCE_OUTPUTS = CUSTOM_TEMPLATE_RESOURCE_OUTPUTS
DEFAULT_INDEX_NAMES = ("contoso-travel-policy", "contoso-travel-approval")
EXPECTED_INDEX_FIELDS = (
    "id",
    "manifest_id",
    "title",
    "content",
    "citation",
    "category",
    "source_path",
    "url",
    "source_url",
    "blob_url",
    "chunk_index",
    "heading",
    "token_count",
    "content_vector",
)
FOUNDRY_USER_ROLE_ID = "53ca6127-db72-4b80-b1b0-d745d6d5456d"
TRANSIENT_HTTP_STATUS = frozenset({403, 408, 425, 429, 500, 502, 503, 504})
_PERMANENT_FAILURES = (
    "invalidparameter",
    "invalidrequest",
    "badrequest",
    "insufficientquota",
    "insufficient_quota",
    "quotaexceeded",
    "quota_exceeded",
    "insufficientcapacity",
    "skunotavailable",
    "modelnotsupported",
    "requestdisallowedbypolicy",
    "publicnetworkaccessdisabled",
    "public access is disabled",
    "certificate_verify_failed",
    "certificate verify failed",
)
_TRANSIENT_FAILURES = (
    "authorizationfailed",
    "authorizationpermissionmismatch",
    "forbidden",
    "toomanyrequests",
    "too many requests",
    "ratelimiterror",
    "ratelimitreached",
    "deploymentnotfound",
    "serviceunavailable",
    "gatewaytimeout",
    "internalservererror",
    "connectionerror",
    "connection reset",
    "connection refused",
    "connecttimeout",
    "readtimeout",
    "timeouterror",
    "servicerequesterror",
    "serviceresponseerror",
    "temporary failure in name resolution",
)
_RESOURCE_API_VERSIONS = {
    "microsoft.cognitiveservices/accounts": "2026-05-01",
    "microsoft.search/searchservices": "2025-05-01",
    "microsoft.app/containerapps": "2025-01-01",
    "microsoft.machinelearningservices/workspaces": "2025-06-01",
}


def redact_diagnostic(detail: str) -> str:
    """Keep stage/service diagnostics without echoing auth headers or signed URLs."""
    detail = re.sub(r"(https?://)[^/\s:@]+:[^@\s/]+@", r"\1[redacted]@", detail)
    detail = re.sub(r"(https?://[^\s?'\"<>]+)\?[^\s'\"<>]*", r"\1?[redacted]", detail)
    detail = re.sub(r"(?i)\bBearer\s+[^\s'\"<>]+", "Bearer [redacted]", detail)
    detail = re.sub(
        r"""(?i)(["']?(?:access[_-]?token|refresh[_-]?token|client[_-]?secret|password|"""
        r"""account[_-]?key|api[_-]?key|sig)["']?\s*[:=]\s*["']?)[^\s"',}]+""",
        r"\1[redacted]",
        detail,
    )
    return re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "[redacted]", detail)


def is_transient_failure(detail: str) -> bool:
    """Classify known readiness failures; unrecognized and hard errors fail closed."""
    normalized = detail.casefold()
    if any(code in normalized for code in _PERMANENT_FAILURES):
        return False
    statuses = {
        int(value)
        for value in re.findall(
            r"(?i)(?:\bHTTP(?:/\d(?:\.\d)?)?\s*|\bstatus(?:[ _]code)?\s*[:=]?\s*|"
            r"\berror code\s*:\s*)(\d{3})\b",
            detail,
        )
    }
    allowed_statuses = TRANSIENT_HTTP_STATUS | (
        {404} if "deploymentnotfound" in normalized else set()
    )
    if statuses and not statuses <= allowed_statuses:
        return False
    return bool(statuses) or any(code in normalized for code in _TRANSIENT_FAILURES)


def is_transient_exception(exc: Exception) -> bool:
    if isinstance(exc, ssl.SSLCertVerificationError):
        return False
    detail = str(exc)
    if any(code in detail.casefold() for code in _PERMANENT_FAILURES):
        return False
    status_code = (
        exc.code if isinstance(exc, urllib.error.HTTPError) else getattr(exc, "status_code", None)
    )
    if status_code is not None:
        return status_code in TRANSIENT_HTTP_STATUS | {404}
    if isinstance(
        exc,
        (
            TimeoutError,
            ConnectionError,
            ServiceRequestError,
            ServiceResponseError,
            subprocess.TimeoutExpired,
        ),
    ):
        return True
    if isinstance(exc, urllib.error.URLError):
        return not isinstance(exc.reason, ssl.SSLCertVerificationError)
    return is_transient_failure(detail)


def validate_context_metadata(context: dict[str, Any]) -> CheckResult:
    required = (
        "subscription_id",
        "resource_group_name",
        "location",
        "participant_object_id",
        "resource_outputs",
    )
    missing = [key for key in required if not context.get(key)]
    if missing:
        return CheckResult(
            "context-metadata",
            "fail",
            f"context is missing required field(s): {', '.join(missing)}",
        )
    if context.get("setup_status") not in ("infrastructure-ready", "complete"):
        return CheckResult("context-metadata", "fail", "context setup_status is not ready.")
    if (
        context.get("schema_version") != "2.0"
        or context.get("provisioning_method") != "azure-custom-template"
    ):
        return CheckResult(
            "context-metadata",
            "fail",
            "context must describe the Azure custom-template deployment.",
        )
    try:
        participant_object_id(context)
    except WorkshopContextError as exc:
        return CheckResult("context-metadata", "fail", str(exc))
    return CheckResult("context-metadata", "pass", "Canonical provisioning context is ready.")


def validate_resource_outputs_present(
    outputs: dict[str, Any], required_keys: Sequence[str]
) -> CheckResult:
    missing = [
        key
        for key in required_keys
        if not isinstance(outputs.get(key), dict) or outputs[key].get("value") in (None, "")
    ]
    if missing:
        return CheckResult(
            "resource-outputs-present",
            "fail",
            f"missing resource outputs: {', '.join(missing)}",
        )
    return CheckResult(
        "resource-outputs-present",
        "pass",
        f"all {len(required_keys)} expected resource outputs are present.",
    )


def validate_role_assignment_present(
    assignments: list[dict[str, Any]],
    principal_id: str,
    role_definition_id_suffix: str,
    label: str,
) -> CheckResult:
    if any(
        str(assignment.get("principalId", "")).casefold() == principal_id.casefold()
        and str(assignment.get("roleDefinitionId", "")).rsplit("/", 1)[-1].casefold()
        == role_definition_id_suffix.casefold()
        for assignment in assignments
    ):
        return CheckResult(label, "pass", "Role assignment found.")
    return CheckResult(
        label, "fail", "Required participant role assignment was not found.", retryable=True
    )


def validate_search_index(
    index_fields: list[str], expected_fields: Sequence[str], label: str
) -> CheckResult:
    missing = [field for field in expected_fields if field not in index_fields]
    if missing:
        return CheckResult(label, "fail", f"missing index fields: {', '.join(missing)}")
    return CheckResult(label, "pass", "Expected index schema is present.")


def validate_search_document_count(count: int, minimum: int, label: str) -> CheckResult:
    if count < minimum:
        return CheckResult(
            label, "fail", f"index contains {count} documents; expected {minimum}.", retryable=True
        )
    return CheckResult(label, "pass", f"index contains {count} document(s).")


def validate_resource_exists(resource_json: Any, label: str) -> CheckResult:
    if not isinstance(resource_json, dict) or not resource_json.get("id"):
        return CheckResult(label, "fail", "resource was not found.", retryable=True)
    state = resource_json.get("properties", {}).get("provisioningState")
    if state and str(state).casefold() not in {"succeeded", "ready"}:
        return CheckResult(
            label,
            "fail",
            f"resource provisioning state is {state}.",
            retryable=str(state).casefold() in {"accepted", "creating", "updating", "running"},
        )
    return CheckResult(label, "pass", f"resource exists: {resource_json['id']}")


def validate_travel_api_health(status_code: int, label: str) -> CheckResult:
    if status_code != 200:
        return CheckResult(
            label,
            "fail",
            f"Travel Ops API returned HTTP {status_code}.",
            retryable=status_code in TRANSIENT_HTTP_STATUS - {403},
        )
    return CheckResult(label, "pass", "Travel Ops API /health returned HTTP 200.")


def az_cli_json(args: Sequence[str]) -> Any:
    executable = shutil.which("az") or "az"
    completed = subprocess.run(
        [executable, *args, "--only-show-errors", "-o", "json"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=90,
    )
    if completed.returncode:
        raise RuntimeError(
            redact_diagnostic(f"'az {' '.join(args)}' failed: {completed.stderr.strip()}")
        )
    return json.loads(completed.stdout) if completed.stdout.strip() else None


def fetch_role_assignments(resource_id: str) -> list[dict[str, Any]]:
    result = az_cli_json(
        [
            "role",
            "assignment",
            "list",
            "--scope",
            resource_id,
            "--include-inherited",
            "--fill-principal-name",
            "false",
            "--fill-role-definition-name",
            "false",
        ]
    )
    return result if isinstance(result, list) else []


def fetch_resource_by_id(resource_id: str) -> Any:
    resource_type = "/".join(resource_id.casefold().split("/providers/")[-1].split("/")[:2])
    api_version = _RESOURCE_API_VERSIONS[resource_type]
    return az_cli_json(["resource", "show", "--ids", resource_id, "--api-version", api_version])


def fetch_search_index_fields(search_endpoint: str, index_name: str, credential: Any) -> list[str]:
    from azure.search.documents.indexes import SearchIndexClient

    index = SearchIndexClient(search_endpoint, credential).get_index(index_name)
    return [field.name for field in index.fields]


def fetch_search_document_count(search_endpoint: str, index_name: str, credential: Any) -> int:
    from azure.search.documents import SearchClient

    return SearchClient(search_endpoint, index_name, credential).get_document_count()


def fetch_travel_api_health(fqdn: str, timeout: float = 10.0) -> int:
    request = urllib.request.Request(f"https://{fqdn}/health", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.getcode())
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def build_credential() -> AzureCliCredential:
    return AzureCliCredential()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, required=True)
    parser.add_argument(
        "--participant-object-id",
        help="Participant Entra object ID (overrides context; never inferred from login).",
    )
    parser.add_argument("--index-name", dest="index_names", action="append")
    parser.add_argument("--min-documents", type=int, default=1)
    parser.add_argument(
        "--index-min-documents",
        action="append",
        default=[],
        metavar="NAME=COUNT",
        help="Per-index minimum, normally the manifest partition's source document count.",
    )
    parser.add_argument("--skip-search-checks", action="store_true")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.min_documents < 1:
        parser.error("--min-documents must be at least 1")
    minimums: dict[str, int] = {}
    for specification in args.index_min_documents:
        name, separator, value = specification.partition("=")
        if (
            not separator
            or not value.isascii()
            or not value.isdecimal()
            or int(value) < 1
            or name not in (args.index_names or DEFAULT_INDEX_NAMES)
            or name in minimums
        ):
            parser.error("--index-min-documents must specify a selected index once as NAME=COUNT")
        minimums[name] = int(value)
    args.index_min_documents = minimums
    return args


def _output_value(outputs: dict[str, Any], name: str) -> str:
    entry = outputs.get(name)
    return str(entry.get("value", "")) if isinstance(entry, dict) else ""


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        context = json.loads(args.context.read_text(encoding="utf-8"))
        if not isinstance(context, dict):
            raise ValueError("context root must be an object")
        participant_id = participant_object_id(context, args.participant_object_id)
        context = {**context, "participant_object_id": participant_id}
    except (OSError, ValueError, WorkshopContextError) as exc:
        print(f"validate_environment.py: could not read {args.context}: {exc}", file=sys.stderr)
        return 2

    outputs = context.get("resource_outputs")
    outputs = outputs if isinstance(outputs, dict) else {}
    subscription = str(context.get("subscription_id", ""))
    resource_group = str(context.get("resource_group_name", ""))
    rg_id = f"/subscriptions/{subscription}/resourceGroups/{resource_group}"

    specs = [
        CheckSpec("context-metadata", lambda: validate_context_metadata(context)),
        CheckSpec(
            "resource-outputs-present",
            lambda: validate_resource_outputs_present(outputs, REQUIRED_RESOURCE_OUTPUTS),
        ),
    ]
    initial_report = run_checks(specs)
    if initial_report.overall_status == "fail":
        return write_report(initial_report, args)

    account_name = _output_value(outputs, "ai_services_account_name")
    search_name = _output_value(outputs, "search_service_name")
    container_name = _output_value(outputs, "travel_api_container_app_name")
    travel_fqdn = _output_value(outputs, "travel_api_fqdn")

    resources = {
        "arm-foundry-account-exists": (
            f"{rg_id}/providers/Microsoft.CognitiveServices/accounts/{account_name}"
            if account_name
            else ""
        ),
        "arm-search-service-exists": (
            f"{rg_id}/providers/Microsoft.Search/searchServices/{search_name}"
            if search_name
            else ""
        ),
        "arm-travel-api-container-app-exists": (
            f"{rg_id}/providers/Microsoft.App/containerApps/{container_name}"
            if container_name
            else ""
        ),
    }
    for label, resource_id in resources.items():
        if resource_id:
            specs.append(
                CheckSpec(
                    label,
                    lambda selected_id=resource_id, selected_label=label: validate_resource_exists(
                        fetch_resource_by_id(selected_id), selected_label
                    ),
                )
            )

    if account_name:
        account_id = resources["arm-foundry-account-exists"]
        specs.append(
            CheckSpec(
                "rbac-foundry-user-present",
                lambda: validate_role_assignment_present(
                    fetch_role_assignments(account_id),
                    participant_id,
                    FOUNDRY_USER_ROLE_ID,
                    "rbac-foundry-user-present",
                ),
            )
        )
    if travel_fqdn:
        specs.append(
            CheckSpec(
                "travel-api-health",
                lambda: validate_travel_api_health(
                    fetch_travel_api_health(travel_fqdn), "travel-api-health"
                ),
            )
        )

    credential = None
    search_endpoint = _output_value(outputs, "search_service_endpoint")
    if not args.skip_search_checks and search_endpoint:
        credential = build_credential()
        for index_name in args.index_names or list(DEFAULT_INDEX_NAMES):
            schema_label = f"search-index-schema:{index_name}"
            count_label = f"search-index-document-count:{index_name}"
            specs.extend(
                [
                    CheckSpec(
                        schema_label,
                        lambda name=index_name, label=schema_label: validate_search_index(
                            fetch_search_index_fields(search_endpoint, name, credential),
                            EXPECTED_INDEX_FIELDS,
                            label,
                        ),
                    ),
                    CheckSpec(
                        count_label,
                        lambda name=index_name, label=count_label: validate_search_document_count(
                            fetch_search_document_count(search_endpoint, name, credential),
                            args.index_min_documents.get(name, args.min_documents),
                            label,
                        ),
                    ),
                ]
            )

    try:
        report = run_checks(specs)
    finally:
        if credential is not None:
            credential.close()

    return write_report(report, args)


def write_report(report: ValidationReport, args: argparse.Namespace) -> int:
    rendered = (
        json.dumps(report.to_dict(), indent=2) if args.format == "json" else report.to_markdown()
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered)
    return 0 if report.overall_status != "fail" else 2


if __name__ == "__main__":
    raise SystemExit(main())

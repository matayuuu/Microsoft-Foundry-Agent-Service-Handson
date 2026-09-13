"""Network-free tests for canonical post-provisioning validation."""

from __future__ import annotations

import json
import subprocess
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import validate_environment as validation

PARTICIPANT_ID = "11111111-2222-4333-8444-555555555555"
MANAGED_IDENTITY_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def _context() -> dict[str, object]:
    values = {key: f"fixture-{key}" for key in validation.REQUIRED_RESOURCE_OUTPUTS}
    values.update(
        {
            "ai_services_account_name": "aif-fixture",
            "search_service_name": "srch-fixture",
            "search_service_endpoint": "https://search.example.invalid",
            "travel_api_container_app_name": "ca-fixture",
            "travel_api_fqdn": "travel.example.invalid",
        }
    )
    return {
        "schema_version": "2.0",
        "provisioning_method": "azure-custom-template",
        "subscription_id": "00000000-0000-0000-0000-000000000000",
        "resource_group_name": "rg-fixture",
        "location": "japaneast",
        "setup_status": "infrastructure-ready",
        "participant_object_id": PARTICIPANT_ID,
        "resource_outputs": {key: {"value": value} for key, value in values.items()},
    }


def test_context_and_resource_outputs_are_canonical() -> None:
    context = _context()

    assert validation.validate_context_metadata(context).status == "pass"
    assert (
        validation.validate_resource_outputs_present(
            context["resource_outputs"],  # type: ignore[arg-type]
            validation.REQUIRED_RESOURCE_OUTPUTS,
        ).status
        == "pass"
    )


def test_missing_resource_output_fails_with_name() -> None:
    result = validation.validate_resource_outputs_present({}, ("foundry_project_id",))

    assert result.status == "fail"
    assert "foundry_project_id" in result.detail


def test_build_credential_is_explicit_azure_cli() -> None:
    from azure.identity import AzureCliCredential

    assert isinstance(validation.build_credential(), AzureCliCredential)


def test_main_validates_core_api_and_both_search_indexes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(_context()), encoding="utf-8")
    credential = SimpleNamespace(close=lambda: None)
    index_calls: list[str] = []
    resource_calls: list[str] = []

    monkeypatch.setattr(validation, "build_credential", lambda: credential)

    def resource(resource_id: str) -> dict[str, object]:
        resource_calls.append(resource_id)
        return {"id": resource_id, "properties": {"provisioningState": "Succeeded"}}

    monkeypatch.setattr(validation, "fetch_resource_by_id", resource)
    monkeypatch.setattr(
        validation,
        "fetch_role_assignments",
        lambda _: [
            {
                "principalId": PARTICIPANT_ID,
                "roleDefinitionId": f"/roles/{validation.FOUNDRY_USER_ROLE_ID}",
            }
        ],
    )
    monkeypatch.setattr(validation, "fetch_travel_api_health", lambda _: 200)

    def fields(_: str, index_name: str, __: object) -> list[str]:
        index_calls.append(index_name)
        return list(validation.EXPECTED_INDEX_FIELDS)

    monkeypatch.setattr(validation, "fetch_search_index_fields", fields)
    monkeypatch.setattr(
        validation,
        "fetch_search_document_count",
        lambda _, name, __: 9 if name == "contoso-travel-policy" else 1,
    )
    report_path = tmp_path / "report.json"

    result = validation.main(
        [
            "--context",
            str(context_path),
            "--format",
            "json",
            "--output",
            str(report_path),
            "--index-min-documents",
            "contoso-travel-policy=9",
            "--index-min-documents",
            "contoso-travel-approval=1",
        ]
    )

    assert result == 0
    assert index_calls == list(validation.DEFAULT_INDEX_NAMES)
    assert len(resource_calls) == 3
    assert all("MachineLearningServices" not in item for item in resource_calls)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    names = {check["name"] for check in report["checks"]}
    assert {
        "arm-foundry-account-exists",
        "arm-search-service-exists",
        "arm-travel-api-container-app-exists",
        "search-index-schema:contoso-travel-policy",
        "search-index-schema:contoso-travel-approval",
    } <= names
    assert "luna-inference" not in names

    monkeypatch.setattr(validation, "fetch_search_document_count", lambda *_: 1)
    assert (
        validation.main(
            [
                "--context",
                str(context_path),
                "--format",
                "json",
                "--output",
                str(report_path),
                "--index-min-documents",
                "contoso-travel-policy=9",
            ]
        )
        == 2
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    failed = [check for check in report["checks"] if check["status"] == "fail"]
    assert [check["name"] for check in failed] == [
        "search-index-document-count:contoso-travel-policy"
    ]
    assert failed[0]["retryable"] is True


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "user@example.invalid",
        MANAGED_IDENTITY_ID[:12],
        "00000000-0000-0000-0000-000000000000",
    ],
)
def test_missing_or_invalid_participant_fails_before_cloud_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    value: object,
) -> None:
    context = _context()
    context["participant_object_id"] = value
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(context), encoding="utf-8")

    def unexpected(*_: object) -> None:
        pytest.fail("invalid identity must fail without any Azure/Graph call")

    monkeypatch.setattr(validation, "az_cli_json", unexpected)
    monkeypatch.setattr(validation, "build_credential", unexpected)
    assert validation.main(["--context", str(context_path)]) == 2
    assert "participant_object_id" in capsys.readouterr().err


@pytest.mark.parametrize("use_override", [False, True])
def test_participant_and_managed_identity_are_not_interchangeable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    use_override: bool,
) -> None:
    context = _context()
    if use_override:
        context["participant_object_id"] = MANAGED_IDENTITY_ID
    context_path = tmp_path / "context.json"
    context_path.write_text(json.dumps(context), encoding="utf-8")
    monkeypatch.setattr(
        validation,
        "fetch_resource_by_id",
        lambda resource_id: {"id": resource_id, "properties": {"provisioningState": "Succeeded"}},
    )
    monkeypatch.setattr(validation, "fetch_travel_api_health", lambda _: 200)
    monkeypatch.setattr(
        validation,
        "fetch_role_assignments",
        lambda _: [
            {
                "principalId": MANAGED_IDENTITY_ID,
                "roleDefinitionId": f"/roles/{validation.FOUNDRY_USER_ROLE_ID}",
            }
        ],
    )
    arguments = ["--context", str(context_path), "--skip-search-checks"]
    if use_override:
        arguments += ["--participant-object-id", PARTICIPANT_ID]
    assert validation.main(arguments) == 2
    monkeypatch.setattr(
        validation,
        "fetch_role_assignments",
        lambda _: [
            {
                "principalId": PARTICIPANT_ID.upper(),
                "roleDefinitionId": f"/roles/{validation.FOUNDRY_USER_ROLE_ID.upper()}",
            }
        ],
    )
    assert validation.main(arguments) == 0


def test_role_assignment_reads_disable_graph_name_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def query(arguments: list[str]) -> list[object]:
        calls.append(arguments)
        return []

    monkeypatch.setattr(validation, "az_cli_json", query)
    scope = (
        "/subscriptions/sub/resourceGroups/group/providers/Microsoft.Search/searchServices/search"
    )
    assert validation.fetch_role_assignments(scope) == []
    assert calls == [
        [
            "role",
            "assignment",
            "list",
            "--scope",
            scope,
            "--include-inherited",
            "--fill-principal-name",
            "false",
            "--fill-role-definition-name",
            "false",
        ]
    ]
    assert not hasattr(validation, "_signed_in_principal_id")
    assert not hasattr(validation, "_signed_in_principal_id_cache")


def test_resource_reads_do_not_require_provider_catalog_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(validation, "az_cli_json", lambda command: calls.append(command))
    resource_id = (
        "/subscriptions/sub/resourceGroups/group/providers/"
        "Microsoft.CognitiveServices/accounts/account"
    )
    validation.fetch_resource_by_id(resource_id)
    assert calls == [
        [
            "resource",
            "show",
            "--ids",
            resource_id,
            "--api-version",
            "2026-05-01",
        ]
    ]


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("HTTP 503 Service unavailable", True),
        ("Error code: 429 - TooManyRequests", True),
        ("(AuthorizationFailed) role assignment propagation", True),
        ("HTTP 403 PublicNetworkAccessDisabled", False),
        ("HTTP 403 RequestDisallowedByPolicy", False),
        ("HTTP 429 InsufficientQuota", False),
        ("Error code: 429 - {'code': 'insufficient_quota'}", False),
        ("Error code: 404 (DeploymentNotFound)", True),
        ("HTTP 400 InvalidParameter", False),
        ("HTTP 404 unknown API route", False),
        ("HTTP 401 invalid credentials", False),
        ("unknown service failure", False),
    ],
)
def test_readiness_classification_is_bounded_to_transient_cases(
    message: str,
    expected: bool,
) -> None:
    assert validation.is_transient_failure(message) is expected


def test_check_report_marks_only_retryable_failures() -> None:
    def timeout() -> validation.CheckResult:
        raise subprocess.TimeoutExpired(["az", "resource", "show"], 90)

    report = validation.run_checks(
        [
            validation.CheckSpec("resource-timeout", timeout),
            validation.CheckSpec(
                "bad-schema",
                lambda: validation.validate_search_index([], ["content"], "bad-schema"),
            ),
        ]
    )
    assert report.overall_status == "fail"
    assert report.to_dict()["checks"][0]["retryable"] is True
    assert report.to_dict()["checks"][1]["retryable"] is False


def test_hard_provisioning_or_health_failure_is_not_readiness() -> None:
    assert not validation.validate_resource_exists(
        {"id": "id", "properties": {"provisioningState": "Failed"}}, "resource"
    ).retryable
    assert validation.validate_resource_exists(
        {"id": "id", "properties": {"provisioningState": "Creating"}}, "resource"
    ).retryable
    assert validation.validate_travel_api_health(503, "health").retryable
    assert not validation.validate_travel_api_health(400, "health").retryable


def test_diagnostics_never_echo_auth_headers_or_raw_sas() -> None:
    secret = "synthetic-test-secret"
    rendered = validation.redact_diagnostic(
        f"Bearer {secret} https://example.invalid/file?sv=1&sig={secret} "
        f'{{"accessToken": "{secret}", "client_secret": "{secret}"}}'
    )
    assert secret not in rendered
    assert "?sv=" not in rendered


@pytest.mark.parametrize("status", [400, 401])
def test_hard_http_exception_is_not_misclassified_as_network_readiness(status: int) -> None:
    error = urllib.error.HTTPError("https://example.invalid", status, "hard error", {}, None)
    assert not validation.is_transient_exception(error)


def test_per_index_minimums_keep_existing_default_and_validate_explicit_values() -> None:
    defaults = validation.parse_args(["--context", "context.json"])
    assert defaults.min_documents == 1
    assert defaults.index_min_documents == {}
    args = validation.parse_args(
        [
            "--context",
            "context.json",
            "--index-min-documents",
            "contoso-travel-policy=9",
            "--index-min-documents",
            "contoso-travel-approval=1",
        ]
    )
    assert args.index_min_documents == {"contoso-travel-policy": 9, "contoso-travel-approval": 1}


@pytest.mark.parametrize(
    "value", ["contoso-travel-policy=0", "other=1", "contoso-travel-policy=bad"]
)
def test_invalid_document_count_override_is_a_permanent_argument_error(value: str) -> None:
    with pytest.raises(SystemExit) as error:
        validation.parse_args(["--context", "context.json", "--index-min-documents", value])
    assert error.value.code == 2

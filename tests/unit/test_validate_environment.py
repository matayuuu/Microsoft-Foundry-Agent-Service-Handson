"""Unit tests for scripts/validate_environment.py.

scripts/ is intentionally not a Python package, so the module under test is
loaded directly from its file path via importlib. Azure/CLI/network adapters
(``fetch_role_assignments``, ``fetch_search_index_fields``,
``fetch_search_document_count``, ``fetch_resource_by_id``,
``fetch_travel_api_health``, ``_signed_in_principal_id``) are monkeypatched
or exercised only through pure-function seams; no real Azure credentials,
network access, or ``az`` CLI invocation happens in this file.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from azure.core.exceptions import AzureError

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "validate_environment.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_environment", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validate_environment = _load_module()


VALID_OUTPUTS = {
    key: {"value": f"fake-{key}"} for key in validate_environment.REQUIRED_TERRAFORM_OUTPUTS
}


# ---------------------------------------------------------------------------
# CheckResult / ValidationReport
# ---------------------------------------------------------------------------


def test_check_result_rejects_invalid_status() -> None:
    with pytest.raises(ValueError):
        validate_environment.CheckResult(name="x", status="nope", detail="d")


@pytest.mark.parametrize(
    ("statuses", "expected_overall"),
    [
        (["pass", "pass"], "pass"),
        (["pass", "warn"], "warn"),
        (["warn", "fail"], "fail"),
        (["pass", "fail", "warn"], "fail"),
        ([], "pass"),
    ],
)
def test_validation_report_overall_status(statuses: list[str], expected_overall: str) -> None:
    checks = [
        validate_environment.CheckResult(name=f"c{i}", status=s, detail="d")
        for i, s in enumerate(statuses)
    ]

    report = validate_environment.ValidationReport(checks=checks)

    assert report.overall_status == expected_overall


def test_validation_report_to_dict_shape() -> None:
    report = validate_environment.ValidationReport(
        checks=[validate_environment.CheckResult(name="c1", status="pass", detail="ok")]
    )

    as_dict = report.to_dict()

    assert as_dict["overall_status"] == "pass"
    assert as_dict["checks"] == [{"name": "c1", "status": "pass", "detail": "ok"}]


def test_validation_report_to_markdown_contains_table() -> None:
    report = validate_environment.ValidationReport(
        checks=[validate_environment.CheckResult(name="c1", status="fail", detail="broke | pipe")]
    )

    markdown = report.to_markdown()

    assert "| c1 | fail |" in markdown
    assert "broke \\| pipe" in markdown


# ---------------------------------------------------------------------------
# run_checks
# ---------------------------------------------------------------------------


def test_run_checks_returns_results_in_order() -> None:
    specs = [
        validate_environment.CheckSpec(
            name="a", run=lambda: validate_environment.CheckResult("a", "pass", "ok")
        ),
        validate_environment.CheckSpec(
            name="b", run=lambda: validate_environment.CheckResult("b", "warn", "meh")
        ),
    ]

    report = validate_environment.run_checks(specs)

    assert [c.name for c in report.checks] == ["a", "b"]
    assert report.overall_status == "warn"


def test_run_checks_converts_a_raising_check_into_a_failed_result_and_continues() -> None:
    def _boom() -> validate_environment.CheckResult:
        raise RuntimeError("kaboom")

    specs = [
        validate_environment.CheckSpec(name="boom", run=_boom),
        validate_environment.CheckSpec(
            name="ok", run=lambda: validate_environment.CheckResult("ok", "pass", "fine")
        ),
    ]

    report = validate_environment.run_checks(specs)

    assert report.overall_status == "fail"
    assert report.checks[0].status == "fail"
    assert "kaboom" in report.checks[0].detail
    assert report.checks[1].status == "pass"


@pytest.mark.parametrize(
    "exc",
    [
        RuntimeError("az call failed"),
        OSError("az binary not found"),
        ValueError("bad input"),
        KeyError("missing-key"),
        AzureError("search request failed"),
        json.JSONDecodeError("bad json", "{", 0),
    ],
)
def test_run_checks_catches_every_documented_expected_exception_type(exc: Exception) -> None:
    def _boom() -> validate_environment.CheckResult:
        raise exc

    report = validate_environment.run_checks(
        [validate_environment.CheckSpec(name="boom", run=_boom)]
    )

    assert report.checks[0].status == "fail"
    assert type(exc).__name__ in report.checks[0].detail


def test_run_checks_does_not_swallow_an_unexpected_exception_type() -> None:
    """Per the repo's no-broad-catch rule, run_checks must only convert the
    documented, expected exception types into a failed check result -- a
    genuinely unexpected exception type (here, TypeError, which no adapter
    in this module is documented to raise) must propagate so it surfaces as
    a real crash/bug signal instead of being silently folded into the
    report.
    """

    def _boom() -> validate_environment.CheckResult:
        raise TypeError("unexpected programming bug, not an expected check failure")

    with pytest.raises(TypeError):
        validate_environment.run_checks([validate_environment.CheckSpec(name="boom", run=_boom)])


# ---------------------------------------------------------------------------
# pure validators
# ---------------------------------------------------------------------------


def test_validate_terraform_outputs_present_passes_when_all_present() -> None:
    result = validate_environment.validate_terraform_outputs_present(
        VALID_OUTPUTS, validate_environment.REQUIRED_TERRAFORM_OUTPUTS
    )

    assert result.status == "pass"


def test_validate_terraform_outputs_present_fails_when_missing() -> None:
    incomplete = dict(VALID_OUTPUTS)
    del incomplete["travel_api_fqdn"]

    result = validate_environment.validate_terraform_outputs_present(
        incomplete, validate_environment.REQUIRED_TERRAFORM_OUTPUTS
    )

    assert result.status == "fail"
    assert "travel_api_fqdn" in result.detail


def test_validate_role_assignment_present_finds_matching_assignment() -> None:
    assignments = [
        {
            "principalId": "principal-1",
            "roleDefinitionId": (
                "/subscriptions/x/providers/Microsoft.Authorization/roleDefinitions/abc123"
            ),
        }
    ]

    result = validate_environment.validate_role_assignment_present(
        assignments, principal_id="principal-1", role_definition_id_suffix="abc123", label="test"
    )

    assert result.status == "pass"


def test_validate_role_assignment_present_fails_when_absent() -> None:
    result = validate_environment.validate_role_assignment_present(
        [], principal_id="principal-1", role_definition_id_suffix="abc123", label="test"
    )

    assert result.status == "fail"


def test_validate_search_index_passes_with_all_expected_fields() -> None:
    result = validate_environment.validate_search_index(
        ["id", "title", "content"], expected_fields=["id", "title"], label="test"
    )

    assert result.status == "pass"


def test_validate_search_index_fails_with_missing_fields() -> None:
    result = validate_environment.validate_search_index(
        ["id"], expected_fields=["id", "title"], label="test"
    )

    assert result.status == "fail"
    assert "title" in result.detail


def test_validate_search_document_count_passes_at_minimum() -> None:
    result = validate_environment.validate_search_document_count(5, minimum=5, label="test")

    assert result.status == "pass"


def test_validate_search_document_count_fails_below_minimum() -> None:
    result = validate_environment.validate_search_document_count(0, minimum=1, label="test")

    assert result.status == "fail"


def test_validate_resource_exists_passes_with_id_and_provisioning_state() -> None:
    result = validate_environment.validate_resource_exists(
        {"id": "/subscriptions/x/.../foo", "properties": {"provisioningState": "Succeeded"}},
        label="test",
    )

    assert result.status == "pass"
    assert "/subscriptions/x/.../foo" in result.detail
    assert "Succeeded" in result.detail


def test_validate_resource_exists_passes_without_provisioning_state() -> None:
    result = validate_environment.validate_resource_exists(
        {"id": "/subscriptions/x/.../foo"}, label="test"
    )

    assert result.status == "pass"


def test_validate_resource_exists_fails_when_none() -> None:
    result = validate_environment.validate_resource_exists(None, label="test")

    assert result.status == "fail"


def test_validate_resource_exists_fails_when_missing_id_key() -> None:
    result = validate_environment.validate_resource_exists({"properties": {}}, label="test")

    assert result.status == "fail"


def test_validate_travel_api_health_passes_on_200() -> None:
    result = validate_environment.validate_travel_api_health(200, label="test")

    assert result.status == "pass"


@pytest.mark.parametrize("status_code", [500, 404, 302, 0])
def test_validate_travel_api_health_fails_on_non_200(status_code: int) -> None:
    result = validate_environment.validate_travel_api_health(status_code, label="test")

    assert result.status == "fail"
    assert str(status_code) in result.detail


# ---------------------------------------------------------------------------
# fetch_resource_by_id / fetch_travel_api_health adapters (Azure/network-free:
# az_cli_json and urllib.request.urlopen are monkeypatched)
# ---------------------------------------------------------------------------


def test_fetch_resource_by_id_delegates_to_az_cli_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_args: list[list[str]] = []

    def _fake_az_cli_json(args: list[str]) -> dict[str, str]:
        captured_args.append(list(args))
        return {"id": "/subscriptions/x/.../foo"}

    monkeypatch.setattr(validate_environment, "az_cli_json", _fake_az_cli_json)

    result = validate_environment.fetch_resource_by_id("/subscriptions/x/.../foo")

    assert result == {"id": "/subscriptions/x/.../foo"}
    assert captured_args == [["resource", "show", "--ids", "/subscriptions/x/.../foo"]]


def test_fetch_travel_api_health_returns_200_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeResponse:
        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *exc_info: object) -> None:
            return None

        def getcode(self) -> int:
            return 200

    def _fake_urlopen(request: object, timeout: float) -> _FakeResponse:
        assert "https://fake.example.com/health" in request.full_url  # type: ignore[attr-defined]
        return _FakeResponse()

    monkeypatch.setattr(validate_environment.urllib.request, "urlopen", _fake_urlopen)

    status_code = validate_environment.fetch_travel_api_health("fake.example.com")

    assert status_code == 200


def test_fetch_travel_api_health_extracts_status_from_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_urlopen(request: object, timeout: float) -> None:
        raise validate_environment.urllib.error.HTTPError(
            url="https://fake.example.com/health",
            code=503,
            msg="Service Unavailable",
            hdrs=None,  # type: ignore[arg-type]
            fp=None,
        )

    monkeypatch.setattr(validate_environment.urllib.request, "urlopen", _fake_urlopen)

    status_code = validate_environment.fetch_travel_api_health("fake.example.com")

    assert status_code == 503


def test_fetch_travel_api_health_propagates_url_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_urlopen(request: object, timeout: float) -> None:
        raise validate_environment.urllib.error.URLError("name resolution failed")

    monkeypatch.setattr(validate_environment.urllib.request, "urlopen", _fake_urlopen)

    with pytest.raises(validate_environment.urllib.error.URLError):
        validate_environment.fetch_travel_api_health("fake.example.com")


# ---------------------------------------------------------------------------
# main() integration, with Azure/CLI adapters monkeypatched out
# ---------------------------------------------------------------------------


def test_main_reports_pass_when_outputs_present_and_search_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        validate_environment,
        "fetch_role_assignments",
        lambda resource_id: [
            {
                "principalId": "principal-1",
                "roleDefinitionId": (
                    f"/providers/.../roleDefinitions/{validate_environment.FOUNDRY_USER_ROLE_ID}"
                ),
            },
            {
                "principalId": "principal-1",
                "roleDefinitionId": (
                    f"/providers/.../roleDefinitions/"
                    f"{validate_environment.STORAGE_BLOB_DATA_CONTRIBUTOR_ROLE_ID}"
                ),
            },
        ],
    )
    monkeypatch.setattr(validate_environment, "_signed_in_principal_id", lambda: "principal-1")
    monkeypatch.setattr(
        validate_environment,
        "fetch_resource_by_id",
        lambda resource_id: {"id": resource_id, "properties": {"provisioningState": "Succeeded"}},
    )
    monkeypatch.setattr(validate_environment, "fetch_travel_api_health", lambda fqdn: 200)

    outputs_path = tmp_path / "outputs.json"
    outputs_path.write_text(json.dumps(VALID_OUTPUTS), encoding="utf-8")

    exit_code = validate_environment.main(
        [
            "--subscription",
            "00000000-0000-0000-0000-000000000000",
            "--resource-group",
            "rg-test",
            "--terraform-outputs",
            str(outputs_path),
            "--skip-search-checks",
            "--format",
            "json",
        ]
    )

    assert exit_code == 0


def test_main_returns_2_when_outputs_file_missing(tmp_path: Path) -> None:
    exit_code = validate_environment.main(
        [
            "--subscription",
            "00000000-0000-0000-0000-000000000000",
            "--resource-group",
            "rg-test",
            "--terraform-outputs",
            str(tmp_path / "missing.json"),
            "--skip-search-checks",
        ]
    )

    assert exit_code == 2


def test_main_fails_when_rbac_role_assignment_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(validate_environment, "fetch_role_assignments", lambda resource_id: [])
    monkeypatch.setattr(validate_environment, "_signed_in_principal_id", lambda: "principal-1")
    monkeypatch.setattr(
        validate_environment,
        "fetch_resource_by_id",
        lambda resource_id: {"id": resource_id, "properties": {"provisioningState": "Succeeded"}},
    )
    monkeypatch.setattr(validate_environment, "fetch_travel_api_health", lambda fqdn: 200)

    outputs_path = tmp_path / "outputs.json"
    outputs_path.write_text(json.dumps(VALID_OUTPUTS), encoding="utf-8")

    exit_code = validate_environment.main(
        [
            "--subscription",
            "00000000-0000-0000-0000-000000000000",
            "--resource-group",
            "rg-test",
            "--terraform-outputs",
            str(outputs_path),
            "--skip-search-checks",
        ]
    )

    assert exit_code == 2


def test_main_fails_when_arm_resource_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        validate_environment,
        "fetch_role_assignments",
        lambda resource_id: [
            {
                "principalId": "principal-1",
                "roleDefinitionId": (
                    f"/providers/.../roleDefinitions/{validate_environment.FOUNDRY_USER_ROLE_ID}"
                ),
            },
            {
                "principalId": "principal-1",
                "roleDefinitionId": (
                    f"/providers/.../roleDefinitions/"
                    f"{validate_environment.STORAGE_BLOB_DATA_CONTRIBUTOR_ROLE_ID}"
                ),
            },
        ],
    )
    monkeypatch.setattr(validate_environment, "_signed_in_principal_id", lambda: "principal-1")
    # Only the container app resource is reported missing; everything else
    # (RBAC, the other three ARM existence checks) still passes, so this
    # isolates that a single missing resource is enough to fail the overall
    # report rather than being masked by the other passing checks.
    monkeypatch.setattr(
        validate_environment,
        "fetch_resource_by_id",
        lambda resource_id: (
            None if "containerApps" in resource_id else {"id": resource_id, "properties": {}}
        ),
    )
    monkeypatch.setattr(validate_environment, "fetch_travel_api_health", lambda fqdn: 200)

    outputs_path = tmp_path / "outputs.json"
    outputs_path.write_text(json.dumps(VALID_OUTPUTS), encoding="utf-8")

    exit_code = validate_environment.main(
        [
            "--subscription",
            "00000000-0000-0000-0000-000000000000",
            "--resource-group",
            "rg-test",
            "--terraform-outputs",
            str(outputs_path),
            "--skip-search-checks",
            "--format",
            "json",
        ]
    )

    assert exit_code == 2


def test_main_fails_when_travel_api_health_is_non_200(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        validate_environment,
        "fetch_role_assignments",
        lambda resource_id: [
            {
                "principalId": "principal-1",
                "roleDefinitionId": (
                    f"/providers/.../roleDefinitions/{validate_environment.FOUNDRY_USER_ROLE_ID}"
                ),
            },
            {
                "principalId": "principal-1",
                "roleDefinitionId": (
                    f"/providers/.../roleDefinitions/"
                    f"{validate_environment.STORAGE_BLOB_DATA_CONTRIBUTOR_ROLE_ID}"
                ),
            },
        ],
    )
    monkeypatch.setattr(validate_environment, "_signed_in_principal_id", lambda: "principal-1")
    monkeypatch.setattr(
        validate_environment,
        "fetch_resource_by_id",
        lambda resource_id: {"id": resource_id, "properties": {"provisioningState": "Succeeded"}},
    )
    monkeypatch.setattr(validate_environment, "fetch_travel_api_health", lambda fqdn: 503)

    outputs_path = tmp_path / "outputs.json"
    outputs_path.write_text(json.dumps(VALID_OUTPUTS), encoding="utf-8")

    exit_code = validate_environment.main(
        [
            "--subscription",
            "00000000-0000-0000-0000-000000000000",
            "--resource-group",
            "rg-test",
            "--terraform-outputs",
            str(outputs_path),
            "--skip-search-checks",
        ]
    )

    assert exit_code == 2

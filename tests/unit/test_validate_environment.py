"""Network-free tests for canonical post-provisioning validation."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import validate_environment as validation


def _context() -> dict[str, object]:
    values = {key: f"fixture-{key}" for key in validation.REQUIRED_RESOURCE_OUTPUTS}
    values.update(
        {
            "ai_services_account_name": "aif-fixture",
            "search_service_name": "srch-fixture",
            "search_service_endpoint": "https://search.example.invalid",
            "travel_api_container_app_name": "ca-fixture",
            "travel_api_fqdn": "travel.example.invalid",
            "azureml_workspace_id": (
                "/subscriptions/sub/resourceGroups/rg/providers/"
                "Microsoft.MachineLearningServices/workspaces/mlw-fixture"
            ),
        }
    )
    return {
        "schema_version": "1.0",
        "provisioning_method": "cloud-shell-terraform",
        "subscription_id": "00000000-0000-0000-0000-000000000000",
        "resource_group_name": "rg-fixture",
        "location": "japaneast",
        "setup_status": "infrastructure-ready",
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
    result = validation.validate_resource_outputs_present({}, ("azureml_workspace_id",))

    assert result.status == "fail"
    assert "azureml_workspace_id" in result.detail


def test_build_credential_is_explicit_azure_cli() -> None:
    from azure.identity import AzureCliCredential

    assert isinstance(validation.build_credential(), AzureCliCredential)


def test_main_validates_azureml_api_and_both_search_indexes(
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
                "principalId": "participant",
                "roleDefinitionId": f"/roles/{validation.FOUNDRY_USER_ROLE_ID}",
            }
        ],
    )
    monkeypatch.setattr(validation, "_signed_in_principal_id", lambda: "participant")
    monkeypatch.setattr(validation, "fetch_travel_api_health", lambda _: 200)

    def fields(_: str, index_name: str, __: object) -> list[str]:
        index_calls.append(index_name)
        return list(validation.EXPECTED_INDEX_FIELDS)

    monkeypatch.setattr(validation, "fetch_search_index_fields", fields)
    monkeypatch.setattr(validation, "fetch_search_document_count", lambda *_: 3)
    report_path = tmp_path / "report.json"

    result = validation.main(
        [
            "--context",
            str(context_path),
            "--format",
            "json",
            "--output",
            str(report_path),
        ]
    )

    assert result == 0
    assert index_calls == list(validation.DEFAULT_INDEX_NAMES)
    assert any("Microsoft.MachineLearningServices/workspaces" in item for item in resource_calls)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    names = {check["name"] for check in report["checks"]}
    assert {
        "arm-foundry-account-exists",
        "arm-search-service-exists",
        "arm-travel-api-container-app-exists",
        "arm-azureml-workspace-exists",
        "search-index-schema:contoso-travel-policy",
        "search-index-schema:contoso-travel-approval",
    } <= names
    assert "luna-inference" not in names

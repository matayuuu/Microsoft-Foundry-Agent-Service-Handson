"""Read-only deployment discovery and scoped local context generation."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from scripts import configure_workshop as configure
from scripts.lib import workshop_context as context_helpers

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "workshop-context.json"


@pytest.fixture
def context() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def deployment(
    context: dict, name: str = "workshop", timestamp: str = "2026-01-01T00:00:00Z"
) -> dict:
    return {
        "id": (
            f"/subscriptions/{context['subscription_id']}/resourceGroups/"
            f"{context['resource_group_name']}/providers/Microsoft.Resources/deployments/{name}"
        ),
        "name": name,
        "state": "Succeeded",
        "timestamp": timestamp,
        "context": copy.deepcopy(context),
    }


def test_context_from_arm_is_valid_and_has_no_removed_resource_keys(context: dict) -> None:
    validated = context_helpers.validate_workshop_context(context)
    assert validated == context
    assert len(validated["resource_outputs"]) == 24
    assert not {"azureml_workspace_id", "storage_account_id", "key_vault_id"} & set(
        validated["resource_outputs"]
    )
    validated["resource_outputs"]["foundry_project_name"]["value"] = "other"
    assert context["resource_outputs"]["foundry_project_name"]["value"] == "contoso-travel"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema_version", "1.0"),
        ("setup_status", "infrastructure-ready"),
        ("provisioning_method", "other"),
        ("subscription_id", "00000000-0000-0000-0000-000000000000"),
        ("participant_object_id", ""),
        ("source_revision", "main"),
        ("source_base", "https://example.invalid/untrusted"),
        ("location", "centralus"),
        ("resource_group_name", "../other"),
        ("api_key", "must-not-be-persisted"),
    ],
)
def test_invalid_context_is_rejected(context: dict, key: str, value: object) -> None:
    context[key] = value
    with pytest.raises(context_helpers.WorkshopContextError):
        context_helpers.validate_workshop_context(context)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("foundry_project_id", "/subscriptions/another/resourceGroups/rg/providers/fake/project"),
        ("application_insights_id", "https://example.invalid"),
        ("foundry_project_endpoint", "https://attacker.example.invalid"),
        ("openai_endpoint", "https://aif-workshop.openai.azure.com/openai/v1/?key=value"),
        ("search_service_endpoint", "http://srch-workshop.search.windows.net"),
        ("foundry_portal_url", "https://ai.azure.com/?token=value"),
        ("travel_api_fqdn", "example.invalid"),
        ("search_pricing_model", "serverless"),
        ("primary_model_deployment_name", ""),
    ],
)
def test_mismatched_or_unsigned_resource_values_are_rejected(
    context: dict, key: str, value: object
) -> None:
    context["resource_outputs"][key]["value"] = value
    with pytest.raises(context_helpers.WorkshopContextError):
        context_helpers.validate_workshop_context(context)


def test_latest_successful_context_is_selected_and_fetched_again(
    context: dict, tmp_path: Path
) -> None:
    old = deployment(context, "old")
    current = deployment(context, "current", "2026-01-02T00:00:00+00:00")
    calls = []

    def runner(command):
        calls.append(command)
        if command[2] == "list":
            return [{"name": "unrelated", "state": "Succeeded"}, old, current]
        assert command[command.index("--name") + 1] == "current"
        return current

    output = tmp_path / ".workshop" / "context.json"
    result = configure.configure(
        context["subscription_id"], context["resource_group_name"], output, runner=runner
    )
    assert result == context
    assert json.loads(output.read_text(encoding="utf-8")) == context
    assert [command[2] for command in calls] == ["list", "show"]
    for command in calls:
        assert command[command.index("--subscription") + 1] == context["subscription_id"]
        assert command[command.index("--resource-group") + 1] == context["resource_group_name"]
        assert not {"create", "update", "delete", "login", "get-access-token"} & set(command)


def test_explicit_deployment_does_not_enumerate_other_deployments(
    context: dict, tmp_path: Path
) -> None:
    calls = []

    def runner(command):
        calls.append(command)
        return deployment(context, "chosen")

    configure.configure(
        context["subscription_id"],
        context["resource_group_name"],
        tmp_path / "context.json",
        deployment="chosen",
        runner=runner,
    )
    assert len(calls) == 1
    assert calls[0][2] == "show"


def test_old_failed_attempt_does_not_hide_new_success(context: dict) -> None:
    old = deployment(context, "old")
    old["state"] = "Failed"
    current = deployment(context, "current", "2026-01-02T00:00:00Z")
    assert (
        configure.select_deployment(
            [old, current], context["subscription_id"], context["resource_group_name"]
        )
        == "current"
    )


def test_newer_failed_attempt_is_not_silently_replaced_by_old_success(context: dict) -> None:
    old = deployment(context, "old")
    current = deployment(context, "current", "2026-01-02T00:00:00Z")
    current["state"] = "Failed"
    with pytest.raises(configure.WorkshopContextError, match="not succeeded"):
        configure.select_deployment(
            [old, current], context["subscription_id"], context["resource_group_name"]
        )


def test_new_failed_attempt_without_outputs_prevents_stale_context_selection(context: dict) -> None:
    old = deployment(context, "old")
    current = {
        "name": "failed",
        "state": "Failed",
        "timestamp": "2026-01-02T00:00:00Z",
        "context": None,
    }
    with pytest.raises(configure.WorkshopContextError, match="newer deployment"):
        configure.select_deployment(
            [old, current], context["subscription_id"], context["resource_group_name"]
        )


@pytest.mark.parametrize("state", ["Running", "Failed", "Canceled"])
def test_incomplete_deployments_are_not_written(context: dict, tmp_path: Path, state: str) -> None:
    record = deployment(context)
    record["state"] = state
    output = tmp_path / "context.json"
    with pytest.raises(configure.WorkshopContextError, match="not succeeded"):
        configure.configure(
            context["subscription_id"],
            context["resource_group_name"],
            output,
            deployment="workshop",
            runner=lambda _: record,
        )
    assert not output.exists()


def test_ambiguous_projects_and_timestamps_require_explicit_selection(context: dict) -> None:
    one = deployment(context, "one")
    two = deployment(context, "two")
    with pytest.raises(configure.WorkshopContextError, match="ambiguous"):
        configure.select_deployment(
            [one, two], context["subscription_id"], context["resource_group_name"]
        )
    second_context = copy.deepcopy(context)
    values = second_context["resource_outputs"]
    values["foundry_project_name"]["value"] = "other-project"
    values["foundry_project_id"]["value"] = values["foundry_project_id"]["value"].replace(
        "contoso-travel", "other-project"
    )
    values["foundry_project_endpoint"]["value"] = values["foundry_project_endpoint"][
        "value"
    ].replace("contoso-travel", "other-project")
    two = deployment(second_context, "two", "2026-01-02T00:00:00Z")
    with pytest.raises(configure.WorkshopContextError, match="Multiple workshop projects"):
        configure.select_deployment(
            [one, two], context["subscription_id"], context["resource_group_name"]
        )


def test_wrong_scope_does_not_replace_existing_file(context: dict, tmp_path: Path) -> None:
    output = tmp_path / "context.json"
    configure.save_context(output, context)
    original = output.read_bytes()
    with pytest.raises(configure.WorkshopContextError, match="requested subscription/RG"):
        configure.configure(
            context["subscription_id"],
            "different-rg",
            output,
            deployment="workshop",
            runner=lambda _: deployment(context),
        )
    assert output.read_bytes() == original


def test_invalid_existing_file_is_not_overwritten(context: dict, tmp_path: Path) -> None:
    output = tmp_path / "context.json"
    output.write_text("private unrelated content", encoding="utf-8")
    with pytest.raises(configure.WorkshopContextError, match="move it aside"):
        configure.save_context(output, context)
    assert output.read_text(encoding="utf-8") == "private unrelated content"


@pytest.mark.parametrize("records", [None, {}, [], [{"context": None}]])
def test_no_usable_deployment_has_no_success_fallback(context: dict, records: object) -> None:
    with pytest.raises(configure.WorkshopContextError):
        configure.select_deployment(
            records, context["subscription_id"], context["resource_group_name"]
        )


def test_auth_failure_does_not_log_cli_response_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(configure.shutil, "which", lambda _: "az")
    monkeypatch.setattr(
        configure.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 1, "", "token=do-not-show"),
    )
    with pytest.raises(configure.WorkshopContextError, match="Sign in") as error:
        configure.azure_json(["deployment", "group", "list"])
    assert "do-not-show" not in str(error.value)


def test_scope_is_validated_before_any_cli_call(tmp_path: Path) -> None:
    def runner(_):
        raise AssertionError("must not access Azure")

    with pytest.raises(configure.WorkshopContextError, match="subscription ID"):
        configure.configure("invalid", "rg", tmp_path / "context.json", runner=runner)

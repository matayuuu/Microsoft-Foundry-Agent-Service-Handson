"""Hermetic tests for Terraform state reconciliation before workshop setup."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "prepare_terraform_plan.py"

spec = importlib.util.spec_from_file_location("prepare_terraform_plan", MODULE_PATH)
assert spec is not None and spec.loader is not None
prepare_terraform_plan = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = prepare_terraform_plan
spec.loader.exec_module(prepare_terraform_plan)

SUBSCRIPTION_ID = "00000000-0000-0000-0000-000000000001"
RESOURCE_GROUP = "rg-workshop"
RESOURCE_GROUP_ID = f"/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}"
PROJECT_ID = (
    f"{RESOURCE_GROUP_ID}/providers/Microsoft.CognitiveServices/"
    "accounts/aif-fdyws-12345678/projects/contoso-travel"
)
SEARCH_ID = f"{RESOURCE_GROUP_ID}/providers/Microsoft.Search/searchServices/srch-fdyws-12345678"
ROLE_DEFINITION_ID = (
    f"/subscriptions/{SUBSCRIPTION_ID}/providers/Microsoft.Authorization/"
    "roleDefinitions/53ca6127-db72-4b80-b1b0-d745d6d5456d"
)
ACCOUNT_SCOPE = (
    f"{RESOURCE_GROUP_ID}/providers/Microsoft.CognitiveServices/accounts/aif-fdyws-12345678"
)
ROLE_ASSIGNMENT_ID = (
    f"{ACCOUNT_SCOPE}/providers/Microsoft.Authorization/"
    "roleAssignments/11111111-1111-1111-1111-111111111111"
)
PRINCIPAL_ID = "22222222-2222-2222-2222-222222222222"
WORKSHOP_TAGS = {
    "workshop": "foundry-agent-service-handson",
    "managed-by": "terraform",
}


def _result(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> Any:
    return prepare_terraform_plan.CommandResult(returncode, stdout, stderr)


def _config(tmp_path: Path) -> Any:
    return prepare_terraform_plan.PlanConfig(
        terraform_dir=tmp_path / "infra",
        plan_file=tmp_path / "tfplan",
        subscription_id=SUBSCRIPTION_ID,
        resource_group_name=RESOURCE_GROUP,
        terraform_args=("-var", f"subscription_id={SUBSCRIPTION_ID}"),
    )


def _target(address: str, resource_id: str, api_version: str) -> dict[str, str]:
    return {
        "address": address,
        "id": resource_id,
        "api_version": api_version,
        "owner_id": resource_id,
        "owner_api_version": api_version,
    }


def _role_plan() -> dict[str, Any]:
    return {
        "resource_changes": [
            {
                "address": "azurerm_role_assignment.participant_foundry_user",
                "type": "azurerm_role_assignment",
                "change": {
                    "actions": ["create"],
                    "after": {
                        "scope": ACCOUNT_SCOPE,
                        "principal_id": PRINCIPAL_ID,
                        "role_definition_id": ROLE_DEFINITION_ID,
                    },
                },
            }
        ]
    }


class FakeRunner:
    def __init__(
        self,
        *,
        state: set[str] | None = None,
        resource_group_resources: list[dict[str, Any]] | None = None,
        targets: list[dict[str, str]] | None = None,
        arm_resources: dict[str, dict[str, Any]] | None = None,
        plan: dict[str, Any] | None = None,
        role_assignments: list[dict[str, Any]] | None = None,
    ) -> None:
        self.state = set(state or set())
        self.resource_group_resources = resource_group_resources or []
        self.targets = targets or []
        self.arm_resources = arm_resources or {}
        self.plan = plan or {"resource_changes": []}
        self.role_assignments = role_assignments or []
        self.commands: list[list[str]] = []
        self.imports: list[tuple[str, str]] = []
        self.plan_calls = 0

    def __call__(self, command: Any, input_text: str | None = None) -> Any:
        args = list(command)
        self.commands.append(args)

        if args[0] == "terraform":
            action = args[2]
            if action == "state":
                return _result(stdout="\n".join(sorted(self.state)))
            if action == "console":
                assert input_text == "jsonencode(local.state_recovery_targets)\n"
                return _result(stdout=json.dumps(json.dumps(self.targets)))
            if action == "import":
                address, resource_id = args[-2:]
                self.state.add(address)
                self.imports.append((address, resource_id))
                return _result(stdout=f"Imported {address}\n")
            if action == "plan":
                self.plan_calls += 1
                return _result(stdout="Plan prepared\n")
            if action == "show":
                return _result(stdout=json.dumps(self.plan))

        if args[:3] == ["az", "resource", "list"]:
            return _result(stdout=json.dumps(self.resource_group_resources))

        if args[:2] == ["az", "rest"]:
            url = args[args.index("--url") + 1]
            if "/roleAssignments?" in url:
                return _result(stdout=json.dumps({"value": self.role_assignments}))
            resource_id = url.split("https://management.azure.com", 1)[1].split("?api-version=", 1)[
                0
            ]
            resource = self.arm_resources.get(resource_id)
            if resource is None:
                return _result(returncode=1, stderr="ResourceNotFound (404)")
            return _result(stdout=json.dumps(resource))

        raise AssertionError(f"unexpected command: {args}")


def test_fresh_resource_group_plans_without_recovery(tmp_path: Path) -> None:
    runner = FakeRunner()

    imported = prepare_terraform_plan.prepare_terraform_plan(
        _config(tmp_path),
        runner,
    )

    assert imported == 0
    assert runner.imports == []
    assert runner.plan_calls == 1
    assert not any(
        command[2] == "console" for command in runner.commands if command[0] == "terraform"
    )


def test_foundry_connection_not_found_response_is_treated_as_absent() -> None:
    result = _result(
        returncode=1,
        stderr=(
            "Connection demo cannot be found "
            '({"error":{"innerError":{"code":"NotFoundError"}},"statusCode":404})'
        ),
    )

    assert prepare_terraform_plan._is_not_found(result)


def test_recovers_existing_project_search_and_role_assignment(tmp_path: Path) -> None:
    project_address = "azapi_resource.project"
    search_address = "azurerm_search_service.workshop"
    account_resource = {"id": f"{RESOURCE_GROUP_ID}/providers/test/account", "tags": WORKSHOP_TAGS}
    runner = FakeRunner(
        state={"azapi_resource.ai_services"},
        resource_group_resources=[account_resource],
        targets=[
            _target(project_address, PROJECT_ID, "2026-05-01"),
            _target(search_address, SEARCH_ID, "2025-05-01"),
        ],
        arm_resources={
            PROJECT_ID: {"id": PROJECT_ID, "tags": WORKSHOP_TAGS},
            SEARCH_ID: {"id": SEARCH_ID, "tags": WORKSHOP_TAGS},
        },
        plan=_role_plan(),
        role_assignments=[
            {
                "id": ROLE_ASSIGNMENT_ID,
                "properties": {
                    "principalId": PRINCIPAL_ID,
                    "roleDefinitionId": ROLE_DEFINITION_ID,
                    "scope": ACCOUNT_SCOPE,
                },
            }
        ],
    )

    imported = prepare_terraform_plan.prepare_terraform_plan(
        _config(tmp_path),
        runner,
    )

    assert imported == 3
    assert runner.imports == [
        (project_address, f"{PROJECT_ID}?api-version=2026-05-01"),
        (search_address, SEARCH_ID),
        ("azurerm_role_assignment.participant_foundry_user", ROLE_ASSIGNMENT_ID),
    ]
    assert runner.plan_calls == 2


def test_refuses_resource_with_non_workshop_tags(tmp_path: Path) -> None:
    runner = FakeRunner(
        resource_group_resources=[{"id": PROJECT_ID, "tags": WORKSHOP_TAGS}],
        targets=[_target("azapi_resource.project", PROJECT_ID, "2026-05-01")],
        arm_resources={
            PROJECT_ID: {
                "id": PROJECT_ID,
                "tags": {"workshop": "another-workshop", "managed-by": "terraform"},
            }
        },
    )

    with pytest.raises(
        prepare_terraform_plan.StateRecoveryError,
        match="ownership tags do not match",
    ):
        prepare_terraform_plan.prepare_terraform_plan(_config(tmp_path), runner)

    assert runner.imports == []
    assert runner.plan_calls == 0


def test_missing_remote_target_is_left_for_terraform_to_create(tmp_path: Path) -> None:
    runner = FakeRunner(
        resource_group_resources=[{"id": PROJECT_ID, "tags": WORKSHOP_TAGS}],
        targets=[_target("azapi_resource.project", PROJECT_ID, "2026-05-01")],
    )

    imported = prepare_terraform_plan.prepare_terraform_plan(
        _config(tmp_path),
        runner,
    )

    assert imported == 0
    assert runner.imports == []
    assert runner.plan_calls == 1


def test_does_not_import_role_assignment_inherited_from_parent_scope(
    tmp_path: Path,
) -> None:
    inherited_assignment_id = (
        f"{RESOURCE_GROUP_ID}/providers/Microsoft.Authorization/"
        "roleAssignments/33333333-3333-3333-3333-333333333333"
    )
    runner = FakeRunner(
        resource_group_resources=[{"id": PROJECT_ID, "tags": WORKSHOP_TAGS}],
        plan=_role_plan(),
        role_assignments=[
            {
                "id": inherited_assignment_id,
                "properties": {
                    "principalId": PRINCIPAL_ID,
                    "roleDefinitionId": ROLE_DEFINITION_ID,
                    "scope": RESOURCE_GROUP_ID,
                },
            }
        ],
    )

    imported = prepare_terraform_plan.prepare_terraform_plan(
        _config(tmp_path),
        runner,
    )

    assert imported == 0
    assert runner.imports == []
    assert runner.plan_calls == 1

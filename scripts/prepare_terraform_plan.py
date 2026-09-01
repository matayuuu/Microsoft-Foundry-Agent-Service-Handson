#!/usr/bin/env python3
"""Prepare a Terraform plan and safely recover missing local state.

The workshop intentionally uses local Terraform state. An interrupted Azure
create can therefore leave a resource in Azure without a matching state entry.
Before planning, this adapter adopts only deterministic workshop resources
whose ownership tags match this repository. After planning, it also adopts
exact RBAC tuples that Terraform intends to create.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

WORKSHOP_TAG = "foundry-agent-service-handson"
MANAGED_BY_TAG = "terraform"
ROLE_ASSIGNMENTS_API_VERSION = "2022-04-01"
ARM_ENDPOINT = "https://management.azure.com"


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


Runner = Callable[[Sequence[str], str | None], CommandResult]


@dataclass(frozen=True)
class PlanConfig:
    terraform_dir: Path
    plan_file: Path
    subscription_id: str
    resource_group_name: str
    terraform_args: tuple[str, ...]


@dataclass(frozen=True)
class RecoveryTarget:
    address: str
    resource_id: str
    api_version: str
    owner_id: str
    owner_api_version: str


@dataclass(frozen=True)
class RoleAssignmentTarget:
    address: str
    scope: str
    principal_id: str
    role_definition_id: str


class StateRecoveryError(RuntimeError):
    """Raised when state recovery cannot continue safely."""


def run_command(command: Sequence[str], input_text: str | None = None) -> CommandResult:
    executable = shutil.which(command[0]) or command[0]
    try:
        completed = subprocess.run(
            [executable, *command[1:]],
            input=input_text,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        raise StateRecoveryError(f"could not execute {command[0]!r}: {exc}") from exc
    return CommandResult(completed.returncode, completed.stdout, completed.stderr)


def _terraform(config: PlanConfig, *args: str) -> list[str]:
    return ["terraform", f"-chdir={config.terraform_dir}", *args]


def _emit_result(result: CommandResult) -> None:
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)


def _run_checked(
    runner: Runner,
    command: Sequence[str],
    *,
    operation: str,
    input_text: str | None = None,
    visible: bool = False,
) -> CommandResult:
    result = runner(command, input_text)
    if visible:
        _emit_result(result)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        suffix = f": {detail}" if detail else ""
        raise StateRecoveryError(f"{operation} failed{suffix}")
    return result


def _parse_json(text: str, *, source: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise StateRecoveryError(f"{source} did not return valid JSON: {exc}") from exc


def _state_addresses(config: PlanConfig, runner: Runner) -> set[str]:
    result = runner(_terraform(config, "state", "list"), None)
    if result.returncode == 0:
        return {line.strip() for line in result.stdout.splitlines() if line.strip()}

    detail = (result.stderr or result.stdout).casefold()
    if "no state file" in detail or "state snapshot was not found" in detail:
        return set()
    raise StateRecoveryError(
        f"could not inspect Terraform state: {(result.stderr or result.stdout).strip()}"
    )


def _resource_group_has_workshop_resources(config: PlanConfig, runner: Runner) -> bool:
    result = _run_checked(
        runner,
        [
            "az",
            "resource",
            "list",
            "--subscription",
            config.subscription_id,
            "--resource-group",
            config.resource_group_name,
            "--output",
            "json",
            "--only-show-errors",
        ],
        operation="listing resource-group resources",
    )
    resources = _parse_json(result.stdout, source="az resource list")
    if not isinstance(resources, list):
        raise StateRecoveryError("az resource list returned a non-list JSON value")

    return any(
        isinstance(resource, dict)
        and isinstance(resource.get("tags"), dict)
        and resource["tags"].get("workshop") == WORKSHOP_TAG
        and resource["tags"].get("managed-by") == MANAGED_BY_TAG
        for resource in resources
    )


def _load_recovery_targets(config: PlanConfig, runner: Runner) -> list[RecoveryTarget]:
    result = _run_checked(
        runner,
        _terraform(
            config,
            "console",
            *config.terraform_args,
        ),
        input_text="jsonencode(local.state_recovery_targets)\n",
        operation="evaluating Terraform recovery targets",
    )
    encoded_targets = _parse_json(result.stdout.strip(), source="terraform console")
    if not isinstance(encoded_targets, str):
        raise StateRecoveryError("Terraform recovery targets were not JSON-encoded")
    raw_targets = _parse_json(encoded_targets, source="Terraform recovery targets")
    if not isinstance(raw_targets, list):
        raise StateRecoveryError("Terraform recovery targets must be a list")

    targets: list[RecoveryTarget] = []
    required_keys = {
        "address",
        "id",
        "api_version",
        "owner_id",
        "owner_api_version",
    }
    for index, raw_target in enumerate(raw_targets):
        if not isinstance(raw_target, dict) or not required_keys <= raw_target.keys():
            raise StateRecoveryError(f"recovery target {index} is missing required fields")
        values = {key: raw_target[key] for key in required_keys}
        if not all(isinstance(value, str) and value for value in values.values()):
            raise StateRecoveryError(f"recovery target {index} contains an invalid value")
        targets.append(
            RecoveryTarget(
                address=values["address"],
                resource_id=values["id"],
                api_version=values["api_version"],
                owner_id=values["owner_id"],
                owner_api_version=values["owner_api_version"],
            )
        )
    return targets


def _arm_url(resource_id: str, api_version: str) -> str:
    encoded_id = quote(resource_id, safe="/:")
    return f"{ARM_ENDPOINT}{encoded_id}?api-version={quote(api_version, safe='-')}"


def _is_not_found(result: CommandResult) -> bool:
    detail = f"{result.stdout}\n{result.stderr}".casefold()
    return any(
        marker in detail
        for marker in (
            "resourcenotfound",
            "notfounderror",
            "resource not found",
            "could not be found",
            "status code: 404",
            '"statuscode":404',
            "(404)",
        )
    )


def _get_arm_resource(
    runner: Runner,
    resource_id: str,
    api_version: str,
    cache: dict[tuple[str, str], dict[str, Any] | None],
) -> dict[str, Any] | None:
    key = (resource_id.casefold(), api_version)
    if key in cache:
        return cache[key]

    result = runner(
        [
            "az",
            "rest",
            "--method",
            "GET",
            "--url",
            _arm_url(resource_id, api_version),
            "--output",
            "json",
            "--only-show-errors",
        ],
        None,
    )
    if result.returncode != 0:
        if _is_not_found(result):
            cache[key] = None
            return None
        raise StateRecoveryError(
            f"could not inspect existing Azure resource {resource_id}: "
            f"{(result.stderr or result.stdout).strip()}"
        )

    document = _parse_json(result.stdout, source=f"Azure resource {resource_id}")
    if not isinstance(document, dict):
        raise StateRecoveryError(f"Azure resource {resource_id} returned non-object JSON")
    cache[key] = document
    return document


def _verify_workshop_owner(owner: dict[str, Any], owner_id: str) -> None:
    tags = owner.get("tags")
    if not isinstance(tags, dict) or (
        tags.get("workshop") != WORKSHOP_TAG or tags.get("managed-by") != MANAGED_BY_TAG
    ):
        raise StateRecoveryError(
            f"refusing to import {owner_id}: ownership tags do not match this workshop"
        )


def _import_resource(
    config: PlanConfig,
    runner: Runner,
    address: str,
    resource_id: str,
) -> None:
    print(f"    Recovering Terraform state: {address}")
    _run_checked(
        runner,
        _terraform(
            config,
            "import",
            "-input=false",
            *config.terraform_args,
            address,
            resource_id,
        ),
        operation=f"importing {address}",
        visible=True,
    )


def _named_resource_import_id(target: RecoveryTarget) -> str:
    if target.address.startswith("azapi_resource."):
        return f"{target.resource_id}?api-version={target.api_version}"
    return target.resource_id


def _recover_named_resources(
    config: PlanConfig,
    runner: Runner,
    state_addresses: set[str],
) -> int:
    if not _resource_group_has_workshop_resources(config, runner):
        return 0

    targets = _load_recovery_targets(config, runner)
    cache: dict[tuple[str, str], dict[str, Any] | None] = {}
    imported = 0
    for target in targets:
        if target.address in state_addresses:
            continue

        resource = _get_arm_resource(
            runner,
            target.resource_id,
            target.api_version,
            cache,
        )
        if resource is None:
            continue

        if target.owner_id.casefold() == target.resource_id.casefold():
            owner = resource
        else:
            owner = _get_arm_resource(
                runner,
                target.owner_id,
                target.owner_api_version,
                cache,
            )
            if owner is None:
                raise StateRecoveryError(
                    f"cannot verify owner {target.owner_id} for existing {target.resource_id}"
                )
        _verify_workshop_owner(owner, target.owner_id)
        _import_resource(
            config,
            runner,
            target.address,
            _named_resource_import_id(target),
        )
        state_addresses.add(target.address)
        imported += 1
    return imported


def _write_plan(config: PlanConfig, runner: Runner) -> None:
    _run_checked(
        runner,
        _terraform(
            config,
            "plan",
            "-input=false",
            f"-out={config.plan_file}",
            *config.terraform_args,
        ),
        operation="terraform plan",
        visible=True,
    )


def _load_plan(config: PlanConfig, runner: Runner) -> dict[str, Any]:
    result = _run_checked(
        runner,
        _terraform(config, "show", "-json", str(config.plan_file)),
        operation="reading Terraform plan",
    )
    document = _parse_json(result.stdout, source="terraform show -json")
    if not isinstance(document, dict):
        raise StateRecoveryError("terraform show -json returned non-object JSON")
    return document


def _role_assignment_targets(plan: dict[str, Any]) -> list[RoleAssignmentTarget]:
    resource_changes = plan.get("resource_changes", [])
    if not isinstance(resource_changes, list):
        raise StateRecoveryError("Terraform plan resource_changes must be a list")

    targets: list[RoleAssignmentTarget] = []
    for change in resource_changes:
        if not isinstance(change, dict) or change.get("type") != "azurerm_role_assignment":
            continue
        change_body = change.get("change")
        if not isinstance(change_body, dict) or change_body.get("actions") != ["create"]:
            continue
        after = change_body.get("after")
        if not isinstance(after, dict):
            continue

        values = (
            change.get("address"),
            after.get("scope"),
            after.get("principal_id"),
            after.get("role_definition_id"),
        )
        if not all(isinstance(value, str) and value for value in values):
            continue
        targets.append(RoleAssignmentTarget(*values))
    return targets


def _role_assignments_at_scope(
    runner: Runner,
    scope: str,
    cache: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    cache_key = scope.casefold()
    if cache_key in cache:
        return cache[cache_key]

    encoded_scope = quote(scope, safe="/:")
    url = (
        f"{ARM_ENDPOINT}{encoded_scope}/providers/Microsoft.Authorization/"
        f"roleAssignments?api-version={ROLE_ASSIGNMENTS_API_VERSION}&$filter=atScope()"
    )
    result = _run_checked(
        runner,
        [
            "az",
            "rest",
            "--method",
            "GET",
            "--url",
            url,
            "--output",
            "json",
            "--only-show-errors",
        ],
        operation=f"listing role assignments at {scope}",
    )
    document = _parse_json(result.stdout, source=f"role assignments at {scope}")
    raw_assignments = document.get("value") if isinstance(document, dict) else None
    if not isinstance(raw_assignments, list):
        raise StateRecoveryError(f"role assignment query at {scope} returned invalid JSON")
    assignments = [item for item in raw_assignments if isinstance(item, dict)]
    cache[cache_key] = assignments
    return assignments


def _matching_role_assignment_id(
    assignments: Sequence[dict[str, Any]],
    target: RoleAssignmentTarget,
) -> str | None:
    matches: list[str] = []
    for assignment in assignments:
        properties = assignment.get("properties")
        assignment_id = assignment.get("id")
        if not isinstance(properties, dict) or not isinstance(assignment_id, str):
            continue
        principal_id = properties.get("principalId")
        role_definition_id = properties.get("roleDefinitionId")
        scope = properties.get("scope")
        if (
            isinstance(principal_id, str)
            and isinstance(role_definition_id, str)
            and isinstance(scope, str)
            and principal_id.casefold() == target.principal_id.casefold()
            and role_definition_id.casefold() == target.role_definition_id.casefold()
            and scope.casefold() == target.scope.casefold()
        ):
            matches.append(assignment_id)

    if len(matches) > 1:
        raise StateRecoveryError(
            f"multiple role assignments match Terraform target {target.address}"
        )
    return matches[0] if matches else None


def _recover_role_assignments(
    config: PlanConfig,
    runner: Runner,
    state_addresses: set[str],
) -> int:
    plan = _load_plan(config, runner)
    expected_scope_prefix = (
        f"/subscriptions/{config.subscription_id}/resourceGroups/{config.resource_group_name}/"
    ).casefold()
    cache: dict[str, list[dict[str, Any]]] = {}
    imported = 0

    for target in _role_assignment_targets(plan):
        if target.address in state_addresses:
            continue
        if not target.scope.casefold().startswith(expected_scope_prefix):
            raise StateRecoveryError(
                f"refusing to inspect out-of-scope role assignment {target.address}: {target.scope}"
            )
        assignments = _role_assignments_at_scope(runner, target.scope, cache)
        assignment_id = _matching_role_assignment_id(assignments, target)
        if assignment_id is None:
            continue
        _import_resource(config, runner, target.address, assignment_id)
        state_addresses.add(target.address)
        imported += 1
    return imported


def prepare_terraform_plan(config: PlanConfig, runner: Runner = run_command) -> int:
    state_addresses = _state_addresses(config, runner)
    imported = _recover_named_resources(config, runner, state_addresses)
    _write_plan(config, runner)

    imported_roles = _recover_role_assignments(config, runner, state_addresses)
    imported += imported_roles
    if imported_roles:
        _write_plan(config, runner)
    return imported


def _validate_terraform_args(args: Sequence[str]) -> tuple[str, ...]:
    normalized = list(args)
    if normalized and normalized[0] == "--":
        normalized = normalized[1:]
    if len(normalized) % 2 != 0 or any(
        normalized[index] != "-var" for index in range(0, len(normalized), 2)
    ):
        raise StateRecoveryError("Terraform arguments must be repeated '-var name=value' pairs")
    return tuple(normalized)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terraform-dir", type=Path, required=True)
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("terraform_args", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = PlanConfig(
            terraform_dir=args.terraform_dir,
            plan_file=args.plan_file,
            subscription_id=args.subscription,
            resource_group_name=args.resource_group,
            terraform_args=_validate_terraform_args(args.terraform_args),
        )
        imported = prepare_terraform_plan(config)
    except StateRecoveryError as exc:
        print(f"prepare_terraform_plan.py: {exc}", file=sys.stderr)
        return 1

    if imported:
        print(f"    Recovered {imported} existing resource(s) into Terraform state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

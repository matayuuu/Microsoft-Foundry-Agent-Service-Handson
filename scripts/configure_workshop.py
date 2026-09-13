#!/usr/bin/env python3
"""Read a completed workshop deployment and save its non-secret local context."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.workshop_context import (
    CONTEXT_SCHEMA_VERSION,
    DEFAULT_CONTEXT_PATH,
    WorkshopContextError,
    validate_workshop_context,
)

Runner = Callable[[Sequence[str]], Any]
DEPLOYMENT_QUERY = (
    "{id:id,name:name,state:properties.provisioningState,"
    "timestamp:properties.timestamp,context:properties.outputs.workshopContext.value}"
)


def validate_scope(subscription: str, resource_group: str) -> str:
    if (
        re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", subscription) is None
        or UUID(subscription).int == 0
    ):
        raise WorkshopContextError("Supply a valid nonzero Azure subscription ID.")
    if re.fullmatch(r"[\w.()-]{1,90}", resource_group) is None or resource_group.endswith("."):
        raise WorkshopContextError("Supply the resource group created in Lab 1.")
    return str(UUID(subscription))


def azure_json(arguments: Sequence[str]) -> Any:
    executable = shutil.which("az")
    if executable is None:
        raise WorkshopContextError("Azure CLI is missing. Open the workshop Dev Container.")
    completed = subprocess.run(
        [executable, *arguments, "--only-show-errors", "--output", "json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    if completed.returncode:
        raise WorkshopContextError(
            "Azure CLI could not read the requested deployment. Sign in inside this container "
            "with 'az login --use-device-code', then confirm the subscription/RG and read access."
        )
    try:
        return json.loads(completed.stdout)
    except ValueError as exc:
        raise WorkshopContextError("Azure CLI returned an invalid JSON response.") from exc


def deployment_context(record: Any, subscription: str, resource_group: str) -> dict[str, Any]:
    if not isinstance(record, dict) or record.get("state") != "Succeeded":
        raise WorkshopContextError(
            "The selected deployment has not succeeded. Complete Lab 1 first."
        )
    context = validate_workshop_context(
        record.get("context"),
        expected_subscription_id=subscription,
        expected_resource_group=resource_group,
    )
    prefix = f"/subscriptions/{subscription}/resourceGroups/{resource_group}/providers/"
    name = record.get("name")
    expected = f"{prefix}Microsoft.Resources/deployments/{name}"
    if (
        not isinstance(name, str)
        or re.fullmatch(r"[\w.()-]{1,64}", name) is None
        or not isinstance(record.get("id"), str)
        or record["id"].casefold() != expected.casefold()
    ):
        raise WorkshopContextError("Deployment identity does not match the requested scope.")
    return context


def deployment_timestamp(record: dict[str, Any]) -> datetime:
    try:
        timestamp = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        raise WorkshopContextError("Deployment timestamp is missing or invalid.") from exc
    if timestamp.tzinfo is None:
        raise WorkshopContextError("Deployment timestamp must include a timezone.")
    return timestamp


def select_deployment(records: Any, subscription: str, resource_group: str) -> str:
    if not isinstance(records, list):
        raise WorkshopContextError("Azure CLI did not return a deployment list.")
    candidates = [
        record
        for record in records
        if isinstance(record, dict)
        and isinstance(record.get("context"), dict)
        and record["context"].get("provisioning_method") == "azure-custom-template"
    ]
    if not candidates:
        raise WorkshopContextError(
            "No completed workshopContext output was found. Deploy the current template first."
        )
    dated: list[tuple[datetime, dict[str, Any]]] = []
    projects: set[str] = set()
    for record in candidates:
        context = record["context"]
        if context.get("schema_version") != CONTEXT_SCHEMA_VERSION:
            continue
        dated.append((deployment_timestamp(record), record))
    if not dated:
        raise WorkshopContextError(
            "Only an older workshop context exists. Deploy the current template."
        )
    dated.sort(key=lambda pair: pair[0], reverse=True)
    deployment_context(dated[0][1], subscription, resource_group)
    for record in records:
        if (
            isinstance(record, dict)
            and record.get("state") != "Succeeded"
            and deployment_timestamp(record) >= dated[0][0]
        ):
            raise WorkshopContextError(
                "A newer deployment is incomplete or failed. Confirm Lab 1 before configuring."
            )
    for _, record in dated:
        if record.get("state") == "Succeeded":
            validated = deployment_context(record, subscription, resource_group)
            projects.add(validated["resource_outputs"]["foundry_project_id"]["value"].casefold())
    if len(projects) != 1:
        raise WorkshopContextError(
            "Multiple workshop projects exist in this RG. Specify --deployment explicitly."
        )
    if len(dated) > 1 and dated[0][0] == dated[1][0]:
        raise WorkshopContextError("Deployment selection is ambiguous; specify --deployment.")
    return dated[0][1]["name"]


def save_context(path: Path, context: dict[str, Any]) -> None:
    if path.is_symlink() or path.is_dir() or any(parent.is_symlink() for parent in path.parents):
        raise WorkshopContextError("Context output must be a regular file outside symbolic links.")
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise WorkshopContextError(
                "Existing context is unreadable; move it aside explicitly."
            ) from exc
        validate_workshop_context(
            existing,
            expected_subscription_id=context["subscription_id"],
            expected_resource_group=context["resource_group_name"],
        )
        old_project = existing["resource_outputs"]["foundry_project_id"]["value"]
        new_project = context["resource_outputs"]["foundry_project_id"]["value"]
        if old_project.casefold() != new_project.casefold():
            raise WorkshopContextError(
                "Existing context targets another project; move it aside first."
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(f".{path.name}.{uuid4().hex}.pending")
    try:
        with pending.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(context, ensure_ascii=False, indent=2) + "\n")
        pending.chmod(0o600)
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def configure(
    subscription: str,
    resource_group: str,
    output: Path,
    *,
    deployment: str | None = None,
    runner: Runner = azure_json,
) -> dict[str, Any]:
    subscription = validate_scope(subscription, resource_group)
    scope = ("--subscription", subscription, "--resource-group", resource_group)
    if deployment is not None and re.fullmatch(r"[\w.()-]{1,64}", deployment) is None:
        raise WorkshopContextError("Deployment name is invalid.")
    if deployment is None:
        records = runner(
            ["deployment", "group", "list", *scope, "--query", f"[].{DEPLOYMENT_QUERY}"]
        )
        deployment = select_deployment(records, subscription, resource_group)
    record = runner(
        ["deployment", "group", "show", *scope, "--name", deployment, "--query", DEPLOYMENT_QUERY]
    )
    context = deployment_context(record, subscription, resource_group)
    save_context(output, context)
    return context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--deployment")
    parser.add_argument("--output", type=Path, default=DEFAULT_CONTEXT_PATH)
    args = parser.parse_args(argv)
    try:
        context = configure(
            args.subscription, args.resource_group, args.output, deployment=args.deployment
        )
    except (WorkshopContextError, OSError, subprocess.TimeoutExpired) as exc:
        print(f"configure_workshop.py: {exc}", file=sys.stderr)
        return 2
    print(f"Workshop context saved: {args.output}")
    print(f"Project: {context['resource_outputs']['foundry_project_name']['value']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""scripts/delete_hosted_agent.py

Deletes the Hosted Agent (and all of its versions) created by
``scripts/deploy_hosted_agent.py``, so ``scripts/destroy.sh`` can safely run
``terraform destroy`` afterwards (Terraform does not manage this Foundry
data-plane object -- see docs/architecture.md).

CLI contract (do not change without updating scripts/destroy.sh, which is
out of this script's ownership): ``destroy.sh`` always invokes this script as

    python3 delete_hosted_agent.py --subscription "<id>" --resource-group "<rg>"

and treats any non-zero exit as a hard failure (``set -euo pipefail``). Both
flags are accepted here as required, but the actual delete target (the
Foundry project endpoint and the agent name) is resolved from
``.workshop/context.json``, exactly like ``deploy_hosted_agent.py`` -- never
duplicated or re-derived from the subscription/resource-group alone. The two
flags are still cross-checked against the context file's own
``subscription_id``/``resource_group_name`` as a safety check against running
against a stale or wrong ``.workshop/`` directory.

Idempotency: if the agent does not exist, this exits 0 and reports
``action: "not_found"`` -- a second/duplicate ``destroy.sh`` run (or a
workshop environment that never got as far as Lab 7) must not fail. Any other
error (auth, network, permission) is a real failure and is surfaced with a
non-zero exit and a message on stderr, never silently swallowed.

Design, mirroring scripts/deploy_hosted_agent.py: the delete
orchestration (list versions, delete each, then delete the agent) is a single
function taking an injected client-like object, so it is fully
unit/contract-testable with a fake/mock client -- no real Azure call is made
in tests.

Authentication: az login only, via AzureCliCredential (default) or
DefaultAzureCredential (--credential default). No API keys, connection
strings, or client secrets are read anywhere in this script.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Protocol

# Make the sibling `lib` package (and deploy_hosted_agent.py's shared
# constant) importable regardless of current working directory (scripts/ is
# intentionally not an installed Python package).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from azure.ai.projects import AIProjectClient
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from deploy_hosted_agent import DEFAULT_HOSTED_AGENT_NAME
from lib.workshop_context import (
    DEFAULT_CONTEXT_PATH,
    WorkshopContextError,
    build_credential,
    load_context,
    project_endpoint,
)


class _AgentsClientLike(Protocol):
    """The subset of ``AIProjectClient.agents`` this script calls, factored
    out so tests can pass a plain fake/mock instead of a real SDK client."""

    def get(self, agent_name: str) -> Any: ...

    def list_versions(self, agent_name: str, *, include_drafts: bool | None = None) -> Any: ...

    def delete_version(
        self, agent_name: str, agent_version: str, *, force: bool | None = None
    ) -> Any: ...

    def delete(self, agent_name: str, *, force: bool | None = None) -> Any: ...


# ---------------------------------------------------------------------------
# Pure-ish orchestration (unit/contract-testable with a fake client -- no
# real network access; the only I/O is the injected client's own calls)
# ---------------------------------------------------------------------------


def validate_context_matches(
    context: dict[str, Any], *, subscription_id: str, resource_group_name: str
) -> None:
    """Raise ``WorkshopContextError`` if the CLI-supplied
    ``--subscription``/``--resource-group`` disagree with the values recorded
    in ``.workshop/context.json`` -- catches an accidentally-reused or stale
    context file before it deletes the wrong project's agent.
    """
    context_subscription = context.get("subscription_id")
    context_resource_group = context.get("resource_group_name")
    mismatches = []
    if context_subscription and context_subscription != subscription_id:
        mismatches.append(
            f"--subscription '{subscription_id}' != context.json subscription_id "
            f"'{context_subscription}'"
        )
    if context_resource_group and context_resource_group != resource_group_name:
        mismatches.append(
            f"--resource-group '{resource_group_name}' != context.json resource_group_name "
            f"'{context_resource_group}'"
        )
    if mismatches:
        raise WorkshopContextError(
            "refusing to delete: " + "; ".join(mismatches) + ". Pass matching values, or "
            "re-run ./scripts/setup.sh if this .workshop/ directory is stale."
        )


def delete_agent_and_versions(client: _AgentsClientLike, agent_name: str) -> dict[str, Any]:
    """Delete every version of ``agent_name``, then the agent itself.

    Idempotent: if the agent does not exist at all, returns
    ``action: "not_found"`` without error. Each per-version delete also
    tolerates a concurrent/prior deletion of that specific version
    (``ResourceNotFoundError``) rather than treating it as a failure, since
    the end state (that version no longer exists) is what was asked for
    either way. Any other SDK error (auth, permission, network) propagates
    to the caller unchanged -- this function never broad-catches.
    """
    try:
        client.get(agent_name)
    except ResourceNotFoundError:
        return {
            "agent_name": agent_name,
            "action": "not_found",
            "deleted_versions": [],
            "agent_deleted": False,
        }

    versions = list(client.list_versions(agent_name, include_drafts=True))
    deleted_versions: list[str] = []
    for version in versions:
        try:
            client.delete_version(agent_name, version.version, force=True)
            deleted_versions.append(version.version)
        except ResourceNotFoundError:
            # Already gone (e.g. a concurrent delete) -- the desired end
            # state already holds for this version.
            continue

    try:
        response = client.delete(agent_name, force=True)
        agent_deleted = bool(response.deleted)
    except ResourceNotFoundError:
        # The agent itself was removed already (e.g. by a concurrent run, or
        # because deleting its last version cascaded to it) -- idempotent.
        agent_deleted = True

    return {
        "agent_name": agent_name,
        "action": "deleted",
        "deleted_versions": deleted_versions,
        "agent_deleted": agent_deleted,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--subscription",
        required=True,
        help="Azure subscription ID (must match .workshop/context.json)",
    )
    parser.add_argument(
        "--resource-group",
        required=True,
        help="Resource group name (must match .workshop/context.json)",
    )
    parser.add_argument(
        "--context", type=Path, default=DEFAULT_CONTEXT_PATH, help="Path to .workshop/context.json"
    )
    parser.add_argument(
        "--agent-name",
        default=DEFAULT_HOSTED_AGENT_NAME,
        help="Hosted Agent name to delete (must match what deploy_hosted_agent.py used)",
    )
    parser.add_argument(
        "--credential",
        choices=["azure-cli", "default"],
        default="azure-cli",
        help="Credential source (both are az login-only; default: azure-cli)",
    )
    parser.add_argument(
        "--output", choices=["human", "json"], default="human", help="Output format"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.context.exists():
        # destroy.sh treats a missing context file as "nothing was ever set
        # up" for its own defaults, but this script requires it to resolve
        # the project endpoint safely -- if it's missing there is nothing
        # this script can safely delete, so idempotently report success
        # rather than failing destroy.sh outright.
        result = {
            "agent_name": args.agent_name,
            "action": "not_found",
            "deleted_versions": [],
            "agent_deleted": False,
            "note": f"{args.context} does not exist; nothing to delete.",
        }
        _print_result(result, output=args.output)
        return 0

    try:
        context = load_context(args.context)
        validate_context_matches(
            context,
            subscription_id=args.subscription,
            resource_group_name=args.resource_group,
        )
        endpoint = project_endpoint(context)
    except WorkshopContextError as exc:
        print(f"delete_hosted_agent.py: {exc}", file=sys.stderr)
        return 2

    credential = build_credential(args.credential)
    try:
        with AIProjectClient(endpoint=endpoint, credential=credential) as client:
            result = delete_agent_and_versions(client.agents, args.agent_name)
    except HttpResponseError as exc:
        print(f"delete_hosted_agent.py: Foundry API error deleting agent: {exc}", file=sys.stderr)
        return 1

    _print_result(result, output=args.output)
    return 0


def _print_result(result: dict[str, Any], *, output: str) -> None:
    if output == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(f"agent:  {result['agent_name']}")
    print(f"action: {result['action']}")
    if result["deleted_versions"]:
        print(f"deleted versions: {', '.join(result['deleted_versions'])}")
    print(f"agent deleted: {result['agent_deleted']}")
    if "note" in result:
        print(f"note: {result['note']}")


if __name__ == "__main__":
    raise SystemExit(main())

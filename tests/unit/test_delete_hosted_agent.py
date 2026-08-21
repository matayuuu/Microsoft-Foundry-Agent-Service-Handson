"""Unit tests for scripts/delete_hosted_agent.py.

scripts/ is intentionally not a Python package (see scripts/lib), so the
module under test is loaded directly from its file path via importlib,
matching tests/unit/test_create_toolbox.py. No real Azure call happens here:
``delete_agent_and_versions`` is exercised against small fake ``agents``
operations objects, and the CLI/context-matching logic against plain dicts
and a temporary context file -- never a real ``AIProjectClient``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from azure.core.exceptions import ResourceNotFoundError

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_MODULE_PATH = REPO_ROOT / "scripts" / "deploy_hosted_agent.py"
DELETE_MODULE_PATH = REPO_ROOT / "scripts" / "delete_hosted_agent.py"


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# delete_hosted_agent.py does `from deploy_hosted_agent import
# DEFAULT_HOSTED_AGENT_NAME`, which resolves via scripts/'s own sys.path
# insertion at import time -- pre-load deploy_hosted_agent under the exact
# module name it imports itself as, so that lookup succeeds here too.
_load_module("deploy_hosted_agent", DEPLOY_MODULE_PATH)
delete_hosted_agent = _load_module("delete_hosted_agent", DELETE_MODULE_PATH)


# ---------------------------------------------------------------------------
# delete_agent_and_versions
# ---------------------------------------------------------------------------


class _FakeVersion:
    def __init__(self, version: str) -> None:
        self.version = version


class _FakeDeleteResponse:
    def __init__(self, deleted: bool) -> None:
        self.deleted = deleted


class _FakeAgentsOperations:
    """A minimal stand-in for ``AIProjectClient.agents`` covering only the
    four methods ``delete_agent_and_versions`` calls."""

    def __init__(
        self,
        *,
        exists: bool,
        versions: list[str] | None = None,
        missing_versions: set[str] | None = None,
        agent_already_gone_on_delete: bool = False,
    ) -> None:
        self.exists = exists
        self.versions = versions or []
        self.missing_versions = missing_versions or set()
        self.agent_already_gone_on_delete = agent_already_gone_on_delete
        self.deleted_version_calls: list[str] = []
        self.delete_calls = 0

    def get(self, agent_name: str):
        if not self.exists:
            raise ResourceNotFoundError("agent not found")
        return object()

    def list_versions(self, agent_name: str, *, include_drafts: bool | None = None):
        return [_FakeVersion(v) for v in self.versions]

    def delete_version(self, agent_name: str, agent_version: str, *, force: bool | None = None):
        if agent_version in self.missing_versions:
            raise ResourceNotFoundError("version not found")
        self.deleted_version_calls.append(agent_version)
        return _FakeDeleteResponse(deleted=True)

    def delete(self, agent_name: str, *, force: bool | None = None):
        self.delete_calls += 1
        if self.agent_already_gone_on_delete:
            raise ResourceNotFoundError("agent not found")
        return _FakeDeleteResponse(deleted=True)


def test_delete_agent_and_versions_reports_not_found_when_agent_absent() -> None:
    client = _FakeAgentsOperations(exists=False)

    result = delete_hosted_agent.delete_agent_and_versions(client, "my-agent")

    assert result == {
        "agent_name": "my-agent",
        "action": "not_found",
        "deleted_versions": [],
        "agent_deleted": False,
    }


def test_delete_agent_and_versions_deletes_all_versions_then_agent() -> None:
    client = _FakeAgentsOperations(exists=True, versions=["1", "2", "3"])

    result = delete_hosted_agent.delete_agent_and_versions(client, "my-agent")

    assert result["action"] == "deleted"
    assert result["deleted_versions"] == ["1", "2", "3"]
    assert result["agent_deleted"] is True
    assert client.delete_calls == 1


def test_delete_agent_and_versions_tolerates_version_already_gone() -> None:
    client = _FakeAgentsOperations(exists=True, versions=["1", "2"], missing_versions={"2"})

    result = delete_hosted_agent.delete_agent_and_versions(client, "my-agent")

    # version "2" raced away (ResourceNotFoundError) -- not reported as
    # explicitly deleted by this call, but not treated as a failure either.
    assert result["deleted_versions"] == ["1"]
    assert result["agent_deleted"] is True


def test_delete_agent_and_versions_tolerates_agent_already_gone_on_final_delete() -> None:
    client = _FakeAgentsOperations(exists=True, versions=["1"], agent_already_gone_on_delete=True)

    result = delete_hosted_agent.delete_agent_and_versions(client, "my-agent")

    assert result["deleted_versions"] == ["1"]
    assert result["agent_deleted"] is True  # idempotent: already-gone counts as deleted


def test_delete_agent_and_versions_handles_no_versions() -> None:
    client = _FakeAgentsOperations(exists=True, versions=[])

    result = delete_hosted_agent.delete_agent_and_versions(client, "my-agent")

    assert result["deleted_versions"] == []
    assert result["agent_deleted"] is True


# ---------------------------------------------------------------------------
# validate_context_matches
# ---------------------------------------------------------------------------


def test_validate_context_matches_passes_when_equal() -> None:
    context = {"subscription_id": "sub-1", "resource_group_name": "rg-1"}

    delete_hosted_agent.validate_context_matches(
        context, subscription_id="sub-1", resource_group_name="rg-1"
    )  # must not raise


def test_validate_context_matches_raises_on_subscription_mismatch() -> None:
    context = {"subscription_id": "sub-1", "resource_group_name": "rg-1"}

    with pytest.raises(delete_hosted_agent.WorkshopContextError, match="subscription"):
        delete_hosted_agent.validate_context_matches(
            context, subscription_id="sub-2", resource_group_name="rg-1"
        )


def test_validate_context_matches_raises_on_resource_group_mismatch() -> None:
    context = {"subscription_id": "sub-1", "resource_group_name": "rg-1"}

    with pytest.raises(delete_hosted_agent.WorkshopContextError, match="resource-group"):
        delete_hosted_agent.validate_context_matches(
            context, subscription_id="sub-1", resource_group_name="rg-2"
        )


def test_validate_context_matches_tolerates_missing_context_fields() -> None:
    # An older/partial context.json without these keys should not block a
    # delete -- only an actual mismatch is refused.
    delete_hosted_agent.validate_context_matches(
        {}, subscription_id="sub-1", resource_group_name="rg-1"
    )  # must not raise


# ---------------------------------------------------------------------------
# parse_args (destroy.sh's exact invocation contract)
# ---------------------------------------------------------------------------


def test_parse_args_accepts_destroy_sh_contract() -> None:
    args = delete_hosted_agent.parse_args(
        ["--subscription", "sub-id", "--resource-group", "rg-name"]
    )

    assert args.subscription == "sub-id"
    assert args.resource_group == "rg-name"
    assert args.agent_name == delete_hosted_agent.DEFAULT_HOSTED_AGENT_NAME


def test_parse_args_requires_subscription_and_resource_group() -> None:
    with pytest.raises(SystemExit):
        delete_hosted_agent.parse_args([])


# ---------------------------------------------------------------------------
# main: missing context file is idempotent success (exit 0), not a failure
# ---------------------------------------------------------------------------


def test_main_missing_context_file_is_idempotent_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_context = tmp_path / "context.json"

    exit_code = delete_hosted_agent.main(
        [
            "--subscription",
            "sub-id",
            "--resource-group",
            "rg-name",
            "--context",
            str(missing_context),
            "--output",
            "json",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["action"] == "not_found"

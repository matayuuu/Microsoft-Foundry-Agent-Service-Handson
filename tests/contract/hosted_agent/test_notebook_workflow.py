"""Execute the Lab 8 normal-agent workflow notebook without Azure calls."""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import IPython.display
import pytest
import travel_agents
import workflow
from agent_framework import WorkflowViz
from fakes import (
    INTAKE_RESPONSE,
    POLICY_RESPONSE,
    REVIEWER_RESPONSE,
    ScriptedChatClient,
)

from scripts.lib import workshop_runtime as runtime
from scripts.lib.workshop_context import WorkshopContextError

REPO_ROOT = Path(__file__).resolve().parents[3]
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "08-hosted-agent.ipynb"


class _Credential:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _policy_lookup(query: str) -> str:
    return f"synthetic policy for {query}"


async def execute_cells(
    namespace: dict[str, Any],
    *,
    stop_after: str | None = None,
) -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code" or cell["id"] == "test-workflow":
            continue
        code = compile(
            "".join(cell["source"]),
            f"{NOTEBOOK_PATH.name}:{cell['id']}",
            "exec",
            flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
        )
        result = eval(code, namespace)
        if inspect.isawaitable(result):
            await result
        if cell["id"] == stop_after:
            break


@pytest.fixture
def notebook_namespace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    chat_client: ScriptedChatClient,
) -> dict[str, Any]:
    source = tmp_path / "src" / "hosted-agent"
    source.mkdir(parents=True)
    source.joinpath("workflow.py").write_text("# marker\n", encoding="utf-8")
    context_dir = tmp_path / ".workshop"
    context_dir.mkdir()
    context_dir.joinpath("context.json").write_text(
        (REPO_ROOT / "tests" / "fixtures" / "workshop-context.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    for name in (
        "WORKSHOP_CREDENTIAL_MODE",
        "FOUNDRY_PROJECT_ENDPOINT",
        "FOUNDRY_MODEL",
        "AZURE_AI_SEARCH_SERVICE_ENDPOINT",
        "AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME",
    ):
        monkeypatch.delenv(name, raising=False)

    def check_kernel(spec: runtime.EnvironmentSpec) -> None:
        assert spec == runtime.HOSTED_ENVIRONMENT

    monkeypatch.setattr(runtime, "require_current_runtime", check_kernel)
    credential = _Credential()
    chat_client.include_policy_tool_events = True
    monkeypatch.setattr(travel_agents, "create_credential", lambda: credential)
    monkeypatch.setattr(
        travel_agents,
        "create_chat_client",
        lambda supplied: chat_client if supplied is credential else None,
    )
    monkeypatch.setattr(
        travel_agents,
        "create_foundry_iq_tool",
        lambda supplied: _policy_lookup if supplied is credential else None,
    )
    displayed: list[Any] = []
    monkeypatch.setattr(IPython.display, "display", displayed.append)
    return {
        "credential": credential,
        "displayed": displayed,
        "policy_tool": _policy_lookup,
        "input": lambda _: "",
    }


def test_notebook_runs_three_normal_agents_in_sequential_order(
    notebook_namespace: dict[str, Any],
    chat_client: ScriptedChatClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)

    def unexpected(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Run All without confirmation must not launch management commands")

    monkeypatch.setattr(subprocess, "run", unexpected)
    asyncio.run(execute_cells(notebook_namespace))

    assert notebook_namespace["expected_order"] == [
        "intake_agent",
        "policy_agent",
        "reviewer_agent",
    ]
    assert notebook_namespace["execution_order"] == notebook_namespace["expected_order"]
    assert notebook_namespace["intermediate_answers"] == {
        "intake_agent": INTAKE_RESPONSE,
        "policy_agent": POLICY_RESPONSE,
    }
    assert notebook_namespace["policy_actions"] == {"knowledge_base_retrieve"}
    assert notebook_namespace["answer"] == REVIEWER_RESPONSE
    assert [call["messages"] for call in chat_client.calls] == [
        [workflow.SAMPLE_REQUEST],
        [workflow.SAMPLE_REQUEST, INTAKE_RESPONSE],
        [workflow.SAMPLE_REQUEST, INTAKE_RESPONSE, POLICY_RESPONSE],
    ]
    deployed = workflow.build_workflow(
        chat_client=ScriptedChatClient(),
        foundry_iq_tool=_policy_lookup,
        observe_intermediate=True,
    )
    mermaid = WorkflowViz(deployed).to_mermaid()
    assert "policy_agent" in mermaid
    assert "travel_harness_agent" not in mermaid
    assert notebook_namespace["credential"].closed is True


def test_notebook_uses_normal_policy_agent_before_building_workflow() -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    cell_ids = [cell["id"] for cell in notebook["cells"]]

    expected_sequence = [
        "configure-environment",
        "create-participants",
        "build-workflow",
        "visualize-workflow",
        "invoke-workflow",
        "assert-output",
        "inspect-deployment-source",
        "test-workflow",
        "close-resources",
        "deploy-next",
    ]
    positions = [cell_ids.index(cell_id) for cell_id in expected_sequence]

    assert positions == sorted(positions)
    text = NOTEBOOK_PATH.read_text(encoding="utf-8")
    assert "policy_agent" in text
    assert "POLICY_AGENT_INSTRUCTIONS" in text
    assert "knowledge_base_retrieve" in text
    assert "travel_harness_agent" not in text
    assert "build_environment_harness_agent" not in text
    assert "intermediate_output_from" in text
    assert "deploy_hosted_agent.py" in text


def test_notebook_rejects_policy_response_without_retrieval_evidence(
    notebook_namespace: dict[str, Any],
    chat_client: ScriptedChatClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    chat_client.include_policy_tool_events = False

    with pytest.raises(AssertionError, match="Foundry IQ"):
        asyncio.run(execute_cells(notebook_namespace))


def test_notebook_explains_missing_setup(
    notebook_namespace: dict[str, Any],
) -> None:
    Path(".workshop", "context.json").unlink()

    with pytest.raises(FileNotFoundError, match=r"00-setup\.ipynb"):
        asyncio.run(execute_cells(notebook_namespace, stop_after="configure-environment"))


@pytest.mark.parametrize("cancellation", [EOFError, KeyboardInterrupt])
def test_run_all_cancellation_never_launches_management_commands(
    notebook_namespace: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    cancellation: type[BaseException],
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)

    def cancelled(_: str) -> str:
        raise cancellation

    def unexpected(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Cancellation must not deploy or delete")

    notebook_namespace["input"] = cancelled
    monkeypatch.setattr(subprocess, "run", unexpected)
    asyncio.run(execute_cells(notebook_namespace))
    assert notebook_namespace["credential"].closed is True


@pytest.mark.parametrize("field,value", [("schema_version", "1.0"), ("setup_status", "pending")])
def test_notebook_rejects_old_or_incomplete_context_before_agent_creation(
    notebook_namespace: dict[str, Any], field: str, value: str
) -> None:
    path = Path(".workshop", "context.json")
    context = json.loads(path.read_text(encoding="utf-8"))
    context[field] = value
    path.write_text(json.dumps(context), encoding="utf-8")

    with pytest.raises(WorkshopContextError):
        asyncio.run(execute_cells(notebook_namespace, stop_after="configure-environment"))

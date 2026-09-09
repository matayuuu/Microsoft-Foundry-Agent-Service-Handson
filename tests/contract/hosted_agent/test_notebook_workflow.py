"""Execute the Lab 8 workflow notebook with network-free participants."""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import IPython.display
import pytest
import travel_agents
import workflow
from agent_framework import WorkflowViz
from fakes import (
    HARNESS_RESPONSE,
    INTAKE_RESPONSE,
    REVIEWER_RESPONSE,
    ScriptedChatClient,
    build_scripted_harness_agent,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "08-hosted-agent.ipynb"


class _Credential:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


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
        json.dumps(
            {
                "terraform_outputs": {
                    "foundry_project_endpoint": {"value": "https://project.example.invalid"},
                    "primary_model_deployment_name": {"value": "synthetic-model"},
                    "search_service_endpoint": {"value": "https://search.example.invalid"},
                    "foundry_project_name": {"value": "synthetic-project"},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    credential = _Credential()
    chat_client.include_harness_tool_events = True
    harness_agent = build_scripted_harness_agent(chat_client)
    monkeypatch.setattr(travel_agents, "create_credential", lambda: credential)
    monkeypatch.setattr(
        travel_agents,
        "create_chat_client",
        lambda supplied: chat_client if supplied is credential else None,
    )
    monkeypatch.setattr(
        travel_agents,
        "build_environment_harness_agent",
        lambda **kwargs: (
            harness_agent
            if kwargs["default_mode"] == "execute"
            and kwargs["hosted"] is True
            and kwargs["file_memory_store"] is not None
            else None
        ),
    )
    displayed: list[Any] = []
    monkeypatch.setattr(IPython.display, "display", displayed.append)
    return {
        "credential": credential,
        "displayed": displayed,
        "harness_agent": harness_agent,
    }


def test_notebook_runs_shared_harness_in_sequential_order(
    notebook_namespace: dict[str, Any],
    chat_client: ScriptedChatClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)

    asyncio.run(execute_cells(notebook_namespace))

    assert notebook_namespace["expected_order"] == [
        "intake_agent",
        "travel_harness_agent",
        "reviewer_agent",
    ]
    assert notebook_namespace["execution_order"] == notebook_namespace["expected_order"]
    assert notebook_namespace["intermediate_answers"] == {
        "intake_agent": INTAKE_RESPONSE,
        "travel_harness_agent": HARNESS_RESPONSE,
    }
    assert notebook_namespace["answer"] == REVIEWER_RESPONSE
    assert [call["messages"] for call in chat_client.calls] == [
        [workflow.SAMPLE_REQUEST],
        [workflow.SAMPLE_REQUEST, INTAKE_RESPONSE],
        [workflow.SAMPLE_REQUEST, INTAKE_RESPONSE, HARNESS_RESPONSE],
    ]
    deployed = workflow.build_workflow(
        chat_client=ScriptedChatClient(),
        harness_agent=build_scripted_harness_agent(ScriptedChatClient()),
        observe_intermediate=True,
    )
    assert "travel_harness_agent" in WorkflowViz(deployed).to_mermaid()
    assert notebook_namespace["credential"].closed is True


def test_notebook_uses_shared_harness_factory_before_building_workflow() -> None:
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
    assert "build_environment_harness_agent" in text
    assert 'default_mode=\\"execute\\"' in text
    assert "intermediate_output_from" in text
    assert "deploy_hosted_agent.py" in text


def test_notebook_rejects_a_text_only_harness_response(
    notebook_namespace: dict[str, Any],
    chat_client: ScriptedChatClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    chat_client.include_harness_tool_events = False

    with pytest.raises(AssertionError, match="Skill"):
        asyncio.run(execute_cells(notebook_namespace))


def test_notebook_explains_missing_setup(
    notebook_namespace: dict[str, Any],
) -> None:
    Path(".workshop", "context.json").unlink()

    with pytest.raises(FileNotFoundError, match="Lab 1"):
        asyncio.run(execute_cells(notebook_namespace, stop_after="configure-environment"))

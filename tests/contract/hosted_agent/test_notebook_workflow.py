"""Execute the learning cells with real orchestration and a network-free client."""

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
from xml.etree import ElementTree

import IPython.display
import pytest
import workflow
from agent_framework import WorkflowViz
from fakes import (
    PLANNER_RESPONSE,
    POLICY_RESPONSE,
    REVIEWER_RESPONSE,
    ScriptedChatClient,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "07-hosted-agent.ipynb"


async def execute_cells(
    namespace: dict[str, Any],
    *,
    only: set[str] | None = None,
    stop_after: str | None = None,
) -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    for cell in notebook["cells"]:
        # Running pytest from inside pytest would recursively invoke this test.
        if cell["cell_type"] != "code" or cell["id"] == "test-workflow":
            continue
        if only is not None and cell["id"] not in only:
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
    shutil.copyfile(REPO_ROOT / "src" / "hosted-agent" / "workflow.py", source / "workflow.py")
    context_dir = tmp_path / ".workshop"
    context_dir.mkdir()
    context_dir.joinpath("context.json").write_text(
        json.dumps(
            {
                "terraform_outputs": {
                    "foundry_project_endpoint": {
                        "value": "https://example.invalid/api/projects/test"
                    },
                    "primary_model_deployment_name": {"value": "synthetic-model"},
                    "foundry_project_name": {"value": "synthetic-project"},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    monkeypatch.setenv(workflow.FOUNDRY_PROJECT_ENDPOINT_ENV, "unused")
    monkeypatch.setenv(workflow.FOUNDRY_MODEL_ENV, "unused")
    monkeypatch.setattr(workflow, "create_chat_client", lambda: chat_client)
    displayed: list[Any] = []
    monkeypatch.setattr(IPython.display, "display", displayed.append)
    return {"displayed": displayed}


def test_notebook_executes_agents_graph_observation_and_cases_in_order(
    notebook_namespace: dict[str, Any],
    chat_client: ScriptedChatClient,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)

    asyncio.run(execute_cells(notebook_namespace))

    assert chat_client.created_agents == ["policy_agent", "planner_agent", "reviewer_agent"]
    assert notebook_namespace["execution_order"] == [
        "policy_agent",
        "planner_agent",
        "reviewer_agent",
    ]
    assert notebook_namespace["intermediate_answers"] == {
        "policy_agent": POLICY_RESPONSE,
        "planner_agent": PLANNER_RESPONSE,
    }
    assert notebook_namespace["answer"] == REVIEWER_RESPONSE
    assert len(notebook_namespace["final_chunks"]) >= 2
    assert "".join(notebook_namespace["final_chunks"]) == REVIEWER_RESPONSE
    # These scripted answers exercise the cells, not the model's policy judgement.
    assert notebook_namespace["case_results"] == {
        "入力不足": REVIEWER_RESPONSE,
        "海外・business": REVIEWER_RESPONSE,
    }
    requests = [workflow.SAMPLE_REQUEST] + [
        case["request"] for case in notebook_namespace["test_cases"]
    ]
    assert len(chat_client.calls) == 9
    for index, request in enumerate(requests):
        policy, planner, reviewer = chat_client.calls[index * 3 : index * 3 + 3]
        assert policy["messages"] == [request]
        assert planner["messages"] == [request, POLICY_RESPONSE]
        assert reviewer["messages"] == [request, POLICY_RESPONSE, PLANNER_RESPONSE]
        assert [call["instructions"] for call in (policy, planner, reviewer)] == [
            workflow.POLICY_AGENT_INSTRUCTIONS,
            workflow.PLANNER_AGENT_INSTRUCTIONS,
            workflow.REVIEWER_AGENT_INSTRUCTIONS,
        ]

    console = capsys.readouterr().out
    assert "グラフ画像は未生成" in console
    for name in chat_client.created_agents:
        assert f"開始: {name}" in console
    for name in ("policy_agent", "planner_agent"):
        assert f"--- {name} の途中回答 ---" in console
    assert "--- reviewer_agent の途中回答 ---" not in console

    deployed_workflow = workflow.build_workflow(chat_client=ScriptedChatClient())
    assert notebook_namespace["mermaid_graph"] == WorkflowViz(deployed_workflow).to_mermaid()
    deployed_agent = deployed_workflow.as_agent(name=workflow.WORKFLOW_NAME)
    assert asyncio.run(deployed_agent.run(workflow.SAMPLE_REQUEST)).text == REVIEWER_RESPONSE

    asyncio.run(execute_cells(notebook_namespace, only={"invoke-workflow", "assert-output"}))
    assert len(chat_client.calls) == 12
    assert chat_client.calls[9]["messages"] == [workflow.SAMPLE_REQUEST]
    assert "".join(notebook_namespace["final_chunks"]) == REVIEWER_RESPONSE


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz is installed by Codespace setup")
def test_notebook_renders_its_actual_graph_as_inline_svg(
    notebook_namespace: dict[str, Any],
    chat_client: ScriptedChatClient,
) -> None:
    asyncio.run(execute_cells(notebook_namespace, stop_after="visualize-workflow"))

    images = [
        item for item in notebook_namespace["displayed"] if isinstance(item, IPython.display.SVG)
    ]
    assert len(images) == 1
    root = ElementTree.fromstring(images[0].data)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    labels = "".join(root.itertext())
    for name in ("policy_agent", "planner_agent", "reviewer_agent"):
        assert name in labels
    edges = root.findall(".//{http://www.w3.org/2000/svg}path")
    assert len(edges) >= 3
    assert chat_client.calls == []


def test_notebook_does_not_keep_a_stale_answer_after_model_failure(
    notebook_namespace: dict[str, Any],
    chat_client: ScriptedChatClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    asyncio.run(execute_cells(notebook_namespace, stop_after="assert-output"))
    assert notebook_namespace["answer"] == REVIEWER_RESPONSE

    def fail_response(_: str) -> str:
        raise RuntimeError("Synthetic model failure")

    monkeypatch.setattr(chat_client, "_response_for", fail_response)
    with pytest.raises(RuntimeError, match="Synthetic model failure"):
        asyncio.run(execute_cells(notebook_namespace, only={"invoke-workflow"}))
    assert notebook_namespace["answer"] is None
    assert notebook_namespace["final_chunks"] == []


def test_notebook_surfaces_graphviz_errors(
    notebook_namespace: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: "synthetic-dot")

    def fail_render(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        assert args == ["synthetic-dot", "-Tsvg"]
        return subprocess.CompletedProcess(args, 1, "", "Synthetic SVG rendering failure")

    monkeypatch.setattr(subprocess, "run", fail_render)
    with pytest.raises(subprocess.CalledProcessError):
        asyncio.run(execute_cells(notebook_namespace, stop_after="visualize-workflow"))
    assert "Synthetic SVG rendering failure" in capsys.readouterr().out
    assert notebook_namespace["displayed"] == []


def test_notebook_detects_omitted_notice_without_rewriting_the_answer(
    notebook_namespace: dict[str, Any],
    chat_client: ScriptedChatClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    reviewer_answer = "規程確認\n概算\n次のアクション"

    def omit_notice(instructions: str) -> str:
        if instructions == workflow.REVIEWER_AGENT_INSTRUCTIONS:
            return reviewer_answer
        return ScriptedChatClient._response_for(instructions)

    monkeypatch.setattr(chat_client, "_response_for", omit_notice)
    asyncio.run(execute_cells(notebook_namespace, stop_after="invoke-workflow"))
    assert notebook_namespace["answer"] == reviewer_answer
    with pytest.raises(AssertionError):
        asyncio.run(execute_cells(notebook_namespace, only={"assert-output"}))


def test_notebook_explains_missing_setup(
    notebook_namespace: dict[str, Any],
) -> None:
    Path(".workshop", "context.json").unlink()
    with pytest.raises(FileNotFoundError, match="Lab 1"):
        asyncio.run(execute_cells(notebook_namespace, only={"configure-environment"}))

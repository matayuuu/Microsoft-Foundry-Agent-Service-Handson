from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

NOTEBOOKS = {
    "04-create-toolbox.ipynb": {
        "kernel": "foundry-workshop",
        "required_text": [
            "ensure_toolbox",
            "contoso-travel-toolbox",
            "travel_ops_api",
        ],
    },
    "07-hosted-agent.ipynb": {
        "kernel": "foundry-hosted-agent",
        "required_text": [
            "chat_client.as_agent",
            "SequentialBuilder",
            "WorkflowViz",
            "intermediate_output_from",
            "travel_workflow.run",
            "deploy_hosted_agent.py",
        ],
    },
}


@pytest.mark.parametrize("filename", NOTEBOOKS)
def test_participant_notebook_is_clean_and_uses_expected_kernel(filename: str) -> None:
    notebook_path = REPO_ROOT / "notebooks" / filename
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))

    assert notebook["nbformat"] == 4
    assert notebook["metadata"]["kernelspec"]["name"] == NOTEBOOKS[filename]["kernel"]
    assert notebook["cells"][0]["cell_type"] == "markdown"

    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is None
            assert cell["outputs"] == []
            compile(
                "".join(cell["source"]),
                f"{filename}:{cell['id']}",
                "exec",
                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            )


@pytest.mark.parametrize("filename", NOTEBOOKS)
def test_participant_notebook_contains_required_workshop_steps(filename: str) -> None:
    notebook_path = REPO_ROOT / "notebooks" / filename
    text = notebook_path.read_text(encoding="utf-8")

    for required in NOTEBOOKS[filename]["required_text"]:
        assert required in text


def test_codespace_installs_both_notebook_kernels() -> None:
    post_create = (REPO_ROOT / ".devcontainer" / "post-create.sh").read_text(encoding="utf-8")

    assert "--name foundry-workshop" in post_create
    assert "--name foundry-hosted-agent" in post_create


def test_hosted_notebook_builds_and_tests_before_deployment_guidance() -> None:
    notebook = json.loads(
        (REPO_ROOT / "notebooks" / "07-hosted-agent.ipynb").read_text(encoding="utf-8")
    )
    cell_ids = [cell["id"] for cell in notebook["cells"]]
    assert len(cell_ids) == len(set(cell_ids))
    learning_sequence = [
        "configure-environment",
        "create-client",
        "create-policy-agent",
        "create-planner-agent",
        "create-reviewer-agent",
        "build-workflow",
        "visualize-workflow",
        "set-request",
        "invoke-workflow",
        "assert-output",
        "test-input-variants",
        "test-workflow",
        "inspect-deployment-source",
        "deploy-next",
    ]
    positions = [cell_ids.index(cell_id) for cell_id in learning_sequence]
    assert positions == sorted(positions)

    code = "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )
    assert "deploy_hosted_agent.py" not in code
    assert "run_workflow(" not in code


def test_codespace_installs_local_workflow_graph_renderer() -> None:
    post_create = (REPO_ROOT / ".devcontainer" / "post-create.sh").read_text(encoding="utf-8")
    assert "apt-get install --yes --no-install-recommends jq graphviz" in post_create

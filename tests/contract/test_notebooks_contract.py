from __future__ import annotations

import ast
import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

NOTEBOOKS = {
    "00-azureml-setup.ipynb": {
        "kernel": "python310-sdkv2",
        "required_text": [
            "setup_azureml.py",
            "Python (Foundry Workshop)",
            "Python (Foundry Hosted Agent)",
            "resource_outputs",
            "az login --use-device-code",
            "Labs 7 / 8",
        ],
    },
    "04-create-toolbox.ipynb": {
        "kernel": "foundry-workshop",
        "required_text": [
            "ensure_toolbox",
            "contoso-travel-toolbox",
            "travel_ops_api",
            "get_openai_client(agent_name=AGENT_NAME)",
            "responses.create",
            "Conversation ID",
            "conversations.items.list",
            "mcp_call",
            "total_estimate",
        ],
    },
    "07-agent-framework-harness.ipynb": {
        "kernel": "foundry-hosted-agent",
        "required_text": [
            "build_plain_travel_agent",
            "create_harness_agent",
            "Foundry IQ",
            "Toolbox",
            "todos",
            "Lab 8",
        ],
    },
    "08-hosted-agent.ipynb": {
        "kernel": "foundry-hosted-agent",
        "required_text": [
            "chat_client.as_agent",
            "policy_agent",
            "POLICY_AGENT_INSTRUCTIONS",
            "knowledge_base_retrieve",
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


def test_azureml_setup_installs_both_notebook_kernels_and_graphviz() -> None:
    setup = (REPO_ROOT / "scripts" / "setup_azureml.py").read_text(encoding="utf-8")

    assert 'name="foundry-workshop"' in setup
    assert 'name="foundry-hosted-agent"' in setup
    assert '"graphviz"' in setup
    assert '"sudo"' not in setup


def test_hosted_notebook_builds_and_tests_before_deployment_guidance() -> None:
    notebook = json.loads(
        (REPO_ROOT / "notebooks" / "08-hosted-agent.ipynb").read_text(encoding="utf-8")
    )
    cell_ids = [cell["id"] for cell in notebook["cells"]]
    assert len(cell_ids) == len(set(cell_ids))
    learning_sequence = [
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
        "management-runner",
        "deploy-hosted-agent",
        "delete-hosted-agent",
    ]
    positions = [cell_ids.index(cell_id) for cell_id in learning_sequence]
    assert positions == sorted(positions)

    code = "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )
    assert "deploy_hosted_agent.py" in code
    assert "delete_hosted_agent.py" in code
    assert '"foundry-workshop"' in code
    assert "--no-capture-output" in code
    assert "run_workflow(" not in code
    assert "travel_harness_agent" not in code
    assert "build_environment_harness_agent" not in code


def test_azureml_setup_notebook_verifies_template_handoff_before_install() -> None:
    notebook = json.loads(
        (REPO_ROOT / "notebooks" / "00-azureml-setup.ipynb").read_text(encoding="utf-8")
    )
    ids = [cell["id"] for cell in notebook["cells"]]
    expected = [
        "find-bundle-root",
        "verify-context",
        "install-kernels",
        "select-kernels",
    ]
    assert [ids.index(cell_id) for cell_id in expected] == sorted(
        ids.index(cell_id) for cell_id in expected
    )
    text = json.dumps(notebook)
    assert "terraform_outputs" not in text
    assert "client_secret" not in text
    verify_code = "".join(notebook["cells"][ids.index("verify-context")]["source"])
    assert 'context.get("setup_status") != "complete"' in verify_code
    assert 'context.get("resource_outputs")' in verify_code
    assert "az login --use-device-code" in text


def hosted_cell_source(cell_id: str) -> str:
    notebook = json.loads(
        (REPO_ROOT / "notebooks" / "08-hosted-agent.ipynb").read_text(encoding="utf-8")
    )
    cell = next(cell for cell in notebook["cells"] if cell["id"] == cell_id)
    assert cell["cell_type"] == "code"
    return "".join(cell["source"])


def test_hosted_deploy_and_delete_cells_require_explicit_confirmation() -> None:
    calls: list[tuple[object, ...]] = []
    namespace = {
        "HOSTED_AGENT_NAME": "contoso-travel-hosted-planner",
        "input": lambda _: "",
        "run_management_script": lambda *arguments: calls.append(arguments),
    }
    exec(hosted_cell_source("deploy-hosted-agent"), namespace)
    exec(hosted_cell_source("delete-hosted-agent"), namespace)
    assert calls == []


def test_hosted_cells_pass_scoped_context_and_consistent_agent_name(tmp_path: Path) -> None:
    calls: list[tuple[object, ...]] = []
    name = "contoso-travel-hosted-planner"
    namespace = {
        "HOSTED_AGENT_NAME": name,
        "REPO_ROOT": tmp_path,
        "context": {"subscription_id": "test-subscription", "resource_group_name": "test-rg"},
        "input": lambda _: "DEPLOY",
        "run_management_script": lambda *arguments: calls.append(arguments),
    }
    exec(hosted_cell_source("deploy-hosted-agent"), namespace)
    namespace["input"] = lambda _: name
    exec(hosted_cell_source("delete-hosted-agent"), namespace)
    assert calls[0][:3] == ("deploy_hosted_agent.py", "--agent-name", name)
    assert calls[1] == (
        "delete_hosted_agent.py",
        "--agent-name",
        name,
        "--subscription",
        "test-subscription",
        "--resource-group",
        "test-rg",
        "--output",
        "json",
    )


def test_hosted_management_runner_uses_separate_sdk_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs["cwd"] == tmp_path
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(shutil, "which", lambda _: "conda")
    monkeypatch.setattr(subprocess, "run", run)
    context = tmp_path / ".workshop" / "context.json"
    namespace = {"REPO_ROOT": tmp_path, "context_path": context}
    exec(hosted_cell_source("management-runner"), namespace)
    namespace["run_management_script"]("deploy_hosted_agent.py", "--output", "json")
    assert calls[0] == [
        "conda",
        "run",
        "--no-capture-output",
        "--name",
        "foundry-workshop",
        "python",
        str(tmp_path / "scripts" / "deploy_hosted_agent.py"),
        "--context",
        str(context),
        "--output",
        "json",
    ]

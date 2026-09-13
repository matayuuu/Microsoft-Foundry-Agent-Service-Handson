from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.lib import workshop_runtime as runtime
from scripts.lib.workshop_context import WorkshopContextError

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTEXT_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "workshop-context.json"

NOTEBOOKS = {
    "00-setup.ipynb": {
        "kernel": "foundry-workshop",
        "required_text": [
            "configure_workshop.py",
            "Python (Foundry Workshop)",
            "Python (Foundry Hosted Agent)",
            "resource_outputs",
            "az login --use-device-code",
            "Labs 7 / 8",
            "Codespaces",
            "Dev Container",
            "--subscription",
            "--resource-group",
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
    cell_ids = [cell["id"] for cell in notebook["cells"]]
    assert len(cell_ids) == len(set(cell_ids))

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


@pytest.mark.parametrize("filename", NOTEBOOKS)
def test_notebooks_use_only_shared_container_and_current_context(filename: str) -> None:
    notebook = json.loads((REPO_ROOT / "notebooks" / filename).read_text(encoding="utf-8"))
    text = json.dumps(notebook)
    for retired in ("Azure ML", "azureml", "Conda", "conda", "User files", "BUNDLE_ROOT"):
        assert retired not in text
    code = "\n".join(
        "".join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"
    )
    assert "require_current_runtime(" in code
    assert "validate_workshop_context(" in code
    assert "pip install" not in code
    assert "setup_dev_environment.py" not in code
    assert "az login" not in code
    assert "get-access-token" not in code


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
    assert "get_runtime_python(WORKSHOP_ENVIRONMENT)" in code
    assert "current_context != context" in code
    assert "--context" in code
    assert "Foundry Playground" in json.dumps(notebook)
    assert "run_workflow(" not in code
    assert "travel_harness_agent" not in code
    assert "build_environment_harness_agent" not in code


def test_setup_notebook_reads_completed_deployment_after_two_explicit_inputs() -> None:
    notebook = json.loads((REPO_ROOT / "notebooks" / "00-setup.ipynb").read_text(encoding="utf-8"))
    ids = [cell["id"] for cell in notebook["cells"]]
    expected = [
        "find-repository",
        "workshop-inputs",
        "configure-workshop",
        "verify-context",
        "select-kernels",
    ]
    assert [ids.index(cell_id) for cell_id in expected] == sorted(
        ids.index(cell_id) for cell_id in expected
    )
    text = json.dumps(notebook)
    assert "terraform_outputs" not in text
    assert "client_secret" not in text
    verify_code = "".join(notebook["cells"][ids.index("verify-context")]["source"])
    assert "validate_workshop_context(" in verify_code
    assert "expected_subscription_id=subscription_id" in verify_code
    assert "expected_resource_group=resource_group_name" in verify_code
    assert "context['resource_outputs']" in verify_code
    assert "az login --use-device-code" in text
    input_tree = ast.parse(notebook_cell_source("00-setup.ipynb", "workshop-inputs"))
    variables = {
        target.id
        for node in input_tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert variables == {"subscription_id", "resource_group_name"}


def notebook_cell_source(filename: str, cell_id: str) -> str:
    notebook = json.loads((REPO_ROOT / "notebooks" / filename).read_text(encoding="utf-8"))
    cell = next(cell for cell in notebook["cells"] if cell["id"] == cell_id)
    assert cell["cell_type"] == "code"
    return "".join(cell["source"])


def hosted_cell_source(cell_id: str) -> str:
    return notebook_cell_source("08-hosted-agent.ipynb", cell_id)


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


@pytest.fixture
def management_namespace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    context = json.loads(CONTEXT_FIXTURE.read_text(encoding="utf-8"))
    path = tmp_path / ".workshop" / "context.json"
    path.parent.mkdir()
    path.write_text(json.dumps(context), encoding="utf-8")
    python = tmp_path / "envs" / "foundry-workshop" / "bin" / "python"

    def management_python(spec: runtime.EnvironmentSpec) -> Path:
        assert spec == runtime.WORKSHOP_ENVIRONMENT
        return python

    monkeypatch.setattr(runtime, "get_runtime_python", management_python)
    namespace = {
        "REPO_ROOT": tmp_path,
        "context_path": path,
        "context": context,
        "expected_python": python,
    }
    exec(hosted_cell_source("management-runner"), namespace)
    return namespace


def test_hosted_management_runner_uses_separate_sdk_environment(
    management_namespace: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs["cwd"] == management_namespace["REPO_ROOT"]
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    management_namespace["run_management_script"]("deploy_hosted_agent.py", "--output", "json")
    assert calls[0] == [
        str(management_namespace["expected_python"]),
        str(management_namespace["REPO_ROOT"] / "scripts" / "deploy_hosted_agent.py"),
        "--context",
        str(management_namespace["context_path"]),
        "--output",
        "json",
    ]


@pytest.mark.parametrize("cancellation", [EOFError, KeyboardInterrupt])
def test_hosted_confirmation_cancellation_never_deploys_or_deletes(
    cancellation: type[BaseException],
) -> None:
    calls: list[tuple[object, ...]] = []

    def cancelled(_: str) -> str:
        raise cancellation

    namespace = {
        "HOSTED_AGENT_NAME": "contoso-travel-hosted-planner",
        "input": cancelled,
        "run_management_script": lambda *arguments: calls.append(arguments),
    }
    exec(hosted_cell_source("deploy-hosted-agent"), namespace)
    exec(hosted_cell_source("delete-hosted-agent"), namespace)
    assert calls == []


@pytest.mark.parametrize(
    "replacement",
    [
        ("rg-workshop", "rg-other"),
        ("99999999-8888-4777-8666-555555555555", "88888888-8888-4777-8666-555555555555"),
    ],
)
def test_management_runner_rejects_context_scope_changed_after_confirmation(
    management_namespace: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    replacement: tuple[str, str],
) -> None:
    path = management_namespace["context_path"]
    path.write_text(path.read_text(encoding="utf-8").replace(*replacement), encoding="utf-8")

    def unexpected(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("management script must not run for a changed scope")

    monkeypatch.setattr(subprocess, "run", unexpected)
    with pytest.raises(WorkshopContextError, match="requested subscription/RG"):
        management_namespace["run_management_script"]("deploy_hosted_agent.py")


def test_management_runner_rejects_other_context_changes(
    management_namespace: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    path = management_namespace["context_path"]
    context = json.loads(path.read_text(encoding="utf-8"))
    original = context["source_revision"]
    path.write_text(path.read_text(encoding="utf-8").replace(original, "a" * 40), encoding="utf-8")

    def unexpected(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("management script must not run for a changed context")

    monkeypatch.setattr(subprocess, "run", unexpected)
    with pytest.raises(RuntimeError, match="接続設定が変更"):
        management_namespace["run_management_script"]("deploy_hosted_agent.py")


def test_management_runner_surfaces_script_failure(
    management_namespace: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 2, "synthetic output", "synthetic failure"
        ),
    )
    with pytest.raises(subprocess.CalledProcessError):
        management_namespace["run_management_script"]("deploy_hosted_agent.py")
    output = capsys.readouterr().out
    assert "synthetic output" in output
    assert "synthetic failure" in output


def test_management_runner_does_not_fall_back_when_management_venv_is_missing(
    management_namespace: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing(_: runtime.EnvironmentSpec) -> Path:
        raise runtime.WorkshopRuntimeError("management venv is missing")

    def unexpected(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Hosted interpreter must not be used as a fallback")

    management_namespace["get_runtime_python"] = missing
    monkeypatch.setattr(subprocess, "run", unexpected)
    with pytest.raises(runtime.WorkshopRuntimeError, match="management venv is missing"):
        management_namespace["run_management_script"]("deploy_hosted_agent.py")


def test_setup_notebook_finds_checkout_from_notebooks_and_runs_scoped_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "configure_workshop.py").touch()
    (tmp_path / "pyproject.toml").touch()
    notebooks = tmp_path / "notebooks"
    notebooks.mkdir()
    monkeypatch.chdir(notebooks)
    monkeypatch.setattr(sys, "path", sys.path.copy())
    context = json.loads(CONTEXT_FIXTURE.read_text(encoding="utf-8"))
    python = tmp_path / "envs" / "foundry-workshop" / "bin" / "python"
    checked: list[runtime.EnvironmentSpec] = []
    monkeypatch.setattr(runtime, "require_current_runtime", checked.append)
    monkeypatch.setattr(runtime, "get_runtime_python", lambda _: python)
    calls: list[list[str]] = []

    def configure(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert kwargs["cwd"] == tmp_path
        assert kwargs["check"] is True
        path = tmp_path / ".workshop" / "context.json"
        path.parent.mkdir()
        path.write_text(json.dumps(context), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", configure)
    namespace: dict[str, Any] = {}
    exec(notebook_cell_source("00-setup.ipynb", "find-repository"), namespace)
    inputs = notebook_cell_source("00-setup.ipynb", "workshop-inputs")
    inputs = inputs.replace(
        'subscription_id = ""', f"subscription_id = {context['subscription_id']!r}"
    )
    inputs = inputs.replace(
        'resource_group_name = ""', f"resource_group_name = {context['resource_group_name']!r}"
    )
    exec(inputs, namespace)
    exec(notebook_cell_source("00-setup.ipynb", "configure-workshop"), namespace)
    exec(notebook_cell_source("00-setup.ipynb", "verify-context"), namespace)

    assert checked == [runtime.WORKSHOP_ENVIRONMENT]
    assert calls == [
        [
            str(python),
            str(tmp_path / "scripts" / "configure_workshop.py"),
            "--subscription",
            context["subscription_id"],
            "--resource-group",
            context["resource_group_name"],
        ]
    ]
    assert namespace["context"] == context
    assert len(namespace["context"]["resource_outputs"]) == 24


def test_setup_notebook_blank_inputs_stop_run_all() -> None:
    with pytest.raises(ValueError, match="subscription ID"):
        exec(notebook_cell_source("00-setup.ipynb", "workshop-inputs"), {})


def test_setup_notebook_does_not_hide_configuration_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(command: list[str], **kwargs: Any) -> None:
        assert kwargs["check"] is True
        raise subprocess.CalledProcessError(2, command)

    monkeypatch.setattr(subprocess, "run", fail)
    namespace = {
        "subprocess": subprocess,
        "REPO_ROOT": tmp_path,
        "WORKSHOP_ENVIRONMENT": runtime.WORKSHOP_ENVIRONMENT,
        "get_runtime_python": lambda _: tmp_path / "management-python",
        "subscription_id": "synthetic-subscription",
        "resource_group_name": "synthetic-rg",
    }
    with pytest.raises(subprocess.CalledProcessError):
        exec(notebook_cell_source("00-setup.ipynb", "configure-workshop"), namespace)
    assert not (tmp_path / ".workshop" / "context.json").exists()

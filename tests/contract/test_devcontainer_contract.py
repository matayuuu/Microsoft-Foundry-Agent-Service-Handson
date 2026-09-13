"""Static contract for the shared, non-provisioning development container."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from scripts.lib import workshop_runtime as runtime

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = REPO_ROOT / ".devcontainer"


def configuration() -> dict:
    return json.loads((CONFIG_ROOT / "devcontainer.json").read_text(encoding="utf-8"))


def test_shared_container_pins_supported_base_and_feature_options() -> None:
    config = configuration()
    dockerfile = (CONFIG_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM mcr.microsoft.com/devcontainers/python:3.2.3-3.13-bookworm" in dockerfile
    assert config["build"] == {"dockerfile": "Dockerfile", "context": "."}
    features = config["features"]
    python = features["ghcr.io/devcontainers/features/python:1.8.0"]
    assert python == {
        "version": "3.12.14",
        "installPath": "/usr/local/python",
        "installTools": False,
        "installJupyterlab": False,
    }
    assert "additionalVersions" not in python
    assert python["installPath"] != "/usr/local"
    assert "python3.13 --version" in dockerfile
    azure = features["ghcr.io/devcontainers/features/azure-cli:1.3.0"]
    assert azure["version"] == "2.90.0"
    assert azure["extensions"] == ""
    assert azure["installBicep"] is False
    assert "latest" not in json.dumps(features)
    assert "graphviz=2.42.2-7+deb12u1" in dockerfile
    assert "git --version" in dockerfile


def test_container_uses_outside_workspace_venvs_and_correct_editor_defaults() -> None:
    config = configuration()
    assert config["remoteUser"] == "vscode"
    assert config["waitFor"] == "postCreateCommand"
    variables = config["containerEnv"]
    for spec in runtime.ENVIRONMENTS:
        assert variables[spec.variable] == f"/home/vscode/.venvs/{spec.name}/bin/python"
        remote_value = config.get("remoteEnv", {}).get(spec.variable, variables[spec.variable])
        assert remote_value in (
            variables[spec.variable],
            "${containerEnv:" + spec.variable + "}",
        )
    vscode = config["customizations"]["vscode"]
    assert {
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-toolsai.jupyter",
        "charliermarsh.ruff",
    } <= set(vscode["extensions"])
    assert (
        vscode["settings"]["python.defaultInterpreterPath"]
        == variables["WORKSHOP_MANAGEMENT_PYTHON"]
    )
    assert vscode["settings"]["[python]"]["editor.defaultFormatter"] == "charliermarsh.ruff"
    assert variables["PYTHONNOUSERSITE"] == "1"
    assert "${localEnv:" not in json.dumps(config)
    assert "${localWorkspaceFolder}" not in json.dumps(variables)
    assert "mounts" not in config


def test_post_create_only_prepares_dependencies_and_kernels() -> None:
    config = configuration()
    assert config["postCreateCommand"] == ["python3.12", "scripts/setup_dev_environment.py"]
    assert not any(
        key in config
        for key in ("initializeCommand", "onCreateCommand", "postStartCommand", "postAttachCommand")
    )
    source = (REPO_ROOT / "scripts" / "setup_dev_environment.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    ]
    assert all(
        not module.startswith(("azure", "openai", "requests", "httpx")) for module in imports
    )
    for forbidden in (
        "az login",
        "az account",
        "az deployment",
        "az group",
        "azd ",
        "configure_workshop.py",
        "bootstrap_custom_template",
        "get-access-token",
        "DefaultAzureCredential",
        "AzureCliCredential",
        "conda",
    ):
        assert forbidden not in source
    assert 'management_python: str = "python3.12"' in source
    assert 'hosted_python: str = "python3.13"' in source
    assert "inspect_python_command(bases[spec.name])" in source
    assert '"pip", "check"' in source


def test_no_public_notebook_server_or_automatic_forwarding() -> None:
    config = configuration()
    assert not config.get("forwardPorts")
    assert not config.get("appPort")
    assert config["otherPortsAttributes"] == {"onAutoForward": "ignore"}
    assert config["customizations"]["vscode"]["settings"]["remote.autoForwardPorts"] is False
    assert "runArgs" not in config
    assert not config.get("privileged", False)
    source = (REPO_ROOT / "scripts" / "setup_dev_environment.py").read_text(encoding="utf-8")
    assert "jupyter lab" not in source
    assert "jupyter notebook" not in source
    assert "0.0.0.0" not in source


def test_development_tools_are_declared_and_pinned_for_both_environments() -> None:
    pins = (CONFIG_ROOT / "requirements-dev.txt").read_text(encoding="utf-8").splitlines()
    assert {line.split("==", maxsplit=1)[0] for line in pins} == {"ipykernel", "pytest", "ruff"}
    assert all(re.fullmatch(r"[\w-]+==\d+\.\d+\.\d+", line) for line in pins)
    management = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    hosted = (REPO_ROOT / "src" / "hosted-agent" / "requirements.txt").read_text(encoding="utf-8")
    api = (REPO_ROOT / "src" / "travel-api" / "pyproject.toml").read_text(encoding="utf-8")
    assert "azure-ai-projects==2.5.0" in management
    assert "azure-ai-projects>=2.2.0,<2.4.0" in hosted
    assert 'requires-python = ">=3.12,<3.13"' in api

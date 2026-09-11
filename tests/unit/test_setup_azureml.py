"""Tests for Azure ML Conda/kernel setup safeguards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import setup_azureml


class FakeRunner:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.envs: dict[str, Path] = {}
        self.kernels: dict[str, dict[str, Any]] = {}
        self.commands: list[list[str]] = []

    def run(self, command: list[str]) -> None:
        command = list(command)
        self.commands.append(command)
        if command[1:3] == ["create", "--yes"]:
            name = command[command.index("--name") + 1]
            path = self.root / "envs" / name
            path.mkdir(parents=True)
            self.envs[name] = path
        if "ipykernel" in command and "install" in command:
            name = command[command.index("--name") + 1]
            self.kernels[name] = {
                "spec": {"argv": [str(self.envs[name] / "python.exe"), "-m", "ipykernel"]}
            }

    def json(self, command: list[str]) -> Any:
        if command[1:3] == ["env", "list"]:
            return {"envs": [str(path) for path in self.envs.values()]}
        if command[1:3] == ["kernelspec", "list"]:
            return {"kernelspecs": self.kernels}
        raise AssertionError(command)


def test_command_builders_pin_python_and_dependency_boundaries() -> None:
    create = setup_azureml.conda_create_command("conda", setup_azureml.WORKSHOP_ENVIRONMENT)
    workshop = setup_azureml.workshop_install_command("conda")
    hosted = setup_azureml.hosted_install_command("conda")
    graphviz = setup_azureml.graphviz_install_command("conda")

    assert "python=3.10" in create
    assert "--editable" in workshop
    assert workshop[3] == "foundry-workshop"
    assert any(item.endswith("[dev]") and "travel-api" not in item for item in workshop)
    assert any(item.endswith("travel-api[dev]") for item in workshop)
    assert hosted[3] == "foundry-hosted-agent"
    assert any(
        item.replace("\\", "/").endswith("src/hosted-agent/requirements.txt") for item in hosted
    )
    assert {"pytest", "ruff", "ipykernel"} <= set(hosted)
    assert graphviz[-1] == "graphviz"
    assert "sudo" not in graphviz


def test_setup_creates_marks_and_reuses_two_environments(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path)

    setup_azureml.ensure_environments(runner, conda="conda", jupyter="jupyter")
    first_count = len(runner.commands)
    setup_azureml.ensure_environments(runner, conda="conda", jupyter="jupyter")

    assert set(runner.envs) == {"foundry-workshop", "foundry-hosted-agent"}
    for path in runner.envs.values():
        assert (path / setup_azureml.MARKER_NAME).is_file()
    assert set(runner.kernels) == {"foundry-workshop", "foundry-hosted-agent"}
    second_commands = runner.commands[first_count:]
    assert not any(command[1:2] == ["create"] for command in second_commands)
    assert not any(
        "python -m ipykernel install" in " ".join(command) for command in second_commands
    )


def test_setup_refuses_unmarked_existing_environment(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path)
    unrelated = tmp_path / "envs" / "foundry-workshop"
    unrelated.mkdir(parents=True)
    runner.envs["foundry-workshop"] = unrelated

    with pytest.raises(setup_azureml.AzureMLSetupError, match="not marked"):
        setup_azureml.ensure_environments(runner, conda="conda", jupyter="jupyter")


def test_setup_refuses_kernel_pointing_elsewhere(tmp_path: Path) -> None:
    runner = FakeRunner(tmp_path)
    for spec in setup_azureml.ENVIRONMENTS:
        path = tmp_path / "envs" / spec.name
        path.mkdir(parents=True)
        (path / setup_azureml.MARKER_NAME).write_text(
            json.dumps(setup_azureml._marker_payload(spec)),
            encoding="utf-8",
        )
        runner.envs[spec.name] = path
    runner.kernels["foundry-workshop"] = {
        "spec": {"argv": [str(tmp_path / "other" / "python.exe")]}
    }

    with pytest.raises(setup_azureml.AzureMLSetupError, match="unrelated environment"):
        setup_azureml.ensure_environments(runner, conda="conda", jupyter="jupyter")

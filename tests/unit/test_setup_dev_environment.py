"""Exercise environment setup and runtime guards without installing anything."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import setup_dev_environment as setup
from scripts.lib import workshop_runtime as runtime


class FakeRunner:
    def __init__(self, home: Path) -> None:
        self.home = home
        self.versions = {"python3.12": "3.12", "python3.13": "3.13"}
        self.interpreters: dict[str, dict[str, str]] = {}
        self.kernels: dict[str, dict[str, Any]] = {}
        self.commands: list[list[str]] = []
        self.queries: list[list[str]] = []
        self.fail_on: str | None = None
        self.projects = {"foundry-workshop": "2.5.0", "foundry-hosted-agent": "2.3.0"}

    def run(self, command: list[str]) -> None:
        self.commands.append(list(command))
        if self.fail_on in command:
            raise runtime.WorkshopRuntimeError("synthetic command failure")
        if command[1:3] == ["-m", "venv"]:
            path = Path(command[-1])
            python = path / "bin" / "python"
            python.parent.mkdir(parents=True, exist_ok=True)
            python.write_text("synthetic interpreter", encoding="utf-8")
            (path / "pyvenv.cfg").write_text("include-system-site-packages = false\n")
            self.interpreters[str(python)] = {
                "version": self.versions[command[0]],
                "prefix": str(path),
                "base_prefix": str(self.home / "base"),
            }
        if command[1:4] == ["-m", "ipykernel", "install"]:
            name = command[command.index("--name") + 1]
            self.kernels[name] = {
                "spec": {
                    "argv": [command[0], "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                    "display_name": command[command.index("--display-name") + 1],
                    "language": "python",
                }
            }

    def json(self, command: list[str]) -> Any:
        self.queries.append(list(command))
        if command[1:4] == ["-m", "jupyter", "kernelspec"]:
            return {"kernelspecs": self.kernels.copy()}
        if "azure-ai-projects" in command[-1]:
            return self.projects[Path(command[0]).parent.parent.name]
        if command[0] in self.versions:
            return {
                "version": self.versions[command[0]],
                "prefix": str(self.home / "base"),
                "base_prefix": str(self.home / "base"),
            }
        return self.interpreters[command[0]]


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeRunner:
    repo = tmp_path / "checkout"
    repo.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(setup, "REPO_ROOT", repo)
    monkeypatch.setattr(runtime, "REPO_ROOT", repo)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    for spec in runtime.ENVIRONMENTS:
        monkeypatch.delenv(spec.variable, raising=False)
    return FakeRunner(home)


def mark_environment(runner: FakeRunner, spec: runtime.EnvironmentSpec) -> Path:
    python = runtime.runtime_python(spec)
    path = python.parent.parent
    path.mkdir(parents=True)
    (path / runtime.MARKER_NAME).write_text(json.dumps(runtime.marker_payload(spec)))
    runner.run([f"python{spec.python_version}", "-m", "venv", str(path)])
    runner.commands.clear()
    return python


def test_setup_separates_versions_dependency_sets_and_user_kernels(runner: FakeRunner) -> None:
    paths = setup.ensure_environments(runner)

    assert set(paths) == {"foundry-workshop", "foundry-hosted-agent"}
    for spec in runtime.ENVIRONMENTS:
        python = paths[spec.name]
        assert python == runner.home / ".venvs" / spec.name / "bin" / "python"
        assert [f"python{spec.python_version}", "-m", "venv", str(python.parent.parent)] in (
            runner.commands
        )
        assert [str(python), "-m", "pip", "check"] in runner.commands
        assert setup.kernel_install_command(python, spec) in runner.commands
        runtime.verify_ownership(python.parent.parent, spec)
        assert runner.kernels[spec.name]["spec"]["display_name"] == spec.display_name
    management = setup.install_command(paths["foundry-workshop"], runtime.WORKSHOP_ENVIRONMENT)
    hosted = setup.install_command(paths["foundry-hosted-agent"], runtime.HOSTED_ENVIRONMENT)
    assert f"{setup.REPO_ROOT}[dev]" in management
    assert f"{setup.REPO_ROOT / 'src' / 'travel-api'}[dev]" in management
    assert str(setup.REPO_ROOT / "src" / "hosted-agent" / "requirements.txt") in hosted
    assert "--editable" not in hosted
    assert not any("hosted-agent" in item for item in management)
    assert not any("travel-api" in item for item in hosted)
    for command in (management, hosted):
        assert str(setup.REPO_ROOT / ".devcontainer" / "requirements-dev.txt") in command


def test_repeat_setup_reuses_owned_environments_and_identical_kernels(runner: FakeRunner) -> None:
    setup.ensure_environments(runner)
    first = len(runner.commands)

    setup.ensure_environments(runner)

    repeated = runner.commands[first:]
    assert not any(command[1:3] == ["-m", "venv"] for command in repeated)
    assert not any(command[1:3] == ["-m", "ipykernel"] for command in repeated)
    assert set(runner.kernels) == {"foundry-workshop", "foundry-hosted-agent"}


def test_explicit_safe_environment_paths_are_respected(
    runner: FakeRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = {}
    for spec in runtime.ENVIRONMENTS:
        python = runner.home / "custom-environments" / spec.name / "bin" / "python"
        monkeypatch.setenv(spec.variable, str(python))
        expected[spec.name] = python

    assert setup.ensure_environments(runner) == expected
    assert not (runner.home / ".venvs").exists()


def test_host_checkout_venvs_are_untouched(runner: FakeRunner) -> None:
    files = [
        setup.REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        setup.REPO_ROOT / "src" / "hosted-agent" / ".venv" / "bin" / "python",
    ]
    for path in files:
        path.parent.mkdir(parents=True)
        path.write_bytes(b"existing host environment")

    setup.ensure_environments(runner)

    assert all(path.read_bytes() == b"existing host environment" for path in files)
    assert all(not (path.parent.parent / runtime.MARKER_NAME).exists() for path in files)


@pytest.mark.parametrize("location", ["checkout", "host-venv", "relative", "empty", "wrong-name"])
def test_refuses_unsafe_interpreter_overrides_before_writing(
    runner: FakeRunner, monkeypatch: pytest.MonkeyPatch, location: str
) -> None:
    choices = {
        "checkout": str(setup.REPO_ROOT / ".venvs" / "foundry-workshop" / "bin" / "python"),
        "host-venv": str(runner.home / ".venv" / "foundry-workshop" / "bin" / "python"),
        "relative": "foundry-workshop/bin/python",
        "empty": "",
        "wrong-name": str(runtime.runtime_python(runtime.HOSTED_ENVIRONMENT)),
    }
    monkeypatch.setenv("WORKSHOP_MANAGEMENT_PYTHON", choices[location])

    with pytest.raises(runtime.WorkshopRuntimeError):
        setup.ensure_environments(runner)

    assert runner.commands == []
    assert not (runner.home / ".venvs").exists()


def test_both_targets_are_checked_before_any_environment_is_created(runner: FakeRunner) -> None:
    hosted = runtime.runtime_python(runtime.HOSTED_ENVIRONMENT).parent.parent
    hosted.mkdir(parents=True)
    unrelated = hosted / "keep.txt"
    unrelated.write_text("user content")

    with pytest.raises(runtime.WorkshopRuntimeError, match="not marked"):
        setup.ensure_environments(runner)

    assert runner.commands == []
    assert unrelated.read_text() == "user content"
    assert not runtime.runtime_python(runtime.WORKSHOP_ENVIRONMENT).parent.parent.exists()


@pytest.mark.parametrize("field,value", [("owner", "other"), ("python", "3.10"), ("kind", "other")])
def test_refuses_incompatible_markers(runner: FakeRunner, field: str, value: str) -> None:
    python = mark_environment(runner, runtime.WORKSHOP_ENVIRONMENT)
    payload = runtime.marker_payload(runtime.WORKSHOP_ENVIRONMENT)
    payload[field] = value
    marker = python.parent.parent / runtime.MARKER_NAME
    marker.write_text(json.dumps(payload))

    with pytest.raises(runtime.WorkshopRuntimeError, match="ownership or Python"):
        setup.ensure_environments(runner)

    assert runner.commands == []
    assert json.loads(marker.read_text()) == payload


def test_refuses_malformed_marker(runner: FakeRunner) -> None:
    python = mark_environment(runner, runtime.WORKSHOP_ENVIRONMENT)
    (python.parent.parent / runtime.MARKER_NAME).write_text("not json")

    with pytest.raises(runtime.WorkshopRuntimeError, match="not marked"):
        setup.ensure_environments(runner)

    assert runner.commands == []


def test_refuses_wrong_named_base_version_before_any_writes(runner: FakeRunner) -> None:
    runner.versions["python3.13"] = "3.12"

    with pytest.raises(runtime.WorkshopRuntimeError, match=r"requires Python 3\.13"):
        setup.ensure_environments(runner)

    assert runner.commands == []
    assert not (runner.home / ".venvs").exists()


@pytest.mark.parametrize("bad_detail", ["version", "prefix", "base_prefix"])
def test_checks_actual_owned_interpreter_not_just_marker(
    runner: FakeRunner, bad_detail: str
) -> None:
    python = mark_environment(runner, runtime.WORKSHOP_ENVIRONMENT)
    details = runner.interpreters[str(python)]
    details[bad_detail] = {
        "version": "3.13",
        "prefix": str(runner.home / "other-venv"),
        "base_prefix": details["prefix"],
    }[bad_detail]

    with pytest.raises(runtime.WorkshopRuntimeError):
        setup.ensure_environments(runner)

    assert runner.commands == []


def test_partial_owned_environment_is_recoverable_after_creation_failure(
    runner: FakeRunner,
) -> None:
    runner.fail_on = "venv"
    with pytest.raises(runtime.WorkshopRuntimeError, match="synthetic"):
        setup.ensure_environments(runner)
    path = runtime.runtime_python(runtime.WORKSHOP_ENVIRONMENT).parent.parent
    runtime.verify_ownership(path, runtime.WORKSHOP_ENVIRONMENT)

    runner.fail_on = None
    setup.ensure_environments(runner)

    assert (path / "pyvenv.cfg").is_file()
    assert set(runner.kernels) == {"foundry-workshop", "foundry-hosted-agent"}


def test_dependency_failure_stops_before_kernel_registration(runner: FakeRunner) -> None:
    runner.fail_on = "pip"
    with pytest.raises(runtime.WorkshopRuntimeError, match="synthetic"):
        setup.ensure_environments(runner)
    assert runner.kernels == {}

    runner.fail_on = None
    setup.ensure_environments(runner)
    assert len(runner.kernels) == 2


@pytest.mark.parametrize(
    "name,version", [("foundry-workshop", "2.3.0"), ("foundry-hosted-agent", "2.5.0")]
)
def test_post_install_sdk_guard_rejects_mixed_environments(
    runner: FakeRunner, name: str, version: str
) -> None:
    runner.projects[name] = version

    with pytest.raises(runtime.WorkshopRuntimeError, match="incompatible azure-ai-projects"):
        setup.ensure_environments(runner)

    assert runner.kernels == {}


@pytest.mark.parametrize("field", ["argv", "display_name", "language"])
def test_existing_unrelated_kernel_is_never_overwritten(runner: FakeRunner, field: str) -> None:
    setup.ensure_environments(runner)
    spec = runner.kernels["foundry-workshop"]["spec"]
    spec[field] = ["python", "-m", "ipykernel_launcher"] if field == "argv" else "other"
    runner.commands.clear()

    with pytest.raises(runtime.WorkshopRuntimeError, match="refusing to overwrite"):
        setup.ensure_environments(runner)

    assert not any(command[1:3] == ["-m", "ipykernel"] for command in runner.commands)


def test_kernel_registration_is_verified_not_assumed(
    runner: FakeRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = runner.json

    def missing_kernels(command: list[str]) -> Any:
        if command[1:3] == ["-m", "jupyter"]:
            return {"kernelspecs": {}}
        return original(command)

    monkeypatch.setattr(runner, "json", missing_kernels)
    with pytest.raises(runtime.WorkshopRuntimeError, match="Kernel"):
        setup.ensure_environments(runner)


def test_management_resolution_checks_owned_prefix_and_never_falls_back(
    runner: FakeRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = mark_environment(runner, runtime.WORKSHOP_ENVIRONMENT)
    calls: list[list[str]] = []

    def inspect(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert kwargs["check"] is True
        return subprocess.CompletedProcess(command, 0, json.dumps(runner.json(command)), "")

    monkeypatch.setattr(runtime.subprocess, "run", inspect)
    assert runtime.get_runtime_python(runtime.WORKSHOP_ENVIRONMENT) == python
    assert calls[0][0] == str(python)
    runner.interpreters[str(python)]["version"] = "3.13"
    with pytest.raises(runtime.WorkshopRuntimeError, match=r"Python 3\.12"):
        runtime.get_runtime_python(runtime.WORKSHOP_ENVIRONMENT)


def test_management_resolution_does_not_execute_an_unowned_interpreter(
    runner: FakeRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unexpected(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("must not launch unowned Python")

    monkeypatch.setattr(runtime.subprocess, "run", unexpected)
    with pytest.raises(runtime.WorkshopRuntimeError, match="not marked"):
        runtime.get_runtime_python(runtime.WORKSHOP_ENVIRONMENT)


def test_current_kernel_requires_correct_version_and_venv(
    runner: FakeRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    python = mark_environment(runner, runtime.HOSTED_ENVIRONMENT)
    process = SimpleNamespace(
        version_info=(3, 13, 15),
        prefix=str(python.parent.parent),
        base_prefix=str(runner.home / "base"),
    )
    monkeypatch.setattr(runtime, "sys", process)
    runtime.require_current_runtime(runtime.HOSTED_ENVIRONMENT)
    process.prefix = process.base_prefix
    with pytest.raises(runtime.WorkshopRuntimeError, match="own venv"):
        runtime.require_current_runtime(runtime.HOSTED_ENVIRONMENT)


def test_linked_environment_cannot_target_host_checkout(runner: FakeRunner) -> None:
    target = setup.REPO_ROOT / ".venv"
    target.mkdir()
    path = runtime.runtime_python(runtime.WORKSHOP_ENVIRONMENT).parent.parent
    path.parent.mkdir(parents=True)
    try:
        path.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("Creating symlinks is not permitted on this host.")

    with pytest.raises(runtime.WorkshopRuntimeError, match="outside the repository"):
        setup.ensure_environments(runner)

    assert list(target.iterdir()) == []


def test_subprocess_failures_remain_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert kwargs["stderr"] == subprocess.STDOUT
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setattr(setup.subprocess, "run", fail)
    with pytest.raises(runtime.WorkshopRuntimeError, match="exit code 7"):
        setup.SubprocessRunner().run(["python3.12", "-m", "venv", "unused"])


@pytest.mark.parametrize("exit_code,output", [(3, "{}"), (0, "invalid JSON")])
def test_json_command_failures_are_not_ignored(
    monkeypatch: pytest.MonkeyPatch, exit_code: int, output: str
) -> None:
    monkeypatch.setattr(
        setup.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, exit_code, output, "synthetic stderr"
        ),
    )
    with pytest.raises(runtime.WorkshopRuntimeError, match="command"):
        setup.SubprocessRunner().json(["python3.12", "-c", "pass"])


def test_missing_named_interpreter_is_an_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*args: Any, **kwargs: Any) -> None:
        raise FileNotFoundError("python3.12")

    monkeypatch.setattr(setup.subprocess, "run", missing)
    with pytest.raises(runtime.WorkshopRuntimeError, match=r"Cannot run python3\.12"):
        setup.SubprocessRunner().json(runtime.inspect_python_command("python3.12"))


def test_main_refuses_native_host_setup_before_running_commands(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(setup, "sys", SimpleNamespace(platform="win32", stderr=setup.sys.stderr))
    assert setup.main([]) == 2
    assert "local Dev Container" in capsys.readouterr().err

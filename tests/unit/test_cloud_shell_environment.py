from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import cloud_shell_environment as environment


@pytest.fixture
def mounts(tmp_path: Path) -> tuple:
    home = tmp_path / "home"
    repo = home / "workshop"
    share = home / "clouddrive"
    image = share / ".cloudconsole" / "acc_student.img"
    repo.mkdir(parents=True)
    image.parent.mkdir(parents=True)
    image.write_bytes(b"fixture, not a real disk image")
    native = {
        "source": "/dev/loop1",
        "target": str(home),
        "fstype": "ext4",
        "options": "rw,relatime",
        "maj:min": "7:1",
    }
    remote = {
        "source": "//fixture.file.core.windows.net/student",
        "target": str(share),
        "fstype": "cifs",
        "options": "rw",
        "maj:min": "0:43",
    }
    return home, repo, share, native, dict(native), remote, image


@pytest.mark.parametrize("filesystem", ["ext2", "ext3", "ext4", "xfs", "btrfs"])
def test_mount_validation_requires_native_home_disk_image(mounts: tuple, filesystem: str) -> None:
    mounts[3]["fstype"] = filesystem
    mounts[4]["fstype"] = filesystem
    environment.validate_mounts(*mounts)


@pytest.mark.parametrize("filesystem", ["overlay", "tmpfs", "cifs", "fuse", "unknown"])
def test_ephemeral_or_smb_home_is_rejected(mounts: tuple, filesystem: str) -> None:
    mounts[3]["fstype"] = filesystem
    mounts[4]["fstype"] = filesystem
    with pytest.raises(environment.EnvironmentError, match="Persistent Cloud Shell"):
        environment.validate_mounts(*mounts)


@pytest.mark.parametrize("index", [3, 4, 5])
def test_read_only_mount_is_rejected(mounts: tuple, index: int) -> None:
    mounts[index]["options"] = "ro,relatime"
    with pytest.raises(environment.EnvironmentError, match="Do not delete"):
        environment.validate_mounts(*mounts)


def test_directory_named_clouddrive_is_not_persistence(mounts: tuple) -> None:
    mounts[5].update(fstype="ext4", source="/dev/loop1")
    with pytest.raises(environment.EnvironmentError, match="directory alone"):
        environment.validate_mounts(*mounts)


def test_image_outside_mounted_share_is_rejected(mounts: tuple, tmp_path: Path) -> None:
    image = tmp_path / "acc_student.img"
    image.write_bytes(b"fixture")
    with pytest.raises(environment.EnvironmentError, match="disk-image"):
        environment.validate_mounts(*mounts[:-1], image)


@pytest.mark.parametrize("location", ["share", "outside", "home"])
def test_repository_must_be_below_native_home(mounts: tuple, location: str) -> None:
    home, repo, share, *rest = mounts
    repo = {"share": share / "repo", "outside": home.parent / "repo", "home": home}[location]
    with pytest.raises(environment.EnvironmentError, match="Unix HOME"):
        environment.validate_mounts(home, repo, share, *rest)


def test_different_repository_mount_is_rejected(mounts: tuple) -> None:
    mounts[4]["maj:min"] = "8:1"
    with pytest.raises(environment.EnvironmentError, match="Terraform state"):
        environment.validate_mounts(*mounts)


def test_unsupported_platform_fails_without_creating_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(environment.platform, "system", lambda: "Windows")
    with pytest.raises(environment.EnvironmentError, match="Linux x86_64"):
        environment.validate_storage(tmp_path / "not-created", minimum_mib=3072)
    assert not (tmp_path / "not-created").exists()


def test_mount_command_failures_do_not_echo_subprocess_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def failure(*args: object, **kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args[0], 1, "private-output", "private-error")

    monkeypatch.setattr(environment.subprocess, "run", failure)
    with pytest.raises(environment.EnvironmentError, match="Persistent Cloud Shell") as error:
        environment.mounted_filesystem(tmp_path)
    assert "private-" not in str(error.value)


def test_state_directory_is_scoped_by_repository_path(tmp_path: Path) -> None:
    home = tmp_path / "home"
    first = environment.state_directory(home / "repo-one", home)
    second = environment.state_directory(home / "repo-two", home)
    assert first != second
    assert first.parent == home / ".local/share/foundry-cloud-shell"
    assert not first.is_relative_to(home / "repo-one")
    assert first == environment.state_directory(home / "repo-one", home)


def test_dependency_fingerprints_are_separate(tmp_path: Path) -> None:
    (tmp_path / "src/hosted-agent").mkdir(parents=True)
    (tmp_path / "src/travel-api").mkdir()
    (tmp_path / "pyproject.toml").write_text("root dependencies")
    (tmp_path / "src/travel-api/pyproject.toml").write_text("travel dependencies")
    hosted = tmp_path / "src/hosted-agent/requirements.txt"
    hosted.write_text("hosted dependencies")
    root_before = environment.dependency_digest(tmp_path, "root")
    hosted_before = environment.dependency_digest(tmp_path, "hosted")
    hosted.write_text("updated hosted dependencies")
    assert root_before == environment.dependency_digest(tmp_path, "root")
    assert hosted_before != environment.dependency_digest(tmp_path, "hosted")


def test_token_probes_are_read_only_and_never_request_output_tokens(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    calls: list[list[str]] = []

    def fake_run(arguments: list[str], **kwargs: object) -> str:
        calls.append(arguments)
        assert kwargs == {"timeout": 90}
        return "future-expiry"

    monkeypatch.setattr(environment, "run_local", fake_run)
    environment.check_tokens("fixture-subscription")
    assert len(calls) == 4
    for command in calls:
        assert command[:3] == ["az", "account", "get-access-token"]
        assert command[command.index("--query") + 1] == "expiresOn"
        assert command[command.index("--subscription") + 1] == "fixture-subscription"
        assert command[command.index("--output") + 1] == "tsv"
    assert capsys.readouterr().out == ""


def test_unsupported_audience_is_actionable_without_login_or_token_logging(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failure(*args: object, **kwargs: object) -> str:
        raise environment.EnvironmentError("fake sensitive CLI error")

    monkeypatch.setattr(environment, "run_local", failure)
    with pytest.raises(environment.EnvironmentError) as error:
        environment.check_tokens(None)
    message = str(error.value)
    assert "az login --use-device-code" in message
    assert "Conditional Access" in message
    assert "fake sensitive" not in message


@pytest.mark.parametrize("result", ["True", "False", ""])
def test_exact_cpython_313_requirement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, result: str
) -> None:
    calls = []

    def fake_run(arguments: list[str], **kwargs: object) -> str:
        calls.append(arguments)
        return result

    monkeypatch.setattr(environment, "run_local", fake_run)
    assert environment.python_is_313(tmp_path / "python") == (result == "True")
    assert "(3, 13)" in calls[0][2] and "'cpython'" in calls[0][2]


def test_readiness_checks_both_kernel_interpreters(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(environment, "python_is_313", lambda path: True)
    for name, (relative, _) in environment.KERNELS.items():
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)
        kernel = tmp_path / ".venv/share/jupyter/kernels" / name / "kernel.json"
        kernel.parent.mkdir(parents=True)
        kernel.write_text(json.dumps({"argv": [str(tmp_path / relative / "bin/python")]}))
    environment.validate_environments(tmp_path)
    hosted = tmp_path / ".venv/share/jupyter/kernels/foundry-hosted-agent/kernel.json"
    hosted.write_text(json.dumps({"argv": [str(tmp_path / ".venv/bin/python")]}))
    with pytest.raises(environment.EnvironmentError, match="foundry-hosted-agent"):
        environment.validate_environments(tmp_path)


def test_interrupted_setup_cannot_activate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(environment, "validate_storage", lambda *args, **kwargs: tmp_path)
    with pytest.raises(environment.EnvironmentError, match="interrupted"):
        environment.validate_ready(tmp_path / "repo")


def test_insufficient_space_preserves_existing_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    state = tmp_path / "fixture-state"
    state.write_text("keep")
    monkeypatch.setattr(environment.shutil, "disk_usage", lambda path: SimpleNamespace(free=1))
    with pytest.raises(environment.EnvironmentError, match="at least 3072 MiB"):
        environment.validate_free_space(tmp_path, 3072)
    assert state.read_text() == "keep"

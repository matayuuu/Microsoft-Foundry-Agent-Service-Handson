"""Network-free tests for the provisioning-only Cloud Shell core."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts import cloud_shell_environment as environment


def test_validate_mounts_accepts_repository_on_azure_files_clouddrive(tmp_path: Path) -> None:
    home = tmp_path / "home"
    share = home / "clouddrive"
    repo = share / "repo"
    repo.mkdir(parents=True)

    azure_files = {
        "source": "//account.file.core.windows.net/share",
        "fstype": "cifs",
        "options": "rw,relatime",
        "maj:min": "0:50",
    }

    environment.validate_mounts(repo, share, azure_files, azure_files)


def test_validate_mounts_rejects_repository_outside_clouddrive(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = home / "repo"
    share = home / "clouddrive"
    repo.mkdir(parents=True)
    share.mkdir()
    azure_files = {
        "source": "//account.file.core.windows.net/share",
        "fstype": "cifs",
        "options": "rw,relatime",
        "maj:min": "0:50",
    }

    with pytest.raises(environment.EnvironmentError, match="Persistent Cloud Shell storage"):
        environment.validate_mounts(repo, share, azure_files, azure_files)


def test_validate_mounts_rejects_ephemeral_overlay(tmp_path: Path) -> None:
    share = tmp_path / "home" / "clouddrive"
    repo = share / "repo"
    repo.mkdir(parents=True)
    overlay = {
        "source": "overlay",
        "fstype": "overlay",
        "options": "rw",
        "maj:min": "0:1",
    }

    with pytest.raises(environment.EnvironmentError, match="Persistent Cloud Shell storage"):
        environment.validate_mounts(repo, share, overlay, overlay)


def test_runtime_is_session_local_and_state_is_persistent(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = home / "clouddrive" / "repo"

    assert environment.venv_directory(repo, home).is_relative_to(home)
    assert not environment.venv_directory(repo, home).is_relative_to(home / "clouddrive")
    assert environment.state_directory(repo) == repo / ".workshop" / "cloud-shell"


def test_ready_requires_current_digest_and_single_repo_venv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    state = tmp_path / "state"
    python = tmp_path / "runtime" / "venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    state.mkdir()
    marker = {
        "repo": str(repo),
        "python": str(python),
        "dependency_digest": "digest",
        "python_version": "Python 3.12.0",
    }
    (state / "ready.json").write_text(json.dumps(marker), encoding="utf-8")

    monkeypatch.setattr(environment, "validate_storage", lambda *_args, **_kwargs: state)
    monkeypatch.setattr(environment, "venv_directory", lambda _: python.parents[1])
    monkeypatch.setattr(environment, "validate_python", lambda _: None)
    monkeypatch.setattr(environment, "dependency_digest", lambda _: "digest")
    monkeypatch.setattr(environment, "run_local", lambda *_args, **_kwargs: "")

    assert environment.validate_ready(repo)["repo"] == str(repo)


def test_cloud_shell_scripts_are_lightweight_and_provisioning_only() -> None:
    repo = Path(__file__).resolve().parents[2]
    setup = (repo / "scripts" / "setup-cloud-shell.sh").read_text(encoding="utf-8")
    common = (repo / "scripts" / "cloud-shell-common.sh").read_text(encoding="utf-8")
    activation = (repo / "scripts" / "activate-cloud-shell.sh").read_text(encoding="utf-8")
    combined = "\n".join((setup, common, activation)).casefold()
    folded_setup = setup.casefold().replace("\\\n", " ")

    assert environment.REQUIRED_PYTHON == (3, 12)
    assert re.search(
        r'pip\s+install\s+(?:--\S+\s+)*-e\s+"\$\{repo_root\}"',
        folded_setup,
    )
    assert "[dev]" not in combined
    assert "src/hosted-agent" not in combined
    assert "python 3.13" not in combined
    assert "download" not in common.casefold()
    assert "jupyter" not in common.casefold()
    assert "graphviz" not in common.casefold()
    assert "workshop_python" in activation.casefold()
    assert "workshop_cloud_shell_repo" in activation.casefold()
    assert "azureclicredential" in activation.casefold()

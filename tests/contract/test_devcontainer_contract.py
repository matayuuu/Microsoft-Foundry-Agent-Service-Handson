from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEVCONTAINER_DIR = REPO_ROOT / ".devcontainer"


def test_devcontainer_removes_obsolete_yarn_source_before_features_install() -> None:
    config = json.loads((DEVCONTAINER_DIR / "devcontainer.json").read_text(encoding="utf-8"))
    dockerfile = (DEVCONTAINER_DIR / config["build"]["dockerfile"]).read_text(encoding="utf-8")

    assert "image" not in config
    assert "FROM mcr.microsoft.com/devcontainers/python:${VARIANT}" in dockerfile
    assert "rm -f /etc/apt/sources.list.d/yarn.list" in dockerfile
    assert "ghcr.io/devcontainers/features/azure-cli:1" in config["features"]
    assert "ghcr.io/devcontainers/features/sshd:1" in config["features"]
    assert "ghcr.io/devcontainers/features/terraform:1" in config["features"]
    assert "ms-toolsai.jupyter" in config["customizations"]["vscode"]["extensions"]

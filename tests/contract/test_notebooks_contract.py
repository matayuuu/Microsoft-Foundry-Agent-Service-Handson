from __future__ import annotations

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
            "run_workflow",
            "SequentialBuilder",
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

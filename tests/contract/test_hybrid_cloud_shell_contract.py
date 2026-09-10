"""Static contracts for the hybrid Cloud Shell provisioning handoff."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_participant_and_admin_preflight_require_all_providers() -> None:
    scripts = [
        (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")
        for name in ("preflight.sh", "admin-preflight.sh")
    ]
    providers = (
        "Microsoft.CognitiveServices",
        "Microsoft.Search",
        "Microsoft.Insights",
        "Microsoft.OperationalInsights",
        "Microsoft.App",
        "Microsoft.MachineLearningServices",
        "Microsoft.Storage",
        "Microsoft.KeyVault",
    )
    for text in scripts:
        for provider in providers:
            assert f'"{provider}"' in text
    assert "az provider register --namespace" not in scripts[0]
    assert "Storage shared-key" in scripts[0]
    assert "Key Vault RBAC" in scripts[0]


def test_setup_writes_canonical_context_and_exact_download_hook() -> None:
    text = (REPO_ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")

    assert ".resource_outputs = $resource_outputs" in text
    assert ".terraform_outputs =" not in text
    assert '--context "${WORKSHOP_DIR}/context.json"' in text
    assert 'PACKAGER="${SCRIPT_DIR}/prepare_participant_download.py"' in text
    assert 'DOWNLOAD_ZIP="${WORKSHOP_DIR}/download/foundry-workshop-files.zip"' in text
    assert '"${PYTHON_BIN}" "${PACKAGER}"' in text
    assert '--output "${DOWNLOAD_ZIP}"' in text
    assert "REQUIRED participant packager is missing" in text
    assert "type 'exit' immediately" in text


def test_setup_requires_activated_cloud_shell_before_preflight() -> None:
    text = (REPO_ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")

    guard = text.index('cloud_shell_guard "${REPO_ROOT}"')
    preflight = text.index('echo "==> [1/5] Running participant preflight')
    assert guard < preflight


def test_provisioning_openai_dependency_matches_azure_ai_projects() -> None:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"openai>=3.0.0,<4"' in text

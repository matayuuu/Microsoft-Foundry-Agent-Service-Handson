"""Repository-level contracts for the single custom-template provisioning path."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_terraform_definitions_and_cloud_shell_entrypoints_are_retired() -> None:
    assert not list((ROOT / "infra").glob("*.tf"))
    for relative in (
        "infra/.terraform.lock.hcl",
        "infra/backend.remote.tf.example",
        "infra/terraform.tfvars.example",
        "scripts/setup.sh",
        "scripts/destroy.sh",
        "scripts/setup-cloud-shell.sh",
        "scripts/activate-cloud-shell.sh",
        "scripts/cloud-shell-common.sh",
        "scripts/cloud_shell_environment.py",
        "scripts/prepare_terraform_plan.py",
        "scripts/preflight.sh",
        "scripts/prepare_serverless_foundry_iq.sh",
    ):
        assert not (ROOT / relative).exists(), f"retired implementation remains: {relative}"


def test_ci_uses_pinned_bicep_without_automatic_azure_deployment() -> None:
    workflow = yaml.load(
        (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    assert "dev-custom-template" in workflow["on"]["push"]["branches"]
    assert "terraform" not in workflow["jobs"]
    steps = workflow["jobs"]["bicep"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    template = json.loads((ROOT / "infra" / "azuredeploy.json").read_text(encoding="utf-8"))
    compiler_version = ".".join(template["metadata"]["_generator"]["version"].split(".")[:3])
    assert f"az bicep install --version v{compiler_version}" in commands
    assert "make bicep-validate" in commands
    assert "az deployment" not in commands
    assert not any(step.get("uses", "").startswith("azure/login") for step in steps)


def test_makefile_and_administrator_tools_do_not_require_retired_helpers() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "bicep-validate:" in makefile
    assert "terraform" not in makefile.casefold()
    assert "scripts/bootstrap-custom-template.sh" in makefile
    assert "scripts/setup.sh" not in makefile
    admin = (ROOT / "scripts" / "admin-preflight.sh").read_text(encoding="utf-8")
    assert "FALLBACK_LOCATION" not in admin
    assert "scripts/preflight.sh" not in admin
    for provider in (
        "Microsoft.ManagedIdentity",
        "Microsoft.ContainerInstance",
        "Microsoft.Resources",
    ):
        assert provider in admin


def test_runtime_ci_uses_template_image_and_no_credentials_or_azure_calls() -> None:
    workflow = yaml.load(
        (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )
    steps = workflow["jobs"]["bootstrap-runtime"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert ".properties.azCliVersion" in commands
    assert 'cp pyproject.toml README.md "$runtime_context/"' in commands
    assert "AZURE_CLI_VERSION=$cli_version" in commands
    assert "az login" not in commands
    assert "az deployment" not in commands
    assert not any(step.get("uses", "").startswith("azure/login") for step in steps)
    dockerfile = (ROOT / "tests" / "runtime" / "bootstrap.Dockerfile").read_text(encoding="utf-8")
    assert "FROM mcr.microsoft.com/azure-cli:${AZURE_CLI_VERSION}" in dockerfile
    assert "COPY pyproject.toml README.md /workshop/" in dockerfile
    assert "venv /tmp/workshop-python" in dockerfile


def test_state_and_credential_exclusions_survive_tool_retirement() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for pattern in (".workshop/", ".azure/", ".env", "*.tfstate", "*.tfstate.*", "*.zip"):
        assert pattern in ignored

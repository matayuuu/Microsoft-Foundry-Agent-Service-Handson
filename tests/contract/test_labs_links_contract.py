"""Participant-path contracts for the hybrid Cloud Shell and Azure ML workshop."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LABS_DIR = REPO_ROOT / "labs"
AZUREML_GUIDE = REPO_ROOT / "docs" / "participant" / "environments" / "azure-ml.md"
CORE_LABS = [
    LABS_DIR / "00-overview.md",
    LABS_DIR / "01-setup.md",
    LABS_DIR / "02-prompt-agent.md",
    LABS_DIR / "03-rag-foundry-iq.md",
    LABS_DIR / "04-tools-toolbox.md",
    LABS_DIR / "05-evaluation.md",
    LABS_DIR / "06-optimization.md",
    LABS_DIR / "07-agent-framework-harness.md",
    LABS_DIR / "08-hosted-multi-agent.md",
    LABS_DIR / "09-observability-cleanup.md",
]
OWNED_FILES = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "README.en.md",
    REPO_ROOT / "AGENTS.md",
    *CORE_LABS,
    REPO_ROOT / "docs" / "participant" / "prerequisites.md",
    REPO_ROOT / "docs" / "participant" / "troubleshooting.md",
    AZUREML_GUIDE,
    REPO_ROOT / "docs" / "admin" / "prerequisites.md",
    REPO_ROOT / "docs" / "admin" / "troubleshooting.md",
    REPO_ROOT / "docs" / "architecture.md",
    REPO_ROOT / "docs" / "costs-and-cleanup.md",
    REPO_ROOT / "docs" / "feature-support-matrix.md",
    REPO_ROOT / "instructor" / "README.md",
    REPO_ROOT / "instructor" / "runbook.md",
    REPO_ROOT / "src" / "hosted-agent" / "README.md",
    LABS_DIR / "optional" / "README.md",
    LABS_DIR / "optional" / "fabric-iq.md",
    LABS_DIR / "optional" / "work-iq.md",
]

_LINK_PATTERN = re.compile(r"\[[^\]\n]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HANDOFF_ZIP = ".workshop/download/foundry-workshop-files.zip"
LEGACY_TAG_URL = (
    "https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/"
    "tree/codespaces-cloud-shell-v1"
)


def extract_link_targets(markdown_text: str) -> list[str]:
    return _LINK_PATTERN.findall(markdown_text)


def is_external_link(target: str) -> bool:
    if target.startswith("#"):
        return True
    return urlsplit(target).scheme in {"http", "https", "mailto"}


def resolve_link_path(source_file: Path, target: str) -> Path:
    path_part = target.split("#", 1)[0]
    if not path_part:
        raise ValueError(f"link target {target!r} has no file path component")
    return (source_file.parent / path_part).resolve()


@pytest.mark.parametrize("source_file", OWNED_FILES, ids=lambda path: path.name)
def test_owned_participant_file_exists(source_file: Path) -> None:
    assert source_file.is_file(), f"expected owned file to exist: {source_file}"


def _relative_link_cases() -> list[tuple[Path, str]]:
    cases: list[tuple[Path, str]] = []
    for source_file in OWNED_FILES:
        if not source_file.is_file():
            continue
        for target in extract_link_targets(source_file.read_text(encoding="utf-8")):
            if not is_external_link(target):
                cases.append((source_file, target))
    return cases


@pytest.mark.parametrize(
    ("source_file", "target"),
    _relative_link_cases(),
    ids=[f"{path.name}::{target}" for path, target in _relative_link_cases()],
)
def test_relative_markdown_link_resolves(source_file: Path, target: str) -> None:
    resolved = resolve_link_path(source_file, target)
    assert resolved.is_file(), (
        f"{source_file.relative_to(REPO_ROOT)} links to {target!r}, but {resolved} does not exist"
    )


def test_readme_agenda_links_all_ten_labs() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for lab_number, lab in enumerate(CORE_LABS):
        assert f"[Lab {lab_number}](labs/{lab.name})" in readme


def test_each_core_lab_links_to_the_next_lab() -> None:
    for current, following in pairwise(CORE_LABS):
        targets = extract_link_targets(current.read_text(encoding="utf-8"))
        assert any(
            not is_external_link(target)
            and resolve_link_path(current, target) == following.resolve()
            for target in targets
        ), f"{current.name} does not link to {following.name}"


def test_primary_path_uses_cloud_shell_provisioning_and_azureml_execution() -> None:
    primary_files = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.en.md",
        REPO_ROOT / "docs" / "participant" / "prerequisites.md",
        AZUREML_GUIDE,
        *CORE_LABS,
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in primary_files)

    for required in (
        "Azure Portal",
        "Azure Cloud Shell",
        "Microsoft Foundry",
        "Azure Machine Learning",
        "scripts/setup-cloud-shell.sh",
        "scripts/activate-cloud-shell.sh",
        "scripts/setup.sh",
        HANDOFF_ZIP,
    ):
        assert required in combined
    assert "dist/microsoft-foundry-agent-service-handson-portal.zip" not in combined
    assert "terraform_outputs" not in combined


def test_readmes_point_to_handoff_bundle_and_legacy_tag_only() -> None:
    readmes = (REPO_ROOT / "README.md", REPO_ROOT / "README.en.md")
    for readme_path in readmes:
        readme = readme_path.read_text(encoding="utf-8")
        targets = extract_link_targets(readme)

        assert HANDOFF_ZIP in readme
        assert LEGACY_TAG_URL in targets
        assert "docs/participant/environments/cloud-shell.md" in readme
        assert "docs/participant/environments/azure-ml.md" in readme
        assert all(
            "codespaces" not in target.casefold() or target == LEGACY_TAG_URL for target in targets
        )

    for source_file in OWNED_FILES:
        if "codespaces" in source_file.read_text(encoding="utf-8").casefold():
            assert source_file in readmes


def test_cloud_shell_provisioning_files_exist() -> None:
    for required in (
        "docs/participant/environments/cloud-shell.md",
        "scripts/setup-cloud-shell.sh",
        "scripts/activate-cloud-shell.sh",
        "scripts/setup.sh",
        "scripts/destroy.sh",
    ):
        assert (REPO_ROOT / required).is_file()
    assert (REPO_ROOT / "infra").is_dir()
    assert any((REPO_ROOT / "infra").glob("*.tf"))


def test_lab_one_covers_cloud_shell_provisioning_and_manual_azureml_handoff() -> None:
    lab = (LABS_DIR / "01-setup.md").read_text(encoding="utf-8")
    for required in (
        "Azure Cloud Shell Bash",
        "persistent `clouddrive`",
        "cd ~/clouddrive",
        "bash scripts/setup-cloud-shell.sh &&",
        "scripts/setup-cloud-shell.sh",
        "scripts/activate-cloud-shell.sh",
        "scripts/setup.sh",
        "built-in Python 3.12",
        "Foundry resource / project",
        "Azure AI Search",
        "Container App",
        "Luna 40K TPM",
        "GPT-5.5 100K TPM",
        "embedding 40K TPM",
        "Project Managed Identity",
        HANDOFF_ZIP,
        "Azure ML Compute instance は作成しません",
        "Lab 7",
    ):
        assert required in lab
    assert (
        '--query "{resourceGroup:name,location:location,state:properties.provisioningState}"'
        in lab
    )
    assert "cd ~\ngit clone" not in lab
    assert "100K TPM" in lab
    assert "40K TPM" in lab


def test_azureml_guide_preserves_security_persistence_and_cost_boundaries() -> None:
    guide = AZUREML_GUIDE.read_text(encoding="utf-8")
    for required in (
        "User files",
        "Compute instance",
        "Compute > Compute instances > New",
        "Standard_DS3_v2",
        "Python 3.10 - SDK v2",
        "Python (Foundry Workshop)",
        "Python (Foundry Hosted Agent)",
        "az login --use-device-code",
        "device code",
        "Idle shutdown",
        "Export",
        "Stop",
        "Delete",
    ):
        assert required in guide
    assert "Compute instance は作りません" in guide
    for forbidden in ("API key", "client secret", "No storage account required"):
        assert forbidden not in guide


def test_portal_labs_use_resource_outputs_and_required_gpt55() -> None:
    for filename in (
        "01-setup.md",
        "02-prompt-agent.md",
        "03-rag-foundry-iq.md",
        "05-evaluation.md",
        "06-optimization.md",
    ):
        text = (LABS_DIR / filename).read_text(encoding="utf-8")
        assert "terraform_outputs" not in text

    retrieval = (LABS_DIR / "03-rag-foundry-iq.md").read_text(encoding="utf-8")
    evaluation = (LABS_DIR / "05-evaluation.md").read_text(encoding="utf-8")
    optimization = (LABS_DIR / "06-optimization.md").read_text(encoding="utf-8")
    assert "resource_outputs" in retrieval
    assert "gpt-5.5" in retrieval
    assert "gpt-5.5" in evaluation
    assert "gpt-5.5" in optimization
    assert "optional" not in evaluation.casefold()


def test_toolbox_lab_uses_pre_downloaded_skills_and_live_openapi() -> None:
    lab = (LABS_DIR / "04-tools-toolbox.md").read_text(encoding="utf-8")
    for required in (
        "portal-assets/travel-estimation.zip",
        "portal-assets/preapproval-simulation.zip",
        "portal-assets/travel-ops.openapi.json",
        "OpenAPI 3.0+ schema",
        "Project Managed Identity",
        "Publish",
    ):
        assert required in lab


def test_hosted_labs_use_azureml_kernel_and_portal_context() -> None:
    for lab_name, notebook_name in (
        ("07-agent-framework-harness.md", "07-agent-framework-harness.ipynb"),
        ("08-hosted-multi-agent.md", "08-hosted-agent.ipynb"),
    ):
        text = (LABS_DIR / lab_name).read_text(encoding="utf-8")
        assert "Python (Foundry Hosted Agent)" in text
        assert f"../notebooks/{notebook_name}" in text
        assert "Azure ML" in text


def test_cleanup_orders_export_children_compute_destroy_and_resource_group() -> None:
    cleanup = (LABS_DIR / "09-observability-cleanup.md").read_text(encoding="utf-8")
    export = cleanup.index("**Export**")
    delete_agent = cleanup.index("delete_hosted_agent.py")
    stop_compute = cleanup.index("**Stop**", delete_agent)
    delete_compute = cleanup.index("**Delete**", stop_compute)
    activate = cleanup.index("source scripts/activate-cloud-shell.sh", delete_compute)
    destroy = cleanup.index("./scripts/destroy.sh", activate)
    verify_empty = cleanup.index("resource inventory が空", destroy)
    delete_group = cleanup.index("**Delete resource group**", verify_empty)
    exit_cloud_shell = cleanup.index("`exit`", delete_group)

    assert (
        export
        < delete_agent
        < stop_compute
        < delete_compute
        < activate
        < destroy
        < verify_empty
        < delete_group
        < exit_cloud_shell
    )


def test_architecture_assets_describe_hybrid_cloud_shell_azureml_path() -> None:
    rendered = REPO_ROOT / "docs" / "images" / "workshop-architecture.svg"
    source = REPO_ROOT / "docs" / "diagrams" / "workshop-architecture.excalidraw"
    assert rendered.is_file()
    assert source.is_file()

    svg = ET.parse(rendered)
    labels = " ".join(text for node in svg.iter() for text in node.itertext() if text)
    assert "Azure Machine Learning" in labels
    assert "Azure Portal" in labels
    assert "Cloud Shell" in labels
    assert "Codespaces" not in labels


def test_learning_flow_editable_source_remains_valid() -> None:
    source = REPO_ROOT / "docs" / "diagrams" / "workshop-learning-flow.excalidraw"
    diagram = json.loads(source.read_text(encoding="utf-8"))

    assert diagram["type"] == "excalidraw"
    for element in diagram["elements"]:
        if element["type"] == "text" and not element.get("isDeleted", False):
            assert element["width"] > 0
            assert element["height"] > 0

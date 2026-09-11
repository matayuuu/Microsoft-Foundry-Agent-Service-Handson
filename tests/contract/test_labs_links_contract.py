"""Participant contracts for manual RG, custom template, private ZIP, and Azure ML."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from scripts.build_participant_bundle import collect_source_files

REPO_ROOT = Path(__file__).resolve().parents[2]
LABS_DIR = REPO_ROOT / "labs"
AZUREML_GUIDE = REPO_ROOT / "docs" / "participant" / "environments" / "azure-ml.md"
TEMPLATE_GUIDE = REPO_ROOT / "docs" / "participant" / "environments" / "custom-template.md"
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
    *sorted((REPO_ROOT / "docs").rglob("*.md")),
    *sorted((REPO_ROOT / "instructor").rglob("*.md")),
    REPO_ROOT / "src" / "hosted-agent" / "README.md",
    *sorted((LABS_DIR / "optional").glob("*.md")),
]

_LINK_PATTERN = re.compile(r"\[[^\]\n]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HANDOFF_ZIP = ".workshop/download/foundry-workshop-files.zip"
BUNDLE_ROOT = "Microsoft-Foundry-Agent-Service-Handson"
PUBLIC_SOURCE_BASE = "https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/"
RETIRED_PATH_FRAGMENTS = (
    "environments/cloud-shell.md",
    "setup-cloud-shell.sh",
    "activate-cloud-shell.sh",
    "scripts/setup.sh",
    "scripts/destroy.sh",
    "prepare_serverless_foundry_iq",
    "prepare_terraform_plan",
    "codespaces-cloud-shell-v1",
    "clouddrive",
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


def normalized(text: str) -> str:
    return " ".join(text.split())


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


def test_bundled_markdown_links_resolve_inside_the_participant_allowlist() -> None:
    bundled_files = {path.resolve() for path in collect_source_files(REPO_ROOT)}
    missing: list[str] = []
    for source_file in sorted(bundled_files):
        if source_file.suffix != ".md":
            continue
        for target in extract_link_targets(source_file.read_text(encoding="utf-8")):
            if (
                not is_external_link(target)
                and resolve_link_path(source_file, target) not in bundled_files
            ):
                missing.append(f"{source_file.relative_to(REPO_ROOT)} -> {target}")
    assert not missing, "links target files excluded from the participant ZIP:\n" + "\n".join(
        missing
    )


def test_template_download_links_use_public_development_source_not_absent_main() -> None:
    for source_file in (
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.en.md",
        LABS_DIR / "01-setup.md",
        TEMPLATE_GUIDE,
        REPO_ROOT / "docs" / "admin" / "prerequisites.md",
    ):
        targets = [
            target
            for target in extract_link_targets(source_file.read_text(encoding="utf-8"))
            if target.endswith("/infra/azuredeploy.json")
        ]
        assert targets, f"{source_file.name} must link to the externally distributed template"
        for target in targets:
            assert target.startswith(PUBLIC_SOURCE_BASE)
            revision = target.removeprefix(PUBLIC_SOURCE_BASE).split("/", 1)[0]
            assert revision == "dev-custom-template" or re.fullmatch(r"[a-f0-9]{40}", revision)


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


def test_primary_path_uses_portal_template_private_download_and_azureml() -> None:
    primary_files = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.en.md",
        REPO_ROOT / "docs" / "participant" / "prerequisites.md",
        TEMPLATE_GUIDE,
        AZUREML_GUIDE,
        *CORE_LABS,
    ]
    combined = normalized("\n".join(path.read_text(encoding="utf-8") for path in primary_files))

    for required in (
        "Azure Portal",
        "Resource groups > Create",
        "Deploy a custom template",
        "Build your own template in the editor > Load file",
        "infra/azuredeploy.json",
        "Deployment Scripts",
        "Microsoft Entra user account",
        "Storage browser",
        "workshop-files",
        "Download",
        "Microsoft Foundry",
        "Azure Machine Learning",
        HANDOFF_ZIP,
        "resource_outputs.<key>.value",
    ):
        assert required in combined
    assert "dist/microsoft-foundry-agent-service-handson-portal.zip" not in combined
    assert "terraform_outputs" not in combined


def test_readmes_point_to_current_guides_and_immutable_handoff() -> None:
    readmes = (REPO_ROOT / "README.md", REPO_ROOT / "README.en.md")
    for readme_path in readmes:
        readme = readme_path.read_text(encoding="utf-8")
        assert HANDOFF_ZIP in readme
        assert BUNDLE_ROOT in readme
        assert "docs/participant/environments/custom-template.md" in readme
        assert "docs/participant/environments/azure-ml.md" in readme
        assert "Resource groups > Create" in readme
        assert "Deploy a custom template" in readme
        assert "Microsoft Entra user account" in readme
        assert "Delete resource group" in readme
        for lab_number, lab in enumerate(CORE_LABS):
            assert f"[Lab {lab_number}](labs/{lab.name})" in readme


def test_documentation_does_not_reintroduce_retired_provisioning() -> None:
    for source_file in OWNED_FILES:
        text = source_file.read_text(encoding="utf-8")
        for forbidden in RETIRED_PATH_FRAGMENTS:
            assert forbidden not in text, f"{source_file.name} references {forbidden}"
        if source_file.name != "AGENTS.md":
            for forbidden in ("Terraform", "terraform", "Cloud Shell", "Serverless", "serverless"):
                assert forbidden not in text, f"{source_file.name} retains {forbidden}"
        assert "Manage files > Download" not in text
        assert "terraform_outputs" not in text


def test_custom_template_provisioning_files_exist_without_retired_entrypoints() -> None:
    for required in (
        "docs/participant/environments/custom-template.md",
        "infra/main.bicep",
        "infra/azuredeploy.json",
        "scripts/bootstrap-custom-template.sh",
        "scripts/bootstrap_custom_template.py",
    ):
        assert (REPO_ROOT / required).is_file()
    for retired in RETIRED_PATH_FRAGMENTS[:5]:
        path = REPO_ROOT / ("docs/participant" if retired.startswith("environments/") else "")
        if "/" not in retired:
            path /= "scripts"
        assert not (path / retired).exists()
    assert not list((REPO_ROOT / "infra").glob("*.tf"))
    assert not list((REPO_ROOT / "docs" / "images").glob("*cloud-shell*"))


def test_lab_one_covers_template_initialization_and_private_azureml_handoff() -> None:
    lab = (LABS_DIR / "01-setup.md").read_text(encoding="utf-8")
    for required in (
        "Resource groups > Create",
        "Build your own template in the editor > Load file",
        "Review + create",
        "Succeeded",
        "status = complete",
        "Deployment Scripts",
        "private",
        "Microsoft Entra user account",
        "workshop-files",
        "resource_outputs.<key>.value",
        "setup_status = complete",
        "provisioning_method = azure-custom-template",
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
        "OnSuccess",
        "P1D",
        "Shared Key",
        "allowBlobPublicAccess: false",
        "defaultToOAuthAuthentication: true",
    ):
        assert required in lab
    for parameter in (
        "location",
        "primaryModelVersion",
        "evaluationModelVersion",
        "embeddingModelVersion",
        "travelApiImageRef",
        "sourceRevision",
        "participantObjectIdOverride",
        "bootstrapRunId",
    ):
        assert f"`{parameter}`" in lab
    assert "@sha256:" in lab
    assert "40 桁" in lab
    assert "公開済み" in lab
    assert "予約ではありません" in lab
    assert "代理" in lab
    assert "Entra object ID" in lab


def test_lab_one_manually_creates_rg_before_opening_template() -> None:
    lab = (LABS_DIR / "01-setup.md").read_text(encoding="utf-8")
    sections = [lab.index(f"## {number}.") for number in range(1, 7)]
    assert sections == sorted(sections)
    create_rg, load_template, parameters, bootstrap, download, extract = (
        lab[start:end] for start, end in pairwise([*sections, lab.index("## 完了チェック")])
    )
    assert "手動作成" in create_rg
    assert "**Resource groups > Create**" in create_rg
    assert "作成完了後" in create_rg
    assert "**Deploy a custom template**" in load_template
    assert "作成した RG を選びます" in load_template
    assert "**Create new** は使いません" in load_template
    assert "**Review + create**" in parameters
    assert "**Create**" in parameters
    assert "status = complete" in bootstrap
    assert "Microsoft Entra user account" in download
    assert "**Download**" in download
    assert BUNDLE_ROOT in extract
    assert "notebooks/00-azureml-setup.ipynb" in extract
    assert "src/hosted-agent/" in extract
    assert "tests/" in extract
    assert "bundle-manifest.json" in extract


def test_admin_guidance_preserves_published_inputs_identity_and_cleanup_boundaries() -> None:
    admin = (REPO_ROOT / "docs" / "admin" / "prerequisites.md").read_text(encoding="utf-8")
    for required in (
        "Owner 相当",
        "participantObjectIdOverride",
        "Entra User object ID",
        "bootstrapRunId",
        "sourceRevision",
        "GlobalStandard",
        "@sha256:",
        "Microsoft.ManagedIdentity",
        "Microsoft.ContainerInstance",
        "OnSuccess",
        "P1D",
        "Shared Key",
        "allowBlobPublicAccess: false",
        "defaultToOAuthAuthentication: true",
        "contoso-travel-search",
        "contoso-travel-knowledge-lab-mcp",
        "contoso-travel-appinsights",
        "Project Managed Identity",
        "Playwright",
    ):
        assert required in admin
    assert "capacity の証明や予約ではありません" in normalized(admin)
    assert "runtime MI に Owner や subscription-scope roles は与えません" in admin
    assert "参加者の provisioning 手順でも" in admin
    assert "実施結果と未実施項目を区別" in admin


def test_new_preparation_does_not_reuse_old_timing_claims() -> None:
    for path in (
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.en.md",
        LABS_DIR / "01-setup.md",
        TEMPLATE_GUIDE,
        REPO_ROOT / "docs" / "admin" / "prerequisites.md",
        REPO_ROOT / "instructor" / "runbook.md",
    ):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("10〜15", "10\u201315", "8〜10", "8\u201310", "35.5", "18.85", "6分42"):
            assert forbidden not in text


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
        "Upload folder",
        "resource_outputs.<key>.value",
        "Microsoft Entra user account",
        "workshop-files",
        BUNDLE_ROOT,
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
    assert "AAD Search resource connection" in (LABS_DIR / "02-prompt-agent.md").read_text(
        encoding="utf-8"
    )


def test_toolbox_lab_uses_pre_downloaded_skills_and_live_openapi() -> None:
    lab = (LABS_DIR / "04-tools-toolbox.md").read_text(encoding="utf-8")
    for required in (
        "portal-assets/travel-estimation.zip",
        "portal-assets/preapproval-simulation.zip",
        "portal-assets/travel-ops.openapi.json",
        "OpenAPI 3.0+ schema",
        "Project Managed Identity",
        "Publish",
        "Deployment Scripts",
        "servers[0].url",
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
        assert "resource_outputs.<key>.value" in text
        assert "00-azureml-setup.ipynb" in text


def test_cleanup_orders_export_hosted_compute_and_portal_resource_group_deletion() -> None:
    cleanup = (LABS_DIR / "09-observability-cleanup.md").read_text(encoding="utf-8")
    export = cleanup.index("**Export**", cleanup.index("## 2."))
    delete_agent = cleanup.index("delete_hosted_agent.py")
    stop_compute = cleanup.index("**Stop**", cleanup.index("## 3."))
    delete_compute = cleanup.index("**Delete**", stop_compute)
    delete_group = cleanup.index("**Delete resource group**", delete_compute)
    verify_deleted = cleanup.index("## 5. 削除完了を確認", delete_group)
    assert export < delete_agent < stop_compute < delete_compute < delete_group < verify_deleted
    assert "RG とまとめて削除" in cleanup
    assert "deployment history / deployment record" in cleanup
    assert "resources は削除されません" in normalized(cleanup)
    for forbidden in (
        "destroy.sh",
        "resource inventory が空",
        "空であることを確認",
        "empty RG",
        "`exit`",
    ):
        assert forbidden not in cleanup


@pytest.mark.parametrize("name", ["workshop-architecture", "workshop-learning-flow"])
def test_diagrams_match_editable_text_and_describe_current_participant_path(name: str) -> None:
    rendered = REPO_ROOT / "docs" / "images" / f"{name}.svg"
    source = REPO_ROOT / "docs" / "diagrams" / f"{name}.excalidraw"
    assert rendered.is_file()
    assert source.is_file()
    diagram = json.loads(source.read_text(encoding="utf-8"))
    svg = ET.parse(rendered).getroot()
    assert svg.attrib["role"] == "img"
    svg_text = {
        node.attrib["id"]: normalized(" ".join(node.itertext()))
        for node in svg.iter("{http://www.w3.org/2000/svg}text")
    }
    source_text = {
        element["id"]: normalized(element["text"])
        for element in diagram["elements"]
        if element["type"] == "text" and not element.get("isDeleted", False)
    }
    assert svg_text == source_text
    labels = " ".join(source_text.values())
    for required in (
        "Resource groups > Create",
        "Deploy a custom template",
        "Load file",
        "infra/azuredeploy.json",
        "existing RG",
        "Deployment Scripts",
        "Microsoft Entra user account",
        "workshop-files",
        "Azure Machine Learning",
        "Azure Portal",
        "Standard_DS3_v2",
        "Idle shutdown",
        "Python 3.10 - SDK v2",
        "Python (Foundry Hosted Agent)",
        "Delete resource group",
        "verify deletion",
        "deployment history",
    ):
        assert required in labels
    for forbidden in ("Cloud Shell", "Terraform", "Codespaces", "empty RG", "clouddrive"):
        assert forbidden not in labels


@pytest.mark.parametrize("name", ["workshop-architecture", "workshop-learning-flow"])
def test_editable_diagrams_keep_visible_text_and_transparent_containers(name: str) -> None:
    source = REPO_ROOT / "docs" / "diagrams" / f"{name}.excalidraw"
    diagram = json.loads(source.read_text(encoding="utf-8"))
    assert diagram["type"] == "excalidraw"
    assert diagram["version"] == 2
    elements = {
        element["id"]: element
        for element in diagram["elements"]
        if not element.get("isDeleted", False)
    }
    assert len(elements) == len(diagram["elements"])
    rectangles = [element for element in elements.values() if element["type"] == "rectangle"]
    for element in elements.values():
        if element["type"] == "text":
            assert element["width"] > 0
            minimum_height = element["fontSize"] * 2.5 * len(element["text"].splitlines())
            assert element["height"] >= minimum_height
            assert element["strokeColor"] == "#000000"
            if container_id := element.get("containerId"):
                container = elements[container_id]
                assert {"id": element["id"], "type": "text"} in container["boundElements"]
                assert element["x"] >= container["x"]
                assert element["y"] >= container["y"]
                assert element["x"] + element["width"] <= container["x"] + container["width"]
                assert element["y"] + element["height"] <= container["y"] + container["height"]
    for container in rectangles:
        for child in rectangles:
            if (
                container["id"] != child["id"]
                and container["x"] <= child["x"]
                and container["y"] <= child["y"]
                and child["x"] + child["width"] <= container["x"] + container["width"]
                and child["y"] + child["height"] <= container["y"] + container["height"]
            ):
                assert container["backgroundColor"] == "transparent"

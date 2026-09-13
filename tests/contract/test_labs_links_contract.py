"""Documentation contracts for Portal bootstrap, GitHub assets and Dev Containers."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from itertools import pairwise
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LABS_DIR = REPO_ROOT / "labs"
ENVIRONMENTS = REPO_ROOT / "docs" / "participant" / "environments"
CODESPACES_GUIDE = ENVIRONMENTS / "codespaces.md"
LOCAL_GUIDE = ENVIRONMENTS / "local-dev-container.md"
ADMIN_GUIDE = REPO_ROOT / "docs" / "admin" / "prerequisites.md"
CORE_LABS = [
    LABS_DIR / name
    for name in (
        "00-overview.md",
        "01-setup.md",
        "02-prompt-agent.md",
        "03-rag-foundry-iq.md",
        "04-tools-toolbox.md",
        "05-evaluation.md",
        "06-optimization.md",
        "07-agent-framework-harness.md",
        "08-hosted-multi-agent.md",
        "09-observability-cleanup.md",
    )
]
DOCUMENTS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "README.en.md",
    *sorted(LABS_DIR.rglob("*.md")),
    *sorted((REPO_ROOT / "docs").rglob("*.md")),
    *sorted((REPO_ROOT / "instructor").rglob("*.md")),
    REPO_ROOT / "src" / "hosted-agent" / "README.md",
]
REPOSITORY = "matayuuu/Microsoft-Foundry-Agent-Service-Handson"
COMMON_ASSETS = (
    "assets/skills/travel-estimation.zip",
    "assets/skills/preapproval-simulation.zip",
    "assets/openapi/travel-ops.openapi.json",
)
RETIRED_REFERENCES = (
    "environments/azure-ml.md",
    "00-azureml-setup.ipynb",
    "setup_azureml.py",
    "Azure ML",
    "Azure Machine Learning",
    "Standard_DS3_v2",
    "Storage browser",
    "participantDownload",
    "foundry-workshop-files.zip",
    "portal-assets/",
    "Upload folder",
    "conda run",
    "environments/cloud-shell.md",
    "setup-cloud-shell.sh",
    "activate-cloud-shell.sh",
    "scripts/setup.sh",
    "scripts/destroy.sh",
    "terraform_outputs",
)
RETIRED_IMAGES = (
    "lab01-azureml-compute.png",
    "lab01-azureml-idle-shutdown.png",
    "lab01-azureml-upload.png",
    "lab01-bootstrap-outputs.png",
    "lab01-private-zip-download.png",
)
LINK_PATTERN = re.compile(r"\[[^\]\n]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def normalized(text: str) -> str:
    return " ".join(text.replace("**", "").replace("`", "").split())


def assert_in_order(text: str, steps: tuple[str, ...]) -> None:
    text = normalized(text)
    position = 0
    for step in steps:
        index = text.find(step, position)
        assert index >= 0, f"missing or out-of-order step: {step}"
        position = index + len(step)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def links(path: Path) -> list[str]:
    return LINK_PATTERN.findall(read(path))


def local_links() -> list[tuple[Path, str]]:
    return [
        (path, target)
        for path in DOCUMENTS
        for target in links(path)
        if not urlsplit(target).scheme
    ]


def markdown_anchors(text: str) -> set[str]:
    anchors = set(re.findall(r'<a\s+(?:id|name)="([^"]+)"', text))
    counts: dict[str, int] = {}
    for heading in re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE):
        slug = re.sub(r"[^\w -]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        anchors.add(f"{slug}-{count}" if count else slug)
        counts[slug] = count + 1
    return anchors


@pytest.mark.parametrize(
    ("source", "target"),
    local_links(),
    ids=[f"{path.relative_to(REPO_ROOT)}::{target}" for path, target in local_links()],
)
def test_local_document_link_resolves(source: Path, target: str) -> None:
    parsed = urlsplit(target)
    resolved = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
    assert resolved.is_file(), f"{source.relative_to(REPO_ROOT)} -> {target}"
    if parsed.fragment and resolved.suffix == ".md":
        assert unquote(parsed.fragment) in markdown_anchors(read(resolved)), (
            f"{source.relative_to(REPO_ROOT)} -> missing anchor {target}"
        )


@pytest.mark.parametrize("readme", [REPO_ROOT / "README.md", REPO_ROOT / "README.en.md"])
def test_readmes_link_all_labs_and_supported_environments(readme: Path) -> None:
    targets = links(readme)
    for index, lab in enumerate(CORE_LABS):
        assert lab.is_file()
        assert f"[Lab {index}](labs/{lab.name})" in read(readme)
    for guide in ("custom-template.md", "codespaces.md", "local-dev-container.md"):
        assert f"docs/participant/environments/{guide}" in targets


def test_core_labs_link_to_next_lab() -> None:
    for current, following in pairwise(CORE_LABS):
        assert following.name in links(current)


@pytest.mark.parametrize("path", DOCUMENTS, ids=lambda path: str(path.relative_to(REPO_ROOT)))
def test_documents_do_not_reintroduce_retired_handoffs(path: Path) -> None:
    text = read(path)
    for retired in RETIRED_REFERENCES:
        assert retired not in text, f"{path.relative_to(REPO_ROOT)} retains {retired}"


def test_lab_one_creates_rg_then_deploys_defaults_and_waits_for_initialization() -> None:
    lab = read(CORE_LABS[1])
    assert_in_order(
        lab,
        (
            "Resource groups > Create",
            "Review + create > Create",
            "Deploy a custom template",
            "Load file",
            "Subscription",
            "Resource group",
            "既定値",
            "Review + create > Create",
            "Deployment Scripts",
            "Succeeded",
            "workshopContext",
            "setup_status = complete",
            "foundryPortalUrl",
        ),
    )
    for token in ("1 個手動作成", "Create new", "Participant Object Id Override", "空欄"):
        assert token in lab
    for output in ("resourceOutputs", "travelApiBaseUrl", "foundryPortalUrl"):
        assert output in lab


def test_public_source_links_use_development_branch_or_published_revision() -> None:
    prefixes = (
        f"https://github.com/{REPOSITORY}/blob/",
        f"https://github.com/{REPOSITORY}/tree/",
        f"https://raw.githubusercontent.com/{REPOSITORY}/",
    )
    for document in DOCUMENTS:
        for target in links(document):
            for prefix in prefixes:
                if target.startswith(prefix):
                    revision, _, path = (
                        urlsplit(target).path.removeprefix(urlsplit(prefix).path).partition("/")
                    )
                    assert revision == "dev-custom-template" or re.fullmatch(
                        r"[a-f0-9]{40}", revision
                    )
                    assert (REPO_ROOT / unquote(path)).exists(), target
    for document in (CORE_LABS[1], ADMIN_GUIDE):
        assert any(target.endswith("/infra/azuredeploy.json") for target in links(document))


def test_portal_labs_read_arm_outputs_without_requiring_local_context() -> None:
    for index in (2, 3, 5, 6):
        text = read(CORE_LABS[index])
        assert "resourceOutputs" in text
        assert ".workshop/context.json" not in text
    for index in (3, 5, 6):
        assert "gpt-5.5" in read(CORE_LABS[index])
    assert "AAD Search resource connection" in read(CORE_LABS[2])


def test_lab_four_downloads_shared_zip_files_and_replaces_only_the_openapi_server() -> None:
    lab = read(CORE_LABS[4])
    targets = links(CORE_LABS[4])
    for asset in COMMON_ASSETS:
        assert any(
            target.startswith(f"https://raw.githubusercontent.com/{REPOSITORY}/")
            and target.endswith(f"/{asset}")
            for target in targets
        )
        assert (REPO_ROOT / asset).is_file()
    for token in (
        "PC に保存",
        "SKILL.md",
        "直下",
        "servers[0].url",
        "travelApiBaseUrl",
        "OpenAPI 3.0+ schema",
        "Project Managed Identity",
        "Publish",
    ):
        assert token in lab
    for skill in ("travel-estimation", "preapproval-simulation"):
        assert f"../data/skills/{skill}/SKILL.md" in targets


def test_codespaces_guides_browser_creation_login_and_two_input_setup() -> None:
    guide = read(CODESPACES_GUIDE)
    assert_in_order(
        guide,
        (
            "Code > Codespaces",
            "postCreateCommand",
            "Terminal > New Terminal",
            "az login --use-device-code",
            "00-setup.ipynb",
            "Python (Foundry Workshop)",
            "subscription ID",
            "RG 名",
            ".workshop/context.json",
        ),
    )
    for token in (
        "GitHub や Azure Portal",
        "別",
        "scripts/configure_workshop.py",
        "workshopContext",
        "2.0",
        "resource_outputs.<key>.value",
        "~/.venvs/",
        "foundry-workshop",
        "foundry-hosted-agent",
        "3.12",
        "3.13",
    ):
        assert token in guide
    for target in links(CODESPACES_GUIDE):
        assert not target.startswith(
            ("https://codespaces.new/", "https://github.com/codespaces/new")
        )


def test_local_guide_uses_same_container_not_a_native_python_setup() -> None:
    guide = read(LOCAL_GUIDE)
    assert "ローカルで実施される方は以下の前提条件を確認下さい" in guide
    for prerequisite in ("Git", "Visual Studio Code", "Dev Containers", "Docker", "Azure"):
        assert prerequisite in guide
    assert_in_order(
        guide,
        ("git clone", "Dev Containers: Reopen in Container", "codespaces.md#共通手順"),
    )
    for unsupported in ("pip install", "python -m venv", "conda create", "conda activate"):
        assert unsupported not in guide


def test_documented_environment_interfaces_exist() -> None:
    for path in (
        ".devcontainer/devcontainer.json",
        "scripts/setup_dev_environment.py",
        "scripts/configure_workshop.py",
        "notebooks/00-setup.ipynb",
    ):
        assert (REPO_ROOT / path).is_file(), f"pending environment interface: {path}"
    assert not (ENVIRONMENTS / "azure-ml.md").exists()


def test_hosted_labs_use_hosted_kernel_and_confirm_management_actions() -> None:
    for index in (7, 8):
        text = read(CORE_LABS[index])
        for token in (
            "Codespaces",
            "local-dev-container.md",
            "00-setup.ipynb",
            "Python (Foundry Hosted Agent)",
            "foundry-hosted-agent",
            "resource_outputs.<key>.value",
        ):
            assert token in text
    lab_eight = read(CORE_LABS[8])
    for token in ("DEPLOY", "Agent 名", "foundry-workshop", "venv", "3.12", "ソースコード ZIP"):
        assert token in lab_eight


def test_model_defaults_match_generated_template() -> None:
    parameters = json.loads(read(REPO_ROOT / "infra" / "azuredeploy.json"))["parameters"]
    admin = read(ADMIN_GUIDE)
    for model in ("primary", "evaluation", "embedding"):
        name = f"{model}ModelVersion"
        row = next(line for line in admin.splitlines() if f"`{name}`" in line)
        assert f"`{parameters[name]['defaultValue']}`" in row
    for model, capacity in (("gpt-5.6-luna", 40), ("gpt-5.5", 100), ("text-embedding-3-small", 40)):
        row = next(line for line in admin.splitlines() if f"`{model}`" in line)
        assert f"{capacity}K TPM" in row
    for token in (
        "sourceRevision",
        "公開済み",
        "互換",
        "participantObjectIdOverride",
        "bootstrapRunId",
    ):
        assert token in admin


def test_cleanup_saves_results_before_hosted_codespace_and_rg_deletion() -> None:
    cleanup = read(CORE_LABS[9])
    assert_in_order(
        cleanup,
        (
            "Save All",
            "Export",
            "Python (Foundry Hosted Agent)",
            "Agent 名",
            "foundry-workshop",
            "全 versions",
            "Stop codespace",
            "Delete",
            "Delete resource group",
            "RG が消えたことを確認",
        ),
    )
    assert "https://github.com/codespaces" in cleanup
    assert re.search(r"自分.*専用 RG", cleanup)
    assert re.search(r"デプロイ履歴.*リソース.*消えません", cleanup)


@pytest.mark.parametrize("name", ["workshop-architecture", "workshop-learning-flow"])
def test_diagrams_preserve_text_geometry_and_current_flow(name: str) -> None:
    diagram = json.loads(read(REPO_ROOT / "docs" / "diagrams" / f"{name}.excalidraw"))
    svg = ET.parse(REPO_ROOT / "docs" / "images" / f"{name}.svg").getroot()
    assert diagram["type"] == "excalidraw" and diagram["version"] == 2
    assert svg.attrib["role"] == "img"
    elements = {element["id"]: element for element in diagram["elements"]}
    assert len(elements) == len(diagram["elements"])
    source_text = {
        key: normalized(element["text"])
        for key, element in elements.items()
        if element["type"] == "text"
    }
    svg_text = {
        node.attrib["id"]: normalized(" ".join(node.itertext()))
        for node in svg.iter("{http://www.w3.org/2000/svg}text")
    }
    assert svg_text == source_text
    labels = " ".join(source_text.values())
    for token in (
        "Resource groups > Create",
        "existing RG",
        "Deployment Scripts",
        "GitHub",
        "Codespaces",
        "local Dev Container",
        "Azure CLI",
        "00-setup.ipynb",
        "Python (Foundry Hosted Agent)",
        "Delete resource group",
        "verify deletion",
    ):
        assert token in labels
    for retired in RETIRED_REFERENCES:
        assert retired not in labels
    svg_rectangles = {
        node.attrib.get("id"): node for node in svg.iter("{http://www.w3.org/2000/svg}rect")
    }
    rectangles = [element for element in elements.values() if element["type"] == "rectangle"]
    for element in rectangles:
        for dimension in ("x", "y", "width", "height"):
            assert float(svg_rectangles[element["id"]].attrib[dimension]) == element[dimension]
        for child in rectangles:
            if (
                element["id"] != child["id"]
                and element["x"] <= child["x"]
                and element["y"] <= child["y"]
                and child["x"] + child["width"] <= element["x"] + element["width"]
                and child["y"] + child["height"] <= element["y"] + element["height"]
            ):
                assert element["backgroundColor"] == "transparent"
    for element in elements.values():
        if element["type"] != "text":
            continue
        assert element["width"] > 0
        assert element["height"] >= element["fontSize"] * 2.5 * len(element["text"].splitlines())
        assert element["strokeColor"] == "#000000"
        if container_id := element.get("containerId"):
            container = elements[container_id]
            assert {"id": element["id"], "type": "text"} in container["boundElements"]
            assert element["x"] >= container["x"] and element["y"] >= container["y"]
            assert element["x"] + element["width"] <= container["x"] + container["width"]
            assert element["y"] + element["height"] <= container["y"] + container["height"]


def test_retired_screenshots_are_removed_but_generic_completion_example_remains() -> None:
    images = REPO_ROOT / "docs" / "images"
    for filename in RETIRED_IMAGES:
        assert not (images / filename).exists()
    assert (images / "lab01-template-succeeded.png").is_file()

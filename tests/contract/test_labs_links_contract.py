"""Contract test: local workshop and environment-guide markdown links resolve.

The checked path includes the root README files, all core labs, both environment
guides, and their participant, administrator, instructor, and developer support docs.
A relative markdown link that silently rots (wrong path, typo, moved file) is a
real participant-facing failure -- they would click through mid-workshop and hit
a 404. This test statically extracts every ``[text](target)`` link from the
owned files and asserts that every *relative* target (i.e. not ``http(s)://`` or
``mailto:``) resolves to a real file on disk, relative to the linking file's own
directory.

Fragment identifiers (``#section``) are stripped before resolving the file part
only -- this test does not attempt to reproduce GitHub's heading-slug algorithm
for Japanese/CJK headings, so it cannot (and does not try to) verify that the
fragment itself corresponds to a real heading. A pure same-file fragment link
(target starts with ``#``) is treated as always valid.

Every core lab is required.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LABS_DIR = REPO_ROOT / "labs"
ENVIRONMENTS_DIR = REPO_ROOT / "docs" / "participant" / "environments"
OWNED_FILES = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "README.en.md",
    REPO_ROOT / "AGENTS.md",
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
    REPO_ROOT / "docs" / "participant" / "prerequisites.md",
    REPO_ROOT / "docs" / "participant" / "troubleshooting.md",
    ENVIRONMENTS_DIR / "codespaces.md",
    ENVIRONMENTS_DIR / "cloud-shell.md",
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
]

_LINK_PATTERN = re.compile(r"\[[^\]\n]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def extract_link_targets(markdown_text: str) -> list[str]:
    """Return every markdown link target ``[text](target)`` found in ``markdown_text``.

    Deliberately regex-based (not a full markdown parser) since the only thing
    this contract cares about is the literal link target string. Image
    references (``![alt](target)``) use the identical ``(target)`` syntax and
    are intentionally included too -- a broken image link is just as much of a
    participant-facing rot as a broken text link.
    """
    return _LINK_PATTERN.findall(markdown_text)


def is_external_link(target: str) -> bool:
    """True for links this contract does not check (external URLs, mailto, bare fragments)."""
    if target.startswith("#"):
        return True
    scheme = urlsplit(target).scheme
    return scheme in {"http", "https", "mailto"}


def resolve_link_path(source_file: Path, target: str) -> Path:
    """Resolve a relative markdown link ``target`` against the directory of ``source_file``.

    Strips a trailing ``#fragment`` (not validated, see module docstring) and a
    leading ``./`` before joining, matching how a browser/renderer would
    resolve the same relative link.
    """
    path_part = target.split("#", 1)[0]
    if not path_part:
        # Pure fragment link (e.g. "file.md#section" with empty path handled
        # above by is_external_link for "#section"; this branch is defensive).
        raise ValueError(f"link target {target!r} has no file path component")
    return (source_file.parent / path_part).resolve()


@pytest.mark.parametrize("source_file", OWNED_FILES, ids=lambda p: p.name)
def test_owned_lab_file_exists(source_file: Path) -> None:
    assert source_file.is_file(), f"expected owned file to exist: {source_file}"


def _iter_relative_link_cases() -> list[tuple[Path, str]]:
    cases: list[tuple[Path, str]] = []
    for source_file in OWNED_FILES:
        if not source_file.is_file():
            continue
        text = source_file.read_text(encoding="utf-8")
        for target in extract_link_targets(text):
            if not is_external_link(target):
                cases.append((source_file, target))
    return cases


@pytest.mark.parametrize(
    ("source_file", "target"),
    _iter_relative_link_cases(),
    ids=[f"{sf.name}::{t}" for sf, t in _iter_relative_link_cases()],
)
def test_relative_link_resolves_to_a_real_file(source_file: Path, target: str) -> None:
    resolved = resolve_link_path(source_file, target)
    assert resolved.is_file(), (
        f"{source_file.relative_to(REPO_ROOT)} links to {target!r}, which resolves to "
        f"{resolved}, but that file does not exist."
    )


def test_every_owned_file_links_onward_or_is_the_final_lab() -> None:
    """Every lab except the last one must link to *something* under labs/.

    A cheap tripwire against accidentally deleting the "next steps" link at
    the bottom of a lab, which would strand a participant with no way to
    discover the next file from within the document itself.
    """
    final_lab = LABS_DIR / "09-observability-cleanup.md"
    for source_file in OWNED_FILES:
        if source_file == final_lab or not source_file.is_file():
            continue
        text = source_file.read_text(encoding="utf-8")
        targets = extract_link_targets(text)
        has_lab_link = any(
            not is_external_link(t) and resolve_link_path(source_file, t).suffix == ".md"
            for t in targets
        )
        assert has_lab_link, f"{source_file.name} has no onward markdown link"


def test_readme_agenda_links_every_lab_and_uses_duration_columns() -> None:
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

    assert "| Lab | 内容 | 所要時間\uff08目安\uff09 |" in readme
    assert "00:00-" not in readme
    for lab_number, filename in enumerate(
        [
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
        ]
    ):
        assert f"[Lab {lab_number}](labs/{filename})" in readme


def test_readme_architecture_assets_exist() -> None:
    rendered = REPO_ROOT / "docs" / "images" / "workshop-architecture.svg"
    assert rendered.is_file()
    svg = rendered.read_text(encoding="utf-8")
    for required in (
        "Existing Azure Resource Group",
        "Microsoft Foundry account",
        "Foundry project",
        "Azure AI Search",
        "Azure Container Apps environment",
        "Official Azure service icons",
    ):
        assert required in svg
    for omitted in ("AZURE SUBSCRIPTION", "OBSERVABILITY", ">Evaluation<"):
        assert omitted not in svg

    source = REPO_ROOT / "docs" / "diagrams" / "workshop-architecture.excalidraw"
    assert source.is_file()

    diagram = json.loads(source.read_text(encoding="utf-8"))
    assert diagram["type"] == "excalidraw"
    for element in diagram["elements"]:
        if element["type"] == "text":
            assert element["width"] > 0
            assert element["height"] > 0
            assert element["strokeColor"] == "#000000"
        if element["type"] == "rectangle" and element["id"].endswith(
            ("container", "resource-group", "foundry-account", "foundry-project")
        ):
            assert element["backgroundColor"] == "transparent"
    element_ids = {element["id"] for element in diagram["elements"]}
    assert element_ids.isdisjoint({"subscription", "evaluation", "monitoring"})


def test_learning_flow_source_and_rendered_labels_agree() -> None:
    source = REPO_ROOT / "docs" / "diagrams" / "workshop-learning-flow.excalidraw"
    rendered = REPO_ROOT / "docs" / "images" / "workshop-learning-flow.svg"
    diagram = json.loads(source.read_text(encoding="utf-8"))
    svg = ET.parse(rendered).getroot()
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    svg_labels = {
        node.attrib["id"]: " ".join("".join(node.itertext()).split())
        for node in svg.findall(".//svg:text", namespace)
    }

    assert diagram["type"] == "excalidraw"
    for element in diagram["elements"]:
        if element["type"] == "text" and not element.get("isDeleted", False):
            assert element["width"] > 0 and element["height"] > 0
            assert element["strokeColor"] == "#000000"
            assert svg_labels[element["id"]] == " ".join(element["text"].split())
    assert "会話する" not in svg_labels["lab2-prompt-text"]
    assert "Foundry IQ" in svg_labels["lab7-independent-note-text"]


def test_portal_labs_use_setup_prepared_evaluation_assets() -> None:
    setup = (REPO_ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")
    evaluation = (LABS_DIR / "05-evaluation.md").read_text(encoding="utf-8")
    optimization = (LABS_DIR / "06-optimization.md").read_text(encoding="utf-8")

    assert "--prepare-only" in setup
    assert "contoso-travel-eval-live-subset" in evaluation
    assert "contoso-travel-eval-live-subset" in optimization
    assert "Contoso Travel Rubric" in optimization


def test_core_labs_use_gpt55_for_evaluation_and_optimizer() -> None:
    retrieval = (LABS_DIR / "03-rag-foundry-iq.md").read_text(encoding="utf-8")
    evaluation = (LABS_DIR / "05-evaluation.md").read_text(encoding="utf-8")
    optimization = (LABS_DIR / "06-optimization.md").read_text(encoding="utf-8")

    assert "knowledge_model: .primary_model_deployment_name.value" in retrieval
    assert "gpt-5.5" not in retrieval
    assert "evaluation_model_deployment_name" in evaluation
    assert "gpt-5.5" in evaluation
    assert "evaluation_model: .optimizer_model_deployment_name.value" in optimization
    assert "optimization_model: .optimizer_model_deployment_name.value" in optimization
    assert "gpt-5.5" in optimization
    assert "Max candidates | `1`" in optimization
    assert "optimizer-run.simulated.json" in optimization
    assert "agent-optimizer-overview#models" in optimization


def test_toolbox_lab_uses_portal_for_openapi_and_skills() -> None:
    lab = (LABS_DIR / "04-tools-toolbox.md").read_text(encoding="utf-8")
    for step in (
        "Build > Tools",
        "Create toolbox",
        "Select a tool > Custom > OpenAPI tool",
        "OpenAPI 3.0+ schema",
        "Add skill > Upload skill",
        "Publish",
        "prepare_toolbox_assets.py",
        "travel-estimation",
        "preapproval-simulation",
        "resources/list",
        "resources/read",
        "登録・公開済み",
        "利用は未確認",
    ):
        assert step in lab
    assert "Notebook は本編では使いません" in lab
    assert "Conversations view" in lab
    assert "execute_tool" in lab
    assert "tools/call" in lab
    assert lab.index("Always auto-approve all tools") < lab.index("Playground の **New chat**")
    assert "Approve once" not in lab


def test_beginner_path_handles_observed_portal_defaults() -> None:
    prompt = (LABS_DIR / "02-prompt-agent.md").read_text(encoding="utf-8")
    toolbox = (LABS_DIR / "04-tools-toolbox.md").read_text(encoding="utf-8")
    optimization = (LABS_DIR / "06-optimization.md").read_text(encoding="utf-8")
    hosted = (LABS_DIR / "08-hosted-multi-agent.md").read_text(encoding="utf-8")
    codespaces = (ENVIRONMENTS_DIR / "codespaces.md").read_text(encoding="utf-8")

    assert "Web search" in prompt and "Remove" in prompt
    assert "web_search" in toolbox and "code_interpreter" in toolbox
    assert "最初から入っている場合は残します" in toolbox
    assert "FoundryMCPServerpreview" in toolbox
    assert "**Actions > Remove**" in toolbox
    assert "Select dataset and criteria" in optimization
    assert "Generate data" in optimization
    assert "Jupyter Kernel..." in codespaces
    assert "Python (Foundry Hosted Agent)" in hosted
    assert "src/hosted-agent/.venv/bin/python" in hosted
    assert "Recommended" in codespaces


def test_environment_selection_converges_on_common_labs_and_notebooks() -> None:
    for source in (
        REPO_ROOT / "README.md",
        REPO_ROOT / "README.en.md",
        REPO_ROOT / "docs" / "participant" / "prerequisites.md",
        LABS_DIR / "01-setup.md",
    ):
        text = source.read_text(encoding="utf-8")
        assert "environments/codespaces.md" in text
        assert "environments/cloud-shell.md" in text

    for lab, notebook in (
        ("07-agent-framework-harness.md", "07-agent-framework-harness.ipynb"),
        ("08-hosted-multi-agent.md", "08-hosted-agent.ipynb"),
    ):
        text = (LABS_DIR / lab).read_text(encoding="utf-8")
        assert f"../notebooks/{notebook}" in text
        assert "Python (Foundry Hosted Agent)" in text
        assert "environments/codespaces.md#notebook" in text
        assert "environments/cloud-shell.md#notebook" in text
        assert "sudo apt-get" not in text

    codespaces = (ENVIRONMENTS_DIR / "codespaces.md").read_text(encoding="utf-8")
    for preserved_asset in (
        "lab00-create-codespace.png",
        "lab07-hosted-kernel.png",
        "lab08-stop-codespace.png",
    ):
        assert preserved_asset in codespaces
    assert "Codespaces: Stop Current Codespace" in codespaces

    cleanup = (LABS_DIR / "09-observability-cleanup.md").read_text(encoding="utf-8")
    assert cleanup.index("./scripts/destroy.sh") < cleanup.index("environments/cloud-shell.md#stop")
    assert "environments/codespaces.md#stop" in cleanup


def test_participant_creates_an_empty_workload_group_before_lab_one() -> None:
    prerequisites = (REPO_ROOT / "docs" / "participant" / "prerequisites.md").read_text(
        encoding="utf-8"
    )
    lab_one = (LABS_DIR / "01-setup.md").read_text(encoding="utf-8")

    for required in (
        "Resource groups",
        "Review + create > Create",
        "Resources**が0件",
        "Access control (IAM) > View my access",
        "Owner",
        "Cloud Shellの初回画面が自動作成する",
        "Storage用RGは別物",
    ):
        assert required in prerequisites
    assert prerequisites.index("教材workload用のリソースグループを作成する") < (
        prerequisites.index("実行環境を選ぶ")
    )
    assert "参加者向け前提条件で自分が作成したworkload用RG" in lab_one
    assert "az group create" not in prerequisites
    assert "az group create" not in lab_one


def test_cloud_shell_guide_keeps_a_concise_participant_workflow() -> None:
    cloud_shell = (ENVIRONMENTS_DIR / "cloud-shell.md").read_text(encoding="utf-8")
    for required in (
        "Mount storage account",
        "We will create a storage account for you",
        "Select existing storage account",
        "No storage account required",
        "https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson.git",
        'git clone --branch "<branch-name>" --single-branch',
        'id="setup"',
        'id="persistence"',
        "Restart",
        'id="jupyter"',
        "start-cloud-shell-jupyter.sh",
        "source scripts/activate-cloud-shell.sh",
        'id="notebook"',
        "Python (Foundry Hosted Agent)",
        "%pip install",
        'id="files"',
        'realpath --relative-to="$HOME"',
        ".workshop/toolbox/travel-estimation.zip",
        ".workshop/toolbox/preapproval-simulation.zip",
        "Manage files > Download",
        "Download file",
        'id="resume"',
        "20分",
        'id="stop"',
        "Delete resource group",
        "Terraform state",
        "XSRF",
    ):
        assert required in cloud_shell
    assert len(cloud_shell.splitlines()) <= 250
    assert cloud_shell.index("We will create a storage account for you") < cloud_shell.index(
        "Select existing storage account"
    )
    assert "教材workload用RGは`destroy.sh`でもこの手順でも削除しません" in cloud_shell
    for removed in (
        "## 1. 入力する値と組織の許可を確認する",
        "## 3. 永続 storage と Bash を確認する",
        "standalone CPython",
        "micromamba",
        "SHA-256",
        "HTTP polling",
        "Secure / HttpOnly",
    ):
        assert removed not in cloud_shell
    stop = cloud_shell.split("## Lab 9後に終了する", 1)[1].split("## 公式資料", 1)[0]
    assert re.findall(r"^\d+\.", stop, re.MULTILINE) == ["1.", "2.", "3."]
    assert "File > Shut Down" not in stop
    assert "Close port" not in stop
    commands = "\n".join(re.findall(r"```bash\n(.*?)```", cloud_shell, re.DOTALL))
    for forbidden in (
        "sudo ",
        "apt-get ",
        "--allow-origin=*",
        "az group create",
        "az group delete",
    ):
        assert forbidden not in commands


def test_hosted_notebook_keeps_practical_notices_without_preview_disclaimer() -> None:
    notebook = json.loads(
        (REPO_ROOT / "notebooks" / "08-hosted-agent.ipynb").read_text(encoding="utf-8")
    )
    introduction = "".join(notebook["cells"][0]["source"])

    assert "プレビューの制約" not in introduction
    assert "架空のデータだけ" in introduction
    assert "モデル利用料金" in introduction
    assert "別途の実行料金" in introduction
    assert "Run All ではデプロイしません" in introduction


def test_overview_and_setup_omit_instructor_led_basics() -> None:
    overview = (LABS_DIR / "00-overview.md").read_text(encoding="utf-8")
    setup = (LABS_DIR / "01-setup.md").read_text(encoding="utf-8")
    for heading in ("最初に知っておく言葉", "操作面の使い分け", "モデルと自分の環境の値"):
        assert heading not in overview
    assert "新しい画面を English・ダークモードに揃える" not in setup
    project_selection = setup.split("## 6.", 1)[1].split("## 完了チェック", 1)[0]
    assert "![" not in project_selection


def test_prompt_creation_and_search_attachment_use_scoped_saves() -> None:
    prompt = (LABS_DIR / "02-prompt-agent.md").read_text(encoding="utf-8")
    creation = prompt.split("## 1.", 1)[1].split("## 2.", 1)[0]
    initial_configuration = prompt.split("## 1.", 1)[1].split("## 5.", 1)[0]
    search_attachment = prompt.split("## 5.", 1)[1].split("## 6.", 1)[0]
    assert creation.count("![") == 1
    assert "lab02-agent-list.png" in creation
    assert initial_configuration.count("**Save**") == 1
    assert "まとめて保存" in initial_configuration
    assert search_attachment.count("**Save**") == 1
    assert "contoso-travel-policy" in search_attachment
    assert "囲みのバッククォート" not in prompt


def test_search_learning_steps_are_split_between_prompt_and_iq_labs() -> None:
    prompt = (LABS_DIR / "02-prompt-agent.md").read_text(encoding="utf-8")
    retrieval = (LABS_DIR / "03-rag-foundry-iq.md").read_text(encoding="utf-8")

    assert "## 5. Azure AI Search tool を接続する" in prompt
    assert "## 6. Direct search と citation を確認する" in prompt
    assert "東京から大阪へ日帰り出張する場合" in prompt
    assert "## 1. Foundry IQ knowledge base を作成する" in retrieval
    assert "## 1. Azure AI Search tool を接続する" not in retrieval
    assert "Lab 2 と同じ質問" in retrieval
    assert "規程を参照した回答には出典を付け" in prompt


def test_core_labs_do_not_show_answer_screenshots_or_numbered_image_captions() -> None:
    excluded_images = {
        "lab03-direct-answer.png",
        "lab03-direct-comparison.png",
        "lab03-iq-answer.png",
        "lab03-iq-sources.png",
        "lab04-estimate-result.png",
        "lab04-estimate-output.png",
        "lab05-evaluation-results.png",
        "lab05-read-reason.png",
        "lab06-optimizer-results.png",
        "lab06-view-changes.png",
        "lab06-rubric-reason.png",
        "lab08-hosted-agent-playground.png",
        "lab09-reviewer-output.png",
    }
    for source in OWNED_FILES:
        if source.parent != LABS_DIR:
            continue
        text = source.read_text(encoding="utf-8")
        assert not re.search(r"!\[[^\]]*\d+[:\uff1a]", text)
        assert all(image not in text for image in excluded_images)


# ---------------------------------------------------------------------------
# Pure-function unit coverage (no filesystem access) for the helpers above.
# ---------------------------------------------------------------------------


def test_extract_link_targets_finds_plain_and_titled_links() -> None:
    text = (
        "See [Lab 1](01-setup.md) and "
        '[external](https://example.com "a title") and ![alt](../img/x.png).'
    )
    assert extract_link_targets(text) == [
        "01-setup.md",
        "https://example.com",
        "../img/x.png",
    ]


def test_is_external_link_classifies_correctly() -> None:
    assert is_external_link("https://learn.microsoft.com/azure") is True
    assert is_external_link("http://example.com") is True
    assert is_external_link("mailto:someone@example.com") is True
    assert is_external_link("#section") is True
    assert is_external_link("../docs/architecture.md") is False
    assert is_external_link("01-setup.md") is False
    assert is_external_link("../docs/costs-and-cleanup.md#cleanup-order") is False


def test_resolve_link_path_strips_fragment_and_joins_relative(tmp_path: Path) -> None:
    labs_dir = tmp_path / "labs"
    labs_dir.mkdir()
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    target_file = docs_dir / "architecture.md"
    target_file.write_text("# Architecture\n", encoding="utf-8")
    source_file = labs_dir / "00-overview.md"

    resolved = resolve_link_path(source_file, "../docs/architecture.md#some-heading")

    assert resolved == target_file.resolve()
    assert resolved.is_file()

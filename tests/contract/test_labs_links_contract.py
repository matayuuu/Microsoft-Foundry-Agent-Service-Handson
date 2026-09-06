"""Contract test: every local markdown link in the participant path resolves.

This workstream owns the root README files, ``labs/00-overview.md`` through
``labs/08-observability-cleanup.md``, and participant support docs. It also reads
several sibling docs it does not own (``README.md``, ``docs/architecture.md``,
``docs/feature-support-matrix.md``, ``docs/costs-and-cleanup.md``,
``docs/participant/prerequisites.md``, ``docs/admin/troubleshooting.md``).
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
OWNED_FILES = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "README.en.md",
    LABS_DIR / "00-overview.md",
    LABS_DIR / "01-setup.md",
    LABS_DIR / "02-prompt-agent.md",
    LABS_DIR / "03-rag-foundry-iq.md",
    LABS_DIR / "04-tools-toolbox.md",
    LABS_DIR / "05-evaluation.md",
    LABS_DIR / "06-optimization.md",
    LABS_DIR / "07-hosted-multi-agent.md",
    LABS_DIR / "08-observability-cleanup.md",
    REPO_ROOT / "docs" / "participant" / "prerequisites.md",
    REPO_ROOT / "docs" / "participant" / "troubleshooting.md",
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
    final_lab = LABS_DIR / "08-observability-cleanup.md"
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
            "07-hosted-multi-agent.md",
            "08-observability-cleanup.md",
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
    assert "には接続しない" in svg_labels["lab7-independent-note-text"]


def test_portal_labs_use_setup_prepared_evaluation_assets() -> None:
    setup = (REPO_ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")
    evaluation = (LABS_DIR / "05-evaluation.md").read_text(encoding="utf-8")
    optimization = (LABS_DIR / "06-optimization.md").read_text(encoding="utf-8")

    assert "--prepare-only" in setup
    assert "contoso-travel-eval-live-subset" in evaluation
    assert "contoso-travel-eval-live-subset" in optimization
    assert "Contoso Travel Rubric" in optimization


def test_core_labs_use_gpt55_for_iq_planning_evaluation_and_optimization() -> None:
    retrieval = (LABS_DIR / "03-rag-foundry-iq.md").read_text(encoding="utf-8")
    evaluation = (LABS_DIR / "05-evaluation.md").read_text(encoding="utf-8")
    optimization = (LABS_DIR / "06-optimization.md").read_text(encoding="utf-8")

    assert "knowledge_model: .optimizer_model_deployment_name.value" in retrieval
    assert "knowledge_model: .primary_model_deployment_name.value" not in retrieval
    assert "gpt-5.5" in retrieval
    assert "gpt-5.5" in evaluation
    assert "evaluation_model: .optimizer_model_deployment_name.value" in optimization
    assert "optimization_model: .optimizer_model_deployment_name.value" in optimization
    assert "gpt-5.5" in optimization


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


def test_beginner_path_handles_observed_portal_defaults() -> None:
    prompt = (LABS_DIR / "02-prompt-agent.md").read_text(encoding="utf-8")
    toolbox = (LABS_DIR / "04-tools-toolbox.md").read_text(encoding="utf-8")
    optimization = (LABS_DIR / "06-optimization.md").read_text(encoding="utf-8")
    hosted = (LABS_DIR / "07-hosted-multi-agent.md").read_text(encoding="utf-8")

    assert "Web search" in prompt and "Remove" in prompt
    for default_tool in ("web_search", "code_interpreter", "FoundryMCPServerpreview"):
        assert default_tool in toolbox
    assert "Select dataset and criteria" in optimization
    assert "Generate data" in optimization
    assert "Jupyter Kernel..." in hosted
    assert "src/hosted-agent/.venv/bin/python" in hosted
    assert "Recommended" in hosted


def test_hosted_notebook_keeps_practical_notices_without_preview_disclaimer() -> None:
    notebook = json.loads(
        (REPO_ROOT / "notebooks" / "07-hosted-agent.ipynb").read_text(encoding="utf-8")
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


def test_prompt_creation_uses_one_entry_image_and_one_final_save() -> None:
    prompt = (LABS_DIR / "02-prompt-agent.md").read_text(encoding="utf-8")
    creation = prompt.split("## 1.", 1)[1].split("## 2.", 1)[0]
    assert creation.count("![") == 1
    assert "lab02-agent-list.png" in creation
    assert prompt.count("**Save**") == 1
    assert "まとめて保存" in prompt
    assert "囲みのバッククォート" not in prompt


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
        "lab07-hosted-agent-playground.png",
        "lab08-reviewer-output.png",
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

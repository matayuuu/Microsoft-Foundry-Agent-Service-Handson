"""Contract test: every local markdown link under labs/optional/ and instructor/ resolves.

This workstream owns ``labs/optional/**`` and ``instructor/**`` exclusively (see the
`author-optional-content` todo). It must not modify ``tests/contract/test_labs_links_contract.py``
(owned by the core-labs workstream), so this is a deliberately separate, self-contained test
module that duplicates the small amount of link-extraction/resolution logic needed, scoped only
to the files this workstream authors.

Unlike the core-labs link contract, the optional labs are **not** a fixed linear sequence (see
``labs/optional/README.md`` "読む順序"), so this test does not enforce a "must link onward"
tripwire per file. Instead it enforces the weaker, more relevant invariant that the two index
files (``labs/optional/README.md`` and ``instructor/README.md``) actually link to every sibling
document they are supposed to index, so a newly authored (or renamed) file can never silently
become undiscoverable.

Links into files outside this workstream's ownership (e.g. ``../00-overview.md``,
``../../README.md``, ``../../docs/architecture.md``) are still resolved and checked -- a
dangling cross-link is just as much a participant/instructor-facing 404 as a link within the
owned tree, and checking it does not require *modifying* any file outside the owned tree.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
OPTIONAL_LABS_DIR = REPO_ROOT / "labs" / "optional"
INSTRUCTOR_DIR = REPO_ROOT / "instructor"

_LINK_PATTERN = re.compile(r"\[[^\]\n]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def extract_link_targets(markdown_text: str) -> list[str]:
    """Return every markdown link target ``[text](target)`` found in ``markdown_text``."""
    return _LINK_PATTERN.findall(markdown_text)


def is_external_link(target: str) -> bool:
    """True for links this contract does not check (external URLs, mailto, bare fragments)."""
    if target.startswith("#"):
        return True
    scheme = urlsplit(target).scheme
    return scheme in {"http", "https", "mailto"}


def resolve_link_path(source_file: Path, target: str) -> Path:
    """Resolve a relative markdown link ``target`` against the directory of ``source_file``."""
    path_part = target.split("#", 1)[0]
    if not path_part:
        raise ValueError(f"link target {target!r} has no file path component")
    return (source_file.parent / path_part).resolve()


def _discover_owned_markdown_files() -> list[Path]:
    """All markdown files under labs/optional/ and instructor/, sorted for stable test ids."""
    files: list[Path] = []
    for base in (OPTIONAL_LABS_DIR, INSTRUCTOR_DIR):
        if base.is_dir():
            files.extend(base.rglob("*.md"))
    return sorted(files)


OWNED_MARKDOWN_FILES = _discover_owned_markdown_files()


def test_owned_directories_exist() -> None:
    assert OPTIONAL_LABS_DIR.is_dir(), f"expected {OPTIONAL_LABS_DIR} to exist"
    assert INSTRUCTOR_DIR.is_dir(), f"expected {INSTRUCTOR_DIR} to exist"


def test_at_least_the_expected_optional_labs_and_instructor_files_exist() -> None:
    expected_optional_labs = {
        "README.md",
        "fabric-iq.md",
        "work-iq.md",
        "advanced-hosted-agent.md",
        "a2a-routines-publish.md",
        "cicd-continuous-evaluation.md",
        "azd-appendix.md",
    }
    actual_optional_labs = {p.name for p in OPTIONAL_LABS_DIR.glob("*.md")}
    missing = expected_optional_labs - actual_optional_labs
    assert not missing, f"labs/optional/ is missing expected files: {sorted(missing)}"

    expected_instructor_files = {"README.md", "runbook.md"}
    actual_instructor_files = {p.name for p in INSTRUCTOR_DIR.glob("*.md")}
    missing_instructor = expected_instructor_files - actual_instructor_files
    assert not missing_instructor, (
        f"instructor/ is missing expected files: {sorted(missing_instructor)}"
    )

    completed_run_assets_readme = INSTRUCTOR_DIR / "completed-run-assets" / "README.md"
    assert completed_run_assets_readme.is_file()


def _iter_relative_link_cases() -> list[tuple[Path, str]]:
    cases: list[tuple[Path, str]] = []
    for source_file in OWNED_MARKDOWN_FILES:
        text = source_file.read_text(encoding="utf-8")
        for target in extract_link_targets(text):
            if not is_external_link(target):
                cases.append((source_file, target))
    return cases


_RELATIVE_LINK_CASES = _iter_relative_link_cases()


@pytest.mark.parametrize(
    ("source_file", "target"),
    _RELATIVE_LINK_CASES,
    ids=[f"{sf.relative_to(REPO_ROOT)}::{t}" for sf, t in _RELATIVE_LINK_CASES],
)
def test_relative_link_resolves_to_a_real_file(source_file: Path, target: str) -> None:
    resolved = resolve_link_path(source_file, target)
    assert resolved.is_file(), (
        f"{source_file.relative_to(REPO_ROOT)} links to {target!r}, which resolves to "
        f"{resolved}, but that file does not exist."
    )


def test_optional_labs_readme_links_to_every_sibling_lab() -> None:
    readme = OPTIONAL_LABS_DIR / "README.md"
    text = readme.read_text(encoding="utf-8")
    targets = {
        resolve_link_path(readme, t) for t in extract_link_targets(text) if not is_external_link(t)
    }
    sibling_labs = [p for p in OPTIONAL_LABS_DIR.glob("*.md") if p.name != "README.md"]
    assert sibling_labs, "expected at least one optional lab alongside labs/optional/README.md"
    for lab in sibling_labs:
        assert lab.resolve() in targets, (
            f"labs/optional/README.md does not link to {lab.relative_to(REPO_ROOT)}"
        )


def test_instructor_readme_links_to_runbook_and_completed_run_assets() -> None:
    readme = INSTRUCTOR_DIR / "README.md"
    text = readme.read_text(encoding="utf-8")
    targets = {
        resolve_link_path(readme, t) for t in extract_link_targets(text) if not is_external_link(t)
    }
    runbook = INSTRUCTOR_DIR / "runbook.md"
    completed_run_assets_readme = INSTRUCTOR_DIR / "completed-run-assets" / "README.md"
    assert runbook.resolve() in targets, "instructor/README.md does not link to runbook.md"
    assert completed_run_assets_readme.resolve() in targets, (
        "instructor/README.md does not link to completed-run-assets/README.md"
    )


# ---------------------------------------------------------------------------
# Pure-function unit coverage (no filesystem access) for the helpers above.
# ---------------------------------------------------------------------------


def test_extract_link_targets_finds_plain_and_titled_links() -> None:
    text = (
        "See [Fabric IQ](fabric-iq.md) and "
        '[external](https://example.com "a title") and ![alt](../img/x.png).'
    )
    assert extract_link_targets(text) == [
        "fabric-iq.md",
        "https://example.com",
        "../img/x.png",
    ]


def test_is_external_link_classifies_correctly() -> None:
    assert is_external_link("https://learn.microsoft.com/azure") is True
    assert is_external_link("http://example.com") is True
    assert is_external_link("mailto:someone@example.com") is True
    assert is_external_link("#section") is True
    assert is_external_link("../../docs/architecture.md") is False
    assert is_external_link("work-iq.md") is False
    assert is_external_link("../../README.md#core-と-optional-の境界") is False


def test_resolve_link_path_strips_fragment_and_joins_relative(tmp_path: Path) -> None:
    optional_dir = tmp_path / "labs" / "optional"
    optional_dir.mkdir(parents=True)
    target_file = optional_dir / "work-iq.md"
    target_file.write_text("# Work IQ\n", encoding="utf-8")
    source_file = optional_dir / "README.md"

    resolved = resolve_link_path(source_file, "work-iq.md#section")

    assert resolved == target_file.resolve()
    assert resolved.is_file()

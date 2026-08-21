"""Contract test: every local markdown link in the participant labs resolves.

This workstream owns ``labs/00-overview.md`` .. ``labs/08-observability-cleanup.md``,
``docs/participant/troubleshooting.md``, and (indirectly, via cross-links) reads
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

``labs/07-*.md`` is explicitly out of this workstream's ownership and may not
exist in a given checkout (a different workstream authors it) -- links to it
are intentionally never emitted by the files this test scans, and this test
does not require it to exist.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LABS_DIR = REPO_ROOT / "labs"
OWNED_FILES = [
    LABS_DIR / "00-overview.md",
    LABS_DIR / "01-setup.md",
    LABS_DIR / "02-prompt-agent.md",
    LABS_DIR / "03-rag-foundry-iq.md",
    LABS_DIR / "04-tools-toolbox.md",
    LABS_DIR / "05-evaluation.md",
    LABS_DIR / "06-optimization.md",
    LABS_DIR / "08-observability-cleanup.md",
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

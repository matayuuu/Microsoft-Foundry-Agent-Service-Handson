"""Contract test: instructor/completed-run-assets/*.simulated.json are safe fallback assets.

This workstream owns ``instructor/completed-run-assets/**`` exclusively (see the
`author-optional-content` todo). These JSON files are shown to instructors as a fallback when a
live Lab 5/6/7 demo cannot complete in time; they must never be mistaken for real Foundry
execution output. This test enforces, for every ``*.simulated.json`` file under
``instructor/completed-run-assets/``:

1. It parses as JSON and validates against its sibling schema under ``schemas/``.
2. Its own schema is itself a structurally valid JSON Schema.
3. It carries an explicit ``asset_status`` label of ``SIMULATED`` or ``REFERENCE`` and a
   non-empty ``disclaimer_ja`` explanation that it is not a real Foundry run.
4. It contains no secret-like substrings (API keys, connection strings, bearer tokens) and no
   realistic-looking Azure identifiers (GUIDs, which is what subscription/tenant/resource IDs
   look like) anywhere in the serialized document -- only the obviously-fake ``SIMULATED-...``
   style identifiers and ``.invalid``-domain URLs used throughout these fixtures.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = REPO_ROOT / "instructor" / "completed-run-assets"
SCHEMAS_DIR = ASSETS_DIR / "schemas"

_GUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_SECRET_LIKE_PATTERNS = [
    re.compile(r"AccountKey=", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{10,}"),
    re.compile(r"client_secret", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def _discover_simulated_assets() -> list[Path]:
    if not ASSETS_DIR.is_dir():
        return []
    return sorted(ASSETS_DIR.glob("*.simulated.json"))


SIMULATED_ASSET_FILES = _discover_simulated_assets()
EXPECTED_ASSET_NAMES = {
    "evaluation-run.simulated.json",
    "optimizer-run.simulated.json",
    "hosted-agent-deploy.simulated.json",
}


def _schema_path_for(asset_path: Path) -> Path:
    stem = asset_path.name.removesuffix(".simulated.json")
    return SCHEMAS_DIR / f"{stem}.schema.json"


def test_completed_run_assets_directory_exists() -> None:
    assert ASSETS_DIR.is_dir(), f"expected {ASSETS_DIR} to exist"
    assert SCHEMAS_DIR.is_dir(), f"expected {SCHEMAS_DIR} to exist"


def test_expected_simulated_assets_are_present() -> None:
    actual = {p.name for p in SIMULATED_ASSET_FILES}
    missing = EXPECTED_ASSET_NAMES - actual
    assert not missing, f"instructor/completed-run-assets/ is missing: {sorted(missing)}"


@pytest.mark.parametrize("asset_path", SIMULATED_ASSET_FILES, ids=lambda p: p.name)
def test_asset_has_a_sibling_schema_file(asset_path: Path) -> None:
    schema_path = _schema_path_for(asset_path)
    assert schema_path.is_file(), f"expected schema {schema_path} for asset {asset_path.name}"


@pytest.mark.parametrize("asset_path", SIMULATED_ASSET_FILES, ids=lambda p: p.name)
def test_sibling_schema_is_itself_a_valid_json_schema(asset_path: Path) -> None:
    schema_path = _schema_path_for(asset_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)


@pytest.mark.parametrize("asset_path", SIMULATED_ASSET_FILES, ids=lambda p: p.name)
def test_asset_conforms_to_its_schema(asset_path: Path) -> None:
    schema_path = _schema_path_for(asset_path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    document = json.loads(asset_path.read_text(encoding="utf-8"))
    jsonschema.validate(document, schema)


@pytest.mark.parametrize("asset_path", SIMULATED_ASSET_FILES, ids=lambda p: p.name)
def test_asset_declares_a_simulated_or_reference_status(asset_path: Path) -> None:
    document: dict[str, Any] = json.loads(asset_path.read_text(encoding="utf-8"))
    assert document.get("asset_status") in {"SIMULATED", "REFERENCE"}, (
        f"{asset_path.name} must set asset_status to SIMULATED or REFERENCE"
    )
    disclaimer = document.get("disclaimer_ja")
    assert isinstance(disclaimer, str) and disclaimer.strip(), (
        f"{asset_path.name} must have a non-empty disclaimer_ja"
    )


@pytest.mark.parametrize("asset_path", SIMULATED_ASSET_FILES, ids=lambda p: p.name)
def test_asset_contains_no_secret_like_or_realistic_identifier_strings(asset_path: Path) -> None:
    raw_text = asset_path.read_text(encoding="utf-8")

    guid_matches = _GUID_PATTERN.findall(raw_text)
    assert not guid_matches, (
        f"{asset_path.name} contains GUID-shaped strings that look like real Azure "
        f"subscription/tenant/resource IDs: {guid_matches}"
    )

    for pattern in _SECRET_LIKE_PATTERNS:
        assert not pattern.search(raw_text), (
            f"{asset_path.name} contains a secret-like pattern matching {pattern.pattern!r}"
        )


def test_schemas_directory_has_no_orphaned_schema_without_an_asset() -> None:
    """Every schema file should correspond to at least one *.simulated.json asset.

    Guards against a schema being authored (or renamed) without ever wiring up a matching
    fixture, which would otherwise go unnoticed since schema files are not directly tested
    for "is used" elsewhere.
    """
    schema_files = sorted(SCHEMAS_DIR.glob("*.schema.json")) if SCHEMAS_DIR.is_dir() else []
    asset_stems = {p.name.removesuffix(".simulated.json") for p in SIMULATED_ASSET_FILES}
    for schema_path in schema_files:
        stem = schema_path.name.removesuffix(".schema.json")
        assert stem in asset_stems, (
            f"{schema_path.name} has no matching {stem}.simulated.json asset"
        )

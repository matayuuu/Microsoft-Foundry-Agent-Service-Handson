"""Contract tests for data/manifest.json <-> scripts/bootstrap_data.py.

This locks the interface between this workstream (scripts/bootstrap_data.py)
and the data workstream, which owns both ``data/manifest.json`` and its
JSON Schema at ``data/schemas/manifest.schema.json``. Rather than inventing
a second, parallel description of the contract, these tests treat the data
workstream's own schema file as the single source of truth and verify:

1. The real ``data/manifest.json`` (if present) validates against the real
   ``data/schemas/manifest.schema.json``.
2. ``bootstrap_data.validate_manifest_schema()`` agrees with that verdict --
   for the real manifest, for hand-built valid fixtures, and for a battery
   of invalid fixtures -- so the two can never silently drift apart.
3. Every source file the real manifest references actually exists on disk
   with matching sha256/size (the same check bootstrap_data.py itself runs
   before indexing), using bootstrap_data.py's own pure checksum function.
4. Citation building resolves the source_url placeholder and includes every
   field manifest["citation"]["required_fields"] names.

If the data workstream is not yet available in a given checkout, the tests
that depend on the real files are skipped (not failed) with an explanatory
message; the fixture-based tests still run unconditionally against a
minimal, hand-written schema capturing the same shape, so this suite is
useful before and after data/ lands.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
REAL_MANIFEST_PATH = REPO_ROOT / "data" / "manifest.json"
REAL_SCHEMA_PATH = REPO_ROOT / "data" / "schemas" / "manifest.schema.json"
REAL_DATA_DIR = REPO_ROOT / "data"


def _load_bootstrap_data_module() -> Any:
    module_name = "bootstrap_data_contract_under_test"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / "bootstrap_data.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


bootstrap_data = _load_bootstrap_data_module()

# A minimal JSON Schema capturing the same document shape as
# data/schemas/manifest.schema.json, used for fixture-only tests that must
# run even before/without the real data/ directory being present.
MINIMAL_MANIFEST_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["source_url_base_placeholder", "citation", "embedding", "documents"],
    "properties": {
        "source_url_base_placeholder": {"type": "string"},
        "citation": {
            "type": "object",
            "required": ["required_fields"],
            "properties": {"required_fields": {"type": "array", "items": {"type": "string"}}},
        },
        "embedding": {
            "type": "object",
            "required": ["default_dimensions"],
            "properties": {"default_dimensions": {"type": "integer", "minimum": 1}},
        },
        "documents": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "title",
                    "category",
                    "path",
                    "effective_date",
                    "applies_to",
                    "source_url",
                    "sha256",
                    "size_bytes",
                ],
                "properties": {
                    "id": {"type": "string", "minLength": 1},
                    "title": {"type": "string", "minLength": 1},
                    "category": {"type": "string", "minLength": 1},
                    "path": {"type": "string", "minLength": 1},
                    "effective_date": {"type": "string", "minLength": 1},
                    "applies_to": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                    "source_url": {"type": "string", "minLength": 1},
                    "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
                    "size_bytes": {"type": "integer", "minimum": 1},
                },
            },
        },
    },
}


def _is_schema_valid(manifest: dict[str, Any], schema: dict[str, Any]) -> bool:
    try:
        jsonschema.validate(manifest, schema)
    except jsonschema.ValidationError:
        return False
    return True


def _valid_fixture_manifest() -> dict[str, Any]:
    return {
        "source_url_base_placeholder": "{{WORKSHOP_SOURCE_BASE}}",
        "citation": {"required_fields": ["id", "title", "source_url", "effective_date"]},
        "embedding": {"default_dimensions": 1536},
        "documents": [
            {
                "id": "policy-flights-001",
                "title": "Flight booking policy",
                "category": "flights",
                "path": "policies/flights.md",
                "effective_date": "2026-04-01",
                "applies_to": ["all_employees"],
                "source_url": "{{WORKSHOP_SOURCE_BASE}}/data/policies/flights.md",
                "sha256": "a" * 64,
                "size_bytes": 123,
            }
        ],
    }


def _invalid_fixture_manifests() -> dict[str, dict[str, Any]]:
    valid = _valid_fixture_manifest()
    missing_documents = {k: v for k, v in valid.items() if k != "documents"}
    empty_documents = {**valid, "documents": []}
    bad_sha256 = json.loads(json.dumps(valid))
    bad_sha256["documents"][0]["sha256"] = "not-a-valid-hash"
    missing_field = json.loads(json.dumps(valid))
    del missing_field["documents"][0]["category"]
    return {
        "missing_documents_key": missing_documents,
        "empty_documents_list": empty_documents,
        "sha256_wrong_format": bad_sha256,
        "document_missing_required_field": missing_field,
    }


def test_valid_fixture_manifest_satisfies_minimal_schema() -> None:
    jsonschema.validate(_valid_fixture_manifest(), MINIMAL_MANIFEST_JSON_SCHEMA)


@pytest.mark.parametrize("name", sorted(_invalid_fixture_manifests()))
def test_invalid_fixture_manifests_violate_minimal_schema(name: str) -> None:
    assert not _is_schema_valid(_invalid_fixture_manifests()[name], MINIMAL_MANIFEST_JSON_SCHEMA)


def test_bootstrap_data_agrees_with_minimal_schema_for_valid_manifest() -> None:
    manifest = _valid_fixture_manifest()
    assert _is_schema_valid(manifest, MINIMAL_MANIFEST_JSON_SCHEMA)
    assert bootstrap_data.validate_manifest_schema(manifest, MINIMAL_MANIFEST_JSON_SCHEMA) == []


@pytest.mark.parametrize("name", sorted(_invalid_fixture_manifests()))
def test_bootstrap_data_agrees_with_minimal_schema_for_invalid_manifests(name: str) -> None:
    manifest = _invalid_fixture_manifests()[name]
    assert not _is_schema_valid(manifest, MINIMAL_MANIFEST_JSON_SCHEMA)
    errors = bootstrap_data.validate_manifest_schema(manifest, MINIMAL_MANIFEST_JSON_SCHEMA)
    assert errors != []


def test_fixture_citation_round_trip() -> None:
    manifest = _valid_fixture_manifest()
    documents = bootstrap_data.iter_documents(manifest)
    assert len(documents) == 1

    document = documents[0]
    resolved_url = bootstrap_data.resolve_source_url(
        document.source_url, manifest["source_url_base_placeholder"], "https://example.invalid"
    )
    assert "{{WORKSHOP_SOURCE_BASE}}" not in resolved_url
    assert resolved_url == "https://example.invalid/data/policies/flights.md"

    citation = bootstrap_data.build_citation(
        document, manifest["citation"]["required_fields"], resolved_url
    )
    for field in manifest["citation"]["required_fields"]:
        assert field in citation


@pytest.fixture(scope="module")
def real_schema() -> dict[str, Any]:
    if not REAL_SCHEMA_PATH.exists():
        pytest.skip("data/schemas/manifest.schema.json has not been created yet")
    return json.loads(REAL_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def real_manifest() -> dict[str, Any]:
    if not REAL_MANIFEST_PATH.exists():
        pytest.skip("data/manifest.json has not been created yet")
    return json.loads(REAL_MANIFEST_PATH.read_text(encoding="utf-8"))


def test_real_manifest_schema_is_itself_a_valid_json_schema(real_schema: dict[str, Any]) -> None:
    validator_cls = jsonschema.validators.validator_for(real_schema)
    validator_cls.check_schema(real_schema)


def test_real_manifest_conforms_to_real_schema(
    real_manifest: dict[str, Any], real_schema: dict[str, Any]
) -> None:
    jsonschema.validate(real_manifest, real_schema)


def test_bootstrap_data_agrees_for_real_manifest_and_schema(
    real_manifest: dict[str, Any], real_schema: dict[str, Any]
) -> None:
    assert bootstrap_data.validate_manifest_schema(real_manifest, real_schema) == []


def test_real_manifest_documents_have_matching_checksums_on_disk(
    real_manifest: dict[str, Any],
) -> None:
    documents = bootstrap_data.iter_documents(real_manifest)
    assert len(documents) >= 1

    def _read_bytes(document: Any) -> bytes:
        return bootstrap_data.read_source_bytes(REAL_DATA_DIR, document)

    errors = bootstrap_data.verify_source_checksums(documents, _read_bytes)
    assert errors == []


def test_real_manifest_citations_resolve_and_include_required_fields(
    real_manifest: dict[str, Any],
) -> None:
    documents = bootstrap_data.iter_documents(real_manifest)
    placeholder = real_manifest["source_url_base_placeholder"]
    required_fields = real_manifest["citation"]["required_fields"]

    for document in documents:
        resolved_url = bootstrap_data.resolve_source_url(
            document.source_url, placeholder, "https://workshop.example.invalid"
        )
        assert placeholder not in resolved_url

        citation = bootstrap_data.build_citation(document, required_fields, resolved_url)
        for field in required_fields:
            assert field in citation

"""Schema validation for the static corpus/fixture/manifest JSON files.

Uses jsonschema + PyYAML, both already present in the repository root
pyproject.toml, so this file is expected to run in the root CI environment
without any project-local sub-venv.
"""

import json
import re
from pathlib import Path

import jsonschema

SCHEMA_NAMES = {
    "manifest": "manifest.schema.json",
    "trip": "trip.schema.json",
    "receipt": "receipt.schema.json",
    "eval_case": "eval_case.schema.json",
}


def _load_schema(data_dir: Path, name: str) -> dict:
    schema_path = data_dir / "schemas" / SCHEMA_NAMES[name]
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_matches_schema(data_dir):
    schema = _load_schema(data_dir, "manifest")
    manifest = _load_json(data_dir / "manifest.json")
    jsonschema.validate(instance=manifest, schema=schema)


def test_manifest_has_ten_policy_documents(data_dir):
    manifest = _load_json(data_dir / "manifest.json")
    assert len(manifest["documents"]) == 10


def test_manifest_document_ids_are_unique(data_dir):
    manifest = _load_json(data_dir / "manifest.json")
    ids = [doc["id"] for doc in manifest["documents"]]
    assert len(ids) == len(set(ids))


def test_manifest_documents_reference_files_that_exist_on_disk(data_dir):
    manifest = _load_json(data_dir / "manifest.json")
    for doc in manifest["documents"]:
        assert (data_dir / doc["path"]).is_file(), f"missing {doc['path']}"
    for group_name in ("receipts", "fixtures", "evaluation"):
        for entry in manifest[group_name]["files"]:
            assert (data_dir / entry["path"]).is_file(), f"missing {entry['path']}"


def test_manifest_checksums_match_files_on_disk(data_dir):
    import hashlib

    manifest = _load_json(data_dir / "manifest.json")
    for doc in manifest["documents"]:
        actual = hashlib.sha256((data_dir / doc["path"]).read_bytes()).hexdigest()
        assert actual == doc["sha256"], f"checksum drift for {doc['path']}"
        assert (data_dir / doc["path"]).stat().st_size == doc["size_bytes"]
    for group_name in ("receipts", "fixtures", "evaluation"):
        for entry in manifest[group_name]["files"]:
            actual = hashlib.sha256((data_dir / entry["path"]).read_bytes()).hexdigest()
            assert actual == entry["sha256"], f"checksum drift for {entry['path']}"


def test_manifest_matches_build_manifest_tool_output(repo_root, data_dir):
    """Regenerating the manifest in-memory must produce byte-identical output.

    This catches the case where someone hand-edits data/manifest.json (or a
    source file changes) without re-running data/tools/build_manifest.py.
    """
    import importlib.util

    tool_path = repo_root / "data" / "tools" / "build_manifest.py"
    spec = importlib.util.spec_from_file_location("build_manifest", tool_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    regenerated = module.build_manifest()
    committed = _load_json(data_dir / "manifest.json")
    assert regenerated == committed, (
        "data/manifest.json is stale; run `python data/tools/build_manifest.py`"
    )


def test_trips_fixture_matches_schema(data_dir):
    schema = _load_schema(data_dir, "trip")
    trips = _load_json(data_dir / "fixtures" / "trips.json")
    assert isinstance(trips, list)
    assert len(trips) >= 1
    for trip in trips:
        jsonschema.validate(instance=trip, schema=schema)


def test_trips_fixture_ids_are_unique(data_dir):
    trips = _load_json(data_dir / "fixtures" / "trips.json")
    ids = [trip["trip_id"] for trip in trips]
    assert len(ids) == len(set(ids))


def test_trips_fixture_has_no_pii(data_dir):
    trips = _load_json(data_dir / "fixtures" / "trips.json")
    alias_pattern = re.compile(r"^employee-\d{3}$")
    for trip in trips:
        assert alias_pattern.match(trip["employee_alias"]), (
            f"employee_alias {trip['employee_alias']!r} is not a synthetic alias"
        )


def test_receipts_json_matches_schema(data_dir):
    schema = _load_schema(data_dir, "receipt")
    receipts = _load_json(data_dir / "receipts" / "receipts.json")
    assert isinstance(receipts, list)
    assert len(receipts) >= 1
    for receipt in receipts:
        jsonschema.validate(instance=receipt, schema=schema)


def test_receipts_json_ids_are_unique(data_dir):
    receipts = _load_json(data_dir / "receipts" / "receipts.json")
    ids = [receipt["receipt_id"] for receipt in receipts]
    assert len(ids) == len(set(ids))


def test_receipts_reference_known_trips(data_dir):
    trips = _load_json(data_dir / "fixtures" / "trips.json")
    trip_ids = {trip["trip_id"] for trip in trips}
    receipts = _load_json(data_dir / "receipts" / "receipts.json")
    for receipt in receipts:
        assert receipt["trip_id"] in trip_ids, (
            f"receipt {receipt['receipt_id']} references unknown trip {receipt['trip_id']}"
        )


def test_receipts_have_no_pii(data_dir):
    receipts = _load_json(data_dir / "receipts" / "receipts.json")
    alias_pattern = re.compile(r"^employee-\d{3}$")
    for receipt in receipts:
        assert alias_pattern.match(receipt["employee_alias"]), (
            f"employee_alias {receipt['employee_alias']!r} is not a synthetic alias"
        )


def test_receipt_notes_match_policy_limits(data_dir):
    receipts = {
        receipt["receipt_id"]: receipt
        for receipt in _load_json(data_dir / "receipts" / "receipts.json")
    }

    assert receipts["rcpt-0004"]["note"] == "domestic_tier1 上限(15,000円)内"
    assert "精算上限5,000円のみ対象" in receipts["rcpt-0007"]["note"]
    assert "残額40,000円は別途例外承認が必要" in receipts["rcpt-0007"]["note"]


def test_receipts_csv_round_trips_against_json(data_dir):
    import csv

    receipts_json = _load_json(data_dir / "receipts" / "receipts.json")
    with (data_dir / "receipts" / "receipts.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == len(receipts_json)
    for csv_row, json_row in zip(rows, receipts_json, strict=True):
        for key, json_value in json_row.items():
            csv_value = csv_row[key]
            if isinstance(json_value, bool):
                assert csv_value == json.dumps(json_value)
            elif isinstance(json_value, float | int):
                assert float(csv_value) == float(json_value)
            else:
                assert csv_value == json_value


def test_policy_markdown_front_matter_ids_match_manifest(data_dir):
    """Every policy markdown file's YAML front matter id/source_url must match
    the corresponding manifest entry (guards against hand-edits to either
    side going stale relative to the other)."""
    import sys

    sys.path.insert(0, str(data_dir / "tools"))
    import build_manifest

    documents = build_manifest._build_documents()
    manifest = _load_json(data_dir / "manifest.json")
    manifest_by_path = {doc["path"]: doc for doc in manifest["documents"]}

    for doc in documents:
        committed = manifest_by_path[doc["path"]]
        assert committed["id"] == doc["id"]
        assert committed["source_url"] == doc["source_url"]
        assert committed["title"] == doc["title"]
        assert committed["category"] == doc["category"]

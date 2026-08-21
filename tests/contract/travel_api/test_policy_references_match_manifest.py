"""Cross-check that every policy reference the API can cite actually exists
in data/manifest.json, so src/travel-api/** and data/** cannot silently drift
apart even though they are edited independently.
"""

import json
from pathlib import Path

from travel_api.application import use_cases

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _manifest_document_ids() -> set[str]:
    manifest_path = _REPO_ROOT / "data" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {doc["id"] for doc in manifest["documents"]}


def _manifest_documents_by_id() -> dict:
    manifest_path = _REPO_ROOT / "data" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {doc["id"]: doc for doc in manifest["documents"]}


def test_all_referenced_policy_ids_exist_in_manifest():
    manifest_ids = _manifest_document_ids()
    referenced_ids = {
        ref.id
        for group in (
            use_cases.PER_DIEM_REFERENCES,
            use_cases.TRIP_ESTIMATE_REFERENCES,
            use_cases.PREAPPROVAL_REFERENCES,
        )
        for ref in group
    }
    missing = referenced_ids - manifest_ids
    assert not missing, f"policy references not found in data/manifest.json: {missing}"


def test_referenced_source_urls_match_manifest_source_urls():
    documents_by_id = _manifest_documents_by_id()
    for group in (
        use_cases.PER_DIEM_REFERENCES,
        use_cases.TRIP_ESTIMATE_REFERENCES,
        use_cases.PREAPPROVAL_REFERENCES,
    ):
        for ref in group:
            assert ref.source_url == documents_by_id[ref.id]["source_url"], (
                f"source_url mismatch for {ref.id}"
            )


def test_source_url_placeholder_matches_manifest_placeholder():
    manifest_path = _REPO_ROOT / "data" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["source_url_base_placeholder"] == use_cases.SOURCE_URL_BASE_PLACEHOLDER

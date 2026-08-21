"""Deterministic manifest builder for the Travel Ops synthetic corpus.

This is a maintenance tool owned by the data/** workstream. It is not part of
the participant-facing scripts/ CLI surface. Run it whenever a policy
document, receipt fixture, trip fixture, or evaluation JSONL file changes:

    python data/tools/build_manifest.py

It regenerates data/manifest.json from:
  * the YAML front matter embedded in each data/policies/*.md file (single
    source of truth for id/title/category/effective_date/applies_to/source_url)
  * SHA-256 checksums computed from canonical LF bytes

so that scripts/bootstrap_data.py (owned by another workstream) can verify
corpus integrity before indexing content into Azure AI Search / Foundry IQ.

The script is idempotent: running it twice with unchanged inputs produces a
byte-identical data/manifest.json.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent
SOURCE_URL_BASE_PLACEHOLDER = "{{WORKSHOP_SOURCE_BASE}}"
CORPUS_VERSION = "2026.04.1"

CHUNKING = {
    "strategy": "markdown-heading",
    "unit": "tokens",
    "max_tokens": 512,
    "overlap_tokens": 64,
}

EMBEDDING = {
    "default_dimensions": 1536,
    "configurable_by": ["scripts/setup.sh", "scripts/bootstrap_data.py"],
}

CITATION = {
    "required_fields": ["id", "title", "source_url", "effective_date"],
}


def canonical_bytes(path: Path) -> bytes:
    """Return text bytes with platform-specific newlines normalized to LF."""
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def _split_front_matter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        raise ValueError("missing YAML front matter delimiter '---'")
    end = text.index("\n---", 4)
    front_matter = text[4:end]
    return yaml.safe_load(front_matter)


def _build_documents() -> list[dict[str, Any]]:
    documents = []
    policies_dir = DATA_DIR / "policies"
    for path in sorted(policies_dir.glob("*.md")):
        meta = _split_front_matter(path.read_text(encoding="utf-8"))
        rel_path = f"policies/{path.name}"
        effective_date = meta["effective_date"]
        if isinstance(effective_date, datetime.date):
            effective_date = effective_date.isoformat()
        documents.append(
            {
                "id": meta["id"],
                "title": meta["title"],
                "category": meta["category"],
                "path": rel_path,
                "effective_date": effective_date,
                "applies_to": meta["applies_to"],
                "source_url": meta["source_url"],
                "sha256": _sha256(path),
                "size_bytes": len(canonical_bytes(path)),
            }
        )
    return documents


def _file_group(*, base_dir: Path, files: list[tuple[str, Path]]) -> dict[str, Any]:
    entries = []
    for name, path in files:
        entries.append(
            {
                "name": name,
                "path": str(path.relative_to(DATA_DIR)).replace("\\", "/"),
                "sha256": _sha256(path),
                "size_bytes": len(canonical_bytes(path)),
            }
        )
    return {"files": entries}


def build_manifest() -> dict[str, Any]:
    documents = _build_documents()

    receipts = _file_group(
        base_dir=DATA_DIR,
        files=[
            ("receipts_csv", DATA_DIR / "receipts" / "receipts.csv"),
            ("receipts_json", DATA_DIR / "receipts" / "receipts.json"),
        ],
    )
    fixtures = _file_group(
        base_dir=DATA_DIR,
        files=[
            ("trips_json", DATA_DIR / "fixtures" / "trips.json"),
        ],
    )
    evaluation = _file_group(
        base_dir=DATA_DIR,
        files=[
            ("eval_master_jsonl", DATA_DIR / "eval" / "master.jsonl"),
            ("eval_live_subset_jsonl", DATA_DIR / "eval" / "live_subset.jsonl"),
        ],
    )

    return {
        "corpus_version": CORPUS_VERSION,
        "language": "ja",
        "source_url_base_placeholder": SOURCE_URL_BASE_PLACEHOLDER,
        "chunking": CHUNKING,
        "embedding": EMBEDDING,
        "citation": CITATION,
        "documents": documents,
        "receipts": receipts,
        "fixtures": fixtures,
        "evaluation": evaluation,
    }


def main() -> None:
    manifest = build_manifest()
    out_path = DATA_DIR / "manifest.json"
    out_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {out_path} ({len(manifest['documents'])} documents)")


if __name__ == "__main__":
    main()

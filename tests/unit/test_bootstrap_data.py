"""Unit tests for scripts/bootstrap_data.py.

scripts/ is intentionally not a Python package (pyproject.toml only
discovers packages under src/), so the module under test is loaded directly
from its file path via importlib. Only the pure functions and thin adapter
seams are exercised here; no real Azure credentials or network access are
used anywhere in this file, and the real data/manifest.json /
data/schemas/manifest.schema.json are never read -- every test builds its
own tmp_path fixtures so this suite is hermetic and independent of the data
workstream's content.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "bootstrap_data.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bootstrap_data", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


bootstrap_data = _load_module()


# A minimal permissive JSON Schema mirroring data/schemas/manifest.schema.json's
# document shape, used so these unit tests never depend on the real file.
TEST_SCHEMA = {
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


def _make_document_dict(**overrides: object) -> dict:
    base = {
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
    base.update(overrides)
    return base


def _valid_manifest(*document_overrides: dict, chunking: dict | None = None) -> dict:
    documents = [_make_document_dict(**overrides) for overrides in document_overrides] or [
        _make_document_dict()
    ]
    return {
        "source_url_base_placeholder": "{{WORKSHOP_SOURCE_BASE}}",
        "citation": {"required_fields": ["id", "title", "source_url", "effective_date"]},
        "embedding": {"default_dimensions": 2},
        "chunking": chunking
        if chunking is not None
        else {
            "strategy": "markdown-heading",
            "unit": "tokens",
            "max_tokens": 512,
            "overlap_tokens": 64,
        },
        "documents": documents,
    }


class FakeTokenizer:
    """Deterministic, whitespace-word-based fake tokenizer used by every
    chunking test in this file, so the pure chunking functions -- and
    main()'s dry-run path when the real ``build_tokenizer()`` adapter is
    monkeypatched -- never need the real ``tiktoken`` package's ``cl100k_base``
    vocabulary (which may fetch from the network on first use in some
    sandboxes). Each distinct whitespace-separated word gets its own stable
    integer id, assigned in first-seen order across all encode() calls on
    one instance, so decode() can reconstruct the original words."""

    def __init__(self) -> None:
        self._id_to_word: list[str] = []
        self._word_to_id: dict[str, int] = {}

    def encode(self, text: str) -> list[int]:
        ids = []
        for word in text.split(" "):
            if word not in self._word_to_id:
                self._word_to_id[word] = len(self._id_to_word)
                self._id_to_word.append(word)
            ids.append(self._word_to_id[word])
        return ids

    def decode(self, tokens: list[int]) -> str:
        return " ".join(self._id_to_word[t] for t in tokens)


# ---------------------------------------------------------------------------
# load_manifest / load_schema
# ---------------------------------------------------------------------------


def test_load_manifest_reads_valid_json(tmp_path: Path) -> None:
    manifest = _valid_manifest()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    loaded = bootstrap_data.load_manifest(manifest_path)

    assert loaded == manifest


def test_load_manifest_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(bootstrap_data.ManifestError):
        bootstrap_data.load_manifest(tmp_path / "does-not-exist.json")


def test_load_manifest_raises_on_invalid_json(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(bootstrap_data.ManifestError):
        bootstrap_data.load_manifest(manifest_path)


def test_load_manifest_raises_on_non_object_top_level(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")

    with pytest.raises(bootstrap_data.ManifestError):
        bootstrap_data.load_manifest(manifest_path)


def test_load_schema_reads_valid_json(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(TEST_SCHEMA), encoding="utf-8")

    loaded = bootstrap_data.load_schema(schema_path)

    assert loaded == TEST_SCHEMA


def test_load_schema_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(bootstrap_data.ManifestError):
        bootstrap_data.load_schema(tmp_path / "does-not-exist.json")


# ---------------------------------------------------------------------------
# validate_manifest_schema
# ---------------------------------------------------------------------------


def test_validate_manifest_schema_accepts_valid_manifest() -> None:
    errors = bootstrap_data.validate_manifest_schema(_valid_manifest(), TEST_SCHEMA)

    assert errors == []


def test_validate_manifest_schema_reports_missing_documents_key() -> None:
    manifest = _valid_manifest()
    del manifest["documents"]

    errors = bootstrap_data.validate_manifest_schema(manifest, TEST_SCHEMA)

    assert any("documents" in e for e in errors)


def test_validate_manifest_schema_rejects_empty_documents_list() -> None:
    manifest = _valid_manifest()
    manifest["documents"] = []

    errors = bootstrap_data.validate_manifest_schema(manifest, TEST_SCHEMA)

    assert errors != []


@pytest.mark.parametrize(
    "missing_field",
    ["id", "title", "category", "path", "effective_date", "applies_to", "source_url", "sha256"],
)
def test_validate_manifest_schema_requires_each_document_field(missing_field: str) -> None:
    doc = _make_document_dict()
    del doc[missing_field]
    manifest = _valid_manifest()
    manifest["documents"] = [doc]

    errors = bootstrap_data.validate_manifest_schema(manifest, TEST_SCHEMA)

    assert errors != []


def test_validate_manifest_schema_reports_multiple_errors_in_one_pass() -> None:
    manifest = {}  # missing every required top-level key

    errors = bootstrap_data.validate_manifest_schema(manifest, TEST_SCHEMA)

    assert len(errors) >= 2


# ---------------------------------------------------------------------------
# iter_documents
# ---------------------------------------------------------------------------


def test_iter_documents_builds_normalized_documents() -> None:
    manifest = _valid_manifest({"id": "policy-flights-001"}, {"id": "policy-hotels-001"})

    docs = bootstrap_data.iter_documents(manifest)

    assert len(docs) == 2
    assert docs[0].id == "policy-flights-001"
    assert docs[0].category == "flights"
    assert docs[0].applies_to == ("all_employees",)
    assert isinstance(docs[0], bootstrap_data.ManifestDocument)


def test_iter_documents_raises_on_missing_field() -> None:
    manifest = {"documents": [{"id": "x", "title": "x"}]}

    with pytest.raises(bootstrap_data.ManifestError):
        bootstrap_data.iter_documents(manifest)


def test_iter_documents_raises_when_applies_to_is_not_a_list() -> None:
    doc = _make_document_dict(applies_to="not-a-list")
    manifest = _valid_manifest()
    manifest["documents"] = [doc]

    with pytest.raises(bootstrap_data.ManifestError):
        bootstrap_data.iter_documents(manifest)


# ---------------------------------------------------------------------------
# checksum verification
# ---------------------------------------------------------------------------


def _document_for_bytes(
    content_bytes: bytes, **overrides: object
) -> bootstrap_data.ManifestDocument:
    digest = hashlib.sha256(content_bytes).hexdigest()
    doc_dict = _make_document_dict(sha256=digest, size_bytes=len(content_bytes), **overrides)
    manifest = _valid_manifest()
    manifest["documents"] = [doc_dict]
    return bootstrap_data.iter_documents(manifest)[0]


def test_checksum_error_returns_none_for_matching_content() -> None:
    content = b"hello world"
    document = _document_for_bytes(content)

    assert bootstrap_data.checksum_error(document, content) is None


def test_checksum_error_normalizes_crlf_to_manifest_lf_bytes() -> None:
    canonical = b"line one\nline two\n"
    document = _document_for_bytes(canonical)

    assert bootstrap_data.checksum_error(document, b"line one\r\nline two\r\n") is None


def test_checksum_error_reports_sha256_mismatch() -> None:
    document = _document_for_bytes(b"hello world")

    error = bootstrap_data.checksum_error(document, b"tampered content")

    assert error is not None
    assert "sha256 mismatch" in error


def test_checksum_error_reports_size_mismatch_for_correct_hash_wrong_size() -> None:
    # Constructs a document whose recorded sha256 matches content A, then
    # checks content B (same sha256 intentionally impossible to fabricate,
    # so instead assert the size-mismatch branch directly via a document
    # whose sha256 matches but whose recorded size_bytes is wrong).
    content = b"hello world"
    digest = hashlib.sha256(content).hexdigest()
    doc_dict = _make_document_dict(sha256=digest, size_bytes=len(content) + 1)
    manifest = _valid_manifest()
    manifest["documents"] = [doc_dict]
    document = bootstrap_data.iter_documents(manifest)[0]

    error = bootstrap_data.checksum_error(document, content)

    assert error is not None
    assert "size mismatch" in error


def test_verify_source_checksums_aggregates_errors_across_documents() -> None:
    good_content = b"good"
    bad_content = b"bad"
    good_doc = _document_for_bytes(good_content, id="policy-good-001")
    manifest = _valid_manifest()
    manifest["documents"] = [
        _make_document_dict(
            id="policy-good-001",
            sha256=hashlib.sha256(good_content).hexdigest(),
            size_bytes=len(good_content),
        ),
        _make_document_dict(
            id="policy-bad-001",
            sha256=hashlib.sha256(b"expected").hexdigest(),
            size_bytes=len(b"expected"),
        ),
    ]
    documents = bootstrap_data.iter_documents(manifest)

    def read_bytes_fn(document: bootstrap_data.ManifestDocument) -> bytes:
        return good_content if document.id == "policy-good-001" else bad_content

    errors = bootstrap_data.verify_source_checksums(documents, read_bytes_fn)

    assert len(errors) == 1
    assert "policy-bad-001" in errors[0]
    assert good_doc.id == "policy-good-001"  # sanity: fixture built as expected


# ---------------------------------------------------------------------------
# strip_front_matter
# ---------------------------------------------------------------------------


def test_strip_front_matter_removes_yaml_block() -> None:
    text = "---\nid: x\ntitle: y\n---\n\n# Heading\n\nBody text.\n"

    result = bootstrap_data.strip_front_matter(text)

    assert result == "# Heading\n\nBody text.\n"


def test_strip_front_matter_returns_text_unchanged_without_front_matter() -> None:
    text = "# Heading\n\nBody text.\n"

    assert bootstrap_data.strip_front_matter(text) == text


def test_strip_front_matter_returns_text_unchanged_when_closing_delimiter_missing() -> None:
    text = "---\nid: x\ntitle: y\n\nno closing delimiter here"

    assert bootstrap_data.strip_front_matter(text) == text


def test_strip_front_matter_handles_crlf_line_endings() -> None:
    # The real data/policies/*.md files are checked out with CRLF line
    # endings on Windows; strip_front_matter must not require LF-only input.
    text = "---\r\nid: x\r\ntitle: y\r\n---\r\n\r\n# Heading\r\n\r\nBody text.\r\n"

    result = bootstrap_data.strip_front_matter(text)

    assert result == "# Heading\n\nBody text.\n"


# ---------------------------------------------------------------------------
# resolve_source_url / build_citation
# ---------------------------------------------------------------------------


def test_resolve_source_url_substitutes_placeholder() -> None:
    result = bootstrap_data.resolve_source_url(
        "{{WORKSHOP_SOURCE_BASE}}/data/policies/flights.md",
        "{{WORKSHOP_SOURCE_BASE}}",
        "https://example.invalid",
    )

    assert result == "https://example.invalid/data/policies/flights.md"


def test_build_citation_includes_every_required_field_in_order() -> None:
    manifest = _valid_manifest()
    document = bootstrap_data.iter_documents(manifest)[0]

    citation = bootstrap_data.build_citation(
        document,
        ["id", "title", "source_url", "effective_date"],
        "https://resolved.example/flights.md",
    )

    assert citation == (
        "id=policy-flights-001 | title=Flight booking policy | "
        "source_url=https://resolved.example/flights.md | effective_date=2026-04-01"
    )


def test_build_citation_raises_on_unsupported_field() -> None:
    manifest = _valid_manifest()
    document = bootstrap_data.iter_documents(manifest)[0]

    with pytest.raises(bootstrap_data.ManifestError):
        bootstrap_data.build_citation(document, ["not_a_real_field"], "https://x")


def test_search_document_id_is_deterministic_and_valid_key() -> None:
    manifest = _valid_manifest()
    document = bootstrap_data.iter_documents(manifest)[0]

    key_1 = bootstrap_data.chunk_search_document_id(document.id, 0)
    key_2 = bootstrap_data.chunk_search_document_id(document.id, 0)
    key_other_chunk = bootstrap_data.chunk_search_document_id(document.id, 1)

    assert key_1 == key_2
    assert key_1 != key_other_chunk
    assert all(ch.isalnum() or ch in "-_=" for ch in key_1)


# ---------------------------------------------------------------------------
# markdown-heading, token-aware chunking
# ---------------------------------------------------------------------------


def test_split_markdown_sections_tracks_heading_breadcrumbs() -> None:
    text = (
        "Intro text before any heading.\n\n"
        "# Flights\n\nFlights body.\n\n"
        "## Economy\n\nEconomy body.\n\n"
        "# Hotels\n\nHotels body.\n"
    )

    sections = bootstrap_data.split_markdown_sections(text)

    assert sections == [
        ("", "Intro text before any heading."),
        ("Flights", "Flights body."),
        ("Flights > Economy", "Economy body."),
        ("Hotels", "Hotels body."),
    ]


def test_split_markdown_sections_drops_empty_sections() -> None:
    text = "# Heading with no body\n\n# Next heading\n\nBody.\n"

    sections = bootstrap_data.split_markdown_sections(text)

    assert sections == [("Next heading", "Body.")]


def test_chunk_text_by_tokens_returns_single_window_when_under_max() -> None:
    tokenizer = FakeTokenizer()

    windows = bootstrap_data.chunk_text_by_tokens(
        "one two three", tokenizer, max_tokens=10, overlap_tokens=2
    )

    assert windows == [("one two three", 3)]


def test_chunk_text_by_tokens_slides_with_overlap() -> None:
    tokenizer = FakeTokenizer()
    text = "a b c d e f g"  # 7 tokens

    windows = bootstrap_data.chunk_text_by_tokens(text, tokenizer, max_tokens=3, overlap_tokens=1)

    # step = max_tokens - overlap_tokens = 2
    assert [w[0] for w in windows] == ["a b c", "c d e", "e f g"]
    assert all(count <= 3 for _, count in windows)


def test_chunk_text_by_tokens_rejects_overlap_not_smaller_than_max() -> None:
    tokenizer = FakeTokenizer()

    with pytest.raises(bootstrap_data.BootstrapError):
        bootstrap_data.chunk_text_by_tokens("a b c", tokenizer, max_tokens=2, overlap_tokens=2)


def test_chunk_text_by_tokens_rejects_non_positive_max_tokens() -> None:
    tokenizer = FakeTokenizer()

    with pytest.raises(bootstrap_data.BootstrapError):
        bootstrap_data.chunk_text_by_tokens("a b c", tokenizer, max_tokens=0, overlap_tokens=0)


def test_chunk_markdown_document_assigns_sequential_global_chunk_index() -> None:
    tokenizer = FakeTokenizer()
    text = "# Flights\n\na b c d e\n\n# Hotels\n\nf g h\n"

    chunks = bootstrap_data.chunk_markdown_document(text, tokenizer, max_tokens=3, overlap_tokens=1)

    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert chunks[0].heading == "Flights"
    assert chunks[-1].heading == "Hotels"
    assert all(isinstance(c.token_count, int) and c.token_count > 0 for c in chunks)


def test_stale_chunk_ids_returns_ids_no_longer_produced() -> None:
    existing = ["doc-a", "doc-b", "doc-c"]
    current = ["doc-b"]

    assert bootstrap_data.stale_chunk_ids(existing, current) == ["doc-a", "doc-c"]


def test_stale_chunk_ids_returns_empty_when_nothing_stale() -> None:
    assert bootstrap_data.stale_chunk_ids(["doc-a"], ["doc-a", "doc-b"]) == []


# ---------------------------------------------------------------------------
# build_search_document / validate_search_documents
# ---------------------------------------------------------------------------


def test_build_search_document_shape() -> None:
    manifest = _valid_manifest()
    document = bootstrap_data.iter_documents(manifest)[0]
    chunk = bootstrap_data.MarkdownChunk(
        chunk_index=0, heading="Flights", text="some text", token_count=2
    )

    result = bootstrap_data.build_search_document(
        document,
        chunk,
        embedding=[0.1, 0.2, 0.3],
        citation="id=policy-flights-001 | title=Flight booking policy",
        resolved_source_url="https://resolved.example/flights.md",
    )

    assert result["manifest_id"] == "policy-flights-001"
    assert result["title"] == "Flight booking policy"
    assert result["content"] == "some text"
    assert result["citation"] == "id=policy-flights-001 | title=Flight booking policy"
    assert result["category"] == "flights"
    assert result["source_path"] == "policies/flights.md"
    assert result["source_url"] == "https://resolved.example/flights.md"
    assert result["effective_date"] == "2026-04-01"
    assert result["applies_to"] == "all_employees"
    assert result["blob_url"] == "https://resolved.example/flights.md"
    assert result["chunk_index"] == 0
    assert result["heading"] == "Flights"
    assert result["token_count"] == 2
    assert result["content_vector"] == [0.1, 0.2, 0.3]
    assert result["id"] == bootstrap_data.chunk_search_document_id(document.id, 0)


def test_validate_search_documents_accepts_valid_documents() -> None:
    docs = [
        {
            "id": "a",
            "citation": "c1",
            "source_url": "https://x/1",
            "content_vector": [0.0, 0.0],
        },
        {
            "id": "b",
            "citation": "c2",
            "source_url": "https://x/2",
            "content_vector": [0.0, 0.0],
        },
    ]

    errors = bootstrap_data.validate_search_documents(docs, expected_dimensions=2)

    assert errors == []


def test_validate_search_documents_rejects_empty_list() -> None:
    errors = bootstrap_data.validate_search_documents([], expected_dimensions=2)

    assert any("no search documents" in e for e in errors)


def test_validate_search_documents_rejects_duplicate_ids() -> None:
    docs = [
        {"id": "a", "citation": "c1", "content_vector": [0.0, 0.0]},
        {"id": "a", "citation": "c2", "content_vector": [0.0, 0.0]},
    ]

    errors = bootstrap_data.validate_search_documents(docs, expected_dimensions=2)

    assert any("duplicate id" in e for e in errors)


def test_validate_search_documents_rejects_missing_citation() -> None:
    docs = [
        {
            "id": "a",
            "citation": "  ",
            "source_url": "https://x/1",
            "content_vector": [0.0, 0.0],
        }
    ]

    errors = bootstrap_data.validate_search_documents(docs, expected_dimensions=2)

    assert any("citation" in e for e in errors)


def test_validate_search_documents_rejects_missing_source_url() -> None:
    docs = [{"id": "a", "citation": "c", "source_url": "", "content_vector": [0.0, 0.0]}]

    errors = bootstrap_data.validate_search_documents(docs, expected_dimensions=2)

    assert any("source_url" in e for e in errors)


def test_validate_search_documents_rejects_wrong_vector_dimensions() -> None:
    docs = [
        {
            "id": "a",
            "citation": "c",
            "source_url": "https://x/1",
            "content_vector": [0.0, 0.0, 0.0],
        }
    ]

    errors = bootstrap_data.validate_search_documents(docs, expected_dimensions=2)

    assert any("dimension" in e for e in errors)


# ---------------------------------------------------------------------------
# index definition
# ---------------------------------------------------------------------------


def test_build_index_fields_includes_expected_fields_and_dimensions() -> None:
    fields = bootstrap_data.build_index_fields(embedding_dimensions=1536)
    by_name = {f["name"]: f for f in fields}

    assert "content_vector" in by_name
    assert by_name["content_vector"]["vector_search_dimensions"] == 1536
    assert "citation" in by_name
    assert "effective_date" in by_name
    assert "applies_to" in by_name
    assert "source_url" in by_name
    assert by_name["chunk_index"]["sortable"] is True
    assert "heading" in by_name
    assert "token_count" in by_name
    assert by_name["id"]["key"] is True


def test_to_search_index_builds_sdk_model_with_expected_shape() -> None:
    index = bootstrap_data.to_search_index("contoso-travel-policy", embedding_dimensions=1536)

    assert index.name == "contoso-travel-policy"
    field_names = {f.name for f in index.fields}
    assert field_names == {
        "id",
        "manifest_id",
        "title",
        "content",
        "citation",
        "category",
        "source_path",
        "source_url",
        "effective_date",
        "applies_to",
        "blob_url",
        "chunk_index",
        "heading",
        "token_count",
        "content_vector",
    }
    assert index.vector_search is not None
    assert index.semantic_search is not None


# ---------------------------------------------------------------------------
# build_documents wiring (fakes for read/embedding adapters)
# ---------------------------------------------------------------------------


def _write_policy_file(rag_dir: Path, relative_path: str, body: str) -> bytes:
    file_path = rag_dir / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    text = f"---\nid: x\n---\n\n{body}"
    file_path.write_text(text, encoding="utf-8")
    return file_path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def test_build_documents_wires_pure_functions_with_injected_adapters(tmp_path: Path) -> None:
    rag_dir = tmp_path
    flights_bytes = _write_policy_file(rag_dir, "policies/flights.md", "Flight content")

    manifest = _valid_manifest(
        {
            "id": "policy-flights-001",
            "path": "policies/flights.md",
            "sha256": hashlib.sha256(flights_bytes).hexdigest(),
            "size_bytes": len(flights_bytes),
        }
    )
    documents = bootstrap_data.iter_documents(manifest)

    embedding_calls: list[tuple[str, str]] = []

    def fake_read_bytes_fn(document: bootstrap_data.ManifestDocument) -> bytes:
        return bootstrap_data.read_source_bytes(rag_dir, document)

    def fake_embedding_fn(deployment: str, text: str) -> list[float]:
        embedding_calls.append((deployment, text))
        return [0.1, 0.2]

    def fake_list_existing_ids_fn(manifest_id: str) -> list[str]:
        # Simulates a previous run that indexed one chunk id no longer
        # produced by the current (single-chunk) content, so it must be
        # reported as stale for the caller to delete.
        return ["doc-stale-from-previous-run"]

    search_documents, stale_ids = bootstrap_data.build_documents(
        manifest=manifest,
        documents=documents,
        rag_dir=rag_dir,
        source_base="https://resolved.example",
        max_tokens=10,
        overlap_tokens=0,
        tokenizer=FakeTokenizer(),
        read_bytes_fn=fake_read_bytes_fn,
        embedding_fn=fake_embedding_fn,
        embedding_deployment="embedding",
        list_existing_ids_fn=fake_list_existing_ids_fn,
    )

    assert len(search_documents) == 1
    assert len(embedding_calls) == 1
    assert search_documents[0]["content"] == "Flight content"
    assert search_documents[0]["chunk_index"] == 0
    assert search_documents[0]["blob_url"] == ("https://resolved.example/data/policies/flights.md")
    assert "https://resolved.example" in search_documents[0]["citation"]
    assert "{{WORKSHOP_SOURCE_BASE}}" not in search_documents[0]["citation"]
    assert search_documents[0]["source_url"] == "https://resolved.example/data/policies/flights.md"
    assert stale_ids == ["doc-stale-from-previous-run"]


def test_read_source_bytes_raises_bootstrap_error_on_missing_file(tmp_path: Path) -> None:
    manifest = _valid_manifest()
    document = bootstrap_data.iter_documents(manifest)[0]

    with pytest.raises(bootstrap_data.BootstrapError):
        bootstrap_data.read_source_bytes(tmp_path, document)


# ---------------------------------------------------------------------------
# list_existing_chunk_ids / delete_chunk_documents (thin adapter wiring,
# exercised with plain fake client objects -- no real Azure SDK needed)
# ---------------------------------------------------------------------------


class _FakeSearchClientForListing:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids
        self.last_filter: str | None = None

    def search(self, *, search_text: str, filter: str, select: list[str]) -> list[dict]:
        self.last_filter = filter
        return [{"id": i} for i in self._ids]


def test_list_existing_chunk_ids_filters_by_manifest_id_and_returns_ids() -> None:
    client = _FakeSearchClientForListing(["doc-1", "doc-2"])

    ids = bootstrap_data.list_existing_chunk_ids(client, "policy-flights-001")

    assert ids == ["doc-1", "doc-2"]
    assert client.last_filter == "manifest_id eq 'policy-flights-001'"


def test_list_existing_chunk_ids_escapes_single_quotes() -> None:
    client = _FakeSearchClientForListing([])

    bootstrap_data.list_existing_chunk_ids(client, "o'brien-policy")

    assert client.last_filter == "manifest_id eq 'o''brien-policy'"


class _FakeSearchClientForAllChunks:
    def __init__(self, ids: list[str]) -> None:
        self._ids = ids

    def search(self, *, search_text: str, select: list[str]) -> list[dict]:
        assert search_text == "*"
        assert select == ["id"]
        return [{"id": item_id} for item_id in self._ids]


def test_list_all_existing_chunk_ids_includes_orphaned_manifest_chunks() -> None:
    client = _FakeSearchClientForAllChunks(["doc-current", "doc-removed-manifest"])

    ids = bootstrap_data.list_all_existing_chunk_ids(client)

    assert ids == ["doc-current", "doc-removed-manifest"]


class _FakeSearchClientForDeletion:
    def __init__(self) -> None:
        self.deleted_documents: list[dict] | None = None

    def delete_documents(self, *, documents: list[dict]) -> list[dict]:
        self.deleted_documents = documents
        return documents


def test_delete_chunk_documents_is_noop_for_empty_list() -> None:
    client = _FakeSearchClientForDeletion()

    result = bootstrap_data.delete_chunk_documents(client, [])

    assert result is None
    assert client.deleted_documents is None


def test_delete_chunk_documents_deletes_given_ids() -> None:
    client = _FakeSearchClientForDeletion()

    bootstrap_data.delete_chunk_documents(client, ["doc-a", "doc-b"])

    assert client.deleted_documents == [{"id": "doc-a"}, {"id": "doc-b"}]


# ---------------------------------------------------------------------------
# Azure OpenAI adapter
# ---------------------------------------------------------------------------


def test_build_openai_client_uses_v1_endpoint_and_entra_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import azure.identity
    import openai

    credential = object()
    token_provider = object()
    client = object()
    calls: dict[str, object] = {}

    def fake_get_bearer_token_provider(received_credential: object, scope: str) -> object:
        calls["credential"] = received_credential
        calls["scope"] = scope
        return token_provider

    def fake_openai(*, base_url: str, api_key: object) -> object:
        calls["base_url"] = base_url
        calls["api_key"] = api_key
        return client

    monkeypatch.setattr(
        azure.identity,
        "get_bearer_token_provider",
        fake_get_bearer_token_provider,
    )
    monkeypatch.setattr(openai, "OpenAI", fake_openai)

    result = bootstrap_data.build_openai_client(
        "https://example.openai.azure.com/openai/v1/",
        credential,
    )

    assert result is client
    assert calls == {
        "credential": credential,
        "scope": "https://ai.azure.com/.default",
        "base_url": "https://example.openai.azure.com/openai/v1/",
        "api_key": token_provider,
    }


# ---------------------------------------------------------------------------
# main() integration (dry-run only -- no Azure calls)
# ---------------------------------------------------------------------------


def _write_manifest_schema_and_rag(tmp_path: Path) -> tuple[Path, Path]:
    rag_dir = tmp_path
    flights_bytes = _write_policy_file(rag_dir, "policies/flights.md", "Flight content")
    hotels_bytes = _write_policy_file(rag_dir, "policies/hotels.md", "Hotel content")

    manifest = _valid_manifest(
        {
            "id": "policy-flights-001",
            "category": "flights",
            "path": "policies/flights.md",
            "sha256": hashlib.sha256(flights_bytes).hexdigest(),
            "size_bytes": len(flights_bytes),
        },
        {
            "id": "policy-hotels-001",
            "category": "hotels",
            "path": "policies/hotels.md",
            "sha256": hashlib.sha256(hotels_bytes).hexdigest(),
            "size_bytes": len(hotels_bytes),
        },
    )
    manifest_path = rag_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(TEST_SCHEMA), encoding="utf-8")

    return manifest_path, schema_path


def _base_cli_args(manifest_path: Path, schema_path: Path) -> list[str]:
    return [
        "--manifest",
        str(manifest_path),
        "--schema",
        str(schema_path),
        "--search-endpoint",
        "https://example.search.windows.net",
        "--openai-endpoint",
        "https://example.openai.azure.com/openai/v1/",
        "--embedding-deployment",
        "embedding",
        "--dry-run",
    ]


def test_main_dry_run_succeeds_for_valid_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # main()'s dry-run path prints a real chunk plan via build_tokenizer(),
    # which normally lazily imports the real tiktoken cl100k_base encoder.
    # Monkeypatching it to the hermetic FakeTokenizer keeps this test free of
    # any network dependency regardless of whether tiktoken's vocabulary is
    # already cached in the current environment.
    monkeypatch.setattr(bootstrap_data, "build_tokenizer", lambda: FakeTokenizer())
    manifest_path, schema_path = _write_manifest_schema_and_rag(tmp_path)

    exit_code = bootstrap_data.main(_base_cli_args(manifest_path, schema_path))

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "policy-flights-001" in captured.out
    assert "embedding_dimensions=2" in captured.out
    assert "max_tokens=512" in captured.out
    assert "chunks=" in captured.out


def test_main_returns_1_when_manifest_missing(tmp_path: Path) -> None:
    _, schema_path = _write_manifest_schema_and_rag(tmp_path)

    exit_code = bootstrap_data.main(_base_cli_args(tmp_path / "no-manifest.json", schema_path))

    assert exit_code == 1


def test_main_returns_1_when_schema_missing(tmp_path: Path) -> None:
    manifest_path, _ = _write_manifest_schema_and_rag(tmp_path)

    exit_code = bootstrap_data.main(_base_cli_args(manifest_path, tmp_path / "no-schema.json"))

    assert exit_code == 1


def test_main_returns_2_for_invalid_manifest_schema(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    _, schema_path = _write_manifest_schema_and_rag(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"documents": []}), encoding="utf-8")

    exit_code = bootstrap_data.main(_base_cli_args(manifest_path, schema_path))

    assert exit_code == 2
    assert "failed schema validation" in capsys.readouterr().err


def test_main_returns_2_for_checksum_mismatch(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    rag_dir = tmp_path
    _write_policy_file(rag_dir, "policies/flights.md", "Flight content")

    manifest = _valid_manifest(
        {
            "id": "policy-flights-001",
            "category": "flights",
            "path": "policies/flights.md",
            "sha256": "0" * 64,  # deliberately wrong
            "size_bytes": 999999,
        }
    )
    manifest_path = rag_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(TEST_SCHEMA), encoding="utf-8")

    exit_code = bootstrap_data.main(_base_cli_args(manifest_path, schema_path))

    assert exit_code == 2
    assert "do not match data/manifest.json" in capsys.readouterr().err


def test_main_returns_2_when_chunking_config_is_missing(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    rag_dir = tmp_path
    flights_bytes = _write_policy_file(rag_dir, "policies/flights.md", "Flight content")

    manifest = _valid_manifest(
        {
            "id": "policy-flights-001",
            "path": "policies/flights.md",
            "sha256": hashlib.sha256(flights_bytes).hexdigest(),
            "size_bytes": len(flights_bytes),
        },
        chunking={},
    )
    manifest_path = rag_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(TEST_SCHEMA), encoding="utf-8")

    exit_code = bootstrap_data.main(_base_cli_args(manifest_path, schema_path))

    assert exit_code == 2
    assert "chunking.max_tokens/overlap_tokens" in capsys.readouterr().err


def test_main_returns_2_when_overlap_tokens_not_smaller_than_max_tokens(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    rag_dir = tmp_path
    flights_bytes = _write_policy_file(rag_dir, "policies/flights.md", "Flight content")

    manifest = _valid_manifest(
        {
            "id": "policy-flights-001",
            "path": "policies/flights.md",
            "sha256": hashlib.sha256(flights_bytes).hexdigest(),
            "size_bytes": len(flights_bytes),
        },
        chunking={
            "strategy": "markdown-heading",
            "unit": "tokens",
            "max_tokens": 10,
            "overlap_tokens": 10,
        },
    )
    manifest_path = rag_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps(TEST_SCHEMA), encoding="utf-8")

    exit_code = bootstrap_data.main(_base_cli_args(manifest_path, schema_path))

    assert exit_code == 2
    assert "must be smaller than" in capsys.readouterr().err

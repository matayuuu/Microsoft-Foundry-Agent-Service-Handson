#!/usr/bin/env python3
"""scripts/bootstrap_data.py

Seeds the Contoso travel-policy RAG content into Azure AI Search (and its
backing blob container) for the Foundry Agent Service hands-on workshop.

Design: pure functions (manifest parsing/validation, markdown-heading
chunking, citation/index-document shaping, checksum verification, result
validation) are fully unit testable without any Azure credentials, network
access, or even the ``tiktoken`` package -- the token-aware chunker takes an
injectable ``Tokenizer`` (``encode``/``decode``) so tests can supply a
deterministic fake. All Azure I/O -- blob upload, embedding generation
(via the Foundry project's OpenAI-compatible client), index create/update,
document upload/merge/delete -- lives in thin adapter functions and is only
exercised by ``main()``.

Consumes ``data/manifest.json`` and ``data/schemas/manifest.schema.json``
(both owned by the data workstream) plus the policy markdown files the
manifest's ``documents[].path`` entries point to (relative to the manifest
file's own directory unless ``--rag-dir`` overrides it). Per
``data/schemas/manifest.schema.json``'s own description ("bootstrap_data.py
uses this contract to verify checksums before indexing content"), this
script:

  * validates the manifest against that JSON Schema (all violations
    reported at once, never just the first),
  * re-hashes every referenced source file and refuses to index anything
    whose sha256/size does not match the manifest (protects against stale
    or tampered content),
  * honors ``manifest["chunking"]`` (``strategy: "markdown-heading"``,
    ``max_tokens``, ``overlap_tokens``, both overridable via
    ``--max-tokens``/``--overlap-tokens``): each document is split on ATX
    (``#``..``######``) headings, then any section still over
    ``max_tokens`` is sliced into token windows (via a real ``tiktoken``
    ``cl100k_base`` encoder in production) that overlap by
    ``overlap_tokens`` tokens, so neighboring chunks keep shared context,
  * builds each chunk's search document with a stable id
    (``sha256(f"{manifest_id}::{chunk_index}")``, so reruns update rather
    than duplicate rows) and a retrievable ``source_url`` field plus
    ``chunk_index``/``heading``/``token_count`` metadata, and
  * reconciles the index after every run: any chunk id previously indexed
    for a ``manifest_id`` that the current run did not (re)produce (e.g. the
    source file shrank) is deleted, so the index never accumulates stale
    chunks.

  Citation strings are built from ``manifest["citation"]["required_fields"]``
  (typically id/title/source_url/effective_date), substituting the
  manifest's ``source_url_base_placeholder`` token with a real, configurable
  base via ``--source-base``. ``--source-base`` defaults to a local
  ``file://`` URI pointing at the resolved RAG directory when not provided
  (useful for direct/local invocation), but ``scripts/setup.sh`` always
  passes a real public source base (this repository's ``main`` branch URL by
  default) so citations are never a Codespace-local ``file://`` path.

If ``data/manifest.json`` does not exist yet, callers should treat that as
a soft warning (see ``scripts/setup.sh``), not a hard failure -- this
script itself still fails loudly if invoked directly against a missing
manifest, since at that point the caller explicitly asked to bootstrap
data.

Everything here is keyless: Azure Search/Storage access uses
``azure.identity.DefaultAzureCredential`` (the participant's own ``az
login`` session, or the caller's ambient identity); embeddings use the
resource's Azure OpenAI v1 endpoint with an Entra ID bearer-token provider.
The Foundry project endpoint does not route embedding requests. No API keys
are read or generated anywhere in this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import jsonschema

DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "schemas" / "manifest.schema.json"
)
DEFAULT_SOURCE_URL_PLACEHOLDER = "{{WORKSHOP_SOURCE_BASE}}"
FRONT_MATTER_DELIMITER = "---"
# text-embedding-3-small (this workshop's embedding model) and the gpt-4.1
# family both tokenize with the cl100k_base BPE vocabulary.
TIKTOKEN_ENCODING_NAME = "cl100k_base"
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*$")


class ManifestError(ValueError):
    """Raised when data/manifest.json does not match the expected contract."""


class BootstrapError(RuntimeError):
    """Raised when a bootstrap step fails in a way the caller must not ignore."""


class Tokenizer(Protocol):
    """Minimal tokenizer contract the pure chunking functions depend on.
    Production code uses a real ``tiktoken`` encoder (which already
    satisfies this protocol); unit tests inject a small deterministic fake
    so they never need the ``tiktoken`` package or network access."""

    def encode(self, text: str) -> list[int]: ...

    def decode(self, tokens: list[int]) -> str: ...


@dataclass(frozen=True)
class MarkdownChunk:
    """One chunk produced by ``chunk_markdown_document()``: a token-window
    slice of one markdown-heading section, with the metadata that ends up
    on its search document."""

    chunk_index: int
    heading: str
    text: str
    token_count: int


# ---------------------------------------------------------------------------
# Pure functions: manifest/schema parsing and validation (no I/O beyond a
# single file read each; source-file reads are separate, explicitly-named
# adapters so tests can inject fixture directories).
# ---------------------------------------------------------------------------


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Reads and JSON-decodes the manifest file. Raises ManifestError on
    anything that is not valid JSON or not a top-level JSON object."""
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"could not read manifest at {manifest_path}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest at {manifest_path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError(f"manifest at {manifest_path} must be a JSON object at the top level")

    return data


def load_schema(schema_path: Path) -> dict[str, Any]:
    """Reads and JSON-decodes the manifest JSON Schema file. Raises
    ManifestError on anything that is not valid JSON or not a top-level
    JSON object."""
    try:
        raw = schema_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"could not read manifest schema at {schema_path}: {exc}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest schema at {schema_path} is not valid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ManifestError(f"manifest schema at {schema_path} must be a JSON object")

    return data


def validate_manifest_schema(manifest: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validates ``manifest`` against the JSON Schema owned by the data
    workstream (``data/schemas/manifest.schema.json`` by default). Returns a
    list of human-readable error strings (empty list means valid); collects
    every violation in one pass instead of stopping at the first, so a
    caller can report the full picture. Never raises -- callers decide
    whether to treat errors as fatal."""
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    validator = validator_cls(schema)

    errors: list[str] = []
    for error in sorted(validator.iter_errors(manifest), key=lambda e: list(e.absolute_path)):
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        errors.append(f"{location}: {error.message}")
    return errors


@dataclass(frozen=True)
class ManifestDocument:
    """Normalized, validated view of one manifest ``documents[]`` entry."""

    id: str
    title: str
    category: str
    path: str
    effective_date: str
    applies_to: tuple[str, ...]
    source_url: str
    sha256: str
    size_bytes: int


def iter_documents(manifest: dict[str, Any]) -> list[ManifestDocument]:
    """Builds ManifestDocument entries from ``manifest["documents"]``.
    Assumes validate_manifest_schema() already returned no errors for this
    manifest; raises ManifestError if a required field is missing or the
    wrong type (defensive -- callers should validate first)."""
    documents: list[ManifestDocument] = []
    for index, raw in enumerate(manifest.get("documents", [])):
        if not isinstance(raw, dict):
            raise ManifestError(f"documents[{index}] must be a JSON object")
        try:
            applies_to = raw["applies_to"]
            if not isinstance(applies_to, list):
                raise ManifestError(f"documents[{index}].applies_to must be a JSON array")
            documents.append(
                ManifestDocument(
                    id=raw["id"],
                    title=raw["title"],
                    category=raw["category"],
                    path=raw["path"],
                    effective_date=raw["effective_date"],
                    applies_to=tuple(applies_to),
                    source_url=raw["source_url"],
                    sha256=raw["sha256"],
                    size_bytes=raw["size_bytes"],
                )
            )
        except KeyError as exc:
            raise ManifestError(f"documents[{index}] is missing required field {exc}") from exc
    return documents


# ---------------------------------------------------------------------------
# Pure functions: markdown-heading, token-aware chunking (manifest
# `chunking` contract: strategy="markdown-heading", unit="tokens").
# ---------------------------------------------------------------------------


def split_markdown_sections(text: str) -> list[tuple[str, str]]:
    """Splits ``text`` into ``(heading_path, section_body)`` tuples per the
    manifest's ``markdown-heading`` chunking strategy. ``heading_path`` is
    the `` > ``-joined breadcrumb of ATX headings (``#``..``######``) active
    at that point in the document (text before the first heading, if any,
    gets an empty heading_path). Sections whose body is empty/whitespace-
    only after the heading line itself are dropped. Pure: no I/O, no
    tokenizer -- only markdown structure."""
    stack: list[tuple[int, str]] = []
    sections: list[tuple[str, str]] = []
    current_body: list[str] = []

    def _flush() -> None:
        body = "\n".join(current_body).strip("\n")
        if body.strip():
            sections.append((" > ".join(title for _, title in stack), body))

    for line in text.split("\n"):
        match = _HEADING_RE.match(line)
        if match is None:
            current_body.append(line)
            continue
        _flush()
        current_body = []
        level = len(match.group(1))
        title = match.group(2)
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
    _flush()
    return sections


def chunk_text_by_tokens(
    text: str,
    tokenizer: Tokenizer,
    max_tokens: int,
    overlap_tokens: int,
) -> list[tuple[str, int]]:
    """Splits already section-scoped ``text`` into token windows of at most
    ``max_tokens`` tokens, sliding forward by ``max_tokens - overlap_tokens``
    tokens each step so neighboring windows share ``overlap_tokens`` tokens
    of context. Returns ``(chunk_text, token_count)`` tuples in order,
    dropping any window that decodes to empty/whitespace. When the whole
    section already fits in one window, returns it unchanged (not
    round-tripped through the tokenizer's decode), so no-op chunking never
    introduces token-boundary artifacts. Pure given an injected
    ``tokenizer`` -- production code uses a real tiktoken ``cl100k_base``
    encoder; tests inject a deterministic fake so they never need network
    access."""
    if max_tokens <= 0:
        raise BootstrapError(f"chunking.max_tokens must be positive, got {max_tokens}")
    if overlap_tokens < 0:
        raise BootstrapError(f"chunking.overlap_tokens must be >= 0, got {overlap_tokens}")
    if overlap_tokens >= max_tokens:
        raise BootstrapError(
            f"chunking.overlap_tokens ({overlap_tokens}) must be smaller than "
            f"chunking.max_tokens ({max_tokens})"
        )

    tokens = tokenizer.encode(text)
    if not tokens:
        return []
    if len(tokens) <= max_tokens:
        return [(text.strip(), len(tokens))]

    step = max_tokens - overlap_tokens
    windows: list[tuple[str, int]] = []
    start = 0
    total = len(tokens)
    while start < total:
        end = min(start + max_tokens, total)
        window_tokens = tokens[start:end]
        window_text = tokenizer.decode(window_tokens).strip()
        if window_text:
            windows.append((window_text, len(window_tokens)))
        if end == total:
            break
        start += step
    return windows


def chunk_markdown_document(
    content: str,
    tokenizer: Tokenizer,
    max_tokens: int,
    overlap_tokens: int,
) -> list[MarkdownChunk]:
    """Applies the full ``markdown-heading`` chunking contract to one
    document's (front-matter-stripped) body: split into heading sections,
    then token-window each section, assigning a document-global, sequential
    ``chunk_index``. Pure given an injected ``tokenizer``."""
    chunks: list[MarkdownChunk] = []
    index = 0
    for heading_path, body in split_markdown_sections(content):
        windows = chunk_text_by_tokens(body, tokenizer, max_tokens, overlap_tokens)
        for chunk_text, token_count in windows:
            chunks.append(
                MarkdownChunk(
                    chunk_index=index,
                    heading=heading_path,
                    text=chunk_text,
                    token_count=token_count,
                )
            )
            index += 1
    return chunks


def stale_chunk_ids(existing_ids: Sequence[str], current_ids: Sequence[str]) -> list[str]:
    """Pure set-difference: chunk document ids already indexed for a
    manifest document (from a previous run) that the current chunking of
    that document did not (re)produce -- e.g. the source file shrank and
    now needs fewer chunks. Sorted for deterministic output/tests."""
    return sorted(set(existing_ids) - set(current_ids))


# ---------------------------------------------------------------------------
# Pure functions: checksum verification, citation building, naming, and
# search-document/index shaping.
# ---------------------------------------------------------------------------


def checksum_error(document: ManifestDocument, content_bytes: bytes) -> str | None:
    """Returns a human-readable error if ``content_bytes`` (the actual bytes
    read from disk for this document) does not match the manifest's
    recorded sha256/size_bytes, or None if it matches. Pure: takes bytes
    already read by an adapter, never touches the filesystem itself."""
    canonical = content_bytes.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    actual_sha256 = hashlib.sha256(canonical).hexdigest()
    if actual_sha256 != document.sha256:
        return (
            f"documents id={document.id}: source file sha256 mismatch "
            f"(manifest={document.sha256}, actual={actual_sha256}); "
            "the file on disk does not match data/manifest.json"
        )
    if len(canonical) != document.size_bytes:
        return (
            f"documents id={document.id}: source file size mismatch "
            f"(manifest={document.size_bytes} bytes, actual={len(canonical)} canonical bytes)"
        )
    return None


def verify_source_checksums(
    documents: Sequence[ManifestDocument],
    read_bytes_fn: Callable[[ManifestDocument], bytes],
) -> list[str]:
    """Runs checksum_error() for every document, using the injected
    ``read_bytes_fn`` adapter to fetch each document's actual on-disk bytes.
    Returns the aggregate list of error strings (empty means every source
    file matches the manifest)."""
    errors: list[str] = []
    for document in documents:
        content_bytes = read_bytes_fn(document)
        error = checksum_error(document, content_bytes)
        if error is not None:
            errors.append(error)
    return errors


def strip_front_matter(text: str) -> str:
    """Strips a leading YAML front-matter block (delimited by ``---`` lines)
    from a policy markdown file's text, if present, returning only the
    document body used for embeddings/search content. Returns the text
    unchanged if it does not start with a front-matter delimiter. Normalizes
    CRLF to LF first so this works regardless of the source file's line
    endings (the real data/policies/*.md files are checked out as CRLF on
    Windows)."""
    normalized = text.replace("\r\n", "\n")
    prefix = f"{FRONT_MATTER_DELIMITER}\n"
    if not normalized.startswith(prefix):
        return text
    end_marker = f"\n{FRONT_MATTER_DELIMITER}"
    end_index = normalized.find(end_marker, len(prefix))
    if end_index == -1:
        return text
    return normalized[end_index + len(end_marker) :].lstrip("\n")


def resolve_source_url(source_url: str, placeholder: str, source_base: str) -> str:
    """Substitutes the manifest's placeholder token (e.g.
    ``{{WORKSHOP_SOURCE_BASE}}``) in ``source_url`` with a real, configurable
    base, per data/schemas/manifest.schema.json's own documented intent."""
    return source_url.replace(placeholder, source_base)


def build_citation(
    document: ManifestDocument,
    required_fields: Sequence[str],
    resolved_source_url: str,
) -> str:
    """Builds the human-readable citation string surfaced by search results,
    from exactly the fields ``manifest["citation"]["required_fields"]``
    names (typically id/title/source_url/effective_date). Pure: takes the
    already-resolved source URL rather than re-deriving it."""
    field_values = {
        "id": document.id,
        "title": document.title,
        "source_url": resolved_source_url,
        "effective_date": document.effective_date,
    }
    parts = []
    for field in required_fields:
        if field not in field_values:
            raise ManifestError(f"citation.required_fields contains unsupported field '{field}'")
        parts.append(f"{field}={field_values[field]}")
    return " | ".join(parts)


def blob_name_for(document: ManifestDocument) -> str:
    """Deterministic blob path for a manifest document: stable across reruns
    (idempotent uploads) and namespaced by category."""
    suffix = Path(document.path).suffix or ".txt"
    safe_id = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in document.id)
    return f"{document.category}/{safe_id}{suffix}"


def chunk_search_document_id(document_id: str, chunk_index: int) -> str:
    """Azure AI Search document keys must match ``^[a-zA-Z0-9_\\-=]+$``.
    Each chunk's key is derived from ``manifest_id`` + its
    (document-scoped, sequential) ``chunk_index``, hashed to a stable,
    always-valid key -- deterministic across reruns as long as a document's
    chunk count/order does not change, so unchanged chunks are updated
    (merge) in place rather than re-created with a new id each run."""
    digest = hashlib.sha256(f"{document_id}::{chunk_index}".encode()).hexdigest()
    return f"doc-{digest[:32]}"


def build_search_document(
    document: ManifestDocument,
    chunk: MarkdownChunk,
    embedding: Sequence[float],
    blob_url: str,
    citation: str,
    resolved_source_url: str,
) -> dict[str, Any]:
    """Builds the plain-dict search document uploaded/merged into the
    ``contoso-travel-policy`` index for one chunk. Pure: no I/O, only
    shaping already-fetched/-computed values (an already-built
    ``MarkdownChunk``, an already-computed embedding vector, an
    already-uploaded blob URL, an already-built citation string, and the
    already-resolved public ``source_url``)."""
    return {
        "id": chunk_search_document_id(document.id, chunk.chunk_index),
        "manifest_id": document.id,
        "title": document.title,
        "content": chunk.text,
        "citation": citation,
        "category": document.category,
        "source_path": document.path,
        "source_url": resolved_source_url,
        "effective_date": document.effective_date,
        "applies_to": ",".join(document.applies_to),
        "blob_url": blob_url,
        "chunk_index": chunk.chunk_index,
        "heading": chunk.heading,
        "token_count": chunk.token_count,
        "content_vector": list(embedding),
    }


def validate_search_documents(
    documents: Sequence[dict[str, Any]],
    expected_dimensions: int,
) -> list[str]:
    """Validates document count, embedding dimensions, and presence of the
    citation field before they are uploaded. Returns a list of error
    strings (empty means valid)."""
    errors: list[str] = []

    if len(documents) == 0:
        errors.append("no search documents were built from the manifest (expected at least 1)")

    seen_ids: set[str] = set()
    for i, doc in enumerate(documents):
        doc_id = doc.get("id")
        if not isinstance(doc_id, str) or not doc_id:
            errors.append(f"documents[{i}] is missing a valid 'id'")
        elif doc_id in seen_ids:
            errors.append(f"documents[{i}] has duplicate id '{doc_id}'")
        else:
            seen_ids.add(doc_id)

        citation = doc.get("citation")
        if not isinstance(citation, str) or citation.strip() == "":
            errors.append(f"documents[{i}] (id={doc_id}) is missing a non-empty 'citation' field")

        source_url = doc.get("source_url")
        if not isinstance(source_url, str) or source_url.strip() == "":
            errors.append(f"documents[{i}] (id={doc_id}) is missing a non-empty 'source_url' field")

        vector = doc.get("content_vector")
        if not isinstance(vector, list) or len(vector) != expected_dimensions:
            actual = len(vector) if isinstance(vector, list) else "n/a"
            errors.append(
                f"documents[{i}] (id={doc_id}) content_vector has dimension {actual}, "
                f"expected {expected_dimensions}"
            )

    return errors


def build_index_fields(embedding_dimensions: int) -> list[dict[str, Any]]:
    """Returns a plain-dict field-list contract for the
    ``contoso-travel-policy`` index. Kept as plain dicts (rather than
    azure-search-documents SDK model instances) so this function has zero
    SDK/network coupling and can be unit tested with a bare Python
    interpreter; ``to_search_index()`` below is the thin adapter that
    converts this contract into real SDK model objects."""
    return [
        {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
        {"name": "manifest_id", "type": "Edm.String", "filterable": True},
        {"name": "title", "type": "Edm.String", "searchable": True},
        {"name": "content", "type": "Edm.String", "searchable": True},
        {"name": "citation", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "category", "type": "Edm.String", "filterable": True, "facetable": True},
        {"name": "source_path", "type": "Edm.String", "retrievable": True},
        {"name": "source_url", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "effective_date", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "applies_to", "type": "Edm.String", "filterable": True, "retrievable": True},
        {"name": "blob_url", "type": "Edm.String", "retrievable": True},
        {
            "name": "chunk_index",
            "type": "Edm.Int32",
            "filterable": True,
            "sortable": True,
            "retrievable": True,
        },
        {"name": "heading", "type": "Edm.String", "retrievable": True},
        {"name": "token_count", "type": "Edm.Int32", "retrievable": True},
        {
            "name": "content_vector",
            "type": "Collection(Edm.Single)",
            "searchable": True,
            "vector_search_dimensions": embedding_dimensions,
            "vector_search_profile_name": "contoso-travel-policy-vector-profile",
        },
    ]


def to_search_index(index_name: str, embedding_dimensions: int) -> Any:
    """Adapter: converts the plain-dict field contract above into a real
    ``azure.search.documents.indexes.models.SearchIndex``. Constructing SDK
    model objects performs no network I/O, but importing the SDK is kept
    local to this function so pure-function unit tests never require
    ``azure-search-documents`` to be import-successful in a stripped-down
    test environment."""
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        SearchableField,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )

    fields: list[Any] = []
    for spec in build_index_fields(embedding_dimensions):
        if spec["type"] == "Collection(Edm.Single)":
            fields.append(
                SearchField(
                    name=spec["name"],
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=spec["vector_search_dimensions"],
                    vector_search_profile_name=spec["vector_search_profile_name"],
                )
            )
        elif spec.get("searchable"):
            fields.append(SearchableField(name=spec["name"], type=spec["type"]))
        else:
            fields.append(
                SimpleField(
                    name=spec["name"],
                    type=spec["type"],
                    key=spec.get("key", False),
                    filterable=spec.get("filterable", False),
                    facetable=spec.get("facetable", False),
                    sortable=spec.get("sortable", False),
                    retrievable=spec.get("retrievable", True),
                )
            )

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="contoso-travel-policy-hnsw")],
        profiles=[
            VectorSearchProfile(
                name="contoso-travel-policy-vector-profile",
                algorithm_configuration_name="contoso-travel-policy-hnsw",
            )
        ],
    )

    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="contoso-travel-policy-semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="content")],
                    keywords_fields=[SemanticField(field_name="category")],
                ),
            )
        ]
    )

    return SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )


# ---------------------------------------------------------------------------
# Adapters: filesystem and Azure I/O. Kept thin and separate from the pure
# functions above so tests can substitute fixtures/fakes freely.
# ---------------------------------------------------------------------------


def read_source_bytes(rag_dir: Path, document: ManifestDocument) -> bytes:
    """Reads the raw bytes of the local source file a manifest document
    points to. This is local filesystem I/O (not Azure), kept as an adapter
    purely so tests can point it at a temporary fixture directory instead of
    the real ``data/`` directory."""
    source_file = rag_dir / document.path
    try:
        return source_file.read_bytes()
    except OSError as exc:
        raise BootstrapError(
            f"could not read source file for document '{document.id}' at {source_file}: {exc}"
        ) from exc


def upload_blob(
    blob_service_client: Any,
    container_name: str,
    blob_name: str,
    content: str,
) -> str:
    """Uploads ``content`` to the given blob, overwriting any existing blob
    with the same name (idempotent re-runs), and returns its URL."""
    container_client = blob_service_client.get_container_client(container_name)
    blob_client = container_client.upload_blob(
        name=blob_name,
        data=content.encode("utf-8"),
        overwrite=True,
    )
    return str(blob_client.url)


def get_embedding(openai_client: Any, deployment: str, text: str) -> list[float]:
    """Requests an embedding vector for ``text`` from the given Azure OpenAI
    deployment via the already-authenticated ``openai_client``."""
    response = openai_client.embeddings.create(model=deployment, input=text)
    return list(response.data[0].embedding)


def ensure_index(index_client: Any, index: Any) -> None:
    """Creates the index if absent, or updates it in place if it already
    exists (idempotent re-runs)."""
    index_client.create_or_update_index(index)


def merge_or_upload_documents(search_client: Any, documents: Sequence[dict[str, Any]]) -> Any:
    """Merges each document into the index if its key already exists, or
    inserts it otherwise (idempotent re-runs; never duplicates rows)."""
    return search_client.merge_or_upload_documents(documents=list(documents))


def list_existing_chunk_ids(search_client: Any, manifest_id: str) -> list[str]:
    """Returns the ``id`` of every chunk document currently indexed for
    ``manifest_id``, so a rerun can diff them against the chunk ids the
    current chunking pass produced (see ``stale_chunk_ids()``) and delete
    anything no longer produced. Escapes the OData string literal so a
    manifest id containing a single quote cannot break the filter."""
    escaped_id = manifest_id.replace("'", "''")
    results = search_client.search(
        search_text="*",
        filter=f"manifest_id eq '{escaped_id}'",
        select=["id"],
    )
    return [result["id"] for result in results]


def list_all_existing_chunk_ids(search_client: Any) -> list[str]:
    """Return all keys from the workshop-dedicated index.

    This catches chunks whose entire manifest document was removed since the
    previous run; per-manifest reconciliation alone cannot discover those
    orphaned rows.
    """
    results = search_client.search(search_text="*", select=["id"])
    return [result["id"] for result in results]


def delete_chunk_documents(search_client: Any, chunk_ids: Sequence[str]) -> Any | None:
    """Deletes the given chunk document ids from the index. No-op (and no
    network call) when ``chunk_ids`` is empty, since
    ``search_client.delete_documents`` requires at least one document."""
    if not chunk_ids:
        return None
    return search_client.delete_documents(documents=[{"id": chunk_id} for chunk_id in chunk_ids])


def build_tokenizer() -> Tokenizer:
    """Adapter: returns a real tiktoken ``cl100k_base`` encoder. Imported
    lazily (only when Azure I/O actually runs, i.e. not in pure-function
    unit tests) so the ``tiktoken`` package -- and any first-use network
    fetch of its vocabulary file -- is never required just to import this
    module or exercise its pure functions."""
    import tiktoken

    return tiktoken.get_encoding(TIKTOKEN_ENCODING_NAME)


def build_credential() -> Any:
    """Returns a azure.identity.DefaultAzureCredential -- the workshop's
    single, keyless authentication mechanism for every Azure data-plane
    call this script makes."""
    from azure.identity import DefaultAzureCredential

    return DefaultAzureCredential()


def build_openai_client(openai_endpoint: str, credential: Any) -> Any:
    """Returns a keyless OpenAI client for the resource's v1 endpoint.

    Microsoft Learn's SDK endpoint guidance (retrieved 2026-08-26) states
    that the Foundry project endpoint does not route embedding requests.
    """
    from azure.identity import get_bearer_token_provider
    from openai import OpenAI

    token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")
    return OpenAI(base_url=openai_endpoint, api_key=token_provider)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path, help="Path to data/manifest.json")
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help="Path to the manifest JSON Schema. Defaults to "
        "data/schemas/manifest.schema.json next to this repository's data/ directory.",
    )
    parser.add_argument(
        "--rag-dir",
        type=Path,
        default=None,
        help="Directory manifest 'documents[].path' entries are relative to. "
        "Defaults to the manifest file's own directory (data/).",
    )
    parser.add_argument(
        "--source-base",
        default=None,
        help="Replaces the manifest's source_url_base_placeholder token "
        "(e.g. {{WORKSHOP_SOURCE_BASE}}) in each document's source_url before it is used "
        "for citations and the indexed source_url field. Defaults to a local file:// URI over "
        "--rag-dir when not set (useful for direct/local invocation), but scripts/setup.sh "
        "always passes a real public source base so citations/source_url are never a "
        "Codespace-local file:// path.",
    )
    parser.add_argument(
        "--search-endpoint", required=True, help="https://<search-service>.search.windows.net"
    )
    parser.add_argument("--storage-account-name", required=True)
    parser.add_argument("--storage-container", required=True)
    parser.add_argument(
        "--openai-endpoint",
        required=True,
        help="Azure OpenAI v1 endpoint "
        "(https://<account>.openai.azure.com/openai/v1/) used for keyless embedding calls.",
    )
    parser.add_argument("--embedding-deployment", required=True)
    parser.add_argument(
        "--embedding-dimensions",
        type=int,
        default=None,
        help="Overrides manifest['embedding']['default_dimensions'] when set.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=None,
        help="Overrides manifest['chunking']['max_tokens'] when set.",
    )
    parser.add_argument(
        "--overlap-tokens",
        type=int,
        default=None,
        help="Overrides manifest['chunking']['overlap_tokens'] when set.",
    )
    parser.add_argument("--index-name", default="contoso-travel-policy")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the manifest, verify checksums, and print the planned index/chunk-plan "
        "without calling Azure.",
    )
    return parser.parse_args(argv)


def build_documents(
    manifest: dict[str, Any],
    documents: Sequence[ManifestDocument],
    rag_dir: Path,
    source_base: str,
    max_tokens: int,
    overlap_tokens: int,
    tokenizer: Tokenizer,
    read_bytes_fn: Callable[[ManifestDocument], bytes],
    embedding_fn: Any,
    embedding_deployment: str,
    blob_upload_fn: Any,
    storage_container: str,
    list_existing_ids_fn: Callable[[str], Sequence[str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Wires the pure chunking/shaping functions to the (already-selected)
    I/O functions for the manifest's documents -> ``(search_documents,
    stale_chunk_ids)``. Each manifest document is chunked per the
    manifest's ``markdown-heading`` strategy and produces one search
    document per chunk. ``stale_chunk_ids`` is the aggregate, across all
    documents, of chunk ids previously indexed (per ``list_existing_ids_fn``)
    that this run's chunking no longer produced, and should be deleted by
    the caller after a successful upload. ``read_bytes_fn``, ``embedding_fn``,
    ``blob_upload_fn``, and ``list_existing_ids_fn`` are injected so tests
    can pass fakes. Callers must run verify_source_checksums() against
    ``documents`` before calling this, so any checksum mismatch is reported
    up front rather than surfacing mid-upload."""
    placeholder = manifest.get("source_url_base_placeholder", DEFAULT_SOURCE_URL_PLACEHOLDER)
    required_citation_fields = manifest["citation"]["required_fields"]

    built: list[dict[str, Any]] = []
    all_stale_ids: list[str] = []
    for manifest_document in documents:
        content_bytes = read_bytes_fn(manifest_document)
        content = strip_front_matter(content_bytes.decode("utf-8"))
        blob_url = blob_upload_fn(storage_container, blob_name_for(manifest_document), content)
        resolved_source_url = resolve_source_url(
            manifest_document.source_url, placeholder, source_base
        )
        citation = build_citation(manifest_document, required_citation_fields, resolved_source_url)

        chunks = chunk_markdown_document(content, tokenizer, max_tokens, overlap_tokens)
        current_chunk_ids: list[str] = []
        for chunk in chunks:
            embedding = embedding_fn(embedding_deployment, chunk.text)
            search_document = build_search_document(
                manifest_document, chunk, embedding, blob_url, citation, resolved_source_url
            )
            built.append(search_document)
            current_chunk_ids.append(search_document["id"])

        existing_ids = list_existing_ids_fn(manifest_document.id)
        all_stale_ids.extend(stale_chunk_ids(existing_ids, current_chunk_ids))

    return built, sorted(set(all_stale_ids))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    manifest_path: Path = args.manifest
    if not manifest_path.exists():
        print(
            f"bootstrap_data.py: manifest not found at {manifest_path}. "
            "This is expected before the data workstream has published data/manifest.json; "
            "nothing to bootstrap yet.",
            file=sys.stderr,
        )
        return 1

    schema_path: Path = args.schema
    if not schema_path.exists():
        print(
            f"bootstrap_data.py: manifest schema not found at {schema_path}. "
            "Cannot validate data/manifest.json without it.",
            file=sys.stderr,
        )
        return 1

    manifest = load_manifest(manifest_path)
    schema = load_schema(schema_path)
    schema_errors = validate_manifest_schema(manifest, schema)
    if schema_errors:
        print(f"bootstrap_data.py: {manifest_path} failed schema validation:", file=sys.stderr)
        for error in schema_errors:
            print(f"  - {error}", file=sys.stderr)
        return 2

    documents = iter_documents(manifest)
    rag_dir = args.rag_dir if args.rag_dir is not None else manifest_path.parent
    source_base = args.source_base if args.source_base is not None else rag_dir.resolve().as_uri()

    chunking = manifest.get("chunking", {})
    max_tokens = args.max_tokens if args.max_tokens is not None else chunking.get("max_tokens")
    overlap_tokens = (
        args.overlap_tokens if args.overlap_tokens is not None else chunking.get("overlap_tokens")
    )
    if max_tokens is None or overlap_tokens is None:
        print(
            "bootstrap_data.py: chunking.max_tokens/overlap_tokens are not set in the manifest "
            "and were not overridden via --max-tokens/--overlap-tokens.",
            file=sys.stderr,
        )
        return 2
    if overlap_tokens >= max_tokens:
        print(
            f"bootstrap_data.py: overlap_tokens ({overlap_tokens}) must be smaller than "
            f"max_tokens ({max_tokens}).",
            file=sys.stderr,
        )
        return 2

    def _read_bytes_fn(document: ManifestDocument) -> bytes:
        return read_source_bytes(rag_dir, document)

    checksum_errors = verify_source_checksums(documents, _read_bytes_fn)
    if checksum_errors:
        print(
            f"bootstrap_data.py: source files under {rag_dir} do not match data/manifest.json:",
            file=sys.stderr,
        )
        for error in checksum_errors:
            print(f"  - {error}", file=sys.stderr)
        return 2

    embedding_dimensions = (
        args.embedding_dimensions
        if args.embedding_dimensions is not None
        else manifest["embedding"]["default_dimensions"]
    )

    if args.dry_run:
        tokenizer = build_tokenizer()
        print(
            f"bootstrap_data.py: dry run -- {len(documents)} document(s) validated "
            f"(schema OK, checksums OK, embedding_dimensions={embedding_dimensions}, "
            f"max_tokens={max_tokens}, overlap_tokens={overlap_tokens}):"
        )
        for doc in documents:
            content = strip_front_matter(_read_bytes_fn(doc).decode("utf-8"))
            chunks = chunk_markdown_document(content, tokenizer, max_tokens, overlap_tokens)
            print(
                f"  - {doc.id} -> {blob_name_for(doc)} (category={doc.category}, "
                f"chunks={len(chunks)})"
            )
        return 0

    credential = build_credential()

    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.storage.blob import BlobServiceClient

    blob_service_client = BlobServiceClient(
        account_url=f"https://{args.storage_account_name}.blob.core.windows.net",
        credential=credential,
    )
    index_client = SearchIndexClient(endpoint=args.search_endpoint, credential=credential)
    search_client = SearchClient(
        endpoint=args.search_endpoint,
        index_name=args.index_name,
        credential=credential,
    )
    tokenizer = build_tokenizer()
    openai_client = build_openai_client(args.openai_endpoint, credential)

    def _embedding_fn(deployment: str, text: str) -> list[float]:
        return get_embedding(openai_client, deployment, text)

    def _blob_upload_fn(container: str, blob_name: str, content: str) -> str:
        return upload_blob(blob_service_client, container, blob_name, content)

    def _list_existing_ids_fn(manifest_id: str) -> Sequence[str]:
        return list_existing_chunk_ids(search_client, manifest_id)

    # ensure_index() runs before build_documents()/stale-id queries so even a
    # first-ever run has an existing (freshly created, empty) index to query
    # against -- Azure AI Search naturally returns no results for an empty
    # index, so no special-casing "index doesn't exist yet" is needed.
    index = to_search_index(args.index_name, embedding_dimensions)
    ensure_index(index_client, index)

    search_documents, stale_ids = build_documents(
        manifest=manifest,
        documents=documents,
        rag_dir=rag_dir,
        source_base=source_base,
        max_tokens=max_tokens,
        overlap_tokens=overlap_tokens,
        tokenizer=tokenizer,
        read_bytes_fn=_read_bytes_fn,
        embedding_fn=_embedding_fn,
        embedding_deployment=args.embedding_deployment,
        blob_upload_fn=_blob_upload_fn,
        storage_container=args.storage_container,
        list_existing_ids_fn=_list_existing_ids_fn,
    )

    all_existing_ids = list_all_existing_chunk_ids(search_client)
    current_ids = [document["id"] for document in search_documents]
    stale_ids = sorted(set(stale_ids) | set(stale_chunk_ids(all_existing_ids, current_ids)))

    validation_errors = validate_search_documents(search_documents, embedding_dimensions)
    if validation_errors:
        print("bootstrap_data.py: built search documents failed validation:", file=sys.stderr)
        for error in validation_errors:
            print(f"  - {error}", file=sys.stderr)
        return 2

    result = merge_or_upload_documents(search_client, search_documents)

    succeeded = sum(1 for item in result if getattr(item, "succeeded", False))
    print(
        f"bootstrap_data.py: merged/uploaded {succeeded}/{len(search_documents)} "
        f"chunk document(s) into '{args.index_name}'."
    )
    if succeeded != len(search_documents):
        print(
            "bootstrap_data.py: one or more documents failed to upload; see above.",
            file=sys.stderr,
        )
        return 2

    delete_chunk_documents(search_client, stale_ids)
    if stale_ids:
        print(
            f"bootstrap_data.py: deleted {len(stale_ids)} stale chunk document(s) no longer "
            "produced by the current manifest content."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

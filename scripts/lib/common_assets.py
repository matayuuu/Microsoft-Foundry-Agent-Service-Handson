"""Build public workshop assets from checked-in sources, without Azure access."""

from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_NAMES = ("travel-estimation", "preapproval-simulation")
SKILLS_DIR = REPO_ROOT / "data" / "skills"
TRAVEL_API_DIR = REPO_ROOT / "src" / "travel-api"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "assets"
OPENAPI_SERVER_PLACEHOLDER = "https://replace-with-your-travel-api.example.invalid"
EXPECTED_OPERATIONS = {
    ("get", "/health"): "getHealth",
    ("get", "/per-diem"): "getPerDiem",
    ("post", "/trip-estimates"): "createTripEstimate",
    ("post", "/preapprovals"): "createPreapproval",
}
HTTP_METHODS = frozenset({"get", "put", "post", "delete", "options", "head", "patch", "trace"})


class CommonAssetsError(ValueError):
    """A checked-in source cannot produce the public workshop assets."""


def build_skill_archive(name: str, content: str) -> bytes:
    """Package one validated, byte-preserved SKILL.md at the archive root."""
    front_matter = re.fullmatch(r"---\r?\n(.*?)\r?\n---\r?\n(.*)", content, re.DOTALL)
    if front_matter is None or not front_matter[2].strip():
        raise CommonAssetsError(f"{name}: SKILL.md needs front matter and instructions.")
    try:
        metadata = yaml.safe_load(front_matter[1])
    except yaml.YAMLError as exc:
        raise CommonAssetsError(f"{name}: invalid SKILL.md front matter.") from exc
    if (
        not isinstance(metadata, dict)
        or metadata.get("name") != name
        or not isinstance(metadata.get("description"), str)
        or not metadata["description"].strip()
        or len(metadata["description"]) > 1024
    ):
        raise CommonAssetsError(
            f"{name}: SKILL.md needs a matching name and a description of 1-1024 characters."
        )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        entry = zipfile.ZipInfo("SKILL.md", date_time=(2026, 1, 1, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        # Fix host-dependent ZIP metadata as well as the timestamp.
        entry.create_system = 3
        entry.external_attr = 0o100644 << 16
        archive.writestr(entry, content.encode("utf-8"), compresslevel=9)
    return buffer.getvalue()


def load_travel_api_schema(api_dir: Path = TRAVEL_API_DIR) -> dict[str, Any]:
    """Call the local API's schema factory, never a deployed HTTP endpoint."""
    source = api_dir / "travel_api" / "main.py"
    if not source.is_file():
        raise CommonAssetsError(f"Travel API source not found: {source}")

    previous_path = sys.path.copy()
    sys.path.insert(0, str(api_dir.resolve()))
    try:
        module = import_module("travel_api.main")
    except ImportError as exc:
        raise CommonAssetsError(
            "Cannot import the checked-in Travel API. Use management Python 3.12 with "
            f"the pinned src/travel-api/requirements.txt dependencies: {exc}"
        ) from exc
    except (SyntaxError, OSError) as exc:
        raise CommonAssetsError(f"Cannot load Travel API source {source}: {exc}") from exc
    finally:
        sys.path[:] = previous_path

    if Path(module.__file__).resolve() != source.resolve():
        raise CommonAssetsError(
            f"Travel API was imported from {module.__file__}, not checked-in source {source}."
        )
    try:
        return module.app.openapi()
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        raise CommonAssetsError(f"Cannot generate OpenAPI from {source}: {exc}") from exc


def build_openapi_asset(spec: dict[str, Any]) -> bytes:
    """Keep the API contract intact and supply its single public URL placeholder."""
    if not isinstance(spec, dict) or not str(spec.get("openapi", "")).startswith("3.1."):
        raise CommonAssetsError("Travel API must provide an OpenAPI 3.1 document.")
    paths = spec.get("paths")
    if not isinstance(paths, dict) or not all(isinstance(item, dict) for item in paths.values()):
        raise CommonAssetsError("Travel API OpenAPI paths must be an object of path items.")

    operations = {
        (method, path): operation.get("operationId") if isinstance(operation, dict) else None
        for path, item in paths.items()
        for method, operation in item.items()
        if method in HTTP_METHODS
    }
    if operations != EXPECTED_OPERATIONS or set(paths) != {path for _, path in EXPECTED_OPERATIONS}:
        raise CommonAssetsError(
            "Travel API OpenAPI must contain exactly getHealth, getPerDiem, "
            "createTripEstimate and createPreapproval at their checked-in paths/methods."
        )
    components = spec.get("components", {})
    if not isinstance(components, dict):
        raise CommonAssetsError("Travel API OpenAPI components must be an object.")
    if spec.get("security") or any(
        paths[path][method].get("security") for method, path in operations
    ):
        raise CommonAssetsError("The shared Travel API contract must remain Anonymous.")
    if components.get("securitySchemes"):
        raise CommonAssetsError("The shared Travel API contract must remain Anonymous.")

    document = deepcopy(spec)
    servers = document.setdefault("servers", [{}])
    if (
        not isinstance(servers, list)
        or len(servers) != 1
        or not isinstance(servers[0], dict)
        or set(servers[0]) - {"url"}
    ):
        raise CommonAssetsError("Travel API OpenAPI must have only one plain server URL.")
    servers[0]["url"] = OPENAPI_SERVER_PLACEHOLDER
    try:
        return (
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CommonAssetsError(f"Travel API OpenAPI is not valid JSON: {exc}") from exc


def build_common_assets(
    *, skills_dir: Path = SKILLS_DIR, api_dir: Path = TRAVEL_API_DIR
) -> dict[Path, bytes]:
    """Validate every source before returning any files to the write/check adapter."""
    files = {
        Path("openapi") / "travel-ops.openapi.json": build_openapi_asset(
            load_travel_api_schema(api_dir)
        ),
    }
    for name in SKILL_NAMES:
        source = skills_dir / name / "SKILL.md"
        try:
            content = source.read_bytes().decode("utf-8")
        except (OSError, UnicodeError) as exc:
            raise CommonAssetsError(f"Cannot read UTF-8 Skill source {source}: {exc}") from exc
        files[Path("skills") / f"{name}.zip"] = build_skill_archive(name, content)
    return files

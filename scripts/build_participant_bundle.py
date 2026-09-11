#!/usr/bin/env python3
"""Build the deterministic Azure Portal workshop participant bundle."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from collections.abc import Iterable, Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prepare_toolbox_assets import SKILL_NAMES, SKILLS_DIR, build_skill_archive

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / ".workshop" / "download" / "foundry-workshop-files.zip"
BUNDLE_ROOT = "Microsoft-Foundry-Agent-Service-Handson"
ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)

INCLUDE_FILES = (
    "README.md",
    "README.en.md",
    "pyproject.toml",
    "scripts/__init__.py",
    "scripts/setup_azureml.py",
    "scripts/create_toolbox.py",
    "scripts/connect_toolbox.py",
    "scripts/deploy_hosted_agent.py",
    "scripts/delete_hosted_agent.py",
    "scripts/run_evaluation.py",
)
INCLUDE_DIRECTORIES = (
    "labs",
    "docs",
    "notebooks",
    "data",
    "scripts/lib",
    "src/hosted-agent",
    "src/travel-api",
    "tests/unit/hosted_agent",
    "tests/contract/hosted_agent",
)

FORBIDDEN_PARTS = frozenset(
    {
        ".azure",
        ".devcontainer",
        ".git",
        ".github",
        ".ipynb_checkpoints",
        ".pytest_cache",
        ".ruff_cache",
        ".terraform",
        ".venv",
        ".workshop",
        "__pycache__",
        "artifacts",
        "dist",
        "infra",
        "instructor",
        "logs",
    }
)
FORBIDDEN_SUFFIXES = (
    ".tfstate",
    ".tfplan",
    ".pyc",
)
FORBIDDEN_FILENAMES = frozenset(
    {
        ".env",
        "portal-config.json",
        "terraform.tfvars",
    }
)


class BundleError(RuntimeError):
    """The requested bundle would be incomplete or unsafe."""


def _is_forbidden(path: Path) -> bool:
    return (
        bool(FORBIDDEN_PARTS.intersection(path.parts))
        or any(part.endswith(".egg-info") for part in path.parts)
        or path.name in FORBIDDEN_FILENAMES
        or path.name.endswith(FORBIDDEN_SUFFIXES)
        or path.name.startswith(".env.")
        or ".tfstate." in path.name
    )


def collect_source_files(root: Path = REPO_ROOT) -> list[Path]:
    """Collect the explicit participant allowlist and reject unsafe paths."""
    files: set[Path] = set()
    for name in INCLUDE_FILES:
        path = root / name
        if path.is_symlink():
            raise BundleError(f"participant source must not be a symlink: {name}")
        if path.is_file():
            files.add(path)
    for directory in INCLUDE_DIRECTORIES:
        directory_path = root / directory
        if directory_path.is_symlink():
            raise BundleError(f"participant directory must not be a symlink: {directory}")
        if not directory_path.is_dir():
            continue
        for current, dirnames, filenames in os.walk(directory_path):
            current_path = Path(current)
            dirnames[:] = [
                name
                for name in dirnames
                if not _is_forbidden((current_path / name).relative_to(root))
            ]
            for name in dirnames:
                if (current_path / name).is_symlink():
                    raise BundleError(
                        f"participant directory must not be a symlink: "
                        f"{(current_path / name).relative_to(root)}"
                    )
            for filename in filenames:
                path = current_path / filename
                if not _is_forbidden(path.relative_to(root)):
                    if path.is_symlink():
                        raise BundleError(
                            f"participant source must not be a symlink: {path.relative_to(root)}"
                        )
                    files.add(path)

    selected = sorted(files, key=lambda path: path.relative_to(root).as_posix())

    required = {
        "README.md",
        "notebooks/00-azureml-setup.ipynb",
        "notebooks/07-agent-framework-harness.ipynb",
        "notebooks/08-hosted-agent.ipynb",
        "scripts/setup_azureml.py",
        "scripts/lib/workshop_context.py",
        "scripts/deploy_hosted_agent.py",
        "scripts/delete_hosted_agent.py",
        "src/hosted-agent/main.py",
        "data/manifest.json",
        "tests/contract/hosted_agent/test_sequential_workflow.py",
        "tests/contract/hosted_agent/test_telemetry.py",
    }
    present = {path.relative_to(root).as_posix() for path in selected}
    missing = sorted(required - present)
    if missing:
        raise BundleError("participant bundle is missing required files: " + ", ".join(missing))
    return selected


def _skill_entries() -> dict[str, bytes]:
    entries: dict[str, bytes] = {}
    for name in SKILL_NAMES:
        content = (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
        entries[f"portal-assets/{name}.zip"] = build_skill_archive(name, content)
    return entries


def _context_entry(context_path: Path) -> bytes:
    try:
        context = json.loads(context_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleError(f"could not read canonical context {context_path}: {exc}") from exc
    if not isinstance(context, dict) or not isinstance(context.get("resource_outputs"), dict):
        raise BundleError("canonical context must contain resource_outputs")

    serialized = json.dumps(context, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    forbidden = re.compile(
        r'"[^"]*(?:secret|password|token|api[_-]?key|connection[_-]?string)[^"]*"\s*:',
        re.IGNORECASE,
    )
    if forbidden.search(serialized):
        raise BundleError("canonical context contains a forbidden secret-shaped field")
    if (
        context.get("schema_version") != "1.0"
        or context.get("provisioning_method") != "azure-custom-template"
        or context.get("setup_status") != "complete"
    ):
        raise BundleError("runtime bundle requires completed custom-template initialization")
    revision = context.get("source_revision")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise BundleError("canonical context must contain the published source_revision SHA")
    return serialized.encode("utf-8")


def _generated_portal_entries(portal_assets_dir: Path) -> dict[str, bytes]:
    required = (
        "travel-ops.openapi.json",
        "portal-values.json",
        "travel-estimation.zip",
        "preapproval-simulation.zip",
    )
    entries: dict[str, bytes] = {}
    for name in required:
        path = portal_assets_dir / name
        try:
            entries[f"portal-assets/{name}"] = path.read_bytes()
        except OSError as exc:
            raise BundleError(f"required Portal asset is missing: {path}") from exc
        if not entries[f"portal-assets/{name}"]:
            raise BundleError(f"required Portal asset is empty: {path}")
    return entries


def build_entries(
    files: Iterable[Path],
    *,
    root: Path = REPO_ROOT,
    context_path: Path | None = None,
    portal_assets_dir: Path | None = None,
) -> dict[str, bytes]:
    context_bytes = _context_entry(context_path) if context_path is not None else None
    if context_bytes is not None and portal_assets_dir is None:
        raise BundleError("runtime bundle requires generated live Portal assets")
    entries = {path.relative_to(root).as_posix(): path.read_bytes() for path in files}
    entries.update(
        _generated_portal_entries(portal_assets_dir)
        if portal_assets_dir is not None
        else _skill_entries()
    )
    if context_bytes is not None:
        entries[".workshop/context.json"] = context_bytes

    manifest_files = {
        name: {
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
        for name, content in sorted(entries.items())
    }
    manifest = {
        "schema_version": 1,
        "bundle": "microsoft-foundry-agent-service-handson-custom-template",
        "source_revision": (
            json.loads(context_bytes)["source_revision"] if context_bytes is not None else None
        ),
        "files": manifest_files,
    }
    entries["bundle-manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return entries


def build_zip_bytes(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(entries.items()):
            info = zipfile.ZipInfo(f"{BUNDLE_ROOT}/{name}", date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    return buffer.getvalue()


def build_bundle(
    root: Path = REPO_ROOT,
    *,
    context_path: Path | None = None,
    portal_assets_dir: Path | None = None,
) -> bytes:
    return build_zip_bytes(
        build_entries(
            collect_source_files(root),
            root=root,
            context_path=context_path,
            portal_assets_dir=portal_assets_dir,
        )
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--portal-assets-dir", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        expected = build_bundle(
            context_path=args.context,
            portal_assets_dir=args.portal_assets_dir,
        )
    except (BundleError, OSError) as exc:
        print(f"build_participant_bundle.py: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(expected)
    print(f"Participant bundle written: {args.output}")
    print(f"SHA-256: {hashlib.sha256(expected).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

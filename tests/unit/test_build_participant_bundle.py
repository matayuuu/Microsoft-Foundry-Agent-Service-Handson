from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest

from scripts import build_participant_bundle as bundle


@pytest.fixture(scope="module")
def bundle_entries() -> dict[str, bytes]:
    return _read_bundle(bundle.build_bundle())


def _read_bundle(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        prefix = f"{bundle.BUNDLE_ROOT}/"
        return {
            name.removeprefix(prefix): archive.read(name)
            for name in archive.namelist()
            if name.startswith(prefix)
        }


def test_bundle_is_deterministic_and_contains_required_participant_files() -> None:
    first = bundle.build_bundle()
    second = bundle.build_bundle()

    assert first == second
    entries = _read_bundle(first)
    for required in (
        "README.md",
        "notebooks/00-azureml-setup.ipynb",
        "notebooks/07-agent-framework-harness.ipynb",
        "notebooks/08-hosted-agent.ipynb",
        "portal-assets/travel-estimation.zip",
        "portal-assets/preapproval-simulation.zip",
        "scripts/setup_azureml.py",
        "src/hosted-agent/main.py",
        "bundle-manifest.json",
    ):
        assert required in entries


def test_bundle_manifest_covers_every_payload_with_matching_hash(
    bundle_entries: dict[str, bytes],
) -> None:
    entries = dict(bundle_entries)
    manifest = json.loads(entries.pop("bundle-manifest.json"))

    assert manifest["source_branch"] == "main"
    assert set(manifest["files"]) == set(entries)
    for name, content in entries.items():
        assert manifest["files"][name] == {
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }


def test_bundle_excludes_state_credentials_and_infrastructure(
    bundle_entries: dict[str, bytes],
) -> None:
    for name in bundle_entries:
        path = Path(name)
        assert not bundle.FORBIDDEN_PARTS.intersection(path.parts)
        assert path.name not in bundle.FORBIDDEN_FILENAMES
        assert not path.name.endswith(bundle.FORBIDDEN_SUFFIXES)


def test_runtime_bundle_includes_only_non_secret_context_and_live_assets(
    tmp_path: Path,
) -> None:
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "resource_outputs": {
                    "foundry_project_endpoint": {
                        "value": "https://example.invalid/api/projects/contoso-travel"
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    assets = tmp_path / "toolbox"
    assets.mkdir()
    for name, content in {
        "travel-ops.openapi.json": b"{}",
        "portal-values.json": b"{}",
        "travel-estimation.zip": b"travel",
        "preapproval-simulation.zip": b"approval",
    }.items():
        (assets / name).write_bytes(content)

    entries = _read_bundle(bundle.build_bundle(context_path=context, portal_assets_dir=assets))

    assert ".workshop/context.json" in entries
    assert entries["portal-assets/travel-ops.openapi.json"] == b"{}"
    assert b"secret" not in entries[".workshop/context.json"].lower()


def test_runtime_bundle_rejects_secret_shaped_context(tmp_path: Path) -> None:
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "resource_outputs": {"project": {"value": "x"}},
                "api_key": "must-not-ship",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(bundle.BundleError, match="secret-shaped"):
        bundle.build_bundle(context_path=context)


@pytest.mark.parametrize(
    "name",
    ("travel-estimation", "preapproval-simulation"),
)
def test_bundled_skill_archive_has_skill_at_root(
    name: str,
    bundle_entries: dict[str, bytes],
) -> None:
    with zipfile.ZipFile(io.BytesIO(bundle_entries[f"portal-assets/{name}.zip"])) as archive:
        assert archive.namelist() == ["SKILL.md"]
        assert f"name: {name}" in archive.read("SKILL.md").decode("utf-8")

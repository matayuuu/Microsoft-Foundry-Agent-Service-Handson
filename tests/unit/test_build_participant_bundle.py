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
        "scripts/deploy_hosted_agent.py",
        "scripts/delete_hosted_agent.py",
        "tests/contract/hosted_agent/test_sequential_workflow.py",
        "tests/contract/hosted_agent/test_telemetry.py",
        "src/hosted-agent/main.py",
        "bundle-manifest.json",
    ):
        assert required in entries


def test_bundle_manifest_covers_every_payload_with_matching_hash(
    bundle_entries: dict[str, bytes],
) -> None:
    entries = dict(bundle_entries)
    manifest = json.loads(entries.pop("bundle-manifest.json"))

    assert manifest["source_revision"] is None
    assert "source_branch" not in manifest
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


def test_bundle_contains_runtime_scripts_not_provisioning_implementation(
    bundle_entries: dict[str, bytes],
) -> None:
    for name in (
        "scripts/setup.sh",
        "scripts/destroy.sh",
        "scripts/setup-cloud-shell.sh",
        "scripts/activate-cloud-shell.sh",
        "scripts/cloud-shell-common.sh",
        "scripts/cloud_shell_environment.py",
        "scripts/bootstrap-custom-template.sh",
        "scripts/bootstrap_custom_template.py",
        "scripts/build_participant_bundle.py",
        "scripts/prepare_participant_download.py",
        "scripts/admin-preflight.sh",
        "tests/contract/test_custom_template_contract.py",
        "tests/unit/test_bootstrap_custom_template.py",
    ):
        assert name not in bundle_entries


def test_runtime_bundle_includes_only_non_secret_context_and_live_assets(
    tmp_path: Path,
) -> None:
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "provisioning_method": "azure-custom-template",
                "setup_status": "complete",
                "source_revision": "a" * 40,
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
    assert json.loads(entries["bundle-manifest.json"])["source_revision"] == "a" * 40


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("setup_status", "infrastructure-ready", "completed"),
        ("provisioning_method", "cloud-shell-terraform", "completed"),
        ("schema_version", "2.0", "completed"),
        ("source_revision", "main", "source_revision"),
        ("source_revision", "", "source_revision"),
        ("source_revision", 123, "source_revision"),
    ],
)
def test_runtime_bundle_rejects_incomplete_or_unpinned_context(
    tmp_path: Path, key: str, value: object, message: str
) -> None:
    context = {
        "schema_version": "1.0",
        "provisioning_method": "azure-custom-template",
        "setup_status": "complete",
        "source_revision": "a" * 40,
        "resource_outputs": {"project": {"value": "example"}},
        key: value,
    }
    path = tmp_path / "context.json"
    path.write_text(json.dumps(context), encoding="utf-8")

    with pytest.raises(bundle.BundleError, match=message):
        bundle.build_entries([], root=tmp_path, context_path=path)


def test_runtime_bundle_does_not_fall_back_to_static_assets(tmp_path: Path) -> None:
    context = tmp_path / "context.json"
    context.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "provisioning_method": "azure-custom-template",
                "setup_status": "complete",
                "source_revision": "b" * 40,
                "resource_outputs": {"project": {"value": "example"}},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(bundle.BundleError, match="live Portal assets"):
        bundle.build_entries([], root=tmp_path, context_path=context)


def test_empty_generated_portal_asset_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "travel-ops.openapi.json").write_bytes(b"")
    with pytest.raises(bundle.BundleError, match="empty"):
        bundle._generated_portal_entries(tmp_path)


@pytest.mark.parametrize(
    "name", (".env.local", "state.tfstate.backup", ".azure/token.json", "logs/run.log")
)
def test_local_credentials_and_state_backups_are_excluded(name: str) -> None:
    assert bundle._is_forbidden(Path(name))


def test_symlink_source_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "outside.txt"
    target.write_text("not participant content", encoding="utf-8")
    link = tmp_path / "README.md"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("creating symlinks requires platform permissions")
    with pytest.raises(bundle.BundleError, match="symlink"):
        bundle.collect_source_files(tmp_path)


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

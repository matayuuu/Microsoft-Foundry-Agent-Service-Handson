from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
import yaml

from scripts import prepare_toolbox_assets as assets


def test_export_assets_packages_both_skills_and_only_portal_values(tmp_path: Path) -> None:
    spec = {
        "openapi": "3.1.0",
        "servers": [{"url": "https://travel.example.invalid"}],
        "paths": {},
    }
    paths = assets.export_assets(
        spec=spec, endpoint="https://project.example.invalid", output_dir=tmp_path
    )

    assert {path.name for path in paths} == {
        "travel-ops.openapi.json",
        "portal-values.json",
        "travel-estimation.zip",
        "preapproval-simulation.zip",
    }
    assert json.loads((tmp_path / "travel-ops.openapi.json").read_text()) == spec
    values = json.loads((tmp_path / "portal-values.json").read_text())
    assert values["toolbox_mcp_endpoint"] == (
        "https://project.example.invalid/toolboxes/contoso-travel-toolbox/mcp?api-version=v1"
    )
    assert values["skills"] == list(assets.SKILL_NAMES)
    assert set(values) == {
        "toolbox_name",
        "tool_name",
        "tool_authentication",
        "toolbox_mcp_endpoint",
        "toolbox_audience",
        "skills",
    }
    before = {path.name: path.read_bytes() for path in paths}
    assets.export_assets(spec=spec, endpoint="https://project.example.invalid", output_dir=tmp_path)
    assert {path.name: path.read_bytes() for path in paths} == before


@pytest.mark.parametrize("name", assets.SKILL_NAMES)
def test_skill_archive_contains_valid_root_manifest(name: str) -> None:
    source = (assets.SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")
    with zipfile.ZipFile(io.BytesIO(assets.build_skill_archive(name, source))) as archive:
        assert archive.namelist() == ["SKILL.md"]
        assert archive.read("SKILL.md").decode("utf-8") == source

    front_matter = source.split("---", 2)[1]
    metadata = yaml.safe_load(front_matter)
    assert f"name: {name}\n" in front_matter
    assert metadata["name"] == name
    assert len(metadata["description"]) <= 1024
    assert "実際の予約・承認ではありません" in source
    assert "createPreapproval" in source


@pytest.mark.parametrize(
    "source",
    [
        "no front matter",
        "---\nname: different\ndescription: Example\n---\nBody",
        "---\nname: travel-estimation\n---\nBody",
        "---\nname: travel-estimation\ndescription: Example\n---\n",
        "---\nname: [invalid\n---\nBody",
    ],
)
def test_archive_rejects_invalid_skill(source: str) -> None:
    with pytest.raises(assets.WorkshopContextError):
        assets.build_skill_archive("travel-estimation", source)


def test_main_fetches_live_openapi_without_creating_a_foundry_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    context_path = tmp_path / "context.json"
    context_path.write_text(
        json.dumps(
            {
                "terraform_outputs": {
                    "foundry_project_endpoint": {"value": "https://project.example.invalid"},
                    "travel_api_fqdn": {"value": "travel.example.invalid"},
                }
            }
        ),
        encoding="utf-8",
    )
    calls = []

    def fetch(base_url: str, path: str) -> dict:
        calls.append((base_url, path))
        return {"openapi": "3.1.0", "servers": [{"url": base_url}], "paths": {}}

    monkeypatch.setattr(assets, "fetch_openapi_spec", fetch)
    assert (
        assets.main(["--context", str(context_path), "--output-dir", str(tmp_path / "assets")]) == 0
    )
    assert calls == [("https://travel.example.invalid", "/openapi.json")]


def test_main_reports_missing_context(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert assets.main(["--context", str(tmp_path / "missing.json")]) == 2
    assert "context file not found" in capsys.readouterr().err

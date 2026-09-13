from __future__ import annotations

import io
import json
import socket
import subprocess
import sys
import zipfile
from copy import deepcopy
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from jsonschema import Draft202012Validator

from scripts import build_common_assets as cli
from scripts.lib import common_assets as assets

PUBLIC_PATHS = {
    Path("skills") / "travel-estimation.zip",
    Path("skills") / "preapproval-simulation.zip",
    Path("openapi") / "travel-ops.openapi.json",
}


@pytest.fixture
def api_schema(monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.syspath_prepend(str(assets.TRAVEL_API_DIR))
    module = import_module("travel_api.main")
    assert Path(module.__file__).resolve() == assets.TRAVEL_API_DIR / "travel_api" / "main.py"
    return deepcopy(module.app.openapi())


@pytest.fixture
def skill_sources(tmp_path: Path) -> Path:
    sources = tmp_path / "sources"
    for name in assets.SKILL_NAMES:
        source = sources / name / "SKILL.md"
        source.parent.mkdir(parents=True)
        source.write_bytes((assets.SKILLS_DIR / name / "SKILL.md").read_bytes())
    return sources


def snapshot(directory: Path) -> dict[Path, tuple[bytes, int]]:
    return {
        path.relative_to(directory): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in directory.rglob("*")
        if path.is_file()
    }


def test_checked_in_assets_exactly_match_sources() -> None:
    generated = assets.build_common_assets()
    assert set(generated) == PUBLIC_PATHS
    for relative, content in generated.items():
        assert (assets.DEFAULT_OUTPUT_DIR / relative).read_bytes() == content, (
            f"{relative} has drifted; run python -B -m scripts.build_common_assets"
        )


@pytest.mark.parametrize("name", assets.SKILL_NAMES)
def test_skill_archive_is_reproducible_and_preserves_source_bytes(name: str) -> None:
    source = (assets.SKILLS_DIR / name / "SKILL.md").read_bytes()
    content = source.decode("utf-8")
    archive_bytes = assets.build_skill_archive(name, content)
    assert assets.build_skill_archive(name, content) == archive_bytes

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        assert archive.namelist() == ["SKILL.md"]
        assert archive.read("SKILL.md") == source
        assert archive.testzip() is None
        entry = archive.getinfo("SKILL.md")
        assert entry.date_time == (2026, 1, 1, 0, 0, 0)
        assert entry.create_system == 3
        assert entry.external_attr == 0o100644 << 16
        assert entry.compress_type == zipfile.ZIP_DEFLATED

    metadata = yaml.safe_load(content.split("---", 2)[1])
    assert metadata["name"] == name
    assert 1 <= len(metadata["description"]) <= 1024
    assert "実際の予約・承認ではありません" in content
    assert "createPreapproval" in content


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_skill_archive_preserves_line_endings_and_inline_delimiters(newline: str) -> None:
    source = newline.join(
        [
            "---",
            "name: travel-estimation",
            "description: Example---description",
            "---",
            "# Instructions",
            "Do not invent prices.",
            "---",
            "",
        ]
    )
    with zipfile.ZipFile(io.BytesIO(assets.build_skill_archive("travel-estimation", source))) as z:
        assert z.read("SKILL.md") == source.encode("utf-8")


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("no front matter", "front matter and instructions"),
        ("---\nname: travel-estimation\n---\n", "front matter and instructions"),
        ("---\nname: [invalid\n---\nBody", "invalid SKILL.md front matter"),
        ("---\n- name: travel-estimation\n---\nBody", "matching name"),
        ("---\nname: different\ndescription: Example\n---\nBody", "matching name"),
        ("---\nname: travel-estimation\n---\nBody", "description"),
        ("---\nname: travel-estimation\ndescription: false\n---\nBody", "description"),
        ('---\nname: travel-estimation\ndescription: " "\n---\nBody', "description"),
        (
            "---\nname: travel-estimation\ndescription: " + "x" * 1025 + "\n---\nBody",
            "1-1024 characters",
        ),
        ("---\n!!python/object:example.Unsafe {}\n---\nBody", "invalid SKILL.md front matter"),
    ],
)
def test_skill_archive_rejects_invalid_front_matter(source: str, message: str) -> None:
    with pytest.raises(assets.CommonAssetsError, match=message):
        assets.build_skill_archive("travel-estimation", source)


def test_openapi_matches_actual_app_contract_with_only_one_url_added(api_schema: dict) -> None:
    original = deepcopy(api_schema)
    expected = deepcopy(api_schema)
    expected["servers"] = [{"url": "https://replace-with-your-travel-api.example.invalid"}]
    encoded = assets.build_openapi_asset(api_schema)
    document = json.loads(encoded)

    assert document == expected
    assert api_schema == original
    assert document["openapi"] == "3.1.0"
    assert encoded.endswith(b"\n")
    assert {
        (method, path): operation["operationId"]
        for path, item in document["paths"].items()
        for method, operation in item.items()
    } == {
        ("get", "/health"): "getHealth",
        ("get", "/per-diem"): "getPerDiem",
        ("post", "/trip-estimates"): "createTripEstimate",
        ("post", "/preapprovals"): "createPreapproval",
    }
    assert "security" not in document
    assert "securitySchemes" not in document["components"]
    for component in document["components"]["schemas"].values():
        Draft202012Validator.check_schema(component)


def test_openapi_replaces_an_existing_url_without_mutating_source(api_schema: dict) -> None:
    api_schema["servers"] = [{"url": "https://synthetic-api.example.invalid"}]
    original = deepcopy(api_schema)
    document = json.loads(assets.build_openapi_asset(api_schema))
    assert document["servers"] == [{"url": assets.OPENAPI_SERVER_PLACEHOLDER}]
    document["servers"] = original["servers"]
    assert document == original == api_schema


def test_generation_never_reads_runtime_values_or_calls_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variable in (
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_CLIENT_SECRET",
        "WORKSHOP_CONTEXT_JSON",
        "WORKSHOP_SOURCE_BASE",
        "AZURE_AI_PROJECT_ENDPOINT",
    ):
        monkeypatch.setenv(variable, "synthetic-private-sentinel")

    def reject_network(*_args, **_kwargs):
        pytest.fail("Common asset generation must not connect to a deployed service.")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    files = assets.build_common_assets()
    assert set(files) == PUBLIC_PATHS
    for relative, content in files.items():
        if relative.suffix == ".zip":
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                content = archive.read("SKILL.md")
        text = content.decode("utf-8")
        for forbidden in (
            "synthetic-private-sentinel",
            "portal-values.json",
            "resource_outputs",
            "subscription_id",
            "access_token",
            ".azure.com",
            ".azurecontainerapps.io",
            ".blob.core.windows.net",
        ):
            assert forbidden not in text
    document = json.loads(files[Path("openapi") / "travel-ops.openapi.json"])
    assert document["servers"] == [{"url": assets.OPENAPI_SERVER_PLACEHOLDER}]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("openapi", "3.0.3", "OpenAPI 3.1"),
        ("paths", None, "paths must be an object"),
        ("paths", {"/health": None}, "paths must be an object"),
        ("components", [], "components must be an object"),
        ("security", [{"api_key": []}], "Anonymous"),
        ("servers", [], "one plain server URL"),
        ("servers", None, "one plain server URL"),
        ("servers", [{"url": "one"}, {"url": "two"}], "one plain server URL"),
        ("servers", [{"url": "one", "variables": {}}], "one plain server URL"),
    ],
)
def test_openapi_rejects_invalid_or_unsafe_contract(
    api_schema: dict, field: str, value: object, message: str
) -> None:
    api_schema[field] = value
    with pytest.raises(assets.CommonAssetsError, match=message):
        assets.build_openapi_asset(api_schema)


@pytest.mark.parametrize("change", ["missing", "extra", "wrong-id", "wrong-method", "invalid"])
def test_openapi_rejects_operation_drift(api_schema: dict, change: str) -> None:
    paths = api_schema["paths"]
    if change == "missing":
        del paths["/health"]
    elif change == "extra":
        paths["/health"]["delete"] = {"operationId": "deleteHealth"}
    elif change == "wrong-id":
        paths["/health"]["get"]["operationId"] = "differentHealth"
    elif change == "wrong-method":
        paths["/health"]["post"] = paths["/health"].pop("get")
    else:
        paths["/health"]["get"] = None
    with pytest.raises(assets.CommonAssetsError, match="exactly getHealth"):
        assets.build_openapi_asset(api_schema)


@pytest.mark.parametrize("location", ["operation", "components"])
def test_openapi_rejects_authentication_changes(api_schema: dict, location: str) -> None:
    if location == "operation":
        api_schema["paths"]["/health"]["get"]["security"] = [{"token": []}]
    else:
        api_schema["components"]["securitySchemes"] = {"token": {"type": "http"}}
    with pytest.raises(assets.CommonAssetsError, match="Anonymous"):
        assets.build_openapi_asset(api_schema)


@pytest.mark.parametrize("value", [float("nan"), {"not", "JSON"}])
def test_openapi_rejects_invalid_json_values(api_schema: dict, value: object) -> None:
    api_schema["info"]["x-invalid"] = value
    with pytest.raises(assets.CommonAssetsError, match="not valid JSON"):
        assets.build_openapi_asset(api_schema)


def test_local_schema_loading_preserves_import_path(api_schema: dict) -> None:
    before = sys.path.copy()
    assert assets.load_travel_api_schema() == api_schema
    assert sys.path == before


def test_missing_api_source_has_a_meaningful_error(tmp_path: Path) -> None:
    with pytest.raises(assets.CommonAssetsError, match="Travel API source not found") as error:
        assets.load_travel_api_schema(tmp_path)
    assert str(tmp_path / "travel_api" / "main.py") in str(error.value)


def test_cached_api_from_another_location_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        assets, "import_module", lambda _: SimpleNamespace(__file__=str(tmp_path / "main.py"))
    )
    with pytest.raises(assets.CommonAssetsError, match="not checked-in source"):
        assets.load_travel_api_schema()


@pytest.mark.parametrize(
    ("failure", "message"),
    [
        (ModuleNotFoundError("fastapi"), "management Python 3.12"),
        (SyntaxError("broken API source"), "Cannot load Travel API source"),
        (OSError("unreadable API source"), "Cannot load Travel API source"),
    ],
)
def test_api_import_failure_is_actionable_and_restores_import_path(
    monkeypatch: pytest.MonkeyPatch, failure: Exception, message: str
) -> None:
    def fail_import(_name):
        raise failure

    monkeypatch.setattr(assets, "import_module", fail_import)
    before = sys.path.copy()
    with pytest.raises(assets.CommonAssetsError, match=message):
        assets.load_travel_api_schema()
    assert sys.path == before


def test_invalid_schema_factory_has_a_meaningful_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def invalid_schema():
        raise ValueError("broken schema")

    module = SimpleNamespace(
        __file__=str(assets.TRAVEL_API_DIR / "travel_api" / "main.py"),
        app=SimpleNamespace(openapi=invalid_schema),
    )
    monkeypatch.setattr(assets, "import_module", lambda _: module)
    with pytest.raises(assets.CommonAssetsError, match=r"Cannot generate OpenAPI.*broken schema"):
        assets.load_travel_api_schema()


@pytest.mark.parametrize("failure", ["missing", "invalid-utf8", "invalid-front-matter"])
def test_invalid_skill_source_fails_before_any_output_is_written(
    monkeypatch: pytest.MonkeyPatch,
    skill_sources: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    failure: str,
) -> None:
    source = skill_sources / "preapproval-simulation" / "SKILL.md"
    if failure == "missing":
        source.unlink()
    elif failure == "invalid-utf8":
        source.write_bytes(b"\xff")
    else:
        source.write_text("not a Skill", encoding="utf-8")
    monkeypatch.setattr(
        cli, "build_common_assets", lambda: assets.build_common_assets(skills_dir=skill_sources)
    )
    output = tmp_path / "output"
    assert cli.main(["--output-dir", str(output)]) == 2
    error = capsys.readouterr().err
    assert "preapproval-simulation" in error
    assert "SKILL.md" in error
    assert not output.exists()


def test_cli_generation_is_reproducible_and_check_is_read_only(tmp_path: Path) -> None:
    assert cli.main(["--output-dir", str(tmp_path)]) == 0
    first = {path: content for path, (content, _) in snapshot(tmp_path).items()}
    assert first == assets.build_common_assets()
    assert cli.main(["--output-dir", str(tmp_path)]) == 0
    before_check = snapshot(tmp_path)
    assert {path: content for path, (content, _) in before_check.items()} == first
    assert cli.main(["--check", "--output-dir", str(tmp_path)]) == 0
    assert snapshot(tmp_path) == before_check


@pytest.mark.parametrize("relative", sorted(PUBLIC_PATHS))
def test_check_detects_drift_without_repairing_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], relative: Path
) -> None:
    assert cli.main(["--output-dir", str(tmp_path)]) == 0
    capsys.readouterr()
    (tmp_path / relative).write_bytes(b"drift")
    before = snapshot(tmp_path)
    assert cli.main(["--check", "--output-dir", str(tmp_path)]) == 1
    error = capsys.readouterr().err
    assert f"Out-of-date asset: {tmp_path / relative}" in error
    assert "Regenerate" in error
    assert snapshot(tmp_path) == before


def test_check_reports_missing_files_without_creating_directories(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "missing" / "assets"
    assert cli.main(["--check", "--output-dir", str(output)]) == 1
    assert capsys.readouterr().err.count("Missing asset:") == 3
    assert not output.parent.exists()


def test_write_failure_is_reported_without_overwriting_existing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "blocked"
    output.write_bytes(b"keep me")
    assert cli.main(["--output-dir", str(output)]) == 2
    assert "build_common_assets.py:" in capsys.readouterr().err
    assert output.read_bytes() == b"keep me"


def test_standalone_cli_checks_default_paths_from_another_directory(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            str(assets.REPO_ROOT / "scripts" / "build_common_assets.py"),
            "--check",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "All 3 common assets match" in result.stdout
    assert not list(tmp_path.iterdir())


def test_gitignore_only_allows_the_two_shared_skill_zips() -> None:
    ignored = {
        "unrelated.zip",
        "assets/unrelated.zip",
        "assets/skills/unrelated.zip",
        "other/assets/skills/travel-estimation.zip",
        "artifacts/hosted-source.zip",
        ".workshop/context.json",
        ".workshop/portal-values.json",
        ".azure/credentials.json",
        ".env",
        ".env.local",
        "portal-config.json",
        "private.tfstate",
    }
    allowed = {f"assets/{relative.as_posix()}" for relative in PUBLIC_PATHS} | {".env.example"}
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--stdin", "-z"],
        input=("\0".join(sorted(ignored | allowed)) + "\0").encode("utf-8"),
        cwd=assets.REPO_ROOT,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert set(result.stdout.decode("utf-8").rstrip("\0").split("\0")) == ignored

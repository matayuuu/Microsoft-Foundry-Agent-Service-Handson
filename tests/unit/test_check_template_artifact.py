from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import check_template_artifact as checker


def test_comparison_uses_json_content_without_rewriting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact = tmp_path / "azuredeploy.json"
    original = '{ "resources": [], "contentVersion": "1.0.0.0" }\n'
    artifact.write_text(original, encoding="utf-8")
    monkeypatch.setattr(checker, "compile_template", lambda _: json.loads(original))

    checker.check_artifact(tmp_path / "main.bicep", artifact)

    assert artifact.read_text(encoding="utf-8") == original


def test_stale_artifact_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = tmp_path / "azuredeploy.json"
    artifact.write_text('{"resources": []}', encoding="utf-8")
    monkeypatch.setattr(checker, "compile_template", lambda _: {"resources": [{"name": "new"}]})

    assert checker.main(["--artifact", str(artifact)]) == 2


def test_compile_failure_is_not_an_empty_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(checker.shutil, "which", lambda _: "az")
    monkeypatch.setattr(
        checker.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="invalid Bicep source"
        ),
    )
    with pytest.raises(checker.TemplateArtifactError, match="invalid Bicep source"):
        checker.compile_template(tmp_path / "main.bicep")


def test_missing_compiler_is_actionable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(checker.shutil, "which", lambda _: None)
    with pytest.raises(checker.TemplateArtifactError, match="Bicep compiler"):
        checker.compile_template(tmp_path / "main.bicep")


def test_template_root_must_be_an_object() -> None:
    with pytest.raises(checker.TemplateArtifactError, match="JSON object"):
        checker.parse_template("[]")

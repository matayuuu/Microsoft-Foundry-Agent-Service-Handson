"""Exercise the embedded, stdlib-only Deployment Scripts runtime without network/login."""

from __future__ import annotations

import io
import json
import ssl
import subprocess
import tarfile
import tempfile
import types
import urllib.error
from pathlib import Path
from types import SimpleNamespace

import pytest

SHELL = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap-custom-template.sh"
REVISION = "a1b2c3d4" * 5
ARCHIVE_ROOT = f"Microsoft-Foundry-Agent-Service-Handson-{REVISION}"


def test_embedded_shell_is_utf8_lf_without_a_bom() -> None:
    content = SHELL.read_bytes()
    assert content.startswith(b"#!/usr/bin/env bash\n")
    assert b"\r" not in content
    assert content.endswith(b"\n")
    content.decode("utf-8")


@pytest.fixture
def runtime() -> types.ModuleType:
    source = SHELL.read_bytes().decode("utf-8").split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    module = types.ModuleType("workshop_shell_runtime")
    exec(compile(source, str(SHELL), "exec"), module.__dict__)
    return module


def environment(root: Path) -> dict[str, str]:
    return {
        "WORKSHOP_SOURCE_REVISION": REVISION,
        "WORKSHOP_CONTEXT_JSON": json.dumps(
            {
                "source_revision": REVISION,
                "source_base": (
                    "https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson"
                    f"/blob/{REVISION}"
                ),
            }
        ),
        "WORKSHOP_ARTIFACT_CONTAINER": "workshop-files",
        "AZ_SCRIPTS_OUTPUT_PATH": str(root / "deployment-output.json"),
    }


def archive_file(path: Path, entries: list[tuple[tarfile.TarInfo, bytes]]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for entry, content in entries:
            archive.addfile(entry, io.BytesIO(content) if entry.isfile() else None)


def member(name: str, content: bytes = b"source") -> tuple[tarfile.TarInfo, bytes]:
    entry = tarfile.TarInfo(name)
    entry.size = len(content)
    return entry, content


def valid_entries() -> list[tuple[tarfile.TarInfo, bytes]]:
    return [
        member(f"{ARCHIVE_ROOT}/pyproject.toml", b"[project]\nname='fixture'"),
        member(f"{ARCHIVE_ROOT}/scripts/bootstrap_custom_template.py", b"print('fixture')"),
    ]


def test_archive_extracts_only_the_pinned_repository_root(
    runtime: types.ModuleType,
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.tar.gz"
    archive_file(path, valid_entries())
    root = runtime.extract_source(path, tmp_path, REVISION)
    assert root == tmp_path / ARCHIVE_ROOT
    assert (root / "pyproject.toml").read_bytes() == b"[project]\nname='fixture'"


@pytest.mark.parametrize(
    "name",
    [
        "../outside",
        "/outside",
        f"{ARCHIVE_ROOT}/../../outside",
        f"{ARCHIVE_ROOT}\\..\\outside",
        f"{ARCHIVE_ROOT}/C:/outside",
        f"other-repository-{REVISION}/file",
    ],
)
def test_archive_rejects_traversal_and_unexpected_roots_before_extraction(
    runtime: types.ModuleType,
    tmp_path: Path,
    name: str,
) -> None:
    path = tmp_path / "source.tar.gz"
    archive_file(path, [*valid_entries(), member(name)])
    with pytest.raises(RuntimeError, match="source extraction"):
        runtime.extract_source(path, tmp_path, REVISION)
    assert not (tmp_path / ARCHIVE_ROOT).exists()
    assert not (tmp_path / "outside").exists()


@pytest.mark.parametrize(
    "kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE]
)
def test_archive_rejects_links_and_special_files(
    runtime: types.ModuleType,
    tmp_path: Path,
    kind: bytes,
) -> None:
    path = tmp_path / "source.tar.gz"
    entry = tarfile.TarInfo(f"{ARCHIVE_ROOT}/unsafe")
    entry.type = kind
    entry.linkname = "../../outside"
    archive_file(path, [*valid_entries(), (entry, b"")])
    with pytest.raises(RuntimeError, match="source extraction"):
        runtime.extract_source(path, tmp_path, REVISION)


def test_archive_rejects_duplicate_entries_and_expansion_limit(
    runtime: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "source.tar.gz"
    archive_file(path, [*valid_entries(), valid_entries()[0]])
    with pytest.raises(RuntimeError, match="duplicate"):
        runtime.extract_source(path, tmp_path, REVISION)
    archive_file(path, valid_entries())
    monkeypatch.setattr(runtime, "MAX_EXTRACTED_BYTES", 1)
    with pytest.raises(RuntimeError, match="limits"):
        runtime.extract_source(path, tmp_path, REVISION)


@pytest.mark.parametrize(
    ("variable", "value"),
    [
        ("WORKSHOP_SOURCE_REVISION", "main"),
        ("WORKSHOP_SOURCE_REVISION", "A" * 40),
        ("WORKSHOP_SOURCE_REVISION", "a" * 39),
        ("WORKSHOP_SOURCE_REVISION", "a" * 41),
        ("WORKSHOP_ARTIFACT_CONTAINER", "public-files"),
        ("WORKSHOP_CONTEXT_JSON", "null"),
        ("AZ_SCRIPTS_OUTPUT_PATH", "relative-output.json"),
    ],
)
def test_wrapper_checks_environment_before_source_execution(
    runtime: types.ModuleType,
    tmp_path: Path,
    variable: str,
    value: str,
) -> None:
    values = environment(tmp_path)
    values[variable] = value
    with pytest.raises(RuntimeError, match="inputs"):
        runtime.validate_environment(values)


def test_wrapper_requires_matching_context_revision_and_source(
    runtime: types.ModuleType,
    tmp_path: Path,
) -> None:
    values = environment(tmp_path)
    assert runtime.validate_environment(values) == REVISION
    context = json.loads(values["WORKSHOP_CONTEXT_JSON"])
    context["source_revision"] = "b" * 40
    values["WORKSHOP_CONTEXT_JSON"] = json.dumps(context)
    with pytest.raises(RuntimeError, match="must equal"):
        runtime.validate_environment(values)
    context["source_revision"] = REVISION
    context["source_base"] = "https://untrusted.invalid/source"
    values["WORKSHOP_CONTEXT_JSON"] = json.dumps(context)
    with pytest.raises(RuntimeError, match="fixed workshop repository"):
        runtime.validate_environment(values)


@pytest.mark.parametrize(
    ("http_status", "expected_attempts"), [(404, 1), (400, 1), (429, 5), (503, 5)]
)
def test_source_download_has_bounded_transient_only_retries(
    runtime: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    http_status: int,
    expected_attempts: int,
) -> None:
    urls: list[str] = []
    sleeps: list[float] = []

    def download(request: object, timeout: int) -> None:
        urls.append(request.full_url)
        assert timeout == 120
        raise urllib.error.HTTPError(request.full_url, http_status, "test", {}, None)

    monkeypatch.setattr(
        runtime.urllib.request, "build_opener", lambda *_: SimpleNamespace(open=download)
    )
    with pytest.raises(RuntimeError, match=f"HTTP {http_status}"):
        runtime.download_source(REVISION, tmp_path / "source.tar.gz", sleep=sleeps.append)
    assert len(urls) == expected_attempts
    assert len(sleeps) == expected_attempts - 1
    assert set(urls) == {
        "https://codeload.github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson"
        f"/tar.gz/{REVISION}"
    }


def test_wrapper_never_follows_an_arbitrary_archive_redirect(runtime: types.ModuleType) -> None:
    with pytest.raises(RuntimeError, match="unexpected archive redirect"):
        runtime.NoRedirect().redirect_request(
            None, None, 302, "redirect", {}, "https://untrusted.invalid/script"
        )


def test_tls_failure_is_not_retried(
    runtime: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    def download(*_: object, **__: object) -> None:
        raise urllib.error.URLError(ssl.SSLCertVerificationError("test certificate failure"))

    monkeypatch.setattr(
        runtime.urllib.request, "build_opener", lambda *_: SimpleNamespace(open=download)
    )
    with pytest.raises(RuntimeError, match="TLS certificate"):
        runtime.download_source(REVISION, tmp_path / "source.tar.gz", sleep=sleeps.append)
    assert sleeps == []


def prepare_runtime(
    runtime: types.ModuleType,
    root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(root)
    for name, value in environment(root).items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(runtime, "sys", SimpleNamespace(version_info=(3, 12), executable="python3"))
    monkeypatch.setattr(
        runtime, "importlib", SimpleNamespace(util=SimpleNamespace(find_spec=lambda _: object()))
    )

    def container_directory(*, prefix: str, dir: str) -> str:
        assert dir == "/tmp", "the Azure Files working directory must not host the venv"
        local_root = root / "container-local"
        local_root.mkdir(exist_ok=True)
        return tempfile.mkdtemp(prefix=prefix, dir=local_root)

    monkeypatch.setattr(runtime, "tempfile", SimpleNamespace(mkdtemp=container_directory))

    def download(_: str, path: Path) -> None:
        archive_file(path, valid_entries())

    monkeypatch.setattr(runtime, "download_source", download)


def test_runtime_installs_only_base_provisioning_dependencies_into_its_own_venv(
    runtime: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_runtime(runtime, tmp_path, monkeypatch)
    monkeypatch.setenv("PYTHONPATH", "must-not-contaminate-venv")
    monkeypatch.setenv("PYTHONHOME", "must-not-contaminate-venv")
    monkeypatch.setenv("AZURE_CONFIG_DIR", "keep-existing-auto-login")
    original_path = runtime.os.environ["PATH"]
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(runtime.subprocess, "run", run)
    assert runtime.main() == 0
    assert len(calls) == 3
    assert calls[0][0][:4] == ["python3", "-I", "-m", "venv"]
    virtual_environment = Path(calls[0][0][-1])
    assert virtual_environment.parent.parent == tmp_path / "container-local"
    assert calls[1][0] == [
        str(virtual_environment / "bin" / "python"),
        "-I",
        "-m",
        "pip",
        "--isolated",
        "--disable-pip-version-check",
        "install",
        "--no-input",
        "--no-cache-dir",
        ".",
    ]
    assert calls[2][0] == [
        str(virtual_environment / "bin" / "python"),
        "-s",
        "scripts/bootstrap_custom_template.py",
    ]
    for _, kwargs in calls:
        assert kwargs["env"]["AZURE_CONFIG_DIR"] == "keep-existing-auto-login"
        assert kwargs["env"]["PATH"] == original_path
        assert "PYTHONPATH" not in kwargs["env"]
        assert "PYTHONHOME" not in kwargs["env"]
        assert Path(kwargs["env"]["TMPDIR"]).is_relative_to(virtual_environment.parent)


@pytest.mark.parametrize("missing", ["venv", "ensurepip"])
def test_missing_venv_prerequisites_are_actionable_not_silent_success(
    runtime: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    missing: str,
) -> None:
    prepare_runtime(runtime, tmp_path, monkeypatch)
    monkeypatch.setattr(
        runtime.importlib.util, "find_spec", lambda name: None if name == missing else object()
    )
    with pytest.raises(RuntimeError, match="Select a supported Deployment Scripts AzureCLI image"):
        runtime.main()
    assert list(tmp_path.iterdir()) == []


def test_failed_venv_creation_stops_before_pip(
    runtime: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_runtime(runtime, tmp_path, monkeypatch)
    commands: list[list[str]] = []

    def run(command: list[str], **_: object) -> None:
        commands.append(command)
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(runtime.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="venv creation failed"):
        runtime.main()
    assert len(commands) == 1
    assert commands[0][1:4] == ["-I", "-m", "venv"]


@pytest.mark.parametrize("version", [(3, 9), (3, 14)])
def test_incompatible_runtime_python_fails_explicitly(
    runtime: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version: tuple[int, int],
) -> None:
    prepare_runtime(runtime, tmp_path, monkeypatch)
    monkeypatch.setattr(runtime.sys, "version_info", version)
    with pytest.raises(RuntimeError, match=r"Python 3\.10 through 3\.13"):
        runtime.main()


def test_runtime_failure_removes_any_stale_deployment_success_marker(
    runtime: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_runtime(runtime, tmp_path, monkeypatch)
    output = tmp_path / "deployment-output.json"
    output.write_text('{"status":"complete"}', encoding="utf-8")
    monkeypatch.setattr(runtime.importlib.util, "find_spec", lambda _: None)
    with pytest.raises(RuntimeError, match="unavailable"):
        runtime.main()
    assert not output.exists()


def test_wrapper_propagates_orchestration_exit_status(
    runtime: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare_runtime(runtime, tmp_path, monkeypatch)

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        status = 7 if command[-1] == "scripts/bootstrap_custom_template.py" else 0
        return subprocess.CompletedProcess(command, status, "", "")

    monkeypatch.setattr(runtime.subprocess, "run", run)
    assert runtime.main() == 7

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
BASH = shutil.which("bash")


@pytest.mark.parametrize("script", sorted(SCRIPTS.glob("*.sh")), ids=lambda path: path.name)
def test_shell_sources_use_linux_line_endings(script: Path) -> None:
    assert b"\r" not in script.read_bytes(), (
        f"{script.name} must use LF; Git Bash can hide CRLF failures seen in Azure Cloud Shell"
    )


def bash(
    script: Path, *arguments: str, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    if BASH is None:
        pytest.skip("Bash is required")
    environment = dict(os.environ)
    for key in ("ACC_VERSION", "AZUREPS_HOST_ENVIRONMENT", "WORKSHOP_CLOUD_SHELL_REPO", "BASH_ENV"):
        environment.pop(key, None)
    environment.update(extra_env or {})
    return subprocess.run(
        [BASH, str(script), *arguments],
        cwd=script.parent,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def copy_scripts(tmp_path: Path, names: list[str]) -> Path:
    destination = tmp_path / "fixture" / "scripts"
    destination.mkdir(parents=True)
    for name in names:
        shutil.copyfile(SCRIPTS / name, destination / name)
    return destination


@pytest.mark.parametrize("script", ["setup.sh", "destroy.sh", "preflight.sh"])
def test_unactivated_cloud_shell_blocks_before_azure_and_preserves_state(
    tmp_path: Path, script: str
) -> None:
    scripts = copy_scripts(tmp_path, [script, "cloud-shell-common.sh"])
    root = scripts.parent
    (root / "infra").mkdir()
    (root / ".workshop").mkdir()
    state = root / "infra/terraform.tfstate"
    context = root / ".workshop/context.json"
    state.write_text("fixture-state")
    context.write_text("fixture-context")
    body = (scripts / script).read_text()
    preamble = """
az() { printf 'UNEXPECTED AZ CALL\\n'; return 90; }
terraform() { printf 'UNEXPECTED TERRAFORM CALL\\n'; return 90; }
jq() { printf 'UNEXPECTED JQ CALL\\n'; return 90; }
"""
    (scripts / script).write_text(
        body.replace("set -euo pipefail", "set -euo pipefail\n" + preamble, 1),
        encoding="utf-8",
        newline="\n",
    )
    result = bash(
        scripts / script,
        "--subscription",
        "fixture-sub",
        "--resource-group",
        "fixture-rg",
        extra_env={"ACC_VERSION": "fixture-cloud-shell"},
    )
    assert result.returncode != 0
    assert "source scripts/activate-cloud-shell.sh" in result.stderr
    assert "UNEXPECTED" not in result.stdout + result.stderr
    assert state.read_text() == "fixture-state"
    assert context.read_text() == "fixture-context"


def test_bootstrap_mount_failure_precedes_all_installations(tmp_path: Path) -> None:
    scripts = copy_scripts(
        tmp_path, ["setup-cloud-shell.sh", "cloud-shell-common.sh", "cloud_shell_environment.py"]
    )
    bootstrap = scripts / "setup-cloud-shell.sh"
    body = bootstrap.read_text()
    preamble = """
az() { printf 'UNEXPECTED AZ CALL\\n'; return 90; }
jq() { :; }
curl() { printf 'UNEXPECTED DOWNLOAD\\n'; return 90; }
findmnt() { :; }
flock() { :; }
python3() { printf 'Persistent storage fixture failure\\n' >&2; return 1; }
"""
    bootstrap.write_text(
        body.replace("set -euo pipefail", "set -euo pipefail\n" + preamble, 1),
        encoding="utf-8",
        newline="\n",
    )
    before = set(scripts.parent.rglob("*"))
    result = bash(bootstrap)
    assert result.returncode != 0
    assert "Persistent storage fixture failure" in result.stderr
    assert "UNEXPECTED" not in result.stdout + result.stderr
    assert set(scripts.parent.rglob("*")) == before


def test_invalid_sourced_activation_does_not_exit_or_change_shell_options(tmp_path: Path) -> None:
    scripts = copy_scripts(tmp_path, ["activate-cloud-shell.sh"])
    harness = scripts / "harness.sh"
    harness.write_text(
        "#!/usr/bin/env bash\n"
        'before="$(set +o)"\n'
        'source "$(dirname "${BASH_SOURCE[0]}")/activate-cloud-shell.sh"\n'
        "result=$?\n"
        '[[ "$before" == "$(set +o)" ]] || exit 90\n'
        'printf "ALIVE:%s\\n" "$result"\n',
        newline="\n",
    )
    result = bash(harness)
    assert result.returncode == 0
    assert "ALIVE:1" in result.stdout
    assert "setup-cloud-shell.sh" in result.stderr


def test_child_activation_explains_source_contract(tmp_path: Path) -> None:
    scripts = copy_scripts(tmp_path, ["activate-cloud-shell.sh"])
    result = bash(scripts / "activate-cloud-shell.sh")
    assert result.returncode == 1
    assert "source" in result.stderr and "child process" in result.stderr


def test_verified_download_is_reused_without_network(tmp_path: Path) -> None:
    scripts = copy_scripts(tmp_path, ["cloud-shell-common.sh"])
    payload = b"verified fixture payload"
    (scripts / "cached").write_bytes(payload)
    checksum = hashlib.sha256(payload).hexdigest()
    harness = scripts / "harness.sh"
    harness.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'cd "$(dirname "${BASH_SOURCE[0]}")"\n'
        "source ./cloud-shell-common.sh\n"
        'curl() { printf "UNEXPECTED DOWNLOAD"; return 90; }\n'
        f'cloud_shell_download "https://fixture.invalid/tool" "{checksum}" cached\n'
        'printf "REUSED\\n"\n',
        newline="\n",
    )
    result = bash(harness)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "REUSED\n"


def test_verified_download_symlink_is_rejected_before_checksum_reuse(tmp_path: Path) -> None:
    scripts = copy_scripts(tmp_path, ["cloud-shell-common.sh"])
    payload = b"verified fixture payload"
    original = scripts / "original"
    original.write_bytes(payload)
    try:
        (scripts / "cached").symlink_to(original.name)
    except OSError as exc:
        if os.name == "nt" and exc.winerror == 1314:
            pytest.skip("Creating native symlinks requires Windows Developer Mode or privilege")
        raise
    checksum = hashlib.sha256(payload).hexdigest()
    harness = scripts / "harness.sh"
    harness.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'cd "$(dirname "${BASH_SOURCE[0]}")"\n'
        "source ./cloud-shell-common.sh\n"
        'sha256sum() { printf "UNEXPECTED CHECKSUM" >&2; return 0; }\n'
        'curl() { printf "UNEXPECTED DOWNLOAD" >&2; return 90; }\n'
        f'cloud_shell_download "https://fixture.invalid/tool" "{checksum}" cached\n',
        newline="\n",
    )
    result = bash(harness)
    assert result.returncode != 0
    assert "refusing a symlink" in result.stderr
    assert "UNEXPECTED" not in result.stdout + result.stderr
    assert original.read_bytes() == payload


@pytest.mark.parametrize("name", ["cached", "cached.part"])
def test_download_rejects_directory_entries_without_network(tmp_path: Path, name: str) -> None:
    scripts = copy_scripts(tmp_path, ["cloud-shell-common.sh"])
    (scripts / name).mkdir()
    harness = scripts / "harness.sh"
    harness.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'cd "$(dirname "${BASH_SOURCE[0]}")"\n'
        "source ./cloud-shell-common.sh\n"
        'curl() { printf "UNEXPECTED DOWNLOAD" >&2; return 90; }\n'
        f'cloud_shell_download "https://fixture.invalid/tool" "{"0" * 64}" cached\n',
        newline="\n",
    )
    result = bash(harness)
    assert result.returncode != 0
    assert "non-file entry" in result.stderr
    assert "UNEXPECTED" not in result.stdout + result.stderr
    assert list((scripts / name).iterdir()) == []


def test_bad_download_cannot_replace_verified_destination(tmp_path: Path) -> None:
    scripts = copy_scripts(tmp_path, ["cloud-shell-common.sh"])
    (scripts / "cached").write_text("old cache")
    harness = scripts / "harness.sh"
    harness.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'cd "$(dirname "${BASH_SOURCE[0]}")"\n'
        "source ./cloud-shell-common.sh\n"
        'curl() { printf "corrupt fixture" > cached.part; }\n'
        f'cloud_shell_download "https://fixture.invalid/tool" "{"0" * 64}" cached\n',
        newline="\n",
    )
    result = bash(harness)
    assert result.returncode != 0
    assert "integrity check failed" in result.stderr
    assert (scripts / "cached").read_text() == "old cache"


@pytest.fixture
def venv_harness(tmp_path: Path) -> Path:
    scripts = copy_scripts(tmp_path, ["cloud-shell-common.sh"])
    root = scripts.parent
    executable = root / ".venv/bin/python"
    executable.parent.mkdir(parents=True)
    executable.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "$CALL_LOG"\n'
        'if [[ "$*" == "-m pip install"* && "${FAIL_PIP:-0}" == 1 ]]; then exit 1; fi\n'
        'if [[ "$1" == -c && "${MISSING_MODULE:-0}" == 1 ]]; then exit 1; fi\n',
        newline="\n",
    )
    executable.chmod(0o700)
    body = (SCRIPTS / "setup-cloud-shell.sh").read_text(encoding="utf-8")
    function = (
        "prepare_venv() {" + body.split("prepare_venv() {", 1)[1].split("\n}\n", 1)[0] + "\n}\n"
    )
    harness = scripts / "harness.sh"
    harness.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"\n'
        'export CALL_LOG="$REPO_ROOT/calls"\n'
        'cloud_shell_python_is_313() { [[ "${WRONG_PYTHON:-0}" == 0 ]]; }\n'
        'fake_python() { printf "fixture-digest"; }\n'
        "PYTHON_BIN=fake_python\n" + function + '\nprepare_venv "$REPO_ROOT/.venv" root\n',
        encoding="utf-8",
        newline="\n",
    )
    return harness


def test_dependencies_install_once_and_are_reused(venv_harness: Path) -> None:
    initial = bash(venv_harness)
    assert initial.returncode == 0, initial.stderr
    root = venv_harness.parent.parent
    calls = root / "calls"
    assert calls.read_text().count("-m pip install") == 1
    repeated = bash(venv_harness)
    assert repeated.returncode == 0, repeated.stderr
    assert "Reusing root dependencies" in repeated.stdout
    assert calls.read_text().count("-m pip install") == 1
    assert (root / ".venv/.cloud-shell-dependencies.sha256").read_text().strip() == "fixture-digest"


def test_missing_optional_module_prevents_false_reuse(venv_harness: Path) -> None:
    assert bash(venv_harness).returncode == 0
    repeated = bash(venv_harness, extra_env={"MISSING_MODULE": "1"})
    assert repeated.returncode == 0, repeated.stderr
    calls = venv_harness.parent.parent / "calls"
    assert calls.read_text().count("-m pip install") == 2


def test_interrupted_install_is_not_marked_complete_and_can_be_retried(venv_harness: Path) -> None:
    failed = bash(venv_harness, extra_env={"FAIL_PIP": "1"})
    stamp = venv_harness.parent.parent / ".venv/.cloud-shell-dependencies.sha256"
    assert failed.returncode != 0
    assert not stamp.exists()
    retried = bash(venv_harness)
    assert retried.returncode == 0, retried.stderr
    assert stamp.exists()


def test_wrong_existing_python_is_not_modified(venv_harness: Path) -> None:
    root = venv_harness.parent.parent
    before = (root / ".venv/bin/python").read_bytes()
    result = bash(venv_harness, extra_env={"WRONG_PYTHON": "1"})
    assert result.returncode != 0
    assert "not CPython 3.13" in result.stderr
    assert not (root / "calls").exists()
    assert (root / ".venv/bin/python").read_bytes() == before


def test_successful_activation_exports_only_to_the_sourced_workshop_shell(tmp_path: Path) -> None:
    scripts = copy_scripts(tmp_path, ["activate-cloud-shell.sh"])
    root = scripts.parent
    executable = root / ".venv/bin/python"
    executable.parent.mkdir(parents=True)
    executable.write_text(
        '#!/usr/bin/env bash\nprintf "%s/tools\\n" "$(cd "$(dirname "$0")/../.." && pwd)"\n',
        newline="\n",
    )
    executable.chmod(0o700)
    (executable.parent / "activate").write_text(
        'if [[ -n "${_OLD_VIRTUAL_PATH:-}" ]]; then PATH="$_OLD_VIRTUAL_PATH"; fi\n'
        '_OLD_VIRTUAL_PATH="$PATH"\n'
        'VIRTUAL_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n'
        'export VIRTUAL_ENV PATH="$VIRTUAL_ENV/bin:$PATH"\n',
        newline="\n",
    )
    harness = scripts / "harness.sh"
    harness.write_text(
        "#!/usr/bin/env bash\nset -euo pipefail\n"
        'repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"\n'
        'source "$repo/scripts/activate-cloud-shell.sh"\n'
        'first="$PATH"\n'
        'source "$repo/scripts/activate-cloud-shell.sh"\n'
        '[[ "$PATH" == "$first" ]]\n'
        '[[ "$PATH" == *"$repo/tools"* ]]\n'
        '[[ "$AZURE_TOKEN_CREDENTIALS" == AzureCliCredential ]]\n'
        '[[ "$WORKSHOP_CLOUD_SHELL_REPO" == "$repo" ]]\n'
        '[[ "$WORKSHOP_PYTHON" == "$repo/.venv/bin/python" ]]\n'
        'printf "ACTIVATED\\n"\n',
        newline="\n",
    )
    result = bash(harness)
    assert result.returncode == 0, result.stderr
    assert "ACTIVATED" in result.stdout


@pytest.mark.parametrize(
    "version,expected", [("1.9.8", 1), ("1.10.5", 0), ("1.15.0", 0), ("1.10.0-beta1", 1)]
)
def test_terraform_requirement_is_checked_without_terraform_execution(
    tmp_path: Path, version: str, expected: int
) -> None:
    scripts = copy_scripts(tmp_path, ["cloud-shell-common.sh"])
    harness = scripts / "harness.sh"
    harness.write_text(
        "#!/usr/bin/env bash\n"
        'source "$(dirname "${BASH_SOURCE[0]}")/cloud-shell-common.sh"\n'
        'terraform() { printf "fake"; }\n'
        f'jq() {{ printf "{version}"; }}\n'
        "cloud_shell_terraform_is_supported terraform\n",
        newline="\n",
    )
    assert bash(harness).returncode == expected


def test_bootstrap_has_separate_environments_and_native_graphviz_contract() -> None:
    bootstrap = (SCRIPTS / "setup-cloud-shell.sh").read_text()
    assert 'prepare_venv "$REPO_ROOT/.venv" root' in bootstrap
    assert 'prepare_venv "$REPO_ROOT/src/hosted-agent/.venv" hosted' in bootstrap
    assert "--name foundry-workshop" in bootstrap
    assert "--name foundry-hosted-agent" in bootstrap
    assert "cloud_shell_dot_works" in bootstrap
    assert "graphviz=14.1.2=h8b86629_0" in bootstrap
    assert "--only-binary=:all:" in bootstrap
    assert "sudo " not in bootstrap and "apt-get" not in bootstrap
    assert "rm -rf" not in bootstrap and "LD_LIBRARY_PATH" not in bootstrap
    assert "az login" not in bootstrap
    assert "pip check" in bootstrap and ".cloud-shell-dependencies.sha256" in bootstrap


def test_default_jupyter_launcher_is_one_command_with_manual_fallback() -> None:
    launcher = (SCRIPTS / "start-cloud-shell-jupyter.sh").read_text()
    bootstrap = (SCRIPTS / "setup-cloud-shell.sh").read_text()

    assert 'bash "$REPO_ROOT/scripts/setup-cloud-shell.sh"' in launcher
    assert "bash scripts/start-cloud-shell-jupyter.sh [--port 5000]" in launcher
    assert "--discover-preview" in launcher and "--preview-url" in launcher
    assert "There is no URL copy, Ctrl-C, or second launch command." in launcher
    assert "Notebook launcher: bash scripts/start-cloud-shell-jupyter.sh" in bootstrap


def test_credential_override_never_enters_hosted_runtime() -> None:
    deployment = (SCRIPTS / "deploy_hosted_agent.py").read_text()
    assert "AZURE_TOKEN_CREDENTIALS" not in deployment
    for path in (ROOT / "src/hosted-agent").glob("*.py"):
        assert "AZURE_TOKEN_CREDENTIALS" not in path.read_text(encoding="utf-8")


def test_shell_validation_checks_each_file_not_only_first_argument() -> None:
    makefile = (ROOT / "Makefile").read_text()
    for script in (
        "cloud-shell-common.sh",
        "setup-cloud-shell.sh",
        "activate-cloud-shell.sh",
        "start-cloud-shell-jupyter.sh",
    ):
        assert f"scripts/{script}" in makefile
    assert 'do bash -n "$$script" || exit; done' in makefile
    assert "make shell-validate" in (ROOT / ".github/workflows/validate.yml").read_text()

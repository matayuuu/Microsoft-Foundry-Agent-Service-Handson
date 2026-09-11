"""Local, read-only checks for the provisioning-only Azure Cloud Shell flow."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

STORAGE_GUIDANCE = (
    "Persistent Cloud Shell storage could not be verified. Start Cloud Shell with "
    "'Mount storage account', confirm that ~/clouddrive is a read-write Azure Files mount, "
    "and clone this repository below ~/clouddrive. The rest of $HOME is session-local and "
    "must not hold the repository or Terraform state. If clouddrive is absent, reset the "
    "Cloud Shell user settings and attach storage; never provision from an ephemeral session."
)
REQUIRED_PYTHON = (3, 12)


class EnvironmentError(RuntimeError):
    """An actionable environment problem that never includes token output."""


def run_local(arguments: list[str], *, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EnvironmentError(f"Could not run {Path(arguments[0]).name}; check the tool.") from exc
    if result.returncode:
        raise EnvironmentError(f"{Path(arguments[0]).name} failed; check the tool and permissions.")
    return result.stdout.strip()


def mounted_filesystem(path: Path) -> dict[str, str]:
    try:
        filesystems = json.loads(
            run_local(
                [
                    "findmnt",
                    "--json",
                    "--target",
                    str(path),
                    "--output",
                    "SOURCE,TARGET,FSTYPE,OPTIONS,MAJ:MIN",
                ]
            )
        )["filesystems"]
        if len(filesystems) != 1:
            raise ValueError("expected one mount")
        return filesystems[0]
    except (KeyError, TypeError, ValueError, EnvironmentError) as exc:
        raise EnvironmentError(STORAGE_GUIDANCE) from exc


def validate_mounts(
    repo: Path,
    share: Path,
    repo_mount: dict[str, str],
    share_mount: dict[str, str],
) -> None:
    if (
        repo == share
        or not repo.is_relative_to(share)
        or share_mount.get("fstype") not in {"cifs", "smb3"}
        or not re.match(r"^//[^/]+/[^/]+", share_mount.get("source", ""))
        or repo_mount.get("maj:min") != share_mount.get("maj:min")
        or repo_mount.get("source") != share_mount.get("source")
        or repo_mount.get("fstype") != share_mount.get("fstype")
        or any(
            "rw" not in mount.get("options", "").split(",") for mount in (repo_mount, share_mount)
        )
    ):
        raise EnvironmentError(STORAGE_GUIDANCE)


def runtime_directory(repo: Path, home: Path | None = None) -> Path:
    home = home or Path.home().resolve()
    identifier = hashlib.sha256(str(repo).encode()).hexdigest()[:16]
    return home / ".cache" / "foundry-cloud-shell" / identifier


def venv_directory(repo: Path, home: Path | None = None) -> Path:
    return runtime_directory(repo, home) / "venv"


def state_directory(repo: Path) -> Path:
    return repo / ".workshop" / "cloud-shell"


def validate_free_space(repo: Path, minimum_mib: int) -> None:
    free = shutil.disk_usage(repo).free
    if free < minimum_mib * 1024 * 1024:
        raise EnvironmentError(
            f"Persistent clouddrive needs at least {minimum_mib} MiB free; "
            f"only {free // (1024 * 1024)} MiB is available."
        )


def validate_venv_location(repo: Path, home: Path, share: Path) -> None:
    runtime = runtime_directory(repo, home)
    venv = runtime / "venv"
    if (
        runtime.is_symlink()
        or venv.is_symlink()
        or (venv.exists() and not venv.is_dir())
        or not runtime.resolve().is_relative_to(home)
        or runtime.resolve().is_relative_to(share)
    ):
        raise EnvironmentError(
            "The session-local provisioning environment must be a real directory under $HOME."
        )


def validate_storage(repo: Path, *, minimum_mib: int) -> Path:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise EnvironmentError("Use Azure Cloud Shell Bash on Linux x86_64 (amd64).")
    home = Path.home().resolve()
    share = (home / "clouddrive").resolve()
    if not home.is_dir() or not share.is_dir() or not repo.is_dir():
        raise EnvironmentError(STORAGE_GUIDANCE)

    share_mount = mounted_filesystem(share)
    validate_mounts(
        repo,
        share,
        mounted_filesystem(repo),
        share_mount,
    )
    validate_venv_location(repo, home, share)

    state = state_directory(repo)
    for candidate in (state, state.parent):
        if candidate.is_symlink():
            raise EnvironmentError(
                "Cloud Shell readiness storage must not use symlink directories."
            )
    if state.exists() and (not state.is_dir() or state.stat().st_uid != os.getuid()):
        raise EnvironmentError("Cloud Shell readiness storage must be a user-owned directory.")

    for path in (repo, repo / "infra", repo / ".workshop", state):
        existing = path
        while not existing.exists():
            if existing.is_symlink():
                raise EnvironmentError(f"Broken symlink at {existing}. {STORAGE_GUIDANCE}")
            existing = existing.parent
        resolved = existing.resolve()
        mount = mounted_filesystem(resolved)
        if (
            not resolved.is_relative_to(repo)
            or mount.get("maj:min") != share_mount.get("maj:min")
            or mount.get("source") != share_mount.get("source")
            or mount.get("fstype") != share_mount.get("fstype")
            or not os.access(existing, os.W_OK | os.X_OK)
        ):
            raise EnvironmentError(STORAGE_GUIDANCE)

    validate_free_space(repo, minimum_mib)
    return state


def python_version(executable: Path) -> tuple[int, int]:
    try:
        value = run_local(
            [
                str(executable),
                "-c",
                "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
            ]
        )
        major, minor = value.split(".", 1)
        return int(major), int(minor)
    except (EnvironmentError, ValueError) as exc:
        raise EnvironmentError(f"Could not determine the Python version for {executable}.") from exc


def validate_python(executable: Path) -> None:
    version = python_version(executable)
    if version != REQUIRED_PYTHON:
        raise EnvironmentError(
            f"{executable} uses Python {version[0]}.{version[1]}; "
            "Cloud Shell provisioning requires built-in Python 3.12."
        )


def dependency_digest(repo: Path) -> str:
    digest = hashlib.sha256(b"cloud-shell-provisioning-v2:runtime-only")
    for relative in (
        "pyproject.toml",
        "scripts/setup-cloud-shell.sh",
        "scripts/cloud-shell-common.sh",
        "scripts/cloud_shell_environment.py",
    ):
        digest.update(relative.encode())
        digest.update((repo / relative).read_bytes())
    return digest.hexdigest()


def validate_ready(repo: Path) -> dict[str, str]:
    state = validate_storage(repo, minimum_mib=512)
    venv_python = venv_directory(repo) / "bin" / "python"
    validate_python(venv_python)
    try:
        ready = json.loads((state / "ready.json").read_text())
        expected = {
            "repo": str(repo),
            "python": str(venv_python),
            "dependency_digest": dependency_digest(repo),
        }
        if not isinstance(ready, dict) or any(
            ready.get(key) != value for key, value in expected.items()
        ):
            raise ValueError("stale readiness marker")
    except (OSError, TypeError, ValueError) as exc:
        raise EnvironmentError(
            "Cloud Shell setup is missing, interrupted, or stale. Run "
            "bash scripts/setup-cloud-shell.sh, then source scripts/activate-cloud-shell.sh."
        ) from exc
    run_local([str(venv_python), "-m", "pip", "check"], timeout=120)
    return {key: str(value) for key, value in ready.items()}


def check_tokens(subscription: str | None) -> None:
    for audience in (
        "https://management.azure.com/",
        "https://ai.azure.com",
        "https://search.azure.com",
        "https://cognitiveservices.azure.com",
    ):
        command = [
            "az",
            "account",
            "get-access-token",
            "--resource",
            audience,
            "--query",
            "expiresOn",
            "--output",
            "tsv",
            "--only-show-errors",
        ]
        if subscription:
            command += ["--subscription", subscription]
        try:
            if not run_local(command, timeout=90):
                raise EnvironmentError("empty authentication result")
        except EnvironmentError as exc:
            raise EnvironmentError(
                f"Azure CLI could not acquire a token for {audience}. Sign in to the assigned "
                "tenant/subscription and retry. If Conditional Access blocks this audience, stop "
                "and contact the administrator; never substitute keys or secrets."
            ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["storage", "venv", "ready", "digest", "tokens"])
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--minimum-free-mib", type=int, default=512)
    parser.add_argument("--subscription")
    arguments = parser.parse_args()
    repo = arguments.repo_root.resolve()
    try:
        if arguments.action == "storage":
            print(validate_storage(repo, minimum_mib=arguments.minimum_free_mib))
        elif arguments.action == "venv":
            print(venv_directory(repo))
        elif arguments.action == "digest":
            print(dependency_digest(repo))
        else:
            validate_ready(repo)
            if arguments.action == "tokens":
                check_tokens(arguments.subscription)
        return 0
    except (EnvironmentError, OSError) as exc:
        print(f"Cloud Shell: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

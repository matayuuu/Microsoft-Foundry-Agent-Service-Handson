"""Local, read-only Cloud Shell checks shared by the Bash entry points."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

STORAGE_GUIDANCE = (
    "Persistent Cloud Shell storage could not be verified. Mount your own Azure Files share "
    "using the Cloud Shell storage settings, then put the repository under the persisted "
    "Unix HOME, not directly in clouddrive. Do not delete .workshop or Terraform state. "
    "If HOME is ephemeral or the disk-image backing is not visible, stop and ask the "
    "instructor to verify the mounts; a clouddrive directory alone is not sufficient. "
    "Configured storage can still fail to mount if Azure Policy changes publicNetworkAccess "
    "or allowSharedKeyAccess. Have the administrator check the effective settings and policy; "
    "do not weaken protections or continue from an ephemeral session."
)
KERNELS = {
    "foundry-workshop": (".venv", "Python (Foundry Workshop)"),
    "foundry-hosted-agent": ("src/hosted-agent/.venv", "Python (Foundry Hosted Agent)"),
}


class EnvironmentError(RuntimeError):
    """An actionable environment problem, without subprocess secrets."""


def run_local(arguments: list[str], *, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            arguments, capture_output=True, text=True, check=False, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EnvironmentError(f"Could not run {Path(arguments[0]).name}; check the tool.") from exc
    if result.returncode:
        raise EnvironmentError(f"{Path(arguments[0]).name} failed; check the tool and permissions.")
    return result.stdout.strip()


def mounted_filesystem(path: Path) -> dict[str, str]:
    try:
        result = json.loads(
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
        if len(result) != 1:
            raise ValueError("Expected one mount")
        return result[0]
    except (KeyError, ValueError, EnvironmentError) as exc:
        raise EnvironmentError(STORAGE_GUIDANCE) from exc


def validate_mounts(
    home: Path,
    repo: Path,
    share: Path,
    home_mount: dict[str, str],
    repo_mount: dict[str, str],
    share_mount: dict[str, str],
    backing_file: Path,
) -> None:
    """Require a native HOME disk image backed by the mounted share, not overlayfs."""
    if (
        repo == home
        or not repo.is_relative_to(home)
        or repo.is_relative_to(share)
        or home_mount.get("fstype") not in {"ext2", "ext3", "ext4", "xfs", "btrfs"}
        or repo_mount.get("maj:min") != home_mount.get("maj:min")
        or repo_mount.get("source") != home_mount.get("source")
        or repo_mount.get("fstype") != home_mount.get("fstype")
        or share_mount.get("fstype") not in {"cifs", "smb3"}
        or not re.match(r"^//[^/]+/[^/]+", share_mount.get("source", ""))
        or not backing_file.is_relative_to(share / ".cloudconsole")
        or backing_file.suffix != ".img"
        or not backing_file.is_file()
        or any(
            "rw" not in mount.get("options", "").split(",")
            for mount in (home_mount, repo_mount, share_mount)
        )
    ):
        raise EnvironmentError(STORAGE_GUIDANCE)


def state_directory(repo: Path, home: Path | None = None) -> Path:
    home = home or Path.home().resolve()
    identifier = hashlib.sha256(str(repo).encode()).hexdigest()[:16]
    return home / ".local" / "share" / "foundry-cloud-shell" / identifier


def validate_free_space(repo: Path, minimum_mib: int) -> None:
    free = shutil.disk_usage(repo).free
    if free < minimum_mib * 1024 * 1024:
        raise EnvironmentError(
            f"HOME needs at least {minimum_mib} MiB free; currently {free // (1024 * 1024)} MiB. "
            "Free only your own expendable files, never .workshop or Terraform state, then retry."
        )


def validate_venv_locations(repo: Path) -> None:
    paths = [repo / relative for relative, _ in KERNELS.values()]
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(repo):
            raise EnvironmentError(
                "Both venvs must be separate directories inside this repository."
            )
    if all(path.exists() for path in paths) and paths[0].samefile(paths[1]):
        raise EnvironmentError("Root and Hosted Agent virtual environments must remain separate.")


def validate_storage(repo: Path, *, minimum_mib: int) -> Path:
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise EnvironmentError("Use Azure Cloud Shell Bash on Linux x86_64 (amd64).")
    home = Path.home().resolve()
    share = (home / "clouddrive").resolve()
    if not home.is_dir() or not share.is_dir() or not repo.is_dir():
        raise EnvironmentError(STORAGE_GUIDANCE)
    home_mount = mounted_filesystem(home)
    device = home_mount.get("maj:min", "")
    if not re.fullmatch(r"\d+:\d+", device):
        raise EnvironmentError(STORAGE_GUIDANCE)
    try:
        backing = Path(f"/sys/dev/block/{device}/loop/backing_file").read_text().strip()
        if not backing.startswith("/"):
            backing = "/" + backing
        backing_file = Path(backing).resolve(strict=True)
    except (OSError, ValueError) as exc:
        raise EnvironmentError(STORAGE_GUIDANCE) from exc
    validate_mounts(
        home,
        repo,
        share,
        home_mount,
        mounted_filesystem(repo),
        mounted_filesystem(share),
        backing_file,
    )
    validate_venv_locations(repo)
    state = state_directory(repo, home)
    for path in (state, *state.relative_to(home).parents):
        # Parents from relative_to are relative paths; only inspect inside HOME.
        candidate = path if path.is_absolute() else home / path
        if candidate.is_symlink():
            raise EnvironmentError("Cloud Shell tool storage must not contain symlink directories.")
    if state.exists() and (
        not state.is_dir()
        or state.stat().st_uid != os.getuid()
        or stat.S_IMODE(state.stat().st_mode) != 0o700
    ):
        raise EnvironmentError(
            "Existing Cloud Shell tool storage must be user-owned and mode 0700."
        )
    for path in (home, repo, repo / "infra", repo / ".workshop", state):
        existing = path
        while not existing.exists():
            if existing.is_symlink():
                raise EnvironmentError(f"Broken symlink at {existing}. {STORAGE_GUIDANCE}")
            existing = existing.parent
        resolved = existing.resolve()
        mount = mounted_filesystem(resolved)
        if (
            not resolved.is_relative_to(home)
            or resolved.is_relative_to(share)
            or mount.get("maj:min") != device
            or mount.get("fstype") != home_mount.get("fstype")
            or not os.access(existing, os.W_OK | os.X_OK)
        ):
            raise EnvironmentError(STORAGE_GUIDANCE)
    validate_free_space(repo, minimum_mib)
    return state


def python_is_313(executable: Path) -> bool:
    try:
        return (
            run_local(
                [
                    str(executable),
                    "-c",
                    "import sys; print(sys.version_info[:2] == (3, 13) "
                    "and sys.implementation.name == 'cpython')",
                ]
            )
            == "True"
        )
    except EnvironmentError:
        return False


def dependency_digest(repo: Path, name: str) -> str:
    sources = {
        "root": ["pyproject.toml", "src/travel-api/pyproject.toml"],
        "hosted": ["src/hosted-agent/requirements.txt"],
    }
    digest = hashlib.sha256(b"cloud-shell-v1:dev,cloud-shell:pytest,ruff,ipykernel")
    for source in sources[name]:
        digest.update((repo / source).read_bytes())
    return digest.hexdigest()


def validate_environments(repo: Path) -> None:
    validate_venv_locations(repo)
    for name, (relative, _) in KERNELS.items():
        environment = repo / relative
        if not python_is_313(environment / "bin" / "python"):
            raise EnvironmentError(
                f"{relative} needs CPython >=3.13,<3.14. Existing files are untouched. "
                "Run bash scripts/setup-cloud-shell.sh; do not combine the two venvs."
            )
        kernel = repo / ".venv/share/jupyter/kernels" / name / "kernel.json"
        try:
            arguments = json.loads(kernel.read_text())["argv"]
            correct = Path(arguments[0]) == environment / "bin/python"
        except (OSError, ValueError, KeyError, IndexError):
            correct = False
        if not correct:
            raise EnvironmentError(
                f"The {name} kernel is missing or points elsewhere. Re-run setup-cloud-shell.sh."
            )


def validate_ready(repo: Path) -> dict[str, object]:
    state = validate_storage(repo, minimum_mib=512)
    try:
        ready = json.loads((state / "ready.json").read_text())
        current = {name: dependency_digest(repo, name) for name in ("root", "hosted")}
        if ready["repo"] != str(repo) or ready["dependencies"] != current:
            raise ValueError("Stale setup")
        directories = ready["tool_directories"]
        if not isinstance(directories, list) or not all(
            isinstance(directory, str) and Path(directory).is_absolute()
            for directory in directories
        ):
            raise ValueError("Invalid tool directories")
        for directory in directories:
            if ":" in directory or "\n" in directory or not Path(directory).is_dir():
                raise ValueError("Invalid tool directory")
        dot = str(ready["dot"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise EnvironmentError(
            "Cloud Shell setup is missing, interrupted, or dependencies changed. "
            "Run bash scripts/setup-cloud-shell.sh, then source scripts/activate-cloud-shell.sh."
        ) from exc
    validate_environments(repo)
    try:
        result = subprocess.run(
            [dot, "-Tsvg"],
            input="digraph workshop { environment -> notebook }\n",
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode or "<svg" not in result.stdout:
            raise EnvironmentError("Native Graphviz could not render SVG.")
    except (OSError, subprocess.TimeoutExpired, EnvironmentError) as exc:
        raise EnvironmentError(
            "Native Graphviz SVG rendering failed. Re-run setup-cloud-shell.sh; "
            "the Python graphviz package alone is not sufficient."
        ) from exc
    return ready


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
                raise EnvironmentError("Empty authentication result")
        except EnvironmentError as exc:
            raise EnvironmentError(
                f"Azure CLI could not acquire a token for {audience}. Cloud Shell's "
                "built-in sign-in may not support this audience. Run az login --use-device-code "
                "in this Cloud Shell, select your assigned subscription, then retry. "
                "If Conditional Access or tenant policy blocks sign-in, stop and contact "
                "your administrator; do not use keys, secrets, or bypass the policy."
            ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["storage", "ready", "paths", "digest", "tokens"])
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--minimum-free-mib", type=int, default=512)
    parser.add_argument("--environment", choices=["root", "hosted"])
    parser.add_argument("--subscription")
    arguments = parser.parse_args()
    repo = arguments.repo_root.resolve()
    try:
        if arguments.action == "storage":
            print(validate_storage(repo, minimum_mib=arguments.minimum_free_mib))
        elif arguments.action == "digest":
            if arguments.environment is None:
                parser.error("--environment is required for digest")
            print(dependency_digest(repo, arguments.environment))
        else:
            ready = validate_ready(repo)
            if arguments.action == "paths":
                print(":".join(ready["tool_directories"]))
            elif arguments.action == "tokens":
                check_tokens(arguments.subscription)
        return 0
    except (EnvironmentError, OSError) as exc:
        print(f"Cloud Shell: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Prepare workshop-owned venvs and kernels in Codespaces or the local Dev Container.

No Azure authentication or resource operations are performed. Existing unowned
environments and kernels are never overwritten, and a failed command stops setup.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.lib.workshop_runtime import (
    ENVIRONMENTS,
    HOSTED_ENVIRONMENT,
    MARKER_NAME,
    WORKSHOP_ENVIRONMENT,
    EnvironmentSpec,
    WorkshopRuntimeError,
    environment_path,
    inspect_python_command,
    marker_payload,
    runtime_python,
    verify_ownership,
    verify_python,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PIP_VERSION = "26.2.1"


class Runner(Protocol):
    def run(self, command: Sequence[str]) -> None: ...

    def json(self, command: Sequence[str]) -> Any: ...


class SubprocessRunner:
    def run(self, command: Sequence[str]) -> None:
        try:
            result = subprocess.run(command, cwd=REPO_ROOT, stderr=subprocess.STDOUT, check=False)
        except OSError as exc:
            raise WorkshopRuntimeError(f"Cannot run {command[0]}: {exc}") from exc
        if result.returncode:
            raise WorkshopRuntimeError(
                f"command failed with exit code {result.returncode}: {shlex.join(command)}"
            )

    def json(self, command: Sequence[str]) -> Any:
        try:
            result = subprocess.run(
                command,
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError as exc:
            raise WorkshopRuntimeError(f"Cannot run {command[0]}: {exc}") from exc
        if result.returncode:
            raise WorkshopRuntimeError(
                f"command failed: {shlex.join(command)}\n{result.stderr.strip()}"
            )
        try:
            return json.loads(result.stdout)
        except ValueError as exc:
            raise WorkshopRuntimeError(
                f"command returned invalid JSON: {shlex.join(command)}"
            ) from exc


def install_command(python: Path, spec: EnvironmentSpec) -> list[str]:
    command = [
        str(python),
        "-m",
        "pip",
        "install",
        "--requirement",
        str(REPO_ROOT / ".devcontainer" / "requirements-dev.txt"),
    ]
    if spec == WORKSHOP_ENVIRONMENT:
        command += [
            "--editable",
            f"{REPO_ROOT}[dev]",
            "--editable",
            f"{REPO_ROOT / 'src' / 'travel-api'}[dev]",
        ]
    else:
        command += [
            "--requirement",
            str(REPO_ROOT / "src" / "hosted-agent" / "requirements.txt"),
        ]
    return command


def kernel_install_command(python: Path, spec: EnvironmentSpec) -> list[str]:
    return [
        str(python),
        "-m",
        "ipykernel",
        "install",
        "--user",
        "--name",
        spec.name,
        "--display-name",
        spec.display_name,
    ]


def _kernels(runner: Runner, python: Path) -> dict[str, Any]:
    raw = runner.json([str(python), "-m", "jupyter", "kernelspec", "list", "--json"])
    if not isinstance(raw, dict) or not isinstance(raw.get("kernelspecs"), dict):
        raise WorkshopRuntimeError("Jupyter kernelspec list returned an unexpected response.")
    return raw["kernelspecs"]


def _verify_kernel(kernel: Any, python: Path, spec: EnvironmentSpec) -> None:
    details = kernel.get("spec", {}) if isinstance(kernel, dict) else {}
    argv = details.get("argv", []) if isinstance(details, dict) else []
    if (
        not isinstance(argv, list)
        or not argv
        or not isinstance(argv[0], str)
        or os.path.normcase(os.path.abspath(argv[0])) != os.path.normcase(os.path.abspath(python))
        or details.get("display_name") != spec.display_name
        or details.get("language") != "python"
        or "-m" not in argv
        or argv[argv.index("-m") + 1 : argv.index("-m") + 2] != ["ipykernel_launcher"]
    ):
        raise WorkshopRuntimeError(
            f"Kernel {spec.name!r} is missing or points to an unrelated environment/configuration; "
            "refusing to overwrite it."
        )


def ensure_environments(
    runner: Runner,
    *,
    management_python: str = "python3.12",
    hosted_python: str = "python3.13",
) -> dict[str, Path]:
    paths = {spec.name: runtime_python(spec) for spec in ENVIRONMENTS}
    bases = {WORKSHOP_ENVIRONMENT.name: management_python, HOSTED_ENVIRONMENT.name: hosted_python}
    # Preflight both targets and named interpreters before creating or installing anything.
    for spec in ENVIRONMENTS:
        path = environment_path(paths[spec.name], spec)
        if path.exists():
            verify_ownership(path, spec)
            if (path / "pyvenv.cfg").exists():
                verify_python(
                    runner.json(inspect_python_command(paths[spec.name])), spec, path=path
                )
        verify_python(runner.json(inspect_python_command(bases[spec.name])), spec)

    for spec in ENVIRONMENTS:
        python = paths[spec.name]
        path = environment_path(python, spec)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=False)
            with (path / MARKER_NAME).open("x", encoding="utf-8") as marker:
                marker.write(json.dumps(marker_payload(spec), indent=2) + "\n")
        if not (path / "pyvenv.cfg").is_file():
            runner.run([bases[spec.name], "-m", "venv", str(path)])
        verify_python(runner.json(inspect_python_command(python)), spec, path=path)
        runner.run([str(python), "-m", "pip", "install", f"pip=={PIP_VERSION}"])
        runner.run(install_command(python, spec))
        runner.run([str(python), "-m", "pip", "check"])
        projects_version = runner.json(
            [
                str(python),
                "-c",
                "import json; from importlib.metadata import version; "
                "print(json.dumps(version('azure-ai-projects')))",
            ]
        )
        if (spec == WORKSHOP_ENVIRONMENT and projects_version != "2.5.0") or (
            spec == HOSTED_ENVIRONMENT
            and (
                not isinstance(projects_version, str)
                or projects_version.split(".")[:2] not in (["2", "2"], ["2", "3"])
            )
        ):
            raise WorkshopRuntimeError(
                f"{spec.name} has incompatible azure-ai-projects {projects_version!r}."
            )

    management = paths[WORKSHOP_ENVIRONMENT.name]
    kernels = _kernels(runner, management)
    for spec in ENVIRONMENTS:
        if spec.name in kernels:
            _verify_kernel(kernels[spec.name], paths[spec.name], spec)
    for spec in ENVIRONMENTS:
        if spec.name not in kernels:
            runner.run(kernel_install_command(paths[spec.name], spec))
    registered = _kernels(runner, management)
    for spec in ENVIRONMENTS:
        _verify_kernel(registered.get(spec.name), paths[spec.name], spec)
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--management-python", default="python3.12")
    parser.add_argument("--hosted-python", default="python3.13")
    args = parser.parse_args(argv)
    try:
        if sys.platform != "linux":
            raise WorkshopRuntimeError("Run setup inside Codespaces or the local Dev Container.")
        paths = ensure_environments(
            SubprocessRunner(),
            management_python=args.management_python,
            hosted_python=args.hosted_python,
        )
    except (WorkshopRuntimeError, OSError) as exc:
        print(f"setup_dev_environment.py: {exc}", file=sys.stderr)
        return 2
    print("Workshop kernels are ready. Interpreter paths:")
    for spec in ENVIRONMENTS:
        print(f"export {spec.variable}={shlex.quote(str(paths[spec.name]))}")
        print(f"  {spec.display_name} (Python {spec.python_version})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

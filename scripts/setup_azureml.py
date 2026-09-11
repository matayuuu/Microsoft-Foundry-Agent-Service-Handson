#!/usr/bin/env python3
"""Create or reuse the two isolated Azure ML workshop Conda kernels.

Run this script once from Azure ML's built-in Python 3.10 kernel. Existing
environments and kernels are reused only when this script previously marked
them as workshop-owned; unrelated names are never overwritten or deleted.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

REPO_ROOT = Path(__file__).resolve().parents[1]
MARKER_NAME = ".foundry-workshop-environment.json"
CONDA_CHANNEL = "conda-forge"


class AzureMLSetupError(RuntimeError):
    """A safe, actionable environment setup failure."""


@dataclass(frozen=True)
class EnvironmentSpec:
    name: str
    display_name: str
    purpose: str
    python_version: str


WORKSHOP_ENVIRONMENT = EnvironmentSpec(
    name="foundry-workshop",
    display_name="Python (Foundry Workshop)",
    purpose="root-management-tooling",
    python_version="3.12",
)
HOSTED_ENVIRONMENT = EnvironmentSpec(
    name="foundry-hosted-agent",
    display_name="Python (Foundry Hosted Agent)",
    purpose="hosted-agent-development",
    python_version="3.13",
)
ENVIRONMENTS = (WORKSHOP_ENVIRONMENT, HOSTED_ENVIRONMENT)


class Runner(Protocol):
    def run(self, command: Sequence[str]) -> None: ...

    def json(self, command: Sequence[str]) -> Any: ...


class SubprocessRunner:
    def run(self, command: Sequence[str]) -> None:
        completed = subprocess.run(command, cwd=REPO_ROOT, stderr=subprocess.STDOUT, check=False)
        if completed.returncode:
            raise AzureMLSetupError(
                f"command failed with exit code {completed.returncode}: {' '.join(command)}"
            )

    def json(self, command: Sequence[str]) -> Any:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode:
            raise AzureMLSetupError(
                f"command failed: {' '.join(command)}\n{completed.stderr.strip()}"
            )
        try:
            return json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise AzureMLSetupError(f"command returned invalid JSON: {' '.join(command)}") from exc


def conda_create_command(conda: str, spec: EnvironmentSpec) -> list[str]:
    return [
        conda,
        "create",
        "--yes",
        "--override-channels",
        "--channel",
        CONDA_CHANNEL,
        "--name",
        spec.name,
        f"python={spec.python_version}",
        "pip",
        "ipykernel",
    ]


def workshop_install_command(conda: str) -> list[str]:
    return [
        conda,
        "run",
        "--name",
        WORKSHOP_ENVIRONMENT.name,
        "python",
        "-m",
        "pip",
        "install",
        "--editable",
        f"{REPO_ROOT}[dev]",
        "--editable",
        f"{REPO_ROOT / 'src' / 'travel-api'}[dev]",
    ]


def hosted_install_command(conda: str) -> list[str]:
    return [
        conda,
        "run",
        "--name",
        HOSTED_ENVIRONMENT.name,
        "python",
        "-m",
        "pip",
        "install",
        "--requirement",
        str(REPO_ROOT / "src" / "hosted-agent" / "requirements.txt"),
        "pytest",
        "ruff",
        "ipykernel",
    ]


def graphviz_install_command(conda: str) -> list[str]:
    return [
        conda,
        "install",
        "--yes",
        "--name",
        HOSTED_ENVIRONMENT.name,
        "--override-channels",
        "--channel",
        CONDA_CHANNEL,
        "graphviz",
    ]


def kernel_install_command(conda: str, spec: EnvironmentSpec) -> list[str]:
    return [
        conda,
        "run",
        "--name",
        spec.name,
        "python",
        "-m",
        "ipykernel",
        "install",
        "--user",
        "--name",
        spec.name,
        "--display-name",
        spec.display_name,
    ]


def _env_paths(raw: Any) -> dict[str, Path]:
    if not isinstance(raw, dict) or not isinstance(raw.get("envs"), list):
        raise AzureMLSetupError("conda env list returned an unexpected response")
    result: dict[str, Path] = {}
    for item in raw["envs"]:
        path = Path(str(item))
        result[path.name] = path
    return result


def _marker_payload(spec: EnvironmentSpec) -> dict[str, str]:
    return {
        "owner": "microsoft-foundry-agent-service-handson",
        "name": spec.name,
        "purpose": spec.purpose,
        "python": spec.python_version,
        "channel": CONDA_CHANNEL,
    }


def _verify_or_mark_new_environment(
    path: Path, spec: EnvironmentSpec, *, newly_created: bool
) -> None:
    marker = path / MARKER_NAME
    expected = _marker_payload(spec)
    if newly_created:
        marker.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
        return
    try:
        actual = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AzureMLSetupError(
            f"Conda environment {spec.name!r} already exists but is not marked as "
            "workshop-owned. Rename it manually or choose a clean Azure ML compute; "
            "this script will not overwrite it."
        ) from exc
    if actual != expected:
        raise AzureMLSetupError(
            f"Conda environment {spec.name!r} has an incompatible ownership, "
            "Python, or channel marker; "
            "refusing to mix environments. Use a clean Azure ML Compute instance."
        )


def _kernel_specs(raw: Any) -> Mapping[str, Any]:
    if not isinstance(raw, dict) or not isinstance(raw.get("kernelspecs"), dict):
        raise AzureMLSetupError("jupyter kernelspec list returned an unexpected response")
    return raw["kernelspecs"]


def _kernel_matches_environment(kernel: Mapping[str, Any], env_path: Path) -> bool:
    spec = kernel.get("spec", {})
    argv = spec.get("argv", []) if isinstance(spec, dict) else []
    if not argv:
        return False
    kernel_python = Path(str(argv[0]))
    try:
        return os.path.commonpath([kernel_python.resolve(), env_path.resolve()]) == str(
            env_path.resolve()
        )
    except (OSError, ValueError):
        return False


def ensure_environments(
    runner: Runner,
    *,
    conda: str,
    jupyter: str,
) -> None:
    print(f"Preparing isolated workshop kernels using only the {CONDA_CHANNEL} Conda channel.")
    paths = _env_paths(runner.json([conda, "env", "list", "--json"]))
    for spec in ENVIRONMENTS:
        newly_created = spec.name not in paths
        if newly_created:
            runner.run(conda_create_command(conda, spec))
            paths = _env_paths(runner.json([conda, "env", "list", "--json"]))
            if spec.name not in paths:
                raise AzureMLSetupError(
                    f"Conda reported success but environment {spec.name!r} is unavailable."
                )
        _verify_or_mark_new_environment(paths[spec.name], spec, newly_created=newly_created)

    runner.run(workshop_install_command(conda))
    runner.run(hosted_install_command(conda))
    runner.run(graphviz_install_command(conda))

    kernels = _kernel_specs(runner.json([jupyter, "kernelspec", "list", "--json"]))
    for spec in ENVIRONMENTS:
        existing = kernels.get(spec.name)
        if existing is not None:
            if not isinstance(existing, dict) or not _kernel_matches_environment(
                existing, paths[spec.name]
            ):
                raise AzureMLSetupError(
                    f"Jupyter kernel {spec.name!r} already points to an unrelated environment; "
                    "refusing to overwrite it."
                )
            continue
        runner.run(kernel_install_command(conda, spec))
    registered = _kernel_specs(runner.json([jupyter, "kernelspec", "list", "--json"]))
    missing = [spec.name for spec in ENVIRONMENTS if spec.name not in registered]
    if missing:
        raise AzureMLSetupError(
            "Jupyter did not register the expected kernel(s): " + ", ".join(missing)
        )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conda", default=shutil.which("conda") or "conda")
    parser.add_argument("--jupyter", default=shutil.which("jupyter") or "jupyter")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        ensure_environments(SubprocessRunner(), conda=args.conda, jupyter=args.jupyter)
    except AzureMLSetupError as exc:
        print(f"setup_azureml.py: {exc}", file=sys.stderr)
        return 2
    print("Azure ML kernels are ready:")
    for spec in ENVIRONMENTS:
        print(f"- {spec.display_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

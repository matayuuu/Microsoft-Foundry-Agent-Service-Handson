"""Resolve the two workshop-owned Linux venvs without mixing their SDKs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
MARKER_NAME = ".foundry-workshop-environment.json"


class WorkshopRuntimeError(RuntimeError):
    """An unsafe or incomplete development environment."""


@dataclass(frozen=True)
class EnvironmentSpec:
    name: str
    display_name: str
    purpose: str
    python_version: str
    variable: str


WORKSHOP_ENVIRONMENT = EnvironmentSpec(
    name="foundry-workshop",
    display_name="Python (Foundry Workshop)",
    purpose="root-management-tooling",
    python_version="3.12",
    variable="WORKSHOP_MANAGEMENT_PYTHON",
)
HOSTED_ENVIRONMENT = EnvironmentSpec(
    name="foundry-hosted-agent",
    display_name="Python (Foundry Hosted Agent)",
    purpose="hosted-agent-development",
    python_version="3.13",
    variable="WORKSHOP_HOSTED_PYTHON",
)
ENVIRONMENTS = (WORKSHOP_ENVIRONMENT, HOSTED_ENVIRONMENT)


def environment_path(python: Path, spec: EnvironmentSpec) -> Path:
    """Validate the location, without resolving the venv's interpreter symlink."""
    if not python.is_absolute() or python.parts[-3:] != (spec.name, "bin", "python"):
        raise WorkshopRuntimeError(
            f"{spec.variable} must be an absolute path ending in {spec.name}/bin/python."
        )
    path = python.parent.parent
    resolved = path.resolve()
    repository = REPO_ROOT.resolve()
    if (
        ".venv" in path.parts
        or ".venv" in resolved.parts
        or resolved == repository
        or repository in resolved.parents
        or resolved in repository.parents
        or path.is_symlink()
        or python.parent.is_symlink()
    ):
        raise WorkshopRuntimeError(
            f"Refusing environment path {path}: use a dedicated venv outside the repository; "
            "host .venv directories and linked environment directories are never overwritten."
        )
    return path


def runtime_python(spec: EnvironmentSpec) -> Path:
    value = os.environ.get(spec.variable)
    python = (
        Path.home() / ".venvs" / spec.name / "bin" / "python"
        if value is None
        else Path(value).expanduser()
    )
    environment_path(python, spec)
    return python


def marker_payload(spec: EnvironmentSpec) -> dict[str, str]:
    return {
        "owner": "microsoft-foundry-agent-service-handson",
        "schema_version": "1.0",
        "kind": "venv",
        "name": spec.name,
        "purpose": spec.purpose,
        "python": spec.python_version,
    }


def verify_ownership(path: Path, spec: EnvironmentSpec) -> None:
    marker = path / MARKER_NAME
    try:
        if marker.is_symlink():
            raise ValueError("linked ownership marker")
        actual = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise WorkshopRuntimeError(
            f"{path} exists but is not marked as workshop-owned. "
            "This script will not overwrite it; choose unused paths or a clean Dev Container."
        ) from exc
    if actual != marker_payload(spec):
        raise WorkshopRuntimeError(
            f"{path} has an incompatible ownership or Python version marker; "
            "refusing to overwrite it. Use a clean Dev Container."
        )


def inspect_python_command(python: str | Path) -> list[str]:
    return [
        str(python),
        "-c",
        "import json, sys; print(json.dumps({"
        "'version': '.'.join(map(str, sys.version_info[:2])), "
        "'prefix': sys.prefix, 'base_prefix': sys.base_prefix}))",
    ]


def verify_python(details: Any, spec: EnvironmentSpec, *, path: Path | None = None) -> None:
    if not isinstance(details, dict) or details.get("version") != spec.python_version:
        raise WorkshopRuntimeError(
            f"{spec.name} requires Python {spec.python_version}; "
            f"interpreter reported {details!r}. Rebuild the Dev Container."
        )
    if path is not None and (
        not isinstance(details.get("prefix"), str)
        or not isinstance(details.get("base_prefix"), str)
        or Path(details["prefix"]).resolve() != path.resolve()
        or Path(details["prefix"]).resolve() == Path(details["base_prefix"]).resolve()
    ):
        raise WorkshopRuntimeError(
            f"{spec.name} must run inside its own venv at {path}, not a global/other interpreter."
        )


def _read_interpreter(python: Path) -> Any:
    try:
        result = subprocess.run(
            inspect_python_command(python),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
        return json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        raise WorkshopRuntimeError(
            f"Cannot inspect {python}. Rebuild the Dev Container or rerun "
            "python3.12 scripts/setup_dev_environment.py."
        ) from exc


def get_runtime_python(spec: EnvironmentSpec) -> Path:
    python = runtime_python(spec)
    path = environment_path(python, spec)
    verify_ownership(path, spec)
    if not (path / "pyvenv.cfg").is_file() or not python.is_file():
        raise WorkshopRuntimeError(f"{path} is incomplete. Rerun the Dev Container setup.")
    verify_python(_read_interpreter(python), spec, path=path)
    return python


def require_current_runtime(spec: EnvironmentSpec) -> None:
    python = runtime_python(spec)
    path = environment_path(python, spec)
    verify_ownership(path, spec)
    verify_python(
        {
            "version": ".".join(map(str, sys.version_info[:2])),
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
        },
        spec,
        path=path,
    )

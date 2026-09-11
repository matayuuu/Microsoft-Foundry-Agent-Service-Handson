#!/usr/bin/env python3
"""Check that the Portal ARM artifact matches the Bicep source without modifying it."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class TemplateArtifactError(RuntimeError):
    """The compiled template is missing, invalid, or out of date."""


def parse_template(text: str) -> dict[str, object]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise TemplateArtifactError("ARM template must be a JSON object")
    return value


def compile_template(source: Path) -> dict[str, object]:
    executable = shutil.which("az")
    if executable is None:
        raise TemplateArtifactError("Azure CLI with the pinned Bicep compiler is required")
    completed = subprocess.run(
        [executable, "bicep", "build", "--file", str(source), "--stdout", "--only-show-errors"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode:
        raise TemplateArtifactError(f"Bicep compilation failed: {completed.stderr.strip()}")
    return parse_template(completed.stdout)


def check_artifact(source: Path, artifact: Path) -> None:
    expected = parse_template(artifact.read_text(encoding="utf-8"))
    if compile_template(source) != expected:
        raise TemplateArtifactError(
            "Portal ARM artifact is out of date. Run "
            "'az bicep build --file infra/main.bicep --outfile infra/azuredeploy.json' "
            "with the CI-pinned Bicep version, then commit the generated JSON."
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=REPO_ROOT / "infra" / "main.bicep")
    parser.add_argument("--artifact", type=Path, default=REPO_ROOT / "infra" / "azuredeploy.json")
    args = parser.parse_args(argv)
    try:
        check_artifact(args.source, args.artifact)
    except (OSError, ValueError, TemplateArtifactError) as exc:
        print(f"check_template_artifact.py: {exc}", file=sys.stderr)
        return 2
    print("Portal ARM artifact matches the Bicep source.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

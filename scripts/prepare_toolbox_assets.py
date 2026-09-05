#!/usr/bin/env python3
"""Export local OpenAPI and Skill upload assets for the Portal-first Lab 4.

Only the deployed mock API is read. No Foundry resources are created or updated.
Skills packaging follows Microsoft Learn's Skills preview contract (2026-09-05):
https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import yaml
from create_toolbox import DEFAULT_OPENAPI_PATH, fetch_openapi_spec, mcp_endpoints
from lib.workshop_context import (
    DEFAULT_CONTEXT_PATH,
    DEFAULT_TOOLBOX_NAME,
    REPO_ROOT,
    WorkshopContextError,
    load_context,
    project_endpoint,
    travel_api_base_url,
)

SKILL_NAMES = ("travel-estimation", "preapproval-simulation")
SKILLS_DIR = REPO_ROOT / "data" / "skills"
DEFAULT_OUTPUT_DIR = REPO_ROOT / ".workshop" / "toolbox"


def build_skill_archive(name: str, content: str) -> bytes:
    """Package one validated SKILL.md at the archive root, reproducibly."""
    parts = content.split("---", 2)
    if len(parts) != 3 or parts[0].strip() or not parts[2].strip():
        raise WorkshopContextError(f"{name}: SKILL.md needs front matter and instructions.")
    try:
        metadata = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise WorkshopContextError(f"{name}: invalid SKILL.md front matter.") from exc
    if (
        not isinstance(metadata, dict)
        or metadata.get("name") != name
        or not isinstance(metadata.get("description"), str)
        or not metadata["description"].strip()
    ):
        raise WorkshopContextError(f"{name}: SKILL.md needs a matching name and description.")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        entry = zipfile.ZipInfo("SKILL.md", date_time=(2026, 1, 1, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(entry, content.encode("utf-8"))
    return buffer.getvalue()


def export_assets(
    *,
    spec: dict[str, Any],
    endpoint: str,
    output_dir: Path,
    skills_dir: Path = SKILLS_DIR,
) -> list[Path]:
    """Write upload assets without copying context, credentials, or Terraform state."""
    files: dict[str, bytes] = {
        "travel-ops.openapi.json": json.dumps(spec, ensure_ascii=False, indent=2).encode("utf-8"),
        "portal-values.json": json.dumps(
            {
                "toolbox_name": DEFAULT_TOOLBOX_NAME,
                "tool_name": "travel_ops_api",
                "tool_authentication": "Anonymous",
                "toolbox_mcp_endpoint": mcp_endpoints(endpoint, DEFAULT_TOOLBOX_NAME, "1")[
                    "consumer"
                ],
                "toolbox_audience": "https://ai.azure.com/",
                "skills": list(SKILL_NAMES),
            },
            indent=2,
        ).encode("utf-8"),
    }
    for name in SKILL_NAMES:
        content = (skills_dir / name / "SKILL.md").read_text(encoding="utf-8")
        files[f"{name}.zip"] = build_skill_archive(name, content)

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for filename, content in files.items():
        path = output_dir / filename
        path.write_bytes(content)
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, default=DEFAULT_CONTEXT_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    try:
        context = load_context(args.context)
        spec = fetch_openapi_spec(travel_api_base_url(context), DEFAULT_OPENAPI_PATH)
        paths = export_assets(
            spec=spec,
            endpoint=project_endpoint(context),
            output_dir=args.output_dir,
        )
    except (WorkshopContextError, OSError) as exc:
        print(f"prepare_toolbox_assets.py: {exc}", file=sys.stderr)
        return 2

    for path in paths:
        print(path)
    print("Local assets ready. Create the Toolbox and upload Skills in the Foundry Portal.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

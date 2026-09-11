#!/usr/bin/env python3
"""Build the private Storage download used by Portal and Azure ML labs."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_participant_bundle import BundleError, build_bundle

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTEXT = REPO_ROOT / ".workshop" / "context.json"
DEFAULT_OUTPUT = REPO_ROOT / ".workshop" / "download" / "foundry-workshop-files.zip"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, default=DEFAULT_CONTEXT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        content = build_bundle(
            context_path=args.context,
            portal_assets_dir=args.context.parent / "toolbox",
        )
    except (BundleError, OSError) as exc:
        print(f"prepare_participant_download.py: {exc}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(content)
    print(f"Participant download ready: {args.output.resolve()}")
    print(f"SHA-256: {hashlib.sha256(content).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

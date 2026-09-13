#!/usr/bin/env python3
"""Generate or check the shared GitHub Skill ZIPs and Travel API OpenAPI template."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.lib.common_assets import (
    DEFAULT_OUTPUT_DIR,
    CommonAssetsError,
    build_common_assets,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="Check for drift without writing files."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    try:
        files = build_common_assets()
        if args.check:
            drift = []
            for relative, expected in files.items():
                path = args.output_dir / relative
                if not path.is_file():
                    drift.append(f"Missing asset: {path}")
                elif path.read_bytes() != expected:
                    drift.append(f"Out-of-date asset: {path}")
            if drift:
                print("\n".join(drift), file=sys.stderr)
                print("Regenerate with build_common_assets.py without --check.", file=sys.stderr)
                return 1
            print(f"All {len(files)} common assets match their checked-in sources.")
            return 0

        for relative, content in files.items():
            path = args.output_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            print(path)
    except (CommonAssetsError, OSError) as exc:
        print(f"build_common_assets.py: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())

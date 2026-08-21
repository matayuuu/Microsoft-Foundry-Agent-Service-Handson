#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

sudo apt-get update
sudo apt-get install --yes --no-install-recommends jq
sudo rm -rf /var/lib/apt/lists/*

python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]" -e "./src/travel-api[dev]"

python3.13 -m venv src/hosted-agent/.venv
src/hosted-agent/.venv/bin/python -m pip install --upgrade pip
src/hosted-agent/.venv/bin/python -m pip install -r src/hosted-agent/requirements.txt pytest ruff

printf '\nCodespace ready.\n'
printf 'Next: az login --use-device-code\n'

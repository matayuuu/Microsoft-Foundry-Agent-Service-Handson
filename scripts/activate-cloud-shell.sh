#!/usr/bin/env bash
# Intentionally no `set -euo pipefail`: this file is sourced.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf '%s\n' "Use: source scripts/activate-cloud-shell.sh in EACH Cloud Shell terminal." >&2
  exit 1
fi

_foundry_activate_cloud_shell() {
  local repo venv
  repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)" || return 1
  venv="$(python3 "$repo/scripts/cloud_shell_environment.py" venv --repo-root "$repo")" \
    || return 1
  if [[ ! -x "$venv/bin/python" ]]; then
    printf '%s\n' "Cloud Shell: run bash scripts/setup-cloud-shell.sh first." >&2
    return 1
  fi
  "$venv/bin/python" "$repo/scripts/cloud_shell_environment.py" ready \
    --repo-root "$repo" || return 1
  source "$venv/bin/activate" || return 1
  export AZURE_TOKEN_CREDENTIALS=AzureCliCredential
  export WORKSHOP_CLOUD_SHELL_REPO="$repo"
  export WORKSHOP_PYTHON="$venv/bin/python"
  printf '%s\n' "Cloud Shell provisioning environment activated (AzureCliCredential)."
}

if _foundry_activate_cloud_shell; then
  unset -f _foundry_activate_cloud_shell
else
  unset -f _foundry_activate_cloud_shell
  return 1
fi

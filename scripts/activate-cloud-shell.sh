#!/usr/bin/env bash
# Intentionally no `set -euo pipefail`: this file is sourced by an interactive shell.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf '%s\n' "Use: source scripts/activate-cloud-shell.sh in EACH Cloud Shell terminal. Running it as a child process cannot activate your shell." >&2
  exit 1
fi

_foundry_activate_cloud_shell() {
  local repo tool_path
  repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)" || return 1
  if [[ ! -x "$repo/.venv/bin/python" ]]; then
    printf '%s\n' "Cloud Shell: run bash scripts/setup-cloud-shell.sh first. Existing state was not changed." >&2
    return 1
  fi
  tool_path="$("$repo/.venv/bin/python" "$repo/scripts/cloud_shell_environment.py" paths --repo-root "$repo")" || return 1
  # Only validated, absolute tool directories cross the Python/Bash boundary.
  source "$repo/.venv/bin/activate" || return 1
  export PATH="$repo/.venv/bin:$tool_path:$PATH"
  export AZURE_TOKEN_CREDENTIALS=AzureCliCredential
  export WORKSHOP_CLOUD_SHELL_REPO="$repo"
  export WORKSHOP_PYTHON="$repo/.venv/bin/python"
  printf '%s\n' "Cloud Shell workshop activated (Azure CLI credential, separate Notebook kernels, native Graphviz)."
  printf '%s\n' "Use a dedicated terminal for Jupyter; open New session for shared workshop commands and source this script there too."
}

if _foundry_activate_cloud_shell; then
  unset -f _foundry_activate_cloud_shell
else
  unset -f _foundry_activate_cloud_shell
  return 1
fi

# Sourced helpers: do not change the caller's shell options.

cloud_shell_is_azure_cloud_shell() {
  [[ -n "${ACC_VERSION:-}" || "${AZUREPS_HOST_ENVIRONMENT:-}" == cloud-shell* ]]
}

cloud_shell_venv_directory() {
  local repo="$1"
  python3 "$repo/scripts/cloud_shell_environment.py" venv --repo-root "$repo"
}

cloud_shell_guard() {
  local repo="$1"
  local venv_python
  shift
  if ! cloud_shell_is_azure_cloud_shell; then
    printf '%s\n' "Cloud Shell: provisioning must run in Azure Cloud Shell Bash. No Azure changes were made." >&2
    return 1
  fi
  venv_python="$(cloud_shell_venv_directory "$repo")/bin/python" || return 1
  if [[ "${WORKSHOP_CLOUD_SHELL_REPO:-}" != "$repo" \
    || "${AZURE_TOKEN_CREDENTIALS:-}" != AzureCliCredential \
    || "${WORKSHOP_PYTHON:-}" != "$venv_python" ]]; then
    printf '%s\n' "Cloud Shell: run bash scripts/setup-cloud-shell.sh, then source scripts/activate-cloud-shell.sh in THIS terminal. No Azure changes were made." >&2
    return 1
  fi
  if [[ ! -x "$venv_python" ]]; then
    printf '%s\n' "Cloud Shell: the session-local environment is missing. Re-run setup-cloud-shell.sh; keep the clouddrive repository, .workshop, and Terraform state." >&2
    return 1
  fi
  "$venv_python" "$repo/scripts/cloud_shell_environment.py" ready \
    --repo-root "$repo" || return 1
  if [[ "$#" -gt 0 ]]; then
    "$venv_python" "$repo/scripts/cloud_shell_environment.py" tokens \
      --repo-root "$repo" "$@" || return 1
  fi
}

cloud_shell_python_is_supported() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)' \
    >/dev/null 2>&1
}

cloud_shell_terraform_is_supported() {
  local version major minor
  version="$("$1" version -json 2>/dev/null | jq -r '.terraform_version')" || return 1
  [[ "$version" =~ ^([0-9]+)\.([0-9]+)\.[0-9]+([+-].*)?$ ]] || return 1
  major="${BASH_REMATCH[1]}"
  minor="${BASH_REMATCH[2]}"
  (( major > 1 || (major == 1 && minor >= 10) ))
}

#!/usr/bin/env bash
# Sourced helpers: do not change the caller's shell options.

cloud_shell_guard() {
  local repo="$1"
  shift
  if [[ "${WORKSHOP_CLOUD_SHELL_REPO:-}" != "$repo" || "${AZURE_TOKEN_CREDENTIALS:-}" != AzureCliCredential || "${WORKSHOP_PYTHON:-}" != "$repo/.venv/bin/python" ]]; then
    printf '%s\n' "Cloud Shell: first run bash scripts/setup-cloud-shell.sh, then source scripts/activate-cloud-shell.sh in THIS terminal. No Azure changes were made." >&2
    return 1
  fi
  if [[ ! -x "$repo/.venv/bin/python" ]]; then
    printf '%s\n' "Cloud Shell: root .venv is missing. Re-run setup-cloud-shell.sh; keep Terraform state and .workshop." >&2
    return 1
  fi
  "$repo/.venv/bin/python" "$repo/scripts/cloud_shell_environment.py" ready --repo-root "$repo" || return 1
  if [[ "$#" -gt 0 ]]; then
    "$repo/.venv/bin/python" "$repo/scripts/cloud_shell_environment.py" tokens --repo-root "$repo" "$@" || return 1
  fi
}

cloud_shell_python_is_313() {
  "$1" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 13) and sys.implementation.name == "cpython" else 1)' >/dev/null 2>&1
}

cloud_shell_terraform_is_supported() {
  local version major minor patch
  version="$("$1" version -json 2>/dev/null | jq -r '.terraform_version')" || return 1
  [[ "$version" =~ ^([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] || return 1
  major="${BASH_REMATCH[1]}" minor="${BASH_REMATCH[2]}" patch="${BASH_REMATCH[3]}"
  (( major > 1 || (major == 1 && minor >= 10) )) && [[ -n "$patch" ]]
}

cloud_shell_dot_works() {
  local svg
  svg="$(printf 'digraph workshop { environment -> notebook }\n' | "$1" -Tsvg 2>/dev/null)" || return 1
  [[ "$svg" == *"<svg"* ]]
}

cloud_shell_download() {
  local url="$1" sha256="$2" destination="$3"
  if [[ -L "$destination" || -L "$destination.part" \
    || ( -e "$destination" && ! -f "$destination" ) \
    || ( -e "$destination.part" && ! -f "$destination.part" ) ]]; then
    printf '%s\n' "Cloud Shell: refusing a symlink or non-file entry in the workshop download cache." >&2
    return 1
  fi
  if [[ -f "$destination" ]] && printf '%s  %s\n' "$sha256" "$destination" | sha256sum --check --status; then
    return 0
  fi
  if ! curl --fail --location --silent --show-error --proto '=https' --proto-redir '=https' \
    --connect-timeout 30 --max-time 600 --retry 2 --output "$destination.part" "$url"; then
    printf '%s\n' "Cloud Shell: download failed. Check the approved GitHub/HashiCorp network allow-list and free space, then re-run. Do not bypass organizational policy." >&2
    return 1
  fi
  if ! printf '%s  %s\n' "$sha256" "$destination.part" | sha256sum --check --status; then
    printf '%s\n' "Cloud Shell: download integrity check failed; nothing from this download was executed. Re-run or contact the instructor." >&2
    return 1
  fi
  mv -- "$destination.part" "$destination"
}

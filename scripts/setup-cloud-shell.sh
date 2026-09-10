#!/usr/bin/env bash
# Lightweight, idempotent setup for provisioning and ZIP download only.
set -euo pipefail

START_SECONDS="${SECONDS}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

source "${SCRIPT_DIR}/cloud-shell-common.sh"

if ! cloud_shell_is_azure_cloud_shell; then
  echo "setup-cloud-shell.sh: use Azure Cloud Shell Bash; refusing to continue." >&2
  exit 1
fi

for tool in python3 terraform az jq curl git zip unzip findmnt; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "setup-cloud-shell.sh: Cloud Shell built-in tool '${tool}' is missing." >&2
    exit 1
  fi
done
if ! cloud_shell_python_is_supported "$(command -v python3)"; then
  echo "setup-cloud-shell.sh: built-in Python must be 3.12; no alternate Python is downloaded." >&2
  exit 1
fi
if ! cloud_shell_terraform_is_supported "$(command -v terraform)"; then
  echo "setup-cloud-shell.sh: built-in Terraform >=1.10 is required." >&2
  exit 1
fi

# The first read-only check locates the verified persistent state directory.
STATE_DIR="$(python3 "${SCRIPT_DIR}/cloud_shell_environment.py" storage \
  --repo-root "${REPO_ROOT}" --minimum-free-mib 512)"
if [[ -f "${STATE_DIR}/ready.json" && -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  REQUIRED_FREE_MIB=512
else
  REQUIRED_FREE_MIB=1024
fi
python3 "${SCRIPT_DIR}/cloud_shell_environment.py" storage \
  --repo-root "${REPO_ROOT}" --minimum-free-mib "${REQUIRED_FREE_MIB}" >/dev/null

mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"

if [[ -e "${REPO_ROOT}/.venv" && ! -d "${REPO_ROOT}/.venv" ]]; then
  echo "setup-cloud-shell.sh: refusing non-directory .venv." >&2
  exit 1
fi
if [[ ! -x "${REPO_ROOT}/.venv/bin/python" ]] \
  || ! cloud_shell_python_is_supported "${REPO_ROOT}/.venv/bin/python"; then
  rm -rf "${REPO_ROOT}/.venv"
  python3 -m venv "${REPO_ROOT}/.venv"
fi

"${REPO_ROOT}/.venv/bin/python" -m pip install \
  --disable-pip-version-check \
  --only-binary=:all: \
  -e "${REPO_ROOT}"
"${REPO_ROOT}/.venv/bin/python" -m pip check

DIGEST="$("${REPO_ROOT}/.venv/bin/python" "${SCRIPT_DIR}/cloud_shell_environment.py" \
  digest --repo-root "${REPO_ROOT}")"
READY_PART="${STATE_DIR}/ready.json.part"
if [[ -L "${READY_PART}" || -L "${STATE_DIR}/ready.json" ]]; then
  echo "setup-cloud-shell.sh: refusing symlinked readiness marker." >&2
  exit 1
fi
jq -n \
  --arg repo "${REPO_ROOT}" \
  --arg python "${REPO_ROOT}/.venv/bin/python" \
  --arg dependency_digest "${DIGEST}" \
  --arg python_version "$("${REPO_ROOT}/.venv/bin/python" --version 2>&1)" \
  '{repo: $repo, python: $python, dependency_digest: $dependency_digest,
    python_version: $python_version}' >"${READY_PART}"
chmod 600 "${READY_PART}"
mv -f "${READY_PART}" "${STATE_DIR}/ready.json"

"${REPO_ROOT}/.venv/bin/python" "${SCRIPT_DIR}/cloud_shell_environment.py" ready \
  --repo-root "${REPO_ROOT}"

cat <<'EOF'
Cloud Shell provisioning setup is ready.
Activate this terminal before provisioning:
  source scripts/activate-cloud-shell.sh
No Jupyter, notebook kernels, Hosted Agent environment, Graphviz, or web preview was installed.
EOF
printf 'Provisioning-only environment preparation: %ss\n' "$((SECONDS - START_SECONDS))"

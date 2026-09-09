#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  cat <<'EOF'
Usage: bash scripts/setup-cloud-shell.sh

Prepare this repository in Azure Cloud Shell Bash with mounted persistent storage.
Installs only local workshop tools/dependencies; never logs in or changes Azure.
Requires Linux amd64, a persisted Unix HOME (not clouddrive), and 3 GiB free for
initial setup (512 MiB on a prepared environment). Existing venvs must use Python
3.13. Re-run this command after interruption; state/context are never deleted.

For notebooks, run:
  bash scripts/start-cloud-shell-jupyter.sh
The launcher activates this environment itself. In separate command terminals,
run `source scripts/activate-cloud-shell.sh` before shared workshop commands.
EOF
  exit 0
fi
if [[ "$#" -ne 0 ]]; then
  printf '%s\n' "Unknown argument. Use --help; this bootstrap does not accept Azure resource inputs." >&2
  exit 2
fi
source "$REPO_ROOT/scripts/cloud-shell-common.sh"

for tool in az jq curl git python3 findmnt tar sha256sum unzip flock; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf "Cloud Shell: required built-in tool '%s' is missing. Reopen Azure Cloud Shell Bash or contact the instructor; do not change the system installation.\n" "$tool" >&2
    exit 1
  fi
done

# Inspect mounts before creating even local installation files. A directory named
# clouddrive does not prove that HOME, the repository, or Terraform state persists.
STATE_DIR="$(python3 "$REPO_ROOT/scripts/cloud_shell_environment.py" storage --repo-root "$REPO_ROOT")"
MINIMUM_MIB=3072
if [[ -f "$STATE_DIR/ready.json" ]]; then MINIMUM_MIB=512; fi
python3 "$REPO_ROOT/scripts/cloud_shell_environment.py" storage \
  --repo-root "$REPO_ROOT" --minimum-free-mib "$MINIMUM_MIB" >/dev/null

for environment in "$REPO_ROOT/.venv" "$REPO_ROOT/src/hosted-agent/.venv"; do
  if [[ -L "$environment" ]] || { [[ -e "$environment" ]] && ! cloud_shell_python_is_313 "$environment/bin/python"; }; then
    printf 'Cloud Shell: existing %s must be a separate CPython 3.13 venv. It was not changed. If incomplete, move only this venv aside, then retry; retain all workshop/Terraform state.\n' "$environment" >&2
    exit 1
  fi
done
for directory in "$STATE_DIR/downloads" "$STATE_DIR/build" "$STATE_DIR/pip-cache" \
  "$STATE_DIR/python-3.13.15-20260901" "$STATE_DIR/terraform-1.10.5" \
  "$STATE_DIR/graphviz-14.1.2" "$STATE_DIR/mamba"; do
  if [[ -L "$directory" || ( -e "$directory" && ! -d "$directory" ) ]]; then
    printf 'Cloud Shell: tool directory %s must not be a symlink or regular file. Existing files were not changed.\n' "$directory" >&2
    exit 1
  fi
done

umask 077
mkdir -p -- "$STATE_DIR/downloads" "$STATE_DIR/build"
chmod 700 "$STATE_DIR"
exec 9>"$STATE_DIR/bootstrap.lock"
if ! flock --nonblock 9; then
  printf '%s\n' "Cloud Shell: another bootstrap is running for this repository. Wait for it; do not remove its lock." >&2
  exit 1
fi
export TMPDIR="$STATE_DIR/build"
export PIP_CACHE_DIR="$STATE_DIR/pip-cache"
export PIP_DISABLE_PIP_VERSION_CHECK=1
trap 'printf "%s\n" "Cloud Shell setup did not finish. Check the error, available HOME space, and approved package access; re-run the same command. Existing venvs, .workshop, and Terraform state are preserved." >&2' ERR
trap 'printf "%s\n" "Cloud Shell setup interrupted. Re-run the same command to resume local installation; do not delete workshop state." >&2; exit 130' INT TERM

PYTHON_BIN=""
for candidate in "$REPO_ROOT/.venv/bin/python" python3.13 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && cloud_shell_python_is_313 "$candidate"; then
    PYTHON_BIN="$(command -v "$candidate")"
    break
  fi
done

# The same relocatable CPython distribution used by uv, fetched directly so a
# second Python installer is unnecessary. Pin + SHA from uv 0.12.11's official
# download-metadata.json, retrieved 2026-09-09. No compiler or system changes.
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_PREFIX="$STATE_DIR/python-3.13.15-20260901"
  PYTHON_BIN="$PYTHON_PREFIX/bin/python3.13"
  if ! cloud_shell_python_is_313 "$PYTHON_BIN"; then
    PYTHON_ARCHIVE="$STATE_DIR/downloads/cpython-3.13.15-20260901.tar.gz"
    cloud_shell_download \
      "https://github.com/astral-sh/python-build-standalone/releases/download/20260901/cpython-3.13.15%2B20260901-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz" \
      "8a689a077337bea6d1c4bc0b7df1d52fcaa28f5f67e50df8bf417c1e3f9d8874" "$PYTHON_ARCHIVE"
    mkdir -p -- "$PYTHON_PREFIX"
    tar --extract --gzip --file "$PYTHON_ARCHIVE" --directory "$PYTHON_PREFIX" --strip-components=1
    cloud_shell_python_is_313 "$PYTHON_BIN"
  fi
fi

TOOL_DIRECTORIES=()
TERRAFORM_BIN="$(command -v terraform || true)"
if [[ -z "$TERRAFORM_BIN" ]] || ! cloud_shell_terraform_is_supported "$TERRAFORM_BIN"; then
  TERRAFORM_DIRECTORY="$STATE_DIR/terraform-1.10.5/bin"
  TERRAFORM_BIN="$TERRAFORM_DIRECTORY/terraform"
  if ! cloud_shell_terraform_is_supported "$TERRAFORM_BIN"; then
    cloud_shell_download \
      "https://releases.hashicorp.com/terraform/1.10.5/terraform_1.10.5_linux_amd64.zip" \
      "0566a24f5332098b15716ebc394be503f4094acba5ba529bf5eb0698ed5e2a90" \
      "$STATE_DIR/downloads/terraform-1.10.5.zip"
    mkdir -p -- "$TERRAFORM_DIRECTORY"
    unzip -p "$STATE_DIR/downloads/terraform-1.10.5.zip" terraform > "$TERRAFORM_BIN.part"
    chmod 700 "$TERRAFORM_BIN.part"
    cloud_shell_terraform_is_supported "$TERRAFORM_BIN.part"
    mv -- "$TERRAFORM_BIN.part" "$TERRAFORM_BIN"
  fi
fi
TOOL_DIRECTORIES+=("$(dirname "$TERRAFORM_BIN")")

DOT_BIN="$(command -v dot || true)"
if [[ -z "$DOT_BIN" ]] || ! cloud_shell_dot_works "$DOT_BIN"; then
  GRAPHVIZ_PREFIX="$STATE_DIR/graphviz-14.1.2"
  DOT_BIN="$GRAPHVIZ_PREFIX/bin/dot"
  if ! cloud_shell_dot_works "$DOT_BIN"; then
    # Official micromamba release digest and conda-forge Linux build verified
    # 2026-09-09. --no-rc/--no-env isolates this from a user's conda configuration.
    MICROMAMBA="$STATE_DIR/micromamba-2.9.0"
    cloud_shell_download \
      "https://github.com/mamba-org/micromamba-releases/releases/download/2.9.0-0/micromamba-linux-64" \
      "366cd9cd8be14df1ab8ed50352a82111082a36686b2d389fdb79a92c3fafb3e3" "$MICROMAMBA"
    chmod 700 "$MICROMAMBA"
    MAMBA_ACTION=create
    if [[ -d "$GRAPHVIZ_PREFIX/conda-meta" ]]; then MAMBA_ACTION=install; fi
    "$MICROMAMBA" --no-rc --no-env "$MAMBA_ACTION" --yes \
      --root-prefix "$STATE_DIR/mamba" --prefix "$GRAPHVIZ_PREFIX" \
      --override-channels --channel https://conda.anaconda.org/conda-forge \
      --strict-channel-priority 'graphviz=14.1.2=h8b86629_0'
    "$PYTHON_BIN" - "$GRAPHVIZ_PREFIX" <<'PY'
import json
import sys
from pathlib import Path
metadata = json.loads((Path(sys.argv[1]) / "conda-meta/graphviz-14.1.2-h8b86629_0.json").read_text())
if metadata.get("sha256") != "48d4aae8d2f7dd038b8c2b6a1b68b7bca13fa6b374b78c09fcc0757fa21234a1":
    raise SystemExit("Cloud Shell: Graphviz package checksum metadata did not match the approved build.")
PY
    cloud_shell_dot_works "$DOT_BIN"
  fi
fi
TOOL_DIRECTORIES+=("$(dirname "$DOT_BIN")")

prepare_venv() {
  local environment="$1" name="$2" digest stamp
  if [[ -L "$environment" ]]; then
    printf 'Cloud Shell: %s must be a separate, non-symlink venv. Existing files were not changed.\n' "$environment" >&2
    return 1
  fi
  if [[ -e "$environment" ]]; then
    if ! cloud_shell_python_is_313 "$environment/bin/python"; then
      printf 'Cloud Shell: existing %s is incomplete or not CPython 3.13. Keep it untouched for diagnosis; move ONLY that venv aside before retrying. Never move/delete .workshop or Terraform state.\n' "$environment" >&2
      return 1
    fi
  else
    "$PYTHON_BIN" -m venv "$environment"
  fi
  digest="$("$PYTHON_BIN" "$REPO_ROOT/scripts/cloud_shell_environment.py" digest --repo-root "$REPO_ROOT" --environment "$name")"
  stamp="$environment/.cloud-shell-dependencies.sha256"
  local modules="azure.identity,azure.ai.projects,ipykernel,pytest,ruff"
  if [[ "$name" == root ]]; then modules+=",jupyterlab,jupyter_server"; fi
  if [[ -f "$stamp" && "$(cat "$stamp")" == "$digest" ]] \
    && "$environment/bin/python" -m pip check >/dev/null 2>&1 \
    && "$environment/bin/python" -c 'import importlib.util, sys; sys.exit(any(importlib.util.find_spec(name) is None for name in sys.argv[1].split(",")))' "$modules" >/dev/null 2>&1; then
    printf 'Reusing %s dependencies.\n' "$name"
    return 0
  fi
  if [[ "$name" == root ]]; then
    "$environment/bin/python" -m pip install --only-binary=:all: \
      -e "$REPO_ROOT[dev,cloud-shell]" -e "$REPO_ROOT/src/travel-api[dev]"
  else
    "$environment/bin/python" -m pip install --only-binary=:all: \
      -r "$REPO_ROOT/src/hosted-agent/requirements.txt" pytest ruff ipykernel
  fi
  "$environment/bin/python" -m pip check
  printf '%s\n' "$digest" > "$stamp.part"
  mv -- "$stamp.part" "$stamp"
}

prepare_venv "$REPO_ROOT/.venv" root
prepare_venv "$REPO_ROOT/src/hosted-agent/.venv" hosted
"$REPO_ROOT/.venv/bin/python" -m ipykernel install --prefix "$REPO_ROOT/.venv" \
  --name foundry-workshop --display-name "Python (Foundry Workshop)"
"$REPO_ROOT/src/hosted-agent/.venv/bin/python" -m ipykernel install --prefix "$REPO_ROOT/.venv" \
  --name foundry-hosted-agent --display-name "Python (Foundry Hosted Agent)"

"$REPO_ROOT/.venv/bin/python" - "$REPO_ROOT" "$STATE_DIR" "$DOT_BIN" "${TOOL_DIRECTORIES[@]}" <<'PY'
import json
import sys
from pathlib import Path
repo, state = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(repo / "scripts"))
from cloud_shell_environment import dependency_digest, validate_environments
validate_environments(repo)
ready = {
    "repo": str(repo),
    "dot": sys.argv[3],
    "tool_directories": list(dict.fromkeys(sys.argv[4:])),
    "dependencies": {name: dependency_digest(repo, name) for name in ("root", "hosted")},
}
staging = state / "ready.json.part"
staging.write_text(json.dumps(ready, indent=2) + "\n")
staging.replace(state / "ready.json")
PY
trap - ERR INT TERM
printf '\nCloud Shell dependencies and both Python 3.13 kernels are ready. No Azure resources were changed.\n'
printf 'In EACH workshop terminal run:\n  source "%s/scripts/activate-cloud-shell.sh"\n' "$REPO_ROOT"
printf 'Notebook launcher: bash scripts/start-cloud-shell-jupyter.sh\n'
printf 'For shared commands in another terminal: source scripts/activate-cloud-shell.sh\n'

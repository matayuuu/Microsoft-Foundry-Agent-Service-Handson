#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  cat <<'EOF'
Usage:
  bash scripts/start-cloud-shell-jupyter.sh [--port 5000]
  bash scripts/start-cloud-shell-jupyter.sh --discover-preview [--port 5000]
  bash scripts/start-cloud-shell-jupyter.sh --preview-url 'https://ACTUAL-PREVIEW-HOST/' [options]

The default command prepares or reuses all dependencies, asks for one private
password, and waits for you to open the same port with Web preview > Open and
browse. The browser detects its actual HTTPS URL and reloads into JupyterLab.
There is no URL copy, Ctrl-C, or second launch command.

The explicit --discover-preview / --preview-url modes remain available only for
troubleshooting. No hostname is guessed from environment variables.

Options:
  --port <port>            1025-8079 or 8091-49151; default 5000, never auto-increments.
  --base-url </path/>       Only for an observed proxy path/rewrite.
  --listen <address>        Default 127.0.0.1. If the real preview cannot reach
                            loopback, explicitly retry with 0.0.0.0.

Choose a private password at the hidden prompt (at least 12 characters), or set
JUPYTER_TOKEN_FILE to a known, user-owned 0600 token file outside the repository.
Tokens are never printed. Authentication, Host/Origin checks, and XSRF stay on.
Use a dedicated Jupyter terminal and New session for shared workshop commands.
Stop by saving notebooks, Ctrl-C/confirmation, then closing the Web preview port.
Restart by running the same default command and opening the current preview port.
EOF
  exit 0
fi
bash "$REPO_ROOT/scripts/setup-cloud-shell.sh"
source "$REPO_ROOT/scripts/activate-cloud-shell.sh"
cd "$REPO_ROOT"
exec "$REPO_ROOT/.venv/bin/python" -m scripts.cloud_shell_jupyter "$@"

"""Hermetic, mocked-`curl` contract tests for scripts/setup.sh's optional
`--travel-api-image-ref` / anonymous-GHCR-digest-resolution behavior.

These tests never call real ghcr.io. They extract the CLI-parsing + image/
source-base resolution prefix of the real scripts/setup.sh (everything
before "Step 1: preflight", located dynamically by a stable marker string
rather than a hardcoded line number, so this test tracks the real file even
as it grows) into an isolated fixture repo, and prepend a fake `curl` shell
*function* (not a PATH executable -- exec'ing a shebang script found via
PATH proved unreliable under this Windows/Git-Bash environment, silently
falling through to the real system `curl.exe` instead; a function
definition is looked up by bash before PATH search and is therefore
reliable) that returns canned GHCR OCI registry responses selected via
environment variables, plus no-op `az`/`terraform`/`python3` functions
purely so setup.sh's own `command -v` tool-availability check passes --
none of the three is ever actually invoked before the cut point. The real
`jq` and `git` are used unmodified (jq does no network I/O; git resolves
against the fixture's own, non-git tmp_path, so it always hits the same
documented `matayuuu` git-remote-derivation fallback, keeping these tests
independent of the real development machine's git remote).

They assert the behaviors required by AGENTS.md and the one-command
GHCR-digest hardening pass:

* `--travel-api-image-ref` is optional; when given explicitly, resolution
  is skipped entirely (no curl/ghcr.io calls happen).
* When omitted, the default `ghcr.io/<owner>/travel-ops-api:v1.0.2` (or an
  explicit `--travel-api-image-repo`/`--travel-api-image-tag` override) is
  resolved to an immutable `@sha256:<digest>` reference via curl+jq.
* Both distinct "not anonymously pullable yet" GHCR failure modes --  a
  denied/empty token response (private or nonexistent repository) and a
  404 at the manifest step (public repository, but the tag does not exist)
  -- fail with exit code 2 and print an admin-facing publish instruction,
  strictly before Terraform would ever run. Neither ever falls back to a
  mutable tag.
* `--subscription`/`--resource-group` remain the only required arguments;
  `--help` documents all the new flags.

Requires `bash`, `jq`, and `git` on PATH; skipped automatically otherwise
(this workshop's participant/admin scripts target a Linux devcontainer/
Codespace where all three are expected to be present).
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP_SH = REPO_ROOT / "scripts" / "setup.sh"

BASH = shutil.which("bash")
JQ = shutil.which("jq")
GIT = shutil.which("git")

pytestmark = pytest.mark.skipif(
    BASH is None or JQ is None or GIT is None,
    reason="hermetic setup.sh contract tests require 'bash', 'jq', and 'git' on PATH",
)

# The marker that begins Step 1 (preflight) in the real script -- everything
# before this line is pure CLI-parsing/argument-validation/image- and
# source-base-resolution logic with no Azure/Terraform side effects, so it
# is safe to extract and execute in isolation.
STEP_1_MARKER = 'echo "==> [1/5]'

FAKE_DIGEST_HEX = hashlib.sha256(b"setup.sh contract test fixture").hexdigest()
FAKE_DIGEST = f"sha256:{FAKE_DIGEST_HEX}"

# Injected as bash *functions* -- not PATH executables -- at the top of the
# extracted script. Function lookup happens before PATH search in bash, so
# this reliably shadows any real `curl`/`az`/`terraform`/`python3` binary
# regardless of PATH ordering or shebang-exec quirks. `az`/`terraform`/
# `python3` are only ever probed with `command -v` (never executed) before
# the cut point, so their bodies are irrelevant no-ops; `curl` is the only
# one actually invoked, by resolve_ghcr_digest().
FAKE_TOOLS_PREAMBLE = r"""
az() { return 0; }
terraform() { return 0; }
python3() { return 0; }
curl() {
  local last_arg="${!#}"
  case "${last_arg}" in
    https://ghcr.io/token\?scope=*)
      case "${FAKE_CURL_TOKEN_MODE:-success}" in
        success)
          echo '{"token":"fake-anonymous-pull-token"}'
          ;;
        denied)
          echo '{"errors":[{"code":"DENIED",'\
'"message":"requested access to the resource is denied"}]}'
          ;;
        network-fail)
          return 7
          ;;
        *)
          echo "fake-curl: unknown FAKE_CURL_TOKEN_MODE: ${FAKE_CURL_TOKEN_MODE}" >&2
          return 1
          ;;
      esac
      ;;
    https://ghcr.io/v2/*/manifests/*)
      case "${FAKE_CURL_MANIFEST_MODE:-found}" in
        found)
          printf 'HTTP/1.1 200 OK\r\ndocker-content-digest: %s\r\n\r\n' \
            "${FAKE_CURL_DIGEST:-__DIGEST__}"
          ;;
        not-found)
          printf 'HTTP/1.1 404 Not Found\r\n\r\n'
          ;;
        server-error)
          printf 'HTTP/1.1 500 Internal Server Error\r\n\r\n'
          ;;
        missing-digest-header)
          printf 'HTTP/1.1 200 OK\r\n\r\n'
          ;;
        network-fail)
          return 7
          ;;
        *)
          echo "fake-curl: unknown FAKE_CURL_MANIFEST_MODE: ${FAKE_CURL_MANIFEST_MODE}" >&2
          return 1
          ;;
      esac
      ;;
    *)
      echo "fake-curl: unhandled URL: ${last_arg}" >&2
      return 1
      ;;
  esac
}
""".replace("__DIGEST__", FAKE_DIGEST)


@pytest.fixture
def extracted_setup_head(tmp_path: Path) -> Path:
    """Extract everything in the real setup.sh strictly before Step 1
    (preflight) into an isolated, non-git fixture "repo", preserving the
    real scripts/<name> relative layout so SCRIPT_DIR/REPO_ROOT resolve the
    same way they do in production. The fixture repo deliberately has no
    .git directory, so `git remote get-url origin` always fails there,
    deterministically exercising the script's own documented
    "matayuuu"/fixed-fallback-URL fallback path regardless of this
    development machine's real git remote configuration.
    """
    lines = SETUP_SH.read_text(encoding="utf-8").splitlines(keepends=True)
    cut_index = next(i for i, line in enumerate(lines) if STEP_1_MARKER in line)
    head_text = "".join(lines[:cut_index])
    assert "resolve_ghcr_digest" in head_text, (
        "extracted head must still include resolve_ghcr_digest(); "
        "STEP_1_MARKER may be stale relative to scripts/setup.sh"
    )
    # Inject the fake-tool functions right after the shebang line, ahead of
    # `set -euo pipefail` and everything else, so they are defined before
    # the tool-availability check and resolve_ghcr_digest() ever run.
    shebang, _, rest = head_text.partition("\n")
    head_text = f"{shebang}\n{FAKE_TOOLS_PREAMBLE}\n{rest}"

    fixture_scripts_dir = tmp_path / "fixture-repo" / "scripts"
    fixture_scripts_dir.mkdir(parents=True)
    extracted_path = fixture_scripts_dir / "setup_head.sh"
    extracted_path.write_text(head_text, encoding="utf-8", newline="\n")
    extracted_path.chmod(extracted_path.stat().st_mode | stat.S_IEXEC)
    return extracted_path


def _run_setup_head(
    extracted_setup_head: Path,
    args: list[str],
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update(env_overrides or {})
    return subprocess.run(
        [BASH, str(extracted_setup_head), *args],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(extracted_setup_head.parent),
    )


DEFAULT_ARGS = ["--subscription", "sub-1", "--resource-group", "rg-1"]


def test_explicit_image_ref_bypasses_resolution_entirely(
    extracted_setup_head: Path,
) -> None:
    explicit_ref = f"ghcr.io/some-org/travel-ops-api@{FAKE_DIGEST}"
    result = _run_setup_head(
        extracted_setup_head,
        [*DEFAULT_ARGS, "--travel-api-image-ref", explicit_ref],
        # No FAKE_CURL_* vars set: if resolution were attempted anyway, the
        # fake curl would still respond successfully (default "success"/
        # "found" modes), so absence of the "Resolving immutable digest"
        # log line is what actually proves resolution was skipped.
    )
    assert result.returncode == 0, result.stderr
    assert "Resolving immutable digest" not in result.stderr
    assert "Using --source-base:" in result.stderr


def test_auto_resolves_default_repo_tag_when_ref_omitted(
    extracted_setup_head: Path,
) -> None:
    result = _run_setup_head(
        extracted_setup_head,
        DEFAULT_ARGS,
        {"FAKE_CURL_TOKEN_MODE": "success", "FAKE_CURL_MANIFEST_MODE": "found"},
    )
    assert result.returncode == 0, result.stderr
    assert f"Resolved: ghcr.io/matayuuu/travel-ops-api@{FAKE_DIGEST}" in result.stderr, (
        result.stderr
    )


def test_repo_and_tag_override_used_when_ref_omitted(
    extracted_setup_head: Path,
) -> None:
    result = _run_setup_head(
        extracted_setup_head,
        [
            *DEFAULT_ARGS,
            "--travel-api-image-repo",
            "ghcr.io/other-org/travel-ops-api",
            "--travel-api-image-tag",
            "v9.9.9",
        ],
        {"FAKE_CURL_TOKEN_MODE": "success", "FAKE_CURL_MANIFEST_MODE": "found"},
    )
    assert result.returncode == 0, result.stderr
    assert f"Resolved: ghcr.io/other-org/travel-ops-api@{FAKE_DIGEST}" in result.stderr, (
        result.stderr
    )


def test_denied_token_fails_before_terraform_with_admin_instructions(
    extracted_setup_head: Path,
) -> None:
    """The token endpoint itself denies (empty/missing token) for a private
    or nonexistent repository -- this must fail the same way a 404-at-
    manifest case does: exit 2, admin-facing publish instructions, never a
    mutable-tag fallback."""
    result = _run_setup_head(
        extracted_setup_head,
        DEFAULT_ARGS,
        {"FAKE_CURL_TOKEN_MODE": "denied"},
    )
    assert result.returncode == 2, result.stderr
    assert "not publicly pullable yet" in result.stderr
    assert "travel-api-v<version>" in result.stderr
    assert "Package settings" in result.stderr
    assert "Resolved:" not in result.stderr


def test_tag_not_found_on_existing_public_repo_fails_the_same_way(
    extracted_setup_head: Path,
) -> None:
    """A public repository whose specific tag does not exist fails at the
    manifest (404) step, not the token step -- must be unified with the
    denied-token case into the identical exit-2/admin-instructions path."""
    result = _run_setup_head(
        extracted_setup_head,
        DEFAULT_ARGS,
        {"FAKE_CURL_TOKEN_MODE": "success", "FAKE_CURL_MANIFEST_MODE": "not-found"},
    )
    assert result.returncode == 2, result.stderr
    assert "not publicly pullable yet" in result.stderr
    assert "Resolved:" not in result.stderr


def test_never_falls_back_to_a_mutable_tag_on_unexpected_manifest_error(
    extracted_setup_head: Path,
) -> None:
    result = _run_setup_head(
        extracted_setup_head,
        DEFAULT_ARGS,
        {"FAKE_CURL_TOKEN_MODE": "success", "FAKE_CURL_MANIFEST_MODE": "server-error"},
    )
    assert result.returncode == 2, result.stderr
    assert "aborting rather than falling back to a mutable tag" in result.stderr
    assert "Resolved:" not in result.stderr


def test_missing_required_args_still_fails_with_usage(
    extracted_setup_head: Path,
) -> None:
    result = _run_setup_head(extracted_setup_head, [])
    assert result.returncode == 1
    assert "--subscription and --resource-group are both required" in result.stderr
    assert "Usage: setup.sh" in result.stderr


def test_help_documents_optional_image_ref_and_new_flags(
    extracted_setup_head: Path,
) -> None:
    result = _run_setup_head(extracted_setup_head, ["--help"])
    assert result.returncode == 0
    assert "--travel-api-image-repo" in result.stdout
    assert "--travel-api-image-tag" in result.stdout
    assert "OPTIONAL" in result.stdout
    assert "anonymous GHCR OCI registry lookup" in result.stdout


def test_explicit_ref_with_repo_override_warns_but_still_bypasses_resolution(
    extracted_setup_head: Path,
) -> None:
    explicit_ref = f"ghcr.io/some-org/travel-ops-api@{FAKE_DIGEST}"
    result = _run_setup_head(
        extracted_setup_head,
        [
            *DEFAULT_ARGS,
            "--travel-api-image-ref",
            explicit_ref,
            "--travel-api-image-repo",
            "ghcr.io/ignored/travel-ops-api",
        ],
    )
    assert result.returncode == 0, result.stderr
    assert "are ignored because --travel-api-image-ref was given explicitly" in result.stderr
    assert "Resolving immutable digest" not in result.stderr

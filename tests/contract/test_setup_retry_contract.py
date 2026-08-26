"""Hermetic contract tests for scripts/setup.sh's `retry()` helper.

`retry()` is the bounded-retry mechanism that wraps Terraform apply,
bootstrap_data.py (Step 3), and validate_environment.py (Step 4) invocations
in the real script. Terraform retries must refresh a plan after a partial apply
changes state, while data-plane retries absorb fresh RBAC propagation delays.
Steps 3-6 themselves require a full Terraform-apply context (real
`.workshop/context.json`, populated `TF_OUTPUTS_JSON`, etc.) that is not
practical to fake hermetically, so this test does not execute those steps
directly. Instead -- following the same "extract the real script and inject
fake tools" technique already used by test_setup_travel_api_image_contract.py
-- it extracts the real `retry()` function definition itself (which lives in
the CLI-parsing/argument-validation prefix, strictly before "Step 1:
preflight", so it is included by the exact same STEP_1_MARKER cut point) and
exercises it directly against a small in-fixture "flaky command" so the
actual bounded-retry/backoff/error-visibility semantics are verified against
the real script text, without ever touching Azure, Terraform, or the network.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SETUP_SH = REPO_ROOT / "scripts" / "setup.sh"

BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    BASH is None,
    reason="hermetic setup.sh retry() contract tests require 'bash' on PATH",
)

# Same marker as test_setup_travel_api_image_contract.py: everything before
# this line is pure CLI-parsing/argument-validation/image- and source-base-
# resolution logic plus the retry() helper definition itself, with no
# Azure/Terraform side effects, so it is safe to extract and execute.
STEP_1_MARKER = 'echo "==> [1/5]'

# An explicit --travel-api-image-ref bypasses the (unrelated) anonymous GHCR
# digest resolution entirely, so this harness never makes a real network
# call -- it only cares about retry()'s own behavior, defined further down
# in the same extracted prefix.
DEFAULT_ARGS = [
    "--subscription",
    "sub-1",
    "--resource-group",
    "rg-1",
    "--travel-api-image-ref",
    "ghcr.io/some-org/travel-ops-api@sha256:"
    "0000000000000000000000000000000000000000000000000000000000000000",
]

# Appended after the extracted head so retry() (already defined by then) can
# be exercised against a fake flaky command whose behavior is driven purely
# by environment variables the test controls. `sleep 0` (RETRY_SLEEP=0 below)
# keeps the tests fast; retry()'s own signature is `retry <attempts> <sleep>
# -- <command...>`.
RETRY_HARNESS_FOOTER = r"""
flaky_cmd() {
  local n
  n="$(cat "${COUNTER_FILE}")"
  n=$((n + 1))
  echo "${n}" >"${COUNTER_FILE}"
  if [[ ${n} -ge ${SUCCEED_ON_ATTEMPT} ]]; then
    echo "flaky_cmd: succeeded on attempt ${n}"
    return 0
  fi
  echo "flaky_cmd: failed on attempt ${n}" >&2
  return 1
}

if retry "${RETRY_MAX_ATTEMPTS}" 0 flaky_cmd; then
  echo "RETRY_RESULT=success"
else
  echo "RETRY_RESULT=failure"
fi
echo "RETRY_ATTEMPTS=$(cat "${COUNTER_FILE}")"
"""

TERRAFORM_RETRY_HARNESS_FOOTER = r"""
terraform() {
  local action=""
  local arg
  for arg in "$@"; do
    if [[ "${arg}" == "plan" || "${arg}" == "apply" ]]; then
      action="${arg}"
      break
    fi
  done
  if [[ -z "${action}" ]]; then
    echo "fake terraform: no plan/apply action found: $*" >&2
    return 1
  fi

  echo "${action}" >>"${TERRAFORM_SEQUENCE_FILE}"
  if [[ "${action}" == "apply" && "$(grep -c '^apply$' "${TERRAFORM_SEQUENCE_FILE}")" -eq 1 ]]; then
    echo "fake terraform: simulated partial apply failure" >&2
    return 1
  fi
  return 0
}

TF_VAR_ARGS=(-var "example=value")
if retry 3 0 apply_terraform_plan; then
  echo "TERRAFORM_RETRY_RESULT=success"
else
  echo "TERRAFORM_RETRY_RESULT=failure"
fi
"""


def _extracted_setup_head() -> str:
    lines = SETUP_SH.read_text(encoding="utf-8").splitlines(keepends=True)
    cut_index = next(i for i, line in enumerate(lines) if STEP_1_MARKER in line)
    head_text = "".join(lines[:cut_index])
    return head_text.replace(
        "for tool in az terraform jq curl git; do",
        "for tool in true; do",
    )


@pytest.fixture
def extracted_setup_head_with_retry_harness(tmp_path: Path) -> Path:
    head_text = _extracted_setup_head()
    assert "retry()" in head_text, (
        "extracted head must still include the retry() helper definition; "
        "STEP_1_MARKER or retry()'s position may be stale relative to "
        "scripts/setup.sh"
    )

    fixture_scripts_dir = tmp_path / "fixture-repo" / "scripts"
    fixture_scripts_dir.mkdir(parents=True)
    extracted_path = fixture_scripts_dir / "setup_retry_harness.sh"
    extracted_path.write_text(head_text + RETRY_HARNESS_FOOTER, encoding="utf-8", newline="\n")
    extracted_path.chmod(extracted_path.stat().st_mode | stat.S_IEXEC)
    return extracted_path


@pytest.fixture
def extracted_setup_head_with_terraform_retry_harness(tmp_path: Path) -> Path:
    head_text = _extracted_setup_head()
    assert "apply_terraform_plan()" in head_text

    fixture_scripts_dir = tmp_path / "fixture-repo" / "scripts"
    fixture_scripts_dir.mkdir(parents=True)
    extracted_path = fixture_scripts_dir / "setup_terraform_retry_harness.sh"
    extracted_path.write_text(
        head_text + TERRAFORM_RETRY_HARNESS_FOOTER,
        encoding="utf-8",
        newline="\n",
    )
    extracted_path.chmod(extracted_path.stat().st_mode | stat.S_IEXEC)
    return extracted_path


def _run_harness(
    extracted_setup_head_with_retry_harness: Path,
    counter_file: Path,
    *,
    succeed_on_attempt: int,
    max_attempts: int,
) -> subprocess.CompletedProcess[str]:
    counter_file.write_text("0", encoding="utf-8")
    env = dict(os.environ)
    env.update(
        {
            "COUNTER_FILE": str(counter_file),
            "SUCCEED_ON_ATTEMPT": str(succeed_on_attempt),
            "RETRY_MAX_ATTEMPTS": str(max_attempts),
        }
    )
    return subprocess.run(
        [BASH, str(extracted_setup_head_with_retry_harness), *DEFAULT_ARGS],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(extracted_setup_head_with_retry_harness.parent),
    )


def test_retry_succeeds_immediately_without_retrying(
    extracted_setup_head_with_retry_harness: Path, tmp_path: Path
) -> None:
    result = _run_harness(
        extracted_setup_head_with_retry_harness,
        tmp_path / "counter.txt",
        succeed_on_attempt=1,
        max_attempts=3,
    )
    assert result.returncode == 0, result.stderr
    assert "RETRY_RESULT=success" in result.stdout
    assert "RETRY_ATTEMPTS=1" in result.stdout
    assert "retrying in" not in result.stderr


def test_retry_recovers_after_transient_failures(
    extracted_setup_head_with_retry_harness: Path, tmp_path: Path
) -> None:
    result = _run_harness(
        extracted_setup_head_with_retry_harness,
        tmp_path / "counter.txt",
        succeed_on_attempt=3,
        max_attempts=5,
    )
    assert result.returncode == 0, result.stderr
    assert "RETRY_RESULT=success" in result.stdout
    assert "RETRY_ATTEMPTS=3" in result.stdout
    # Two transient failures (attempts 1 and 2) before the attempt-3 success,
    # and each one's error is still visible, not swallowed.
    assert result.stderr.count("retrying in") == 2
    assert "attempt 1 failed" in result.stderr
    assert "attempt 2 failed" in result.stderr


def test_retry_gives_up_after_bounded_attempts_and_surfaces_failure(
    extracted_setup_head_with_retry_harness: Path, tmp_path: Path
) -> None:
    result = _run_harness(
        extracted_setup_head_with_retry_harness,
        tmp_path / "counter.txt",
        succeed_on_attempt=100,
        max_attempts=3,
    )
    assert result.returncode == 0, result.stderr
    assert "RETRY_RESULT=failure" in result.stdout
    assert "RETRY_ATTEMPTS=3" in result.stdout
    assert "command failed after 3 attempt(s)" in result.stderr


def test_terraform_retry_refreshes_plan_after_partial_apply(
    extracted_setup_head_with_terraform_retry_harness: Path, tmp_path: Path
) -> None:
    sequence_file = tmp_path / "terraform-sequence.txt"
    sequence_file.write_text("", encoding="utf-8")
    env = dict(os.environ)
    env["TERRAFORM_SEQUENCE_FILE"] = str(sequence_file)

    result = subprocess.run(
        [BASH, str(extracted_setup_head_with_terraform_retry_harness), *DEFAULT_ARGS],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(extracted_setup_head_with_terraform_retry_harness.parent),
    )

    assert result.returncode == 0, result.stderr
    assert "TERRAFORM_RETRY_RESULT=success" in result.stdout
    assert sequence_file.read_text(encoding="utf-8").splitlines() == [
        "apply",
        "plan",
        "apply",
    ]

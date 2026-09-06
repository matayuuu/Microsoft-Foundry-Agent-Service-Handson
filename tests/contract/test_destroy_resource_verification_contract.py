"""Hermetic, mocked-`az`/`terraform` contract tests for scripts/destroy.sh's
post-destroy resource-remnant verification and gated local-state removal.

These tests never call real Azure or run real Terraform. They copy the real
scripts/destroy.sh into an isolated fixture "repo" (preserving the real
scripts/<name> + infra/ + .workshop/ relative layout so SCRIPT_DIR/REPO_ROOT/
INFRA_DIR/WORKSHOP_DIR resolve the same way they do in production) and inject
fake `az`/`terraform` bash *functions* (not PATH executables -- exec'ing a
shebang script found via PATH proved unreliable under this Windows/Git-Bash
environment in an earlier hardening pass, silently falling through to the
real system binary instead; a function definition is looked up by bash
before PATH search and is therefore reliable) right after `set -euo
pipefail`, so every `az`/`terraform` invocation in the real script body is
transparently redirected without editing any of the script's actual logic.

They assert the behavior this hardening pass requires:

* After a clean `terraform destroy`, `az resource list` returning no
  workshop-tagged/named resource in the resource group lets the script
  proceed to remove local `.workshop/` state AND
  `infra/terraform.tfstate[.backup]`, and exit 0.
* If any remaining resource matches this workshop's tag
  (`workshop=foundry-agent-service-handson`) or name-prefix (`fdyws`)
  convention, the script exits non-zero and leaves EVERY local state file
  (`.workshop/context.json` and both `terraform.tfstate*` files) untouched --
  never a partial cleanup.
* If the `az resource list` call itself fails, the script fails the same
  fail-safe way -- exits non-zero, touches no local state -- rather than
  assuming an unqueried resource group is clean.
* A partial setup can be destroyed without context.json by using the resolved
  Terraform inputs setup.sh persisted before Terraform started.
* Explicit CLI inputs remain available as a last-resort recovery path when
  neither setup context file exists.
* The resource group itself is never referenced in any `az resource
  group delete`/similar call by this script (defense in depth: the fake `az`
  function fails loudly on any unexpected subcommand, so an accidental RG
  delete call would fail the test rather than silently succeed).

Requires `bash` and `jq` on PATH; skipped automatically otherwise (this
workshop's participant/admin scripts target a Linux devcontainer/Codespace
where both are expected to be present).
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DESTROY_SH = REPO_ROOT / "scripts" / "destroy.sh"

BASH = shutil.which("bash")
JQ = shutil.which("jq")

pytestmark = pytest.mark.skipif(
    BASH is None or JQ is None,
    reason="hermetic destroy.sh contract tests require both 'bash' and 'jq' on PATH",
)

RESOURCE_GROUP_NAME = "rg-fixture-test"
SUBSCRIPTION_ID = "33333333-3333-3333-3333-333333333333"

# Injected as bash *functions* -- not PATH executables -- right after `set
# -euo pipefail` in the copied script, so they are defined before the
# tool-availability check and every subsequent `az`/`terraform` call. Reads
# its canned behavior from environment variables set per-test.
FAKE_TOOLS_PREAMBLE = r"""
az() {
  if [[ "$1 $2" == "resource list" ]]; then
    local count
    count="$(cat "${REPO_ROOT}/resource-list-calls")"
    count=$((count + 1))
    printf '%s\n' "${count}" > "${REPO_ROOT}/resource-list-calls"
    case "${FAKE_AZ_RESOURCE_LIST_MODE:-empty}" in
      empty)
        echo "[]"
        ;;
      remnants|eventually-empty)
        if [[ "${FAKE_AZ_RESOURCE_LIST_MODE}" == "eventually-empty" && ${count} -gt 1 ]]; then
          echo "[]"
          return 0
        fi
        cat <<'JSON'
[
  {
    "name": "stfdywsabc12345",
    "type": "Microsoft.Storage/storageAccounts",
    "tags": {"workshop": "foundry-agent-service-handson"}
  }
]
JSON
        ;;
      call-fails|transient-error)
        if [[ "${FAKE_AZ_RESOURCE_LIST_MODE}" == "transient-error" && ${count} -gt 1 ]]; then
          echo "[]"
          return 0
        fi
        echo "fake-az: simulated transient failure" >&2
        return 1
        ;;
      *)
        echo "fake-az: unknown FAKE_AZ_RESOURCE_LIST_MODE: ${FAKE_AZ_RESOURCE_LIST_MODE}" >&2
        return 1
        ;;
    esac
    return 0
  fi
  echo "fake-az: unexpected/unhandled invocation, refusing to silently succeed: az $*" >&2
  return 1
}

sleep() {
  printf '%s\n' "$1" >> "${REPO_ROOT}/verification-sleeps"
}

terraform() {
  # destroy.sh only ever calls `terraform -chdir=<dir> init ...` and
  # `terraform -chdir=<dir> destroy ...`; both are no-ops here since this
  # test never provisions or destroys real infrastructure.
  case "$*" in
    *" init "*|*" destroy "*|*" init"|*" destroy")
      return 0
      ;;
    *)
      echo "fake-terraform: unexpected/unhandled invocation: terraform $*" >&2
      return 1
      ;;
  esac
}
"""


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    """Build an isolated fixture repo with scripts/destroy.sh (fakes
    injected), an infra/ dir containing dummy local Terraform state files,
    and a .workshop/context.json -- mirroring the real repo's relative
    layout so the script's own SCRIPT_DIR/REPO_ROOT/INFRA_DIR/WORKSHOP_DIR
    resolution logic is exercised unmodified.
    """
    repo_root = tmp_path / "fixture-repo"
    scripts_dir = repo_root / "scripts"
    infra_dir = repo_root / "infra"
    workshop_dir = repo_root / ".workshop"
    scripts_dir.mkdir(parents=True)
    infra_dir.mkdir(parents=True)
    workshop_dir.mkdir(parents=True)

    lines = DESTROY_SH.read_text(encoding="utf-8").splitlines(keepends=True)
    set_e_index = next(i for i, line in enumerate(lines) if line.strip() == "set -euo pipefail")
    patched = (
        "".join(lines[: set_e_index + 1]) + FAKE_TOOLS_PREAMBLE + "".join(lines[set_e_index + 1 :])
    )
    destroy_copy = scripts_dir / "destroy.sh"
    destroy_copy.write_text(patched, encoding="utf-8", newline="\n")
    destroy_copy.chmod(destroy_copy.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    (infra_dir / "terraform.tfstate").write_text('{"version": 4}', encoding="utf-8")
    (infra_dir / "terraform.tfstate.backup").write_text('{"version": 4}', encoding="utf-8")

    context = {
        "subscription_id": SUBSCRIPTION_ID,
        "resource_group_name": RESOURCE_GROUP_NAME,
        "location": "eastus2",
        "source_base": "https://github.com/example/workshop/blob/main",
        "terraform_inputs": {
            "travel_api_image_ref": "ghcr.io/example/travel-ops-api@sha256:" + "0" * 64,
            "optimizer_model_version": "fixture-optimizer-version",
            "primary_model_version": "fixture-primary-version",
            "embedding_model_version": "1",
        },
    }
    (workshop_dir / "context.json").write_text(json.dumps(context), encoding="utf-8")
    recovery_context = {**context, "setup_status": "inputs-resolved"}
    recovery_context.pop("terraform_outputs", None)
    (workshop_dir / "terraform-inputs.json").write_text(
        json.dumps(recovery_context), encoding="utf-8"
    )
    (workshop_dir / ".env").write_text("FOO=bar\n", encoding="utf-8")
    (repo_root / "resource-list-calls").write_text("0\n", encoding="utf-8")

    return repo_root


def _run_destroy(fixture_repo: Path, mode: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["FAKE_AZ_RESOURCE_LIST_MODE"] = mode
    return subprocess.run(
        [BASH, str(fixture_repo / "scripts" / "destroy.sh"), "--auto-approve"],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(fixture_repo),
    )


def test_clean_teardown_removes_all_local_state_and_exits_zero(fixture_repo: Path) -> None:
    result = _run_destroy(fixture_repo, "empty")
    assert result.returncode == 0, result.stderr

    workshop_dir = fixture_repo / ".workshop"
    infra_dir = fixture_repo / "infra"
    assert not (workshop_dir / "context.json").exists()
    assert not (workshop_dir / "terraform-inputs.json").exists()
    assert not (workshop_dir / ".env").exists()
    assert not (infra_dir / "terraform.tfstate").exists()
    assert not (infra_dir / "terraform.tfstate.backup").exists()
    assert "Resource group 'rg-fixture-test' was preserved" in result.stderr


def test_remaining_resources_fail_and_preserve_all_local_state(fixture_repo: Path) -> None:
    result = _run_destroy(fixture_repo, "remnants")
    assert result.returncode != 0
    assert "stfdywsabc12345" in result.stderr
    assert "workshop-managed resource(s) still exist" in result.stderr

    workshop_dir = fixture_repo / ".workshop"
    infra_dir = fixture_repo / "infra"
    assert (workshop_dir / "context.json").exists()
    assert (workshop_dir / "terraform-inputs.json").exists()
    assert (infra_dir / "terraform.tfstate").exists()
    assert (infra_dir / "terraform.tfstate.backup").exists()
    assert (fixture_repo / "resource-list-calls").read_text().strip() == "6"
    assert (fixture_repo / "verification-sleeps").read_text().splitlines() == ["10"] * 5


def test_resource_list_call_failure_fails_safe_and_preserves_all_local_state(
    fixture_repo: Path,
) -> None:
    result = _run_destroy(fixture_repo, "call-fails")
    assert result.returncode != 0
    assert "'az resource list' failed" in result.stderr

    workshop_dir = fixture_repo / ".workshop"
    infra_dir = fixture_repo / "infra"
    assert (workshop_dir / "context.json").exists()
    assert (workshop_dir / "terraform-inputs.json").exists()
    assert (infra_dir / "terraform.tfstate").exists()
    assert (infra_dir / "terraform.tfstate.backup").exists()
    assert (fixture_repo / "resource-list-calls").read_text().strip() == "6"


@pytest.mark.parametrize("mode", ["eventually-empty", "transient-error"])
def test_verification_retries_until_a_confirmed_empty_listing(
    fixture_repo: Path, mode: str
) -> None:
    result = _run_destroy(fixture_repo, mode)

    assert result.returncode == 0, result.stderr
    assert (fixture_repo / "resource-list-calls").read_text().strip() == "2"
    assert (fixture_repo / "verification-sleeps").read_text().splitlines() == ["10"]
    assert not (fixture_repo / ".workshop" / "context.json").exists()
    assert not (fixture_repo / "infra" / "terraform.tfstate").exists()
    assert not (fixture_repo / "infra" / "terraform.tfstate.backup").exists()


def test_recovery_inputs_destroy_partial_setup_without_complete_context(
    fixture_repo: Path,
) -> None:
    workshop_dir = fixture_repo / ".workshop"
    (workshop_dir / "context.json").unlink()
    result = _run_destroy(fixture_repo, "empty")

    assert result.returncode == 0, result.stderr
    assert "reading cleanup inputs from" in result.stderr
    assert not (fixture_repo / "infra" / "terraform.tfstate").exists()


def test_cli_overrides_recover_partial_setup_without_context_files(fixture_repo: Path) -> None:
    workshop_dir = fixture_repo / ".workshop"
    (workshop_dir / "context.json").unlink()
    (workshop_dir / "terraform-inputs.json").unlink()
    env = dict(os.environ)
    env["FAKE_AZ_RESOURCE_LIST_MODE"] = "empty"
    image_ref = "ghcr.io/example/travel-ops-api@sha256:" + "0" * 64

    result = subprocess.run(
        [
            BASH,
            str(fixture_repo / "scripts" / "destroy.sh"),
            "--subscription",
            SUBSCRIPTION_ID,
            "--resource-group",
            RESOURCE_GROUP_NAME,
            "--travel-api-image-ref",
            image_ref,
            "--location",
            "eastus2",
            "--source-base",
            "https://github.com/example/workshop/blob/main",
            "--optimizer-model-version",
            "fixture-optimizer-version",
            "--primary-model-version",
            "fixture-primary-version",
            "--embedding-model-version",
            "1",
            "--auto-approve",
        ],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(fixture_repo),
    )

    assert result.returncode == 0, result.stderr
    assert "relying solely on CLI arguments" in result.stderr
    assert not (fixture_repo / "infra" / "terraform.tfstate").exists()


@pytest.mark.parametrize("role", ["primary", "optimizer"])
def test_missing_required_chat_version_fails_before_cleanup(fixture_repo: Path, role: str) -> None:
    workshop_dir = fixture_repo / ".workshop"
    for name in ("context.json", "terraform-inputs.json"):
        path = workshop_dir / name
        context = json.loads(path.read_text(encoding="utf-8"))
        del context["terraform_inputs"][f"{role}_model_version"]
        path.write_text(json.dumps(context), encoding="utf-8")

    result = _run_destroy(fixture_repo, "empty")

    assert result.returncode == 1
    assert f"--{role}-model-version" in result.stderr
    assert "Deleting SDK-managed" not in result.stderr
    assert (fixture_repo / "infra" / "terraform.tfstate").exists()
    assert (workshop_dir / "context.json").exists()

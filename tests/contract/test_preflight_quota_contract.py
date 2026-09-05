"""Hermetic, mocked-`az` contract tests for scripts/preflight.sh's region and
model/SKU/quota resolution.

These tests never call real Azure. They install a tiny fake `az` shell shim
on PATH (fixture: fake_az) that returns canned JSON shaped exactly like real
`az cognitiveservices model list` / `az cognitiveservices usage list` output
(field names and nesting verified against a live subscription: model.skus[]
entries carry both `name` -- the SKU/deployment-type, e.g. "GlobalStandard"
-- and their own `usageName`, e.g. "OpenAI.GlobalStandard.gpt4.1"; usage-list
entries key on `name.value` matching that exact usageName string and report
`limit`/`currentValue` in thousands of TPM).

They assert the behaviors AGENTS.md and the follow-up hardening pass require:

* The specific SKU (GlobalStandard for all three models) and per-model
  capacity (40/20/40, matching infra/variables.tf) are what gates region
  resolution -- not a generic cross-bucket floor.
* `usageName` is read from the model's own `skus[]` entry, never
  reconstructed from the model name. Synthetic aliases retain the historic
  gpt-4.1 missing-hyphen regression without claiming Luna's live quota name.
* A region is resolved only when EVERY required model's specific usageName
  bucket has enough headroom; otherwise resolution fails over to the next
  candidate region, or fails outright (never silently proceeds on unknown or
  insufficient headroom).
* The report surfaces per-model SKU/usageName/capacity evidence.

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
PREFLIGHT_SH = REPO_ROOT / "scripts" / "preflight.sh"

BASH = shutil.which("bash")
JQ = shutil.which("jq")

pytestmark = pytest.mark.skipif(
    BASH is None or JQ is None,
    reason="hermetic preflight.sh contract tests require both 'bash' and 'jq' on PATH",
)

FAKE_AZ_SCRIPT = r"""#!/usr/bin/env bash
# Hermetic fake `az` for scripts/preflight.sh contract tests. Never touches
# the network; responds only to the subcommands preflight.sh actually
# invokes, using canned fixtures selected via environment variables so each
# test can drive a different region/quota scenario without rewriting this
# script.
set -euo pipefail

find_arg_value() {
  local flag="$1"
  local i
  for ((i = 0; i < ${#ALL_ARGS[@]}; i++)); do
    if [[ "${ALL_ARGS[$i]}" == "${flag}" ]]; then
      echo "${ALL_ARGS[$((i + 1))]}"
      return 0
    fi
  done
  echo ""
}

ALL_ARGS=("$@")
sub1="${1:-}"
sub2="${2:-}"

case "${sub1} ${sub2}" in
  "account show")
    sub_id="${FAKE_SUBSCRIPTION_ID:-sub-0000}"
    echo "{\"id\": \"${sub_id}\", \"user\": {\"name\": \"tester@example.com\"}}"
    ;;
  "account set")
    exit 0
    ;;
  "ad signed-in-user")
    echo '{"id": "00000000-0000-0000-0000-000000000001"}'
    ;;
  "group show")
    sub_id="${FAKE_SUBSCRIPTION_ID:-sub-0000}"
    rg_name="${FAKE_RESOURCE_GROUP:-rg-test}"
    echo "{\"id\": \"/subscriptions/${sub_id}/resourceGroups/${rg_name}\"}"
    ;;
  "role assignment")
    echo '[{"roleDefinitionName": "Owner"}]'
    ;;
  "provider show")
    echo "Registered"
    ;;
  "policy assignment")
    echo "[]"
    ;;
  "cognitiveservices model")
    loc="$(find_arg_value --location)"
    var="FAKE_MODELS_$(echo "${loc}" | tr '[:lower:]' '[:upper:]')"
    file="${!var:-}"
    if [[ -z "${file}" ]]; then
      echo "[]"
    else
      cat "${file}"
    fi
    ;;
  "cognitiveservices usage")
    loc="$(find_arg_value --location)"
    var="FAKE_USAGE_$(echo "${loc}" | tr '[:lower:]' '[:upper:]')"
    val="${!var:-}"
    if [[ "${val}" == "FAIL" ]]; then
      exit 1
    elif [[ -z "${val}" ]]; then
      echo "[]"
    else
      cat "${val}"
    fi
    ;;
  *)
    echo "fake-az: unhandled command: ${ALL_ARGS[*]}" >&2
    exit 1
    ;;
esac
"""


def _model_entry(
    name: str,
    version: str,
    skus: list[tuple[str, str]],
    *,
    is_default_version: bool | None = None,
    deprecated_inference: str | None = None,
) -> dict:
    model: dict = {
        "name": name,
        "version": version,
        "skus": [{"name": sku_name, "usageName": usage_name} for sku_name, usage_name in skus],
    }
    if is_default_version is not None:
        model["isDefaultVersion"] = is_default_version
    if deprecated_inference is not None:
        model["deprecation"] = {"inference": deprecated_inference}
    return {"model": model}


def _usage_entry(usage_name: str, limit: float, current: float) -> dict:
    return {"name": {"value": usage_name}, "limit": limit, "currentValue": current}


# All chat versions and quota aliases below are synthetic, not deployment
# recommendations. Deliberately reuse legacy buckets to catch constructed
# usageName strings: live preflight must read Azure's own SKU entry.
PRIMARY_MODEL = "gpt-5.6-luna"
OPTIMIZER_MODEL = "gpt-5.5"
GPT41_GLOBALSTANDARD_USAGE = "OpenAI.GlobalStandard.gpt4.1"
GPT5_GLOBALSTANDARD_USAGE = "OpenAI.GlobalStandard.gpt-5"
EMBEDDING_GLOBALSTANDARD_USAGE = "OpenAI.GlobalStandard.text-embedding-3-small"

FULL_MODELS_FIXTURE = [
    _model_entry(
        PRIMARY_MODEL,
        "2025-04-14",
        [("Standard", "OpenAI.Standard.gpt4.1"), ("GlobalStandard", GPT41_GLOBALSTANDARD_USAGE)],
    ),
    _model_entry(OPTIMIZER_MODEL, "2025-08-07", [("GlobalStandard", GPT5_GLOBALSTANDARD_USAGE)]),
    _model_entry(
        "text-embedding-3-small",
        "1",
        [
            ("Standard", "OpenAI.Standard.text-embedding-3-small"),
            ("GlobalStandard", EMBEDDING_GLOBALSTANDARD_USAGE),
        ],
    ),
]

# Same three models, but the optimizer never exposes a GlobalStandard SKU in
# this (fake) region -- exercises the "required SKU missing" failure path.
MODELS_MISSING_GPT5_SKU_FIXTURE = [
    _model_entry(
        PRIMARY_MODEL,
        "2025-04-14",
        [("Standard", "OpenAI.Standard.gpt4.1"), ("GlobalStandard", GPT41_GLOBALSTANDARD_USAGE)],
    ),
    _model_entry(OPTIMIZER_MODEL, "2025-08-07", [("Standard", "OpenAI.Standard.gpt-5")]),
    _model_entry(
        "text-embedding-3-small",
        "1",
        [("GlobalStandard", EMBEDDING_GLOBALSTANDARD_USAGE)],
    ),
]


# Reproduces the exact bug this turn's fix targets: the HIGHEST version of
# the primary model ("2025-04-14") does NOT expose the required "GlobalStandard" SKU
# (only "Standard"), while an OLDER version ("2025-01-01") does. The old
# logic picked "2025-04-14" as chosen_version (highest overall) and then
# separately found usageName on "2025-01-01" -- a mismatched, non-existent
# combination. The fixed logic must filter by SKU first and resolve
# "2025-01-01" for both version and usageName.
MODELS_SKU_ONLY_ON_OLDER_VERSION_FIXTURE = [
    _model_entry(PRIMARY_MODEL, "2025-04-14", [("Standard", "OpenAI.Standard.gpt4.1")]),
    _model_entry(
        PRIMARY_MODEL,
        "2025-01-01",
        [("GlobalStandard", GPT41_GLOBALSTANDARD_USAGE)],
    ),
    _model_entry(OPTIMIZER_MODEL, "2025-08-07", [("GlobalStandard", GPT5_GLOBALSTANDARD_USAGE)]),
    _model_entry(
        "text-embedding-3-small",
        "1",
        [("GlobalStandard", EMBEDDING_GLOBALSTANDARD_USAGE)],
    ),
]

# The optimizer has two GlobalStandard-supporting versions; the newer one
# ("2025-08-07") is NOT flagged isDefaultVersion, while the older
# ("2025-06-01") IS. The fix must prefer isDefaultVersion=true over pure
# lexicographic-highest-version.
MODELS_ISDEFAULTVERSION_PREFERRED_FIXTURE = [
    _model_entry(
        PRIMARY_MODEL,
        "2025-04-14",
        [("Standard", "OpenAI.Standard.gpt4.1"), ("GlobalStandard", GPT41_GLOBALSTANDARD_USAGE)],
        is_default_version=True,
    ),
    _model_entry(
        OPTIMIZER_MODEL,
        "2025-08-07",
        [("GlobalStandard", GPT5_GLOBALSTANDARD_USAGE)],
        is_default_version=False,
    ),
    _model_entry(
        OPTIMIZER_MODEL,
        "2025-06-01",
        [("GlobalStandard", GPT5_GLOBALSTANDARD_USAGE)],
        is_default_version=True,
    ),
    _model_entry(
        "text-embedding-3-small",
        "1",
        [("GlobalStandard", EMBEDDING_GLOBALSTANDARD_USAGE)],
        is_default_version=True,
    ),
]


def _sufficient_usage_fixture() -> list[dict]:
    return [
        _usage_entry(GPT41_GLOBALSTANDARD_USAGE, limit=100.0, current=0.0),  # headroom 100 >= 40
        _usage_entry(GPT5_GLOBALSTANDARD_USAGE, limit=100.0, current=0.0),  # headroom 100 >= 20
        _usage_entry(
            EMBEDDING_GLOBALSTANDARD_USAGE, limit=100.0, current=0.0
        ),  # headroom 100 >= 40
    ]


def _insufficient_gpt5_usage_fixture() -> list[dict]:
    return [
        _usage_entry(GPT41_GLOBALSTANDARD_USAGE, limit=100.0, current=0.0),
        _usage_entry(
            GPT5_GLOBALSTANDARD_USAGE, limit=10.0, current=0.0
        ),  # headroom 10 < 20 required
        _usage_entry(EMBEDDING_GLOBALSTANDARD_USAGE, limit=100.0, current=0.0),
    ]


@pytest.fixture
def fake_az_bin(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    az_path = bin_dir / "az"
    az_path.write_text(FAKE_AZ_SCRIPT, encoding="utf-8", newline="\n")
    az_path.chmod(az_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def _write_json(tmp_path: Path, name: str, payload: list[dict]) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _run_preflight(fake_az_bin: Path, tmp_path: Path, env_overrides: dict[str, str]) -> dict:
    env = dict(os.environ)
    env["PATH"] = str(fake_az_bin) + os.pathsep + env.get("PATH", "")
    env["FAKE_SUBSCRIPTION_ID"] = "11111111-1111-1111-1111-111111111111"
    env["FAKE_RESOURCE_GROUP"] = "rg-workshop-test"
    env.update(env_overrides)

    result = subprocess.run(
        [
            BASH,
            str(PREFLIGHT_SH),
            "--subscription",
            env["FAKE_SUBSCRIPTION_ID"],
            "--resource-group",
            env["FAKE_RESOURCE_GROUP"],
            "--format",
            "json",
        ],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode in (0, 2), (
        f"unexpected exit code {result.returncode}\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(
            f"preflight.sh did not emit JSON on stdout: {result.stdout!r}\nstderr={result.stderr}"
        )


def test_resolves_preferred_region_with_sufficient_capacity_evidence(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    report = _run_preflight(
        fake_az_bin,
        tmp_path,
        {
            "FAKE_MODELS_EASTUS2": _write_json(
                tmp_path, "models-eastus2.json", FULL_MODELS_FIXTURE
            ),
            "FAKE_USAGE_EASTUS2": _write_json(
                tmp_path, "usage-eastus2.json", _sufficient_usage_fixture()
            ),
            "FAKE_MODELS_SWEDENCENTRAL": _write_json(
                tmp_path, "models-sc.json", FULL_MODELS_FIXTURE
            ),
            "FAKE_USAGE_SWEDENCENTRAL": _write_json(
                tmp_path, "usage-sc.json", _sufficient_usage_fixture()
            ),
        },
    )

    assert report["resolved_location"] == "eastus2"

    evidence = report["resolved_model_capacity_evidence"]
    assert set(evidence) == {PRIMARY_MODEL, OPTIMIZER_MODEL, "text-embedding-3-small"}
    assert set(report["resolved_model_versions"]) == set(evidence)
    assert evidence[PRIMARY_MODEL] == {
        "sku": "GlobalStandard",
        "usage_name": GPT41_GLOBALSTANDARD_USAGE,
        "required_capacity_k": 40,
    }
    assert evidence[OPTIMIZER_MODEL] == {
        "sku": "GlobalStandard",
        "usage_name": GPT5_GLOBALSTANDARD_USAGE,
        "required_capacity_k": 20,
    }
    assert evidence["text-embedding-3-small"] == {
        "sku": "GlobalStandard",
        "usage_name": EMBEDDING_GLOBALSTANDARD_USAGE,
        "required_capacity_k": 40,
    }
    assert report["resolved_model_versions"][PRIMARY_MODEL] == "2025-04-14"
    assert report["resolved_model_versions"][OPTIMIZER_MODEL] == "2025-08-07"


def test_falls_back_to_swedencentral_when_eastus2_headroom_insufficient(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    report = _run_preflight(
        fake_az_bin,
        tmp_path,
        {
            "FAKE_MODELS_EASTUS2": _write_json(
                tmp_path, "models-eastus2.json", FULL_MODELS_FIXTURE
            ),
            "FAKE_USAGE_EASTUS2": _write_json(
                tmp_path, "usage-eastus2.json", _insufficient_gpt5_usage_fixture()
            ),
            "FAKE_MODELS_SWEDENCENTRAL": _write_json(
                tmp_path, "models-sc.json", FULL_MODELS_FIXTURE
            ),
            "FAKE_USAGE_SWEDENCENTRAL": _write_json(
                tmp_path, "usage-sc.json", _sufficient_usage_fixture()
            ),
        },
    )

    assert report["resolved_location"] == "swedencentral"
    assert report["overall_status"] == "pass"
    # The eastus2 shortfall must be visible as an explicit failed check, not
    # silently swallowed.
    eastus2_gpt5_checks = [
        c for c in report["checks"] if c["name"] == f"quota-usage:{OPTIMIZER_MODEL}/eastus2"
    ]
    assert eastus2_gpt5_checks, "expected an explicit optimizer quota-usage check"
    assert eastus2_gpt5_checks[0]["status"] == "fail"


def test_fails_without_resolving_when_no_region_has_sufficient_capacity(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    report = _run_preflight(
        fake_az_bin,
        tmp_path,
        {
            "FAKE_MODELS_EASTUS2": _write_json(
                tmp_path, "models-eastus2.json", FULL_MODELS_FIXTURE
            ),
            "FAKE_USAGE_EASTUS2": _write_json(
                tmp_path, "usage-eastus2.json", _insufficient_gpt5_usage_fixture()
            ),
            "FAKE_MODELS_SWEDENCENTRAL": _write_json(
                tmp_path, "models-sc.json", FULL_MODELS_FIXTURE
            ),
            "FAKE_USAGE_SWEDENCENTRAL": _write_json(
                tmp_path, "usage-sc.json", _insufficient_gpt5_usage_fixture()
            ),
        },
    )

    assert report["resolved_location"] == ""
    assert report["overall_status"] == "fail"


def test_fails_when_required_sku_is_not_offered_rather_than_guessing_usage_name(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    """The optimizer exposes only a 'Standard' SKU in both fake regions -- never the
    required 'GlobalStandard'. The script must not fall back to guessing a
    usageName string from the model name; it must fail that model/region."""
    report = _run_preflight(
        fake_az_bin,
        tmp_path,
        {
            "FAKE_MODELS_EASTUS2": _write_json(
                tmp_path, "models-eastus2.json", MODELS_MISSING_GPT5_SKU_FIXTURE
            ),
            "FAKE_USAGE_EASTUS2": _write_json(
                tmp_path, "usage-eastus2.json", _sufficient_usage_fixture()
            ),
            "FAKE_MODELS_SWEDENCENTRAL": _write_json(
                tmp_path, "models-sc.json", MODELS_MISSING_GPT5_SKU_FIXTURE
            ),
            "FAKE_USAGE_SWEDENCENTRAL": _write_json(
                tmp_path, "usage-sc.json", _sufficient_usage_fixture()
            ),
        },
    )

    assert report["resolved_location"] == ""
    sku_checks = [
        c for c in report["checks"] if c["name"].startswith(f"model-sku:{OPTIMIZER_MODEL}/")
    ]
    assert sku_checks, "expected an explicit optimizer model-sku failure"
    assert all(c["status"] == "fail" for c in sku_checks)


def test_fails_when_usage_list_call_itself_fails_rather_than_assuming_sufficient(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    report = _run_preflight(
        fake_az_bin,
        tmp_path,
        {
            "FAKE_MODELS_EASTUS2": _write_json(
                tmp_path, "models-eastus2.json", FULL_MODELS_FIXTURE
            ),
            "FAKE_USAGE_EASTUS2": "FAIL",
            "FAKE_MODELS_SWEDENCENTRAL": _write_json(
                tmp_path, "models-sc.json", FULL_MODELS_FIXTURE
            ),
            "FAKE_USAGE_SWEDENCENTRAL": _write_json(
                tmp_path, "usage-sc.json", _sufficient_usage_fixture()
            ),
        },
    )

    assert report["resolved_location"] == "swedencentral"
    eastus2_checks = [
        c for c in report["checks"] if c["name"].endswith("/eastus2") and "quota-usage" in c["name"]
    ]
    assert eastus2_checks, (
        "expected quota-usage checks for eastus2 even when the usage-list call failed"
    )
    assert all(c["status"] == "fail" for c in eastus2_checks)
    assert report["overall_status"] == "pass"


def test_unused_fallback_failure_does_not_fail_successful_preferred_region(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    report = _run_preflight(
        fake_az_bin,
        tmp_path,
        {
            "FAKE_MODELS_EASTUS2": _write_json(
                tmp_path, "models-eastus2.json", FULL_MODELS_FIXTURE
            ),
            "FAKE_USAGE_EASTUS2": _write_json(
                tmp_path, "usage-eastus2.json", _sufficient_usage_fixture()
            ),
            "FAKE_MODELS_SWEDENCENTRAL": _write_json(
                tmp_path, "models-sc.json", MODELS_MISSING_GPT5_SKU_FIXTURE
            ),
            "FAKE_USAGE_SWEDENCENTRAL": _write_json(
                tmp_path, "usage-sc.json", _sufficient_usage_fixture()
            ),
        },
    )

    assert report["resolved_location"] == "eastus2"
    assert report["overall_status"] == "pass"
    fallback_check = next(
        check
        for check in report["checks"]
        if check["name"] == f"model-sku:{OPTIMIZER_MODEL}/swedencentral"
    )
    assert fallback_check["status"] == "fail"


def test_resolves_the_sku_supporting_version_not_the_highest_overall_version(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    """Regression test for the version/SKU-mismatch bug: the primary model's HIGHEST
    version does not support the required 'GlobalStandard' SKU, only an
    older version does. The script must resolve that older, SKU-supporting
    version (and its own usageName) rather than reporting the highest
    version paired with a usageName scraped from a different entry."""
    report = _run_preflight(
        fake_az_bin,
        tmp_path,
        {
            "FAKE_MODELS_EASTUS2": _write_json(
                tmp_path, "models-eastus2.json", MODELS_SKU_ONLY_ON_OLDER_VERSION_FIXTURE
            ),
            "FAKE_USAGE_EASTUS2": _write_json(
                tmp_path, "usage-eastus2.json", _sufficient_usage_fixture()
            ),
            "FAKE_MODELS_SWEDENCENTRAL": _write_json(
                tmp_path, "models-sc.json", MODELS_SKU_ONLY_ON_OLDER_VERSION_FIXTURE
            ),
            "FAKE_USAGE_SWEDENCENTRAL": _write_json(
                tmp_path, "usage-sc.json", _sufficient_usage_fixture()
            ),
        },
    )

    assert report["resolved_location"] == "eastus2"
    # Never the newer, non-SKU-supporting "2025-04-14".
    assert report["resolved_model_versions"][PRIMARY_MODEL] == "2025-01-01"
    assert report["resolved_model_capacity_evidence"][PRIMARY_MODEL]["usage_name"] == (
        GPT41_GLOBALSTANDARD_USAGE
    )
    gpt41_pass_checks = [
        c for c in report["checks"] if c["name"] == f"model:{PRIMARY_MODEL}/eastus2"
    ]
    assert gpt41_pass_checks and gpt41_pass_checks[0]["status"] == "pass"
    assert "resolved version='2025-01-01'" in gpt41_pass_checks[0]["detail"]
    assert f"usageName='{GPT41_GLOBALSTANDARD_USAGE}'" in gpt41_pass_checks[0]["detail"]


def test_prefers_isdefaultversion_over_lexicographically_highest_version(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    """The optimizer has two SKU-supporting versions; the higher one is NOT flagged
    isDefaultVersion, but an older one is. The fix must prefer the
    isDefaultVersion=true entry over the pure lexicographic-highest
    fallback, and say so in the check evidence."""
    report = _run_preflight(
        fake_az_bin,
        tmp_path,
        {
            "FAKE_MODELS_EASTUS2": _write_json(
                tmp_path, "models-eastus2.json", MODELS_ISDEFAULTVERSION_PREFERRED_FIXTURE
            ),
            "FAKE_USAGE_EASTUS2": _write_json(
                tmp_path, "usage-eastus2.json", _sufficient_usage_fixture()
            ),
            "FAKE_MODELS_SWEDENCENTRAL": _write_json(
                tmp_path, "models-sc.json", MODELS_ISDEFAULTVERSION_PREFERRED_FIXTURE
            ),
            "FAKE_USAGE_SWEDENCENTRAL": _write_json(
                tmp_path, "usage-sc.json", _sufficient_usage_fixture()
            ),
        },
    )

    assert report["resolved_location"] == "eastus2"
    assert report["resolved_model_versions"][OPTIMIZER_MODEL] == "2025-06-01"
    gpt5_pass_checks = [
        c for c in report["checks"] if c["name"] == f"model:{OPTIMIZER_MODEL}/eastus2"
    ]
    assert gpt5_pass_checks and gpt5_pass_checks[0]["status"] == "pass"
    assert "resolved version='2025-06-01' (isDefaultVersion=true)" in gpt5_pass_checks[0]["detail"]


@pytest.mark.parametrize(
    ("required_model", "legacy_model"), [(PRIMARY_MODEL, "gpt-4.1"), (OPTIMIZER_MODEL, "gpt-5")]
)
def test_legacy_chat_models_do_not_satisfy_current_deployment_requirements(
    fake_az_bin: Path, tmp_path: Path, required_model: str, legacy_model: str
) -> None:
    models = json.loads(json.dumps(FULL_MODELS_FIXTURE))
    next(entry["model"] for entry in models if entry["model"]["name"] == required_model)["name"] = (
        legacy_model
    )
    report = _run_preflight(
        fake_az_bin,
        tmp_path,
        {
            "FAKE_MODELS_EASTUS2": _write_json(tmp_path, "models.json", models),
            "FAKE_USAGE_EASTUS2": _write_json(tmp_path, "usage.json", _sufficient_usage_fixture()),
        },
    )

    assert report["overall_status"] == "fail"
    assert report["resolved_location"] == ""
    assert all(value == "" for value in report["resolved_model_versions"].values())
    check = next(c for c in report["checks"] if c["name"] == f"model:{required_model}/eastus2")
    assert check["status"] == "fail"

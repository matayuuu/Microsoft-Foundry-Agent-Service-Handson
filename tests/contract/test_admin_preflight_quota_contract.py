"""Hermetic, mocked-`az` contract tests for scripts/admin-preflight.sh's
`--participant-count` aggregate model and Search quota reporting.

These tests never call real Azure. They install a tiny fake `az` shell shim
on PATH (fixture: fake_az_bin). The model.skus[] entries carry
both `name` -- the SKU/deployment-type -- and their own `usageName`; usage-
list entries key on `name.value` matching that exact usageName string and
report `limit`/`currentValue` in thousands of TPM.

They assert the behavior this hardening pass requires:

* `--participant-count` defaults to 1 and multiplies each model's
  per-environment required capacity (gpt-5.6-luna 40K, gpt-5.5 100K,
  text-embedding-3-small 40K) by the participant count to get the
  AGGREGATE requirement the whole event needs from a single region's quota
  pool -- not just one environment's worth.
* Headroom that is sufficient for one environment but not for N
  participants is reported as insufficient (a "warn", matching this
  script's informational-report semantics -- it never itself fails/selects
  a region or substitutes a different model).
* The aggregate math (per-environment capacity * count = required) is
  visible in the check detail text, and `participant_count` is echoed back
  in the JSON report.
* Azure AI Search Basic service-count headroom is compared with the same
  participant count in the explicitly selected region.
* `--participant-count` rejects non-positive-integer values before any
  Azure call is made.

Requires `bash` and `jq` on PATH; skipped automatically otherwise. The
administrator utility targets a Bash environment with both tools installed.
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
ADMIN_PREFLIGHT_SH = REPO_ROOT / "scripts" / "admin-preflight.sh"

BASH = shutil.which("bash")
JQ = shutil.which("jq")

pytestmark = pytest.mark.skipif(
    BASH is None or JQ is None,
    reason="hermetic admin-preflight.sh contract tests require both 'bash' and 'jq' on PATH",
)

# The fake-az shim handles only the subcommands admin-preflight.sh invokes
# (it never touches `group show` / `role assignment` / RG-scoped calls --
# it is a subscription-scope-only report).
FAKE_AZ_SCRIPT = r"""#!/usr/bin/env bash
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
    echo "{\"id\": \"${FAKE_SUBSCRIPTION_ID:-sub-0000}\", " \
         "\"user\": {\"name\": \"admin@example.com\"}}"
    ;;
  "account set")
    exit 0
    ;;
  "provider show")
    fmt="$(find_arg_value -o)"
    if [[ "${fmt}" == "json" ]]; then
      # Regional resource-type availability check: report every resource
      # type as available in both East US 2 and Sweden Central so this
      # fixture's participant-count assertions are not entangled with the
      # (separately tested) region-support checks.
      loc1='"locations": ["East US 2", "Sweden Central"]'
      echo "{\"resourceTypes\": [" \
           "{\"resourceType\": \"accounts\", ${loc1}}, " \
           "{\"resourceType\": \"searchServices\", ${loc1}}, " \
           "{\"resourceType\": \"components\", ${loc1}}, " \
           "{\"resourceType\": \"workspaces\", ${loc1}}, " \
           "{\"resourceType\": \"containerApps\", ${loc1}}, " \
           "{\"resourceType\": \"storageAccounts\", ${loc1}}, " \
           "{\"resourceType\": \"userAssignedIdentities\", ${loc1}}, " \
           "{\"resourceType\": \"containerGroups\", ${loc1}}, " \
           "{\"resourceType\": \"deploymentScripts\", ${loc1}}, " \
           "{\"resourceType\": \"vaults\", ${loc1}}]}"
    else
      var="FAKE_PROVIDER_$(find_arg_value --namespace | tr '.' '_' | tr '[:lower:]' '[:upper:]')"
      echo "${!var:-Registered}"
    fi
    ;;
  "provider register")
    exit 0
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
    "rest --method")
        url="$(find_arg_value --url)"
        if [[ "${url}" == *"/locations/eastus2/usages?"* ]]; then
            var="FAKE_SEARCH_USAGE_EASTUS2"
        elif [[ "${url}" == *"/locations/swedencentral/usages?"* ]]; then
            var="FAKE_SEARCH_USAGE_SWEDENCENTRAL"
        else
            echo "fake-az: unexpected REST URL: ${url}" >&2
            exit 1
        fi
        val="${!var:-}"
        if [[ "${val}" == "FAIL" ]]; then
            exit 1
        elif [[ -z "${val}" ]]; then
            cat <<'JSON'
{"value": [{"name": {"value": "basic"}, "currentValue": 0,
  "limit": 100, "unit": "Count"}]}
JSON
        else
            cat "${val}"
        fi
        ;;
  "policy assignment")
    echo "[]"
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
) -> dict:
    model: dict = {
        "name": name,
        "version": version,
        "skus": [{"name": sku_name, "usageName": usage_name} for sku_name, usage_name in skus],
    }
    if is_default_version is not None:
        model["isDefaultVersion"] = is_default_version
    return {"model": model}


def _usage_entry(usage_name: str, limit: float, current: float) -> dict:
    return {"name": {"value": usage_name}, "limit": limit, "currentValue": current}


def _search_usage_fixture(limit: int, current: int) -> dict:
    return {
        "value": [
            {
                "name": {"value": "basic", "localizedValue": "B - Basic"},
                "limit": limit,
                "currentValue": current,
                "unit": "Count",
            }
        ]
    }


# Synthetic chat versions/aliases, not verified live Luna/GPT-5.5 values.
# Historic bucket names exercise the rule that usageName cannot be derived.
PRIMARY_MODEL = "gpt-5.6-luna"
EVALUATION_MODEL = "gpt-5.5"
GPT41_GLOBALSTANDARD_USAGE = "OpenAI.GlobalStandard.gpt4.1"
GPT55_GLOBALSTANDARD_USAGE = "OpenAI.GlobalStandard.gpt-5.5"
EMBEDDING_GLOBALSTANDARD_USAGE = "OpenAI.GlobalStandard.text-embedding-3-small"

FULL_MODELS_FIXTURE = [
    _model_entry(
        PRIMARY_MODEL,
        "2025-04-14",
        [("Standard", "OpenAI.Standard.gpt4.1"), ("GlobalStandard", GPT41_GLOBALSTANDARD_USAGE)],
    ),
    _model_entry(EVALUATION_MODEL, "2026-08-01", [("GlobalStandard", GPT55_GLOBALSTANDARD_USAGE)]),
    _model_entry(
        "text-embedding-3-small",
        "1",
        [
            ("Standard", "OpenAI.Standard.text-embedding-3-small"),
            ("GlobalStandard", EMBEDDING_GLOBALSTANDARD_USAGE),
        ],
    ),
]


# Regression fixture for the version/SKU-mismatch bug: the primary model's HIGHEST
# version does not expose the required "GlobalStandard" SKU (only
# "Standard"); an older version does. The report must resolve the
# SKU-supporting version, never the highest version paired with a usageName
# scraped from a different (non-SKU-supporting) entry.
MODELS_SKU_ONLY_ON_OLDER_VERSION_FIXTURE = [
    _model_entry(PRIMARY_MODEL, "2025-04-14", [("Standard", "OpenAI.Standard.gpt4.1")]),
    _model_entry(
        PRIMARY_MODEL,
        "2025-01-01",
        [("GlobalStandard", GPT41_GLOBALSTANDARD_USAGE)],
    ),
    _model_entry(EVALUATION_MODEL, "2026-08-01", [("GlobalStandard", GPT55_GLOBALSTANDARD_USAGE)]),
    _model_entry(
        "text-embedding-3-small",
        "1",
        [("GlobalStandard", EMBEDDING_GLOBALSTANDARD_USAGE)],
    ),
]


def _usage_fixture_with_headroom(
    headroom_k: float, *, evaluation_headroom_k: float | None = None
) -> list[dict]:
    if evaluation_headroom_k is None:
        evaluation_headroom_k = headroom_k
    return [
        _usage_entry(GPT41_GLOBALSTANDARD_USAGE, limit=headroom_k, current=0.0),
        _usage_entry(GPT55_GLOBALSTANDARD_USAGE, limit=evaluation_headroom_k, current=0.0),
        _usage_entry(EMBEDDING_GLOBALSTANDARD_USAGE, limit=headroom_k, current=0.0),
    ]


@pytest.fixture
def fake_az_bin(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    az_path = bin_dir / "az"
    az_path.write_text(FAKE_AZ_SCRIPT, encoding="utf-8", newline="\n")
    az_path.chmod(az_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return bin_dir


def _write_json(tmp_path: Path, name: str, payload: object) -> str:
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def _run_admin_preflight(
    fake_az_bin: Path, tmp_path: Path, args: list[str], env_overrides: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = str(fake_az_bin) + os.pathsep + env.get("PATH", "")
    env["FAKE_SUBSCRIPTION_ID"] = "22222222-2222-2222-2222-222222222222"
    env.update(env_overrides)
    effective_args = list(args)
    if "--location" not in effective_args:
        effective_args = ["--location", "eastus2", *effective_args]
    return subprocess.run(
        [
            BASH,
            str(ADMIN_PREFLIGHT_SH),
            "--subscription",
            env["FAKE_SUBSCRIPTION_ID"],
            *effective_args,
        ],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )


def _report(result: subprocess.CompletedProcess[str]) -> dict:
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(
            f"admin-preflight.sh did not emit JSON on stdout: {result.stdout!r}\n"
            f"stderr={result.stderr}"
        )


def test_defaults_participant_count_to_one_and_reports_it(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    # Headroom of 100K is exactly sufficient for GPT-5.5's 100K single-
    # environment requirement, but would fail for any count > 1.
    result = _run_admin_preflight(
        fake_az_bin,
        tmp_path,
        ["--format", "json"],
        {
            "FAKE_MODELS_EASTUS2": _write_json(tmp_path, "models-e.json", FULL_MODELS_FIXTURE),
            "FAKE_USAGE_EASTUS2": _write_json(
                tmp_path, "usage-e.json", _usage_fixture_with_headroom(100.0)
            ),
            "FAKE_MODELS_SWEDENCENTRAL": _write_json(
                tmp_path, "models-s.json", FULL_MODELS_FIXTURE
            ),
            "FAKE_USAGE_SWEDENCENTRAL": _write_json(
                tmp_path, "usage-s.json", _usage_fixture_with_headroom(100.0)
            ),
        },
    )
    report = _report(result)
    assert report["participant_count"] == 1

    gpt41_eastus2 = next(
        c for c in report["checks"] if c["name"] == f"model-sku:{PRIMARY_MODEL}/eastus2"
    )
    assert gpt41_eastus2["status"] == "pass"
    assert "40K * 1 participant(s) = 40K" in gpt41_eastus2["detail"]
    model_checks = [c for c in report["checks"] if c["name"].startswith("model-sku:")]
    assert {c["name"].split(":")[1].split("/")[0] for c in model_checks} == {
        PRIMARY_MODEL,
        EVALUATION_MODEL,
        "text-embedding-3-small",
    }
    assert len(model_checks) == 3
    assert all(c["name"].endswith("/eastus2") for c in model_checks)
    assert "fallback_location" not in report
    assert all(c["status"] == "pass" for c in model_checks)
    evaluation_check = next(
        c for c in model_checks if c["name"] == f"model-sku:{EVALUATION_MODEL}/eastus2"
    )
    assert "100K * 1 participant(s) = 100K" in evaluation_check["detail"]
    for provider in (
        "Microsoft.ManagedIdentity",
        "Microsoft.ContainerInstance",
        "Microsoft.Resources",
    ):
        assert any(
            check["name"] == f"provider:{provider}" and check["status"] == "pass"
            for check in report["checks"]
        )


def test_aggregate_capacity_scales_with_participant_count(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    # Headroom of 90K covers 2 participants' worth of primary (2*40=80) but
    # not 3 (3*40=120). GPT-5.5 headroom of 250K likewise covers 2*100,
    # not 3*100 -- proves both requirements scale with participant count.
    env = {
        "FAKE_MODELS_EASTUS2": _write_json(tmp_path, "models-e.json", FULL_MODELS_FIXTURE),
        "FAKE_USAGE_EASTUS2": _write_json(
            tmp_path,
            "usage-e.json",
            _usage_fixture_with_headroom(90.0, evaluation_headroom_k=250.0),
        ),
        "FAKE_MODELS_SWEDENCENTRAL": _write_json(tmp_path, "models-s.json", FULL_MODELS_FIXTURE),
        "FAKE_USAGE_SWEDENCENTRAL": _write_json(
            tmp_path,
            "usage-s.json",
            _usage_fixture_with_headroom(90.0, evaluation_headroom_k=250.0),
        ),
    }

    report_2 = _report(
        _run_admin_preflight(
            fake_az_bin, tmp_path, ["--participant-count", "2", "--format", "json"], env
        )
    )
    assert report_2["participant_count"] == 2
    gpt41_2 = next(
        c for c in report_2["checks"] if c["name"] == f"model-sku:{PRIMARY_MODEL}/eastus2"
    )
    assert gpt41_2["status"] == "pass"
    assert "40K * 2 participant(s) = 80K" in gpt41_2["detail"]
    evaluation_2 = next(
        c for c in report_2["checks"] if c["name"] == f"model-sku:{EVALUATION_MODEL}/eastus2"
    )
    assert evaluation_2["status"] == "pass"
    assert "100K * 2 participant(s) = 200K" in evaluation_2["detail"]

    report_3 = _report(
        _run_admin_preflight(
            fake_az_bin, tmp_path, ["--participant-count", "3", "--format", "json"], env
        )
    )
    assert report_3["participant_count"] == 3
    gpt41_3 = next(
        c for c in report_3["checks"] if c["name"] == f"model-sku:{PRIMARY_MODEL}/eastus2"
    )
    assert gpt41_3["status"] == "warn"
    assert "40K * 3 participant(s) = 120K" in gpt41_3["detail"]
    assert "BELOW" in gpt41_3["detail"]
    evaluation_3 = next(
        c for c in report_3["checks"] if c["name"] == f"model-sku:{EVALUATION_MODEL}/eastus2"
    )
    assert evaluation_3["status"] == "warn"
    assert "100K * 3 participant(s) = 300K" in evaluation_3["detail"]
    assert "BELOW" in evaluation_3["detail"]


def test_search_basic_service_count_quota_scales_with_participant_count(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    env = {
        "FAKE_MODELS_EASTUS2": _write_json(tmp_path, "models-e.json", FULL_MODELS_FIXTURE),
        "FAKE_USAGE_EASTUS2": _write_json(
            tmp_path, "usage-e.json", _usage_fixture_with_headroom(500.0)
        ),
        "FAKE_MODELS_SWEDENCENTRAL": _write_json(tmp_path, "models-s.json", FULL_MODELS_FIXTURE),
        "FAKE_USAGE_SWEDENCENTRAL": _write_json(
            tmp_path, "usage-s.json", _usage_fixture_with_headroom(500.0)
        ),
        "FAKE_SEARCH_USAGE_EASTUS2": _write_json(
            tmp_path, "search-e.json", _search_usage_fixture(limit=12, current=10)
        ),
        "FAKE_SEARCH_USAGE_SWEDENCENTRAL": _write_json(
            tmp_path, "search-s.json", _search_usage_fixture(limit=12, current=9)
        ),
    }

    report = _report(
        _run_admin_preflight(
            fake_az_bin, tmp_path, ["--participant-count", "3", "--format", "json"], env
        )
    )
    eastus2 = next(c for c in report["checks"] if c["name"] == "search-service-quota:basic/eastus2")
    assert eastus2["status"] == "warn"
    assert "headroom=2 (limit=12, current=10)" in eastus2["detail"]
    assert "required 3 service(s)" in eastus2["detail"]
    assert not any("swedencentral" in check["name"] for check in report["checks"])

    selected_report = _report(
        _run_admin_preflight(
            fake_az_bin,
            tmp_path,
            ["--location", "swedencentral", "--participant-count", "3", "--format", "json"],
            env,
        )
    )
    swedencentral = next(
        check
        for check in selected_report["checks"]
        if check["name"] == "search-service-quota:basic/swedencentral"
    )
    assert swedencentral["status"] == "pass"
    assert "headroom=3 (limit=12, current=9)" in swedencentral["detail"]
    assert "does not guarantee live physical SKU capacity" in swedencentral["detail"]


def test_rejects_non_positive_participant_count_before_any_azure_call(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    result = _run_admin_preflight(
        fake_az_bin,
        tmp_path,
        ["--participant-count", "0", "--format", "json"],
        {},
    )
    assert result.returncode == 1
    assert "--participant-count must be a positive integer" in result.stderr

    result_non_numeric = _run_admin_preflight(
        fake_az_bin,
        tmp_path,
        ["--participant-count", "abc", "--format", "json"],
        {},
    )
    assert result_non_numeric.returncode == 1
    assert "--participant-count must be a positive integer" in result_non_numeric.stderr


def test_markdown_report_shows_participant_count(fake_az_bin: Path, tmp_path: Path) -> None:
    env = {
        "FAKE_MODELS_EASTUS2": _write_json(tmp_path, "models-e.json", FULL_MODELS_FIXTURE),
        "FAKE_USAGE_EASTUS2": _write_json(
            tmp_path, "usage-e.json", _usage_fixture_with_headroom(400.0)
        ),
        "FAKE_MODELS_SWEDENCENTRAL": _write_json(tmp_path, "models-s.json", FULL_MODELS_FIXTURE),
        "FAKE_USAGE_SWEDENCENTRAL": _write_json(
            tmp_path, "usage-s.json", _usage_fixture_with_headroom(400.0)
        ),
    }
    result = _run_admin_preflight(
        fake_az_bin, tmp_path, ["--participant-count", "4", "--format", "markdown"], env
    )
    assert result.returncode == 0, result.stderr
    assert "Participant/team count (aggregate quota target): `4`" in result.stdout


def test_resolves_the_sku_supporting_version_not_the_highest_overall_version(
    fake_az_bin: Path, tmp_path: Path
) -> None:
    """The primary model's HIGHEST version does not support the
    required 'GlobalStandard' SKU, only an older version does. The report
    must show the SKU-supporting version and its own usageName as evidence,
    never the highest version combined with a mismatched usageName."""
    result = _run_admin_preflight(
        fake_az_bin,
        tmp_path,
        ["--format", "json"],
        {
            "FAKE_MODELS_EASTUS2": _write_json(
                tmp_path, "models-e.json", MODELS_SKU_ONLY_ON_OLDER_VERSION_FIXTURE
            ),
            "FAKE_USAGE_EASTUS2": _write_json(
                tmp_path, "usage-e.json", _usage_fixture_with_headroom(100.0)
            ),
            "FAKE_MODELS_SWEDENCENTRAL": _write_json(
                tmp_path, "models-s.json", MODELS_SKU_ONLY_ON_OLDER_VERSION_FIXTURE
            ),
            "FAKE_USAGE_SWEDENCENTRAL": _write_json(
                tmp_path, "usage-s.json", _usage_fixture_with_headroom(100.0)
            ),
        },
    )
    report = _report(result)
    gpt41_eastus2 = next(
        c for c in report["checks"] if c["name"] == f"model-sku:{PRIMARY_MODEL}/eastus2"
    )
    assert gpt41_eastus2["status"] == "pass"
    assert "resolved version='2025-01-01'" in gpt41_eastus2["detail"]
    assert f"usageName='{GPT41_GLOBALSTANDARD_USAGE}'" in gpt41_eastus2["detail"]
    assert "resolved version='2025-04-14'" not in gpt41_eastus2["detail"]

"""Hermetic contract tests for scripts/request-quota-increase.sh."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "request-quota-increase.sh"
BASH = shutil.which("bash")
JQ = shutil.which("jq")

pytestmark = pytest.mark.skipif(
    BASH is None or JQ is None,
    reason="quota request contract tests require bash and jq",
)

FAKE_AZ = r"""#!/usr/bin/env bash
set -euo pipefail

case "${1:-} ${2:-}" in
  "account show")
    exit 0
    ;;
  "cognitiveservices model")
    cat <<'JSON'
[
  {"model":{"name":"gpt-5.6-luna","version":"v1","isDefaultVersion":true,"skus":[{"name":"GlobalStandard","usageName":"OpenAI.GlobalStandard.gpt-5.6-luna"}]}},
  {"model":{"name":"gpt-5.6-sol","version":"v2","isDefaultVersion":true,"skus":[{"name":"GlobalStandard","usageName":"OpenAI.GlobalStandard.gpt-5.6-sol"}]}},
  {"model":{"name":"text-embedding-3-small","version":"1","isDefaultVersion":true,"skus":[{"name":"GlobalStandard","usageName":"OpenAI.GlobalStandard.text-embedding-3-small"}]}}
]
JSON
    ;;
  "rest --method")
    args="$*"
    if [[ "${args}" == *"Microsoft.CognitiveServices"* ]]; then
      cat <<'JSON'
{"value":[
  {"name":{"value":"OpenAI.GlobalStandard.gpt-5.6-luna"},"currentValue":10,"limit":1000},
  {"name":{"value":"OpenAI.GlobalStandard.gpt-5.6-sol"},"currentValue":20,"limit":1000},
  {"name":{"value":"OpenAI.GlobalStandard.text-embedding-3-small"},"currentValue":30,"limit":1000}
]}
JSON
    else
      echo '{"value":[{"name":{"value":"basic"},"currentValue":2,"limit":12}]}'
    fi
    ;;
  *)
    echo "fake az: unhandled command: $*" >&2
    exit 1
    ;;
esac
"""


@pytest.fixture
def fake_bin(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    az_path = bin_dir / "az"
    az_path.write_text(FAKE_AZ, encoding="utf-8")
    az_path.chmod(az_path.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def _run(fake_bin: Path, tmp_path: Path, *args: str, browser: Path | None = None):
    env = dict(os.environ)
    env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
    if browser is not None:
        env["BROWSER"] = str(browser)
    return subprocess.run(
        [BASH, str(SCRIPT), "--subscription", "22222222-2222-2222-2222-222222222222", *args],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )


def test_calculates_minimum_total_limits(fake_bin: Path, tmp_path: Path) -> None:
    result = _run(fake_bin, tmp_path, "--location", "swedencentral", "--participant-count", "3")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["submission_mode"] == "portal-required"
    requested_limits = [
        request["minimum_requested_total_limit_k_tpm"] for request in report["model_requests"]
    ]
    assert requested_limits == [
        70,
        320,
        90,
    ]
    assert report["search_request"] == {
        "sku": "basic",
        "current_service_count": 2,
        "current_limit": 12,
        "aggregate_required_services": 3,
        "minimum_requested_total_limit": 5,
        "note": (
            "This service-count limit does not reserve or guarantee live physical SKU capacity."
        ),
    }


def test_reports_manual_submission_urls(fake_bin: Path, tmp_path: Path) -> None:
    result = _run(fake_bin, tmp_path)

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["portal_urls"] == {
        "model_quota_request_form": "https://aka.ms/oai/stuquotarequest",
        "search_quota": (
            "https://portal.azure.com/#blade/Microsoft_Azure_Capacity/QuotaMenuBlade/myQuotas"
        ),
    }

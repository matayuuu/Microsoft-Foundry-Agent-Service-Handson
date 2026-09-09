"""Static contracts for the Serverless Foundry IQ setup fallback."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "prepare_serverless_foundry_iq.sh"
SETUP = REPO_ROOT / "scripts" / "setup.sh"


def test_serverless_foundry_iq_uses_preview_api_and_keyless_auth() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert 'API_VERSION="2026-08-01-preview"' in text
    assert "az account get-access-token" in text
    assert "https://search.azure.com" in text
    assert "api-key" not in text
    assert "Authorization: Bearer ${ACCESS_TOKEN}" in text


def test_serverless_foundry_iq_prepares_sources_luna_base_and_smoke_retrieve() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    for expected in (
        "contoso-travel-policy-source",
        "contoso-travel-approval-source",
        "contoso-travel-policy",
        "contoso-travel-approval",
        "contoso-travel-knowledge-lab",
        'modelName: "gpt-5.6-luna"',
        "knowledgebases",
        "/retrieve?api-version=",
        "maxOutputSize: 100000",
    ):
        assert expected in text
    assert "maxOutputSizeInTokens" not in text


def test_setup_runs_fallback_only_for_serverless_search() -> None:
    text = SETUP.read_text(encoding="utf-8")

    assert 'if [[ "${SEARCH_PRICING_MODEL}" == "serverless" ]]; then' in text
    assert '"${SCRIPT_DIR}/prepare_serverless_foundry_iq.sh"' in text

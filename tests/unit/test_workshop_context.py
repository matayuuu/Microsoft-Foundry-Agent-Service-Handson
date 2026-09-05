"""Unit tests for scripts/lib/workshop_context.py.

No network or Azure credential exchange happens in this file:
``build_credential`` only constructs credential objects (it never calls
``get_token``), and everything else is pure JSON/dict handling.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from azure.identity import AzureCliCredential, DefaultAzureCredential

from scripts.lib import workshop_context as ctx


def _write_context(tmp_path: Path, terraform_outputs: dict[str, dict[str, str]]) -> Path:
    path = tmp_path / "context.json"
    path.write_text(
        json.dumps(
            {
                "generated_at": "2026-01-01T00:00:00Z",
                "subscription_id": "00000000-0000-0000-0000-000000000000",
                "resource_group_name": "rg-test",
                "location": "eastus2",
                "terraform_inputs": {},
                "terraform_outputs": terraform_outputs,
            }
        ),
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# load_context
# ---------------------------------------------------------------------------


def test_load_context_raises_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(ctx.WorkshopContextError, match="not found"):
        ctx.load_context(tmp_path / "missing.json")


def test_load_context_raises_on_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ctx.WorkshopContextError, match="not valid JSON"):
        ctx.load_context(path)


def test_load_context_raises_when_terraform_outputs_missing(tmp_path: Path) -> None:
    path = tmp_path / "context.json"
    path.write_text(json.dumps({"subscription_id": "x"}), encoding="utf-8")

    with pytest.raises(ctx.WorkshopContextError, match="terraform_outputs"):
        ctx.load_context(path)


def test_load_context_returns_parsed_dict(tmp_path: Path) -> None:
    path = _write_context(tmp_path, {"foundry_project_endpoint": {"value": "https://example"}})

    context = ctx.load_context(path)

    assert context["resource_group_name"] == "rg-test"
    assert context["terraform_outputs"]["foundry_project_endpoint"]["value"] == "https://example"


# ---------------------------------------------------------------------------
# terraform_output / project_endpoint / travel_api_base_url
# ---------------------------------------------------------------------------


def test_terraform_output_returns_value() -> None:
    context = {"terraform_outputs": {"search_service_name": {"value": "srch-workshop-abc123"}}}

    assert ctx.terraform_output(context, "search_service_name") == "srch-workshop-abc123"


@pytest.mark.parametrize(
    ("key", "deployment"),
    [
        ("primary_model_deployment_name", "gpt-5.6-luna"),
        ("optimizer_model_deployment_name", "gpt-5.5"),
        ("embedding_model_deployment_name", "embedding"),
        ("primary_model_deployment_name", "custom-agent-deployment"),
        ("optimizer_model_deployment_name", "custom-judge-deployment"),
    ],
)
def test_model_deployment_output_uses_context_without_fixed_defaults(
    tmp_path: Path, key: str, deployment: str
) -> None:
    context = ctx.load_context(_write_context(tmp_path, {key: {"value": deployment}}))
    assert ctx.terraform_output(context, key) == deployment


def test_terraform_output_raises_with_available_keys_listed() -> None:
    context = {"terraform_outputs": {"foo": {"value": "bar"}}}

    with pytest.raises(ctx.WorkshopContextError, match="foo"):
        ctx.terraform_output(context, "missing_key")


def test_project_endpoint_reads_foundry_project_endpoint_output() -> None:
    context = {
        "terraform_outputs": {
            "foundry_project_endpoint": {
                "value": "https://acct.services.ai.azure.com/api/projects/proj"
            }
        }
    }

    assert ctx.project_endpoint(context) == "https://acct.services.ai.azure.com/api/projects/proj"


def test_travel_api_base_url_prefixes_https_onto_fqdn() -> None:
    context = {"terraform_outputs": {"travel_api_fqdn": {"value": "travel-api.example.io"}}}

    assert ctx.travel_api_base_url(context) == "https://travel-api.example.io"


# ---------------------------------------------------------------------------
# build_credential
# ---------------------------------------------------------------------------


def test_build_credential_default_kind_is_azure_cli() -> None:
    assert isinstance(ctx.build_credential(), AzureCliCredential)


def test_build_credential_default_kind_string_returns_default_azure_credential() -> None:
    assert isinstance(ctx.build_credential("default"), DefaultAzureCredential)


def test_build_credential_rejects_unknown_kind() -> None:
    with pytest.raises(ctx.WorkshopContextError, match="unknown credential kind"):
        ctx.build_credential("client-secret")

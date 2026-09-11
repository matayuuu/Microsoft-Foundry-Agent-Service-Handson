"""Shared helpers for participant SDK scripts.

Participant scripts read the non-secret, portal-neutral
``.workshop/context.json``, resolve a resource output with an actionable error,
and use the signed-in Azure CLI identity.

No network calls happen in this module. It only reads a local JSON file and
constructs (but does not use) a credential object.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from azure.core.credentials import TokenCredential
from azure.identity import AzureCliCredential, DefaultAzureCredential

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTEXT_PATH = REPO_ROOT / ".workshop" / "context.json"

# Fixed workshop-wide constants. These are the same for every participant
# environment (unlike resource group names, subscription IDs, or generated
# FQDNs), so they are safe to hardcode here rather than looked up from
# context.json. Labs must still tell participants to confirm these in the
# portal rather than assuming they were never changed.
DEFAULT_SEARCH_INDEX_NAME = "contoso-travel-policy"
DEFAULT_AGENT_NAME = "contoso-travel-assistant"
DEFAULT_TOOLBOX_NAME = "contoso-travel-toolbox"
SOURCE_REPOSITORY = "https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson"
CUSTOM_TEMPLATE_RESOURCE_OUTPUTS = (
    "resource_group_name",
    "location",
    "ai_services_account_name",
    "ai_services_endpoint",
    "openai_endpoint",
    "foundry_project_name",
    "foundry_project_id",
    "foundry_project_endpoint",
    "primary_model_deployment_name",
    "evaluation_model_deployment_name",
    "optimizer_model_deployment_name",
    "embedding_model_deployment_name",
    "search_service_name",
    "search_service_endpoint",
    "search_pricing_model",
    "log_analytics_workspace_name",
    "application_insights_name",
    "application_insights_id",
    "azureml_workspace_name",
    "azureml_workspace_id",
    "storage_account_name",
    "storage_account_id",
    "key_vault_name",
    "key_vault_id",
    "search_connection_name",
    "knowledge_mcp_connection_name",
    "application_insights_connection_name",
    "travel_api_fqdn",
    "travel_api_container_app_name",
    "foundry_portal_url",
)
CONTEXT_RECOVERY = (
    "Check the custom-template deployment in Azure Portal, then download and extract "
    "the completed workshop ZIP from the private workshop-files container."
)


class WorkshopContextError(Exception):
    """Raised for any problem reading or interpreting ``.workshop/context.json``.

    Callers should catch this specific exception at the CLI boundary and print
    ``str(exc)`` rather than a raw traceback; the message is always written to
    be actionable on its own.
    """


def load_context(path: Path) -> dict[str, Any]:
    """Load and minimally validate ``.workshop/context.json``.

    Raises ``WorkshopContextError`` (never a bare ``Exception``) if the file is
    missing, is not valid JSON, or is missing the canonical
    ``resource_outputs`` object.
    """
    if not path.exists():
        raise WorkshopContextError(f"context file not found: {path}\n{CONTEXT_RECOVERY}")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WorkshopContextError(f"could not read context file {path}: {exc}") from exc
    try:
        context = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WorkshopContextError(f"context file {path} is not valid JSON: {exc}") from exc
    if not isinstance(context, dict):
        raise WorkshopContextError(f"context file {path} must contain a JSON object")
    if not isinstance(context.get("resource_outputs"), dict):
        raise WorkshopContextError(
            f"context file {path} is missing the 'resource_outputs' object. {CONTEXT_RECOVERY}"
        )
    return context


def workshop_output(context: dict[str, Any], key: str) -> str:
    """Return a string resource output ``key`` from a loaded workshop context.

    Raises ``WorkshopContextError`` (listing the available keys) if the output
    is absent, which is more actionable for a participant than a ``KeyError``.
    """
    outputs = context.get("resource_outputs", {})
    entry = outputs.get(key)
    if not isinstance(entry, dict) or "value" not in entry:
        available = ", ".join(sorted(outputs)) or "(none)"
        raise WorkshopContextError(
            f"workshop resource output '{key}' not found in .workshop/context.json. "
            f"Available resource outputs: {available}. {CONTEXT_RECOVERY}"
        )
    value = entry["value"]
    if value is None or value == "":
        raise WorkshopContextError(
            f"workshop resource output '{key}' is unavailable in .workshop/context.json. "
            f"This required output is empty. {CONTEXT_RECOVERY}"
        )
    return str(value)


def participant_object_id(context: dict[str, Any], override: str | None = None) -> str:
    """Resolve the intended participant, never the bootstrap's signed-in identity."""
    value = override if override is not None else context.get("participant_object_id")
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value) is None
        or UUID(value).int == 0
    ):
        raise WorkshopContextError(
            "A valid, nonzero participant_object_id is required in context, or pass "
            "--participant-object-id with the intended participant's Microsoft Entra object ID. "
            "The deployment managed identity is not the participant."
        )
    return str(UUID(value))


def validate_source_revision(value: Any) -> str:
    """Accept only an immutable, published-source SHA; never a branch or tag."""
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise WorkshopContextError(
            "source_revision must be a published lowercase 40-character commit SHA."
        )
    return value


def project_endpoint(context: dict[str, Any]) -> str:
    """Microsoft Foundry project endpoint, e.g.
    ``https://<account>.services.ai.azure.com/api/projects/<project>``."""
    return workshop_output(context, "foundry_project_endpoint")


def travel_api_base_url(context: dict[str, Any]) -> str:
    """Public HTTPS base URL of the deployed Travel Ops API container app."""
    return f"https://{workshop_output(context, 'travel_api_fqdn')}"


def build_credential(kind: str = "azure-cli") -> TokenCredential:
    """Build a credential sourced only from ``az login`` -- no client secrets,
    API keys, or certificates are ever read.

    ``kind="azure-cli"`` (default) uses ``AzureCliCredential`` directly, which
    only ever reads the current ``az login`` session token.
    ``kind="default"`` uses ``DefaultAzureCredential`` for deployed or
    administrator-controlled environments that intentionally use managed identity.
    """
    if kind == "azure-cli":
        return AzureCliCredential()
    if kind == "default":
        return DefaultAzureCredential()
    raise WorkshopContextError(
        f"unknown credential kind '{kind}' (expected 'azure-cli' or 'default')"
    )

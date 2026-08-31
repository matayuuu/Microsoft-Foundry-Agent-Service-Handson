"""Contract tests for infra/*.tf.

These are static, regex-based assertions over the Terraform source text --
deliberately not a full HCL parser dependency -- that lock in the
non-negotiable constraints from AGENTS.md and the workshop design:

* AzureRM/AzAPI provider versions and Foundry ARM API version are pinned as
  documented.
* Provider auto-registration is disabled.
* No resource group, Cosmos DB, Key Vault, or Container Registry resource is
  ever created (existing-RG-only, Basic Agent Setup only).
* Local/shared-key auth is disabled wherever the resource supports it.
* The RBAC role-definition GUIDs match what scripts/validate_environment.py
  and docs/admin expect.

If a future edit to infra/ breaks one of these constraints, this test suite
is the tripwire.
"""

from __future__ import annotations

import re
from pathlib import Path

INFRA_DIR = Path(__file__).resolve().parents[2] / "infra"


def _read(*names: str) -> str:
    return "\n".join((INFRA_DIR / name).read_text(encoding="utf-8") for name in names)


def _all_tf_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in sorted(INFRA_DIR.glob("*.tf")))


def _all_tf_text_excluding_comments() -> str:
    # Strip full-line `#` comments so documentation that *mentions* a
    # disallowed resource type (to explain why it is absent) does not trip
    # substring-based assertions below.
    lines = []
    for p in sorted(INFRA_DIR.glob("*.tf")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip().startswith("#"):
                lines.append(line)
    return "\n".join(lines)


def test_infra_directory_has_expected_files() -> None:
    expected = {
        "versions.tf",
        "providers.tf",
        "variables.tf",
        "locals.tf",
        "data.tf",
        "search.tf",
        "monitoring.tf",
        "container_apps.tf",
        "foundry_account.tf",
        "foundry_project.tf",
        "foundry_deployments.tf",
        "foundry_connections.tf",
        "rbac.tf",
        "outputs.tf",
    }
    actual = {p.name for p in INFRA_DIR.glob("*.tf")}

    assert expected <= actual
    assert "storage.tf" not in actual


def test_provider_versions_are_pinned_as_documented() -> None:
    text = _read("versions.tf")

    assert re.search(r'source\s*=\s*"hashicorp/azurerm"', text)
    assert re.search(r'source\s*=\s*"Azure/azapi"', text)
    assert re.search(r'azurerm\s*=\s*\{[^}]*version\s*=\s*"~>\s*5\.0"', text, re.DOTALL)
    assert re.search(r'azapi\s*=\s*\{[^}]*version\s*=\s*"~>\s*2\.0"', text, re.DOTALL)


def test_versions_tf_declares_no_backend_block() -> None:
    # State must default to local; an active backend is opt-in via
    # backend.tf, copied from the inert backend.remote.tf.example.
    text = _all_tf_text()

    assert 'backend "azurerm"' not in text


def test_backend_remote_example_is_inert() -> None:
    example_path = INFRA_DIR / "backend.remote.tf.example"

    assert example_path.exists()
    text = example_path.read_text(encoding="utf-8")
    # Every non-comment line inside the example backend block must be
    # commented out so a bare `terraform init` never picks it up.
    active_backend_lines = [
        line for line in text.splitlines() if "backend" in line and not line.strip().startswith("#")
    ]
    assert active_backend_lines == []


def test_provider_auto_registration_is_disabled() -> None:
    text = _read("providers.tf")

    assert re.search(r'resource_provider_registrations\s*=\s*"none"', text)
    assert re.search(r"skip_provider_registration\s*=\s*true", text)


def test_no_resource_group_is_ever_created() -> None:
    text = _all_tf_text()

    # The resource group must only ever be read via a data source, never
    # created/destroyed by Terraform.
    assert 'resource "azurerm_resource_group"' not in text
    assert 'data "azurerm_resource_group"' in text


def test_basic_agent_setup_excludes_disallowed_resource_types() -> None:
    text = _all_tf_text_excluding_comments().lower()

    disallowed_markers = [
        "azurerm_cosmosdb",
        "microsoft.documentdb",
        "azurerm_key_vault",
        "microsoft.keyvault",
        "azurerm_container_registry",
        "microsoft.containerregistry",
        "capabilityhosts",
    ]
    for marker in disallowed_markers:
        assert marker not in text, f"found disallowed marker '{marker}' in infra/*.tf"


def test_foundry_resources_use_azapi_and_pinned_api_version() -> None:
    text = _read(
        "foundry_account.tf",
        "foundry_project.tf",
        "foundry_deployments.tf",
        "foundry_connections.tf",
    )

    for resource_type in (
        "Microsoft.CognitiveServices/accounts",
        "Microsoft.CognitiveServices/accounts/projects",
        "Microsoft.CognitiveServices/accounts/deployments",
        "Microsoft.CognitiveServices/accounts/projects/connections",
    ):
        assert (
            f'type      = "{resource_type}@2026-05-01"' in text
            or f'type = "{resource_type}@2026-05-01"' in text
        )


def test_foundry_account_disables_local_auth_and_allows_project_management() -> None:
    text = _read("foundry_account.tf")

    assert re.search(r"disableLocalAuth\s*=\s*true", text)
    assert re.search(r"allowProjectManagement\s*=\s*true", text)


def test_search_service_disables_local_authentication() -> None:
    text = _read("search.tf")

    assert re.search(r"local_authentication_enabled\s*=\s*false", text)
    assert re.search(r'semantic_search_sku\s*=\s*"free"', text)


def test_core_infrastructure_has_no_storage_dependency() -> None:
    text = _all_tf_text_excluding_comments().lower()

    for marker in (
        "azurerm_storage_account",
        "microsoft.storage/storageaccounts",
        "azurestorageaccount",
        "storage_blob_data_contributor",
    ):
        assert marker not in text


def test_container_app_uses_variable_image_reference_not_a_literal() -> None:
    text = _read("container_apps.tf")

    assert "var.travel_api_image_ref" in text
    # Guard against ever hardcoding a literal ghcr.io reference in the
    # resource itself (the variable's own validation enforces the digest
    # format; the resource must always consume the variable).
    assert "ghcr.io/" not in text
    assert re.search(r"min_replicas\s*=\s*0", text)
    assert re.search(r"target_port\s*=\s*var\.travel_api_container_port", text)


def test_container_app_environment_uses_log_analytics_destination() -> None:
    text = _read("container_apps.tf")

    assert re.search(r'logs_destination\s*=\s*"log-analytics"', text)
    assert "log_analytics_workspace_id" in text


def test_travel_api_receives_public_citation_source_base() -> None:
    container_apps = _read("container_apps.tf")
    variables = _read("variables.tf")

    assert 'name  = "WORKSHOP_SOURCE_BASE"' in container_apps
    assert "value = var.source_base" in container_apps
    assert re.search(r'variable\s+"source_base"\s*\{', variables)


def test_travel_api_port_matches_container_contract() -> None:
    text = _read("variables.tf")

    match = re.search(r'variable\s+"travel_api_container_port"\s*\{(.*?)\n\}', text, re.DOTALL)
    assert match is not None
    assert re.search(r"default\s*=\s*8080", match.group(1))


def test_resources_use_selected_workshop_location_not_rg_metadata_location() -> None:
    text = _all_tf_text_excluding_comments()

    assert "data.azurerm_resource_group.workshop.location" not in text
    assert text.count("var.location") >= 8


def test_travel_api_image_ref_variable_requires_immutable_digest() -> None:
    text = _read("variables.tf")

    match = re.search(r'variable\s+"travel_api_image_ref"\s*\{.*?\}\s*\}', text, re.DOTALL)
    assert match is not None
    assert "@sha256" in match.group(0)


def test_optimizer_model_version_has_no_default() -> None:
    text = _read("variables.tf")

    match = re.search(r'variable\s+"optimizer_model_version"\s*\{(.*?)\n\}', text, re.DOTALL)
    assert match is not None
    assert "default" not in match.group(1)


def test_model_deployments_are_serialized_after_project_creation() -> None:
    text = _read("foundry_deployments.tf")

    assert "depends_on = [azapi_resource.project]" in text
    assert "depends_on = [azapi_resource.primary_model_deployment]" in text
    assert "depends_on = [azapi_resource.optimizer_model_deployment]" in text


def test_embedding_model_uses_cross_region_global_standard_sku() -> None:
    text = _read("variables.tf")
    match = re.search(r'variable\s+"embedding_model_sku"\s*\{(.*?)\n\}', text, re.DOTALL)

    assert match is not None
    assert re.search(r'default\s*=\s*"GlobalStandard"', match.group(1))


def test_outputs_include_openai_v1_endpoint_for_embeddings() -> None:
    text = _read("outputs.tf")

    assert 'output "openai_endpoint"' in text
    assert ".openai.azure.com/openai/v1/" in text


EXPECTED_ROLE_IDS = {
    "foundry_user": "53ca6127-db72-4b80-b1b0-d745d6d5456d",
    "foundry_project_manager": "eadc314b-1a2d-4efa-be10-5d325db5065e",
    "search_index_data_contributor": "8ebe5a00-799e-43f5-93ac-243d3dce84a7",
    "search_index_data_reader": "1407120a-92aa-4202-b7e9-c0e197c71c8f",
    "search_service_contributor": "7ca78c08-252a-4471-8644-bb5ff32d4ba0",
    "log_analytics_reader": "73c42c96-874c-492b-b04d-ab87d138a893",
    "privileged_monitoring_data_reader": "dbc9c667-e97f-4491-aee6-90b9cf960190",
    "monitoring_metrics_publisher": "3913510d-42f4-4e42-8a64-420c390055eb",
    "cognitive_services_openai_user": "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd",
}


def test_role_ids_map_matches_documented_guids() -> None:
    text = _read("locals.tf")

    for key, guid in EXPECTED_ROLE_IDS.items():
        assert re.search(rf'{key}\s*=\s*"{guid}"', text), (
            f"role id '{key}' does not match expected GUID {guid}"
        )


def test_rbac_grants_participant_and_managed_identities() -> None:
    text = _read("rbac.tf")

    # Participant grants
    for role in (
        "foundry_user",
        "foundry_project_manager",
        "search_service_contributor",
        "search_index_data_contributor",
        "log_analytics_reader",
        "privileged_monitoring_data_reader",
        "monitoring_metrics_publisher",
    ):
        assert f"local.role_ids.{role}" in text

    # Managed identity grants
    assert "azapi_resource.project.output.identity.principalId" in text
    assert "azurerm_search_service.workshop.identity[0].principal_id" in text
    assert text.count("skip_service_principal_aad_check") >= 4


def test_application_insights_is_connected_keylessly() -> None:
    monitoring = _read("monitoring.tf")
    connections = _read("foundry_connections.tf")

    assert re.search(r"local_authentication_enabled\s*=\s*false", monitoring)
    assert 'category      = "AppInsights"' in connections
    assert "connections@2026-05-15-preview" in connections
    assert 'authType      = "ProjectManagedIdentity"' in connections
    assert "schema_validation_enabled = false" in connections


def test_outputs_never_expose_secrets() -> None:
    text = _read("outputs.tf")

    forbidden_substrings = ["primary_access_key", "connection_string", "admin_key", "primary_key"]
    lowered = text.lower()
    for forbidden in forbidden_substrings:
        assert forbidden not in lowered, (
            f"outputs.tf appears to expose a secret-like value: {forbidden}"
        )

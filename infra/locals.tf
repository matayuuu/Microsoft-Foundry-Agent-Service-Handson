# Naming and shared computed values.
#
# All resource names derive from a short, deterministic hash of the
# subscription + resource group instead of `random_string`, so that re-running
# terraform apply after a lost/regenerated local state still produces the
# same resource names (idempotent retries, no extra state to track).

locals {
  name_seed   = "${var.subscription_id}-${var.resource_group_name}-${var.location}"
  name_suffix = substr(md5(local.name_seed), 0, 8)
  prefix      = "fdyws" # Foundry workshop

  search_service_name      = lower("srch-${local.prefix}-${local.name_suffix}")
  ai_services_account_name = lower("aif-${local.prefix}-${local.name_suffix}")
  log_analytics_name       = lower("log-${local.prefix}-${local.name_suffix}")
  app_insights_name        = lower("appi-${local.prefix}-${local.name_suffix}")
  container_app_env_name   = lower("cae-${local.prefix}-${local.name_suffix}")
  container_app_name       = lower("ca-travel-api-${local.name_suffix}")

  # Built-in Azure role definition GUIDs. Prefer GUIDs over role-definition
  # data-source name lookups: Foundry's roles were recently renamed (Azure AI
  # User -> Foundry User, etc.) and GUIDs are stable across the rename.
  # Sources (retrieved 2026-08-21):
  #   - Foundry roles: https://learn.microsoft.com/azure/foundry/concepts/rbac-foundry
  #     and the microsoft-foundry skill's rbac reference.
  #   - Azure built-in roles: https://learn.microsoft.com/azure/role-based-access-control/built-in-roles
  role_ids = {
    foundry_user                      = "53ca6127-db72-4b80-b1b0-d745d6d5456d"
    foundry_project_manager           = "eadc314b-1a2d-4efa-be10-5d325db5065e"
    search_index_data_contributor     = "8ebe5a00-799e-43f5-93ac-243d3dce84a7"
    search_index_data_reader          = "1407120a-92aa-4202-b7e9-c0e197c71c8f"
    search_service_contributor        = "7ca78c08-252a-4471-8644-bb5ff32d4ba0"
    log_analytics_reader              = "73c42c96-874c-492b-b04d-ab87d138a893"
    privileged_monitoring_data_reader = "dbc9c667-e97f-4491-aee6-90b9cf960190"
    monitoring_metrics_publisher      = "3913510d-42f4-4e42-8a64-420c390055eb"
    cognitive_services_openai_user    = "5e0bd9bd-7b93-4f28-af87-19fc36ad61bd"
  }

  participant_object_id = var.participant_object_id != "" ? var.participant_object_id : data.azurerm_client_config.current.object_id
}

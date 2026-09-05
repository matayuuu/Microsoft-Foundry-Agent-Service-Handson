# Deterministic ARM IDs used only by scripts/prepare_terraform_plan.py when a
# successful Azure create was not persisted to the participant's local state.
# The script imports a target only after verifying the owning resource's
# workshop/managed-by tags, so similarly named non-workshop resources are never
# adopted.
locals {
  workshop_resource_group_id = "/subscriptions/${var.subscription_id}/resourceGroups/${var.resource_group_name}"
  ai_services_id             = "${local.workshop_resource_group_id}/providers/Microsoft.CognitiveServices/accounts/${local.ai_services_account_name}"
  project_id                 = "${local.ai_services_id}/projects/${var.project_name}"

  state_recovery_targets = [
    {
      address           = "azapi_resource.ai_services"
      id                = local.ai_services_id
      api_version       = "2026-05-01"
      owner_id          = local.ai_services_id
      owner_api_version = "2026-05-01"
    },
    {
      address           = "azapi_resource.project"
      id                = local.project_id
      api_version       = "2026-05-01"
      owner_id          = local.project_id
      owner_api_version = "2026-05-01"
    },
    {
      address           = "azapi_resource.primary_model_deployment"
      id                = "${local.ai_services_id}/deployments/gpt-5.6-luna"
      api_version       = "2026-05-01"
      owner_id          = local.ai_services_id
      owner_api_version = "2026-05-01"
    },
    {
      address           = "azapi_resource.optimizer_model_deployment"
      id                = "${local.ai_services_id}/deployments/gpt-5.5"
      api_version       = "2026-05-01"
      owner_id          = local.ai_services_id
      owner_api_version = "2026-05-01"
    },
    {
      address           = "azapi_resource.embedding_model_deployment"
      id                = "${local.ai_services_id}/deployments/embedding"
      api_version       = "2026-05-01"
      owner_id          = local.ai_services_id
      owner_api_version = "2026-05-01"
    },
    {
      address           = "azurerm_search_service.workshop"
      id                = "${local.workshop_resource_group_id}/providers/Microsoft.Search/searchServices/${local.search_service_name}"
      api_version       = "2025-05-01"
      owner_id          = "${local.workshop_resource_group_id}/providers/Microsoft.Search/searchServices/${local.search_service_name}"
      owner_api_version = "2025-05-01"
    },
    {
      address           = "azurerm_log_analytics_workspace.workshop"
      id                = "${local.workshop_resource_group_id}/providers/Microsoft.OperationalInsights/workspaces/${local.log_analytics_name}"
      api_version       = "2023-09-01"
      owner_id          = "${local.workshop_resource_group_id}/providers/Microsoft.OperationalInsights/workspaces/${local.log_analytics_name}"
      owner_api_version = "2023-09-01"
    },
    {
      address           = "azurerm_application_insights.workshop"
      id                = "${local.workshop_resource_group_id}/providers/Microsoft.Insights/components/${local.app_insights_name}"
      api_version       = "2020-02-02"
      owner_id          = "${local.workshop_resource_group_id}/providers/Microsoft.Insights/components/${local.app_insights_name}"
      owner_api_version = "2020-02-02"
    },
    {
      address           = "azurerm_container_app_environment.workshop"
      id                = "${local.workshop_resource_group_id}/providers/Microsoft.App/managedEnvironments/${local.container_app_env_name}"
      api_version       = "2024-03-01"
      owner_id          = "${local.workshop_resource_group_id}/providers/Microsoft.App/managedEnvironments/${local.container_app_env_name}"
      owner_api_version = "2024-03-01"
    },
    {
      address           = "azurerm_container_app.travel_api"
      id                = "${local.workshop_resource_group_id}/providers/Microsoft.App/containerApps/${local.container_app_name}"
      api_version       = "2024-03-01"
      owner_id          = "${local.workshop_resource_group_id}/providers/Microsoft.App/containerApps/${local.container_app_name}"
      owner_api_version = "2024-03-01"
    },
    {
      address           = "azapi_resource.search_connection"
      id                = "${local.project_id}/connections/contoso-travel-search"
      api_version       = "2026-05-01"
      owner_id          = local.project_id
      owner_api_version = "2026-05-01"
    },
    {
      address           = "azapi_resource.application_insights_connection"
      id                = "${local.project_id}/connections/contoso-travel-appinsights"
      api_version       = "2026-05-15-preview"
      owner_id          = local.project_id
      owner_api_version = "2026-05-01"
    },
  ]
}

# RBAC: least-privilege role assignments, scoped to this resource group's
# resources only. Terraform never writes subscription-scope role
# assignments (that would require permissions beyond the participant's
# RG-scoped Owner role and is out of scope for this workshop).
#
# Role GUIDs are defined once in locals.tf (local.role_ids) and cross-checked
# against learn.microsoft.com/azure/foundry/concepts/rbac-foundry and
# learn.microsoft.com/azure/role-based-access-control/built-in-roles
# (retrieved 2026-08-21).

# ---------------------------------------------------------------------------
# Participant grants
# ---------------------------------------------------------------------------

resource "azurerm_role_assignment" "participant_foundry_user" {
  scope              = azapi_resource.ai_services.id
  role_definition_id = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.foundry_user}"
  principal_id       = local.participant_object_id
}

resource "azurerm_role_assignment" "participant_foundry_project_manager" {
  scope              = azapi_resource.project.id
  role_definition_id = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.foundry_project_manager}"
  principal_id       = local.participant_object_id
}

resource "azurerm_role_assignment" "participant_search_service_contributor" {
  scope              = azurerm_search_service.workshop.id
  role_definition_id = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.search_service_contributor}"
  principal_id       = local.participant_object_id
}

resource "azurerm_role_assignment" "participant_search_index_data_contributor" {
  scope              = azurerm_search_service.workshop.id
  role_definition_id = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.search_index_data_contributor}"
  principal_id       = local.participant_object_id
}

resource "azurerm_role_assignment" "participant_log_analytics_reader" {
  scope              = azurerm_log_analytics_workspace.workshop.id
  role_definition_id = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.log_analytics_reader}"
  principal_id       = local.participant_object_id
}

resource "azurerm_role_assignment" "participant_privileged_monitoring_data_reader" {
  scope              = azurerm_application_insights.workshop.id
  role_definition_id = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.privileged_monitoring_data_reader}"
  principal_id       = local.participant_object_id
}

# ---------------------------------------------------------------------------
# Foundry project system-assigned managed identity grants
#
# The project's own identity needs to read/query the Foundry account it
# belongs to and read/write the Search index that backs Foundry IQ / the
# Knowledge Base tool at agent runtime.
# ---------------------------------------------------------------------------

resource "azurerm_role_assignment" "project_mi_foundry_user" {
  scope                            = azapi_resource.ai_services.id
  role_definition_id               = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.foundry_user}"
  principal_id                     = azapi_resource.project.output.identity.principalId
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "project_mi_search_index_data_contributor" {
  scope                            = azurerm_search_service.workshop.id
  role_definition_id               = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.search_index_data_contributor}"
  principal_id                     = azapi_resource.project.output.identity.principalId
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "project_mi_search_service_contributor" {
  scope                            = azurerm_search_service.workshop.id
  role_definition_id               = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.search_service_contributor}"
  principal_id                     = azapi_resource.project.output.identity.principalId
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "project_mi_monitoring_metrics_publisher" {
  scope                            = azurerm_application_insights.workshop.id
  role_definition_id               = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.monitoring_metrics_publisher}"
  principal_id                     = azapi_resource.project.output.identity.principalId
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "project_mi_log_analytics_reader" {
  scope                            = azurerm_application_insights.workshop.id
  role_definition_id               = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.log_analytics_reader}"
  principal_id                     = azapi_resource.project.output.identity.principalId
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "project_mi_privileged_monitoring_data_reader" {
  scope                            = azurerm_application_insights.workshop.id
  role_definition_id               = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.privileged_monitoring_data_reader}"
  principal_id                     = azapi_resource.project.output.identity.principalId
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

# ---------------------------------------------------------------------------
# Search service system-assigned managed identity grant
#
# Minimum role for the Azure AI Search Knowledge Base / built-in vectorizer
# to invoke the embedding and gpt-4.1 model deployments on the Foundry
# AIServices account without a stored API key.
# ---------------------------------------------------------------------------

resource "azurerm_role_assignment" "search_mi_cognitive_services_openai_user" {
  scope                            = azapi_resource.ai_services.id
  role_definition_id               = "/subscriptions/${var.subscription_id}/providers/Microsoft.Authorization/roleDefinitions/${local.role_ids.cognitive_services_openai_user}"
  principal_id                     = azurerm_search_service.workshop.identity[0].principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

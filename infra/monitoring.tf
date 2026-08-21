# Monitoring: workspace-based Application Insights backed by a Log Analytics
# workspace, used for Container App diagnostics and (optionally) as the
# observability sink referenced from the Foundry project's AppInsights
# connection in foundry_connections.tf.
resource "azurerm_log_analytics_workspace" "workshop" {
  name                = local.log_analytics_name
  resource_group_name = data.azurerm_resource_group.workshop.name
  location            = var.location

  sku               = "PerGB2018"
  retention_in_days = 30

  tags = var.tags
}

resource "azurerm_application_insights" "workshop" {
  name                = local.app_insights_name
  resource_group_name = data.azurerm_resource_group.workshop.name
  location            = var.location

  application_type             = "web"
  workspace_id                 = azurerm_log_analytics_workspace.workshop.id
  local_authentication_enabled = false

  tags = var.tags
}

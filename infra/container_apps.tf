# Container Apps: runs the Travel Ops mock API published by another
# workstream to a public, immutable GHCR image digest (var.travel_api_image_ref).
# Terraform only consumes that image reference; it never builds or pushes it.
resource "azurerm_container_app_environment" "workshop" {
  name                       = local.container_app_env_name
  resource_group_name        = data.azurerm_resource_group.workshop.name
  location                   = var.location
  log_analytics_workspace_id = azurerm_log_analytics_workspace.workshop.id

  tags = var.tags
}

resource "azurerm_container_app" "travel_api" {
  name                         = local.container_app_name
  resource_group_name          = data.azurerm_resource_group.workshop.name
  container_app_environment_id = azurerm_container_app_environment.workshop.id
  revision_mode                = "Single"

  template {
    min_replicas = 0
    max_replicas = 1

    container {
      name   = "travel-api"
      image  = var.travel_api_image_ref
      cpu    = var.travel_api_cpu
      memory = var.travel_api_memory
    }
  }

  ingress {
    external_enabled = true
    target_port      = var.travel_api_container_port
    transport        = "auto"

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

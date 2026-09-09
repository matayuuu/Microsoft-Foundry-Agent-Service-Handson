# Azure AI Search defaults to the dedicated Basic tier (1 replica x 1
# partition). When setup.sh receives --serverless, the Serverless Developer
# preview is provisioned through AzAPI because azurerm doesn't expose this
# pricing model yet. Retrieved 2026-09-09:
# https://learn.microsoft.com/azure/search/search-sku-tier
resource "azurerm_search_service" "workshop" {
  count = var.search_pricing_model == "dedicated" ? 1 : 0

  name                = local.search_service_name
  resource_group_name = data.azurerm_resource_group.workshop.name
  location            = var.location

  sku                 = "basic"
  partition_count     = 1
  replica_count       = 1
  semantic_search_sku = "free"

  local_authentication_enabled  = false
  public_network_access_enabled = true

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azapi_resource" "search_service_serverless" {
  count = var.search_pricing_model == "serverless" ? 1 : 0

  type      = "Microsoft.Search/searchServices@2026-03-01-preview"
  name      = local.search_service_name
  parent_id = data.azurerm_resource_group.workshop.id
  location  = var.location
  tags      = var.tags

  body = {
    sku = {
      name = "serverless"
    }
    identity = {
      type = "SystemAssigned"
    }
    properties = {
      disableLocalAuth    = true
      publicNetworkAccess = "enabled"
    }
  }

  response_export_values = ["identity.principalId"]
}

locals {
  search_service_id = (
    var.search_pricing_model == "serverless"
    ? azapi_resource.search_service_serverless[0].id
    : azurerm_search_service.workshop[0].id
  )
  search_service_principal_id = (
    var.search_pricing_model == "serverless"
    ? azapi_resource.search_service_serverless[0].output.identity.principalId
    : azurerm_search_service.workshop[0].identity[0].principal_id
  )
}

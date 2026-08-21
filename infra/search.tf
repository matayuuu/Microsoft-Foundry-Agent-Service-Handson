# Azure AI Search: Basic tier, 1 replica x 1 partition (workshop scale only).
# Local (API key) authentication is disabled -- the workshop is keyless
# end-to-end. A system-assigned identity is enabled so the Knowledge Base /
# built-in vectorizer can invoke the embedding + gpt-4.1 models on the
# Foundry AIServices account without any stored secret (see rbac.tf for the
# minimal "Cognitive Services OpenAI User" role granted to this identity).
resource "azurerm_search_service" "workshop" {
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

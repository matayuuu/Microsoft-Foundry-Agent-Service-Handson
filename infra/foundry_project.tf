# Microsoft Foundry project (child of the AIServices account). Basic Agent
# Setup: no capabilityHosts/agents sub-resource is created here, matching the
# workshop's explicit "no Cosmos DB / no Agent capability host" constraint.
resource "azapi_resource" "project" {
  type      = "Microsoft.CognitiveServices/accounts/projects@2026-05-01"
  name      = var.project_name
  parent_id = azapi_resource.ai_services.id
  location  = var.location
  tags      = var.tags

  identity {
    type = "SystemAssigned"
  }

  body = {
    properties = {
      displayName = "Contoso Travel & Expense Workshop"
      description = "Basic Agent Setup project for the Foundry Agent Service hands-on workshop."
    }
  }

  response_export_values = ["identity.principalId", "properties.internalId"]
}

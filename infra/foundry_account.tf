# Microsoft Foundry AIServices account.
#
# Provisioned via AzAPI (not AzureRM) because the new Foundry resource model
# -- allowProjectManagement, projects/deployments/connections sub-resources --
# is not reliably exposed by the azurerm provider yet. API version pinned to
# 2026-05-01, the current GA (non-preview) version for
# Microsoft.CognitiveServices/accounts as of 2026-08-21
# (learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/2026-05-01/accounts).
resource "azapi_resource" "ai_services" {
  type      = "Microsoft.CognitiveServices/accounts@2026-05-01"
  name      = local.ai_services_account_name
  parent_id = data.azurerm_resource_group.workshop.id
  location  = var.location
  tags      = var.tags

  identity {
    type = "SystemAssigned"
  }

  body = {
    kind = "AIServices"
    sku = {
      name = "S0"
    }
    properties = {
      # Required for Microsoft.CognitiveServices/accounts/projects to exist
      # under this account (Basic Agent Setup uses account-scoped projects,
      # not a standalone Foundry hub).
      allowProjectManagement = true
      customSubDomainName    = local.ai_services_account_name

      # Keyless runtime: no API keys are issued/read anywhere in this
      # workshop. All access is Microsoft Entra ID / RBAC.
      disableLocalAuth = true

      publicNetworkAccess = "Enabled"

      networkAcls = {
        defaultAction = "Allow"
      }
    }
  }

  response_export_values = ["identity.principalId", "properties.endpoint"]
}

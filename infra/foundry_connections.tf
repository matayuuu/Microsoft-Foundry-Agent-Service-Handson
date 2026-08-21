# Project connections wiring the Foundry project to Azure AI Search (Foundry
# IQ / Knowledge Base) and the Storage account (RAG blob content), both using
# Microsoft Entra ID (authType = "AAD") -- no keys are stored in either
# connection.
resource "azapi_resource" "search_connection" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2026-05-01"
  name      = "contoso-travel-search"
  parent_id = azapi_resource.project.id

  body = {
    properties = {
      category      = "CognitiveSearch"
      target        = "https://${local.search_service_name}.search.windows.net"
      authType      = "AAD"
      isSharedToAll = true
      metadata = {
        ApiType    = "Azure"
        ResourceId = azurerm_search_service.workshop.id
        Location   = var.location
      }
    }
  }

  depends_on = [azurerm_search_service.workshop]
}

resource "azapi_resource" "storage_connection" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2026-05-01"
  name      = "contoso-travel-storage"
  parent_id = azapi_resource.project.id

  body = {
    properties = {
      category      = "AzureStorageAccount"
      target        = azurerm_storage_account.workshop.primary_blob_endpoint
      authType      = "AAD"
      isSharedToAll = true
      metadata = {
        ApiType    = "Azure"
        ResourceId = azurerm_storage_account.workshop.id
        Location   = var.location
      }
    }
  }

  depends_on = [azurerm_storage_account.workshop]
}

# Keyless trace ingestion and evaluation access. ProjectManagedIdentity is the
# explicit auth mode used by Microsoft's current Foundry infrastructure sample
# for the project's system-assigned identity. It is exposed by the latest
# preview connection contract but not yet represented in the GA ARM schema,
# so AzAPI schema validation is disabled for this one preview-shaped resource.
# The connection string is routing metadata; local auth is disabled on the
# component and the project identity receives explicit monitoring roles.
resource "azapi_resource" "application_insights_connection" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2026-05-15-preview"
  name                      = "contoso-travel-appinsights"
  parent_id                 = azapi_resource.project.id
  schema_validation_enabled = false

  body = {
    properties = {
      category      = "AppInsights"
      target        = azurerm_application_insights.workshop.id
      authType      = "ProjectManagedIdentity"
      isSharedToAll = true
      metadata = {
        ApiType                             = "Azure"
        ResourceId                          = azurerm_application_insights.workshop.id
        ApplicationInsightsConnectionString = azurerm_application_insights.workshop.connection_string
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.project_mi_monitoring_metrics_publisher,
    azurerm_role_assignment.project_mi_log_analytics_reader,
    azurerm_role_assignment.project_mi_privileged_monitoring_data_reader,
  ]
}

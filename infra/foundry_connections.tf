# Project connection wiring the Foundry project to Azure AI Search (Foundry IQ
# / Knowledge Base) with Microsoft Entra ID (authType = "AAD").
resource "azapi_resource" "search_connection" {
  type      = "Microsoft.CognitiveServices/accounts/projects/connections@2026-05-01"
  name      = "contoso-travel-search"
  parent_id = azapi_resource.project.id

  body = {
    properties = {
      category = "CognitiveSearch"
      target   = "https://${local.search_service_name}.search.windows.net"
      authType = "AAD"
      # Project-scoped ARM connections are normalized to false by the service.
      # Access is granted through project RBAC, not an account-wide share.
      isSharedToAll = false
      metadata = {
        ApiType    = "Azure"
        ResourceId = local.search_service_id
        Location   = var.location
      }
    }
  }

  depends_on = [
    azurerm_search_service.workshop,
    azapi_resource.search_service_serverless,
  ]
}

# Foundry IQ exposes each knowledge base as a RemoteTool MCP endpoint. Prompt
# Agents require a dedicated ProjectManagedIdentity connection for that MCP
# endpoint; the CognitiveSearch/AAD connection above cannot authenticate a
# generic MCP call. The endpoint can be registered before setup creates the
# knowledge base because the connection stores routing metadata only.
resource "azapi_resource" "knowledge_mcp_connection" {
  type                      = "Microsoft.CognitiveServices/accounts/projects/connections@2026-05-15-preview"
  name                      = "contoso-travel-knowledge-lab-mcp"
  parent_id                 = azapi_resource.project.id
  schema_validation_enabled = false

  body = {
    properties = {
      category                    = "RemoteTool"
      target                      = "https://${local.search_service_name}.search.windows.net/knowledgebases/contoso-travel-knowledge-lab/mcp?api-version=2026-08-01-preview"
      authType                    = "ProjectManagedIdentity"
      useWorkspaceManagedIdentity = true
      isSharedToAll               = false
      audience                    = "https://search.azure.com"
      metadata = {
        ApiType = "Azure"
      }
    }
  }

  depends_on = [
    azurerm_role_assignment.project_mi_search_index_data_contributor,
    azurerm_role_assignment.project_mi_search_service_contributor,
  ]
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
      category = "AppInsights"
      target   = azurerm_application_insights.workshop.id
      authType = "ProjectManagedIdentity"
      # Project-scoped ARM connections are normalized to false by the service.
      # Access is granted through project RBAC, not an account-wide share.
      isSharedToAll = false
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

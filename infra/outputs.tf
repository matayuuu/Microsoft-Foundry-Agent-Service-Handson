# Non-secret outputs only. No connection strings, keys, tokens, or
# credentials are ever emitted here -- the workshop is keyless end-to-end and
# scripts/setup.sh writes only these values to .workshop/context.json.

output "resource_group_name" {
  description = "Existing resource group the workshop resources were deployed into."
  value       = data.azurerm_resource_group.workshop.name
}

output "location" {
  value = var.location
}

output "ai_services_account_name" {
  value = azapi_resource.ai_services.name
}

output "ai_services_endpoint" {
  value = azapi_resource.ai_services.output.properties.endpoint
}

output "foundry_project_name" {
  value = azapi_resource.project.name
}

output "foundry_project_id" {
  value = azapi_resource.project.id
}

output "foundry_project_endpoint" {
  description = "Microsoft Foundry project endpoint used by the SDK wrappers."
  value       = "https://${azapi_resource.ai_services.name}.services.ai.azure.com/api/projects/${azapi_resource.project.name}"
}

output "primary_model_deployment_name" {
  value = azapi_resource.primary_model_deployment.name
}

output "optimizer_model_deployment_name" {
  value = azapi_resource.optimizer_model_deployment.name
}

output "embedding_model_deployment_name" {
  value = azapi_resource.embedding_model_deployment.name
}

output "search_service_name" {
  value = azurerm_search_service.workshop.name
}

output "search_service_endpoint" {
  value = "https://${azurerm_search_service.workshop.name}.search.windows.net"
}

output "storage_account_name" {
  value = azurerm_storage_account.workshop.name
}

output "rag_container_name" {
  value = azapi_resource.rag_container.name
}

output "log_analytics_workspace_name" {
  value = azurerm_log_analytics_workspace.workshop.name
}

output "application_insights_name" {
  value = azurerm_application_insights.workshop.name
}

output "application_insights_id" {
  value = azurerm_application_insights.workshop.id
}

output "search_connection_name" {
  value = azapi_resource.search_connection.name
}

output "storage_connection_name" {
  value = azapi_resource.storage_connection.name
}

output "application_insights_connection_name" {
  value = azapi_resource.application_insights_connection.name
}

output "travel_api_fqdn" {
  description = "Public HTTPS FQDN of the deployed Travel Ops API container app."
  value       = azurerm_container_app.travel_api.ingress[0].fqdn
}

output "travel_api_container_app_name" {
  description = "ARM resource name of the Travel Ops API container app, used by validate_environment.py to build its resource ID for an existence check."
  value       = azurerm_container_app.travel_api.name
}

output "foundry_portal_url" {
  description = "Generic, guaranteed-correct entry point to the Foundry portal. Combine with ai_services_account_name and foundry_project_name to locate the workshop project (no officially confirmed deep-link URL format was found at authoring time -- see docs/admin/prerequisites.md)."
  value       = "https://ai.azure.com"
}

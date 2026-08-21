# Storage: Standard_LRS only (Basic Agent Setup, no data residency/CMK
# requirements in scope). Shared key auth is disabled so every caller
# (participant, bootstrap script, Foundry project managed identity) must use
# Microsoft Entra ID / RBAC -- no storage account keys are ever generated or
# read by this workshop.
resource "azurerm_storage_account" "workshop" {
  name                = local.storage_account_name
  resource_group_name = data.azurerm_resource_group.workshop.name
  location            = var.location

  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  min_tls_version          = "TLS1_2"

  shared_access_key_enabled       = false
  public_network_access_enabled   = true
  allow_nested_items_to_be_public = false

  tags = var.tags
}

# Create the private container through the ARM control plane. The AzureRM
# storage-container resource uses the Storage data plane, but an RG Owner does
# not automatically have blob data permissions before Terraform creates the
# role assignment. AzAPI keeps first apply within the participant's existing
# management-plane Owner grant.
resource "azapi_resource" "rag_container" {
  type      = "Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01"
  name      = local.rag_container_name
  parent_id = "${azurerm_storage_account.workshop.id}/blobServices/default"

  body = {
    properties = {
      publicAccess = "None"
    }
  }
}

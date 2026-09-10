# Azure Machine Learning is the participant's post-provisioning execution
# environment. Terraform creates only the workspace and its stable backing
# resources; the participant creates and starts a Compute instance later in
# Azure ML Studio.

resource "azurerm_storage_account" "azureml" {
  name                          = local.storage_account_name
  resource_group_name           = data.azurerm_resource_group.workshop.name
  location                      = var.location
  account_kind                  = "StorageV2"
  account_tier                  = "Standard"
  account_replication_type      = "LRS"
  public_network_access_enabled = true
  shared_access_key_enabled     = true
  min_tls_version               = "TLS1_2"
  tags                          = var.tags
}

resource "azurerm_key_vault" "azureml" {
  name                          = local.key_vault_name
  resource_group_name           = data.azurerm_resource_group.workshop.name
  location                      = var.location
  tenant_id                     = data.azurerm_client_config.current.tenant_id
  sku_name                      = "standard"
  rbac_authorization_enabled    = true
  public_network_access_enabled = true
  purge_protection_enabled      = false
  soft_delete_retention_days    = 7
  tags                          = var.tags
}

resource "azurerm_machine_learning_workspace" "workshop" {
  name                    = local.azureml_workspace_name
  resource_group_name     = data.azurerm_resource_group.workshop.name
  location                = var.location
  application_insights_id = azurerm_application_insights.workshop.id
  key_vault_id            = azurerm_key_vault.azureml.id
  storage_account_id      = azurerm_storage_account.azureml.id

  public_network_access_enabled = true

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

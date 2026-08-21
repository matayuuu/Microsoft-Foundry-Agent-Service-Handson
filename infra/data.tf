# Existing resource group only. Terraform never creates or destroys resource
# groups: the participant is only Owner within a resource group that already
# exists, not at subscription scope.
data "azurerm_resource_group" "workshop" {
  name = var.resource_group_name
}

# Identity Terraform is currently authenticated as (the participant's own
# `az login` session in the common case). Used as the default RBAC target
# when var.participant_object_id is not supplied.
data "azurerm_client_config" "current" {}

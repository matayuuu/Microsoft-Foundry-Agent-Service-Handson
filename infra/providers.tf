# Provider configuration.
#
# resource_provider_registrations = "none" is required so that Terraform
# never attempts to register Azure resource providers on the participant's
# behalf: the participant only has Owner on the existing resource group, not
# subscription-level `/register/action` permissions. Provider registration is
# the subscription administrator's job, handled out-of-band by
# scripts/admin-preflight.sh --apply.
provider "azurerm" {
  features {}

  subscription_id                 = var.subscription_id
  resource_provider_registrations = "none"
}

provider "azapi" {
  subscription_id            = var.subscription_id
  skip_provider_registration = true
}

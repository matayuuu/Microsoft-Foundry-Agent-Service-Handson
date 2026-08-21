# Terraform and provider version pins for the workshop control plane.
#
# Only stable resources belong in AzureRM. The new Microsoft Foundry resource
# model (AIServices account, project, model deployments, project connections)
# is provisioned through AzAPI because AzureRM does not reliably expose it yet.
# See infra/README.md for the full AzureRM vs AzAPI split rationale.

terraform {
  required_version = ">= 1.10.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.0"
    }
    azapi = {
      source  = "Azure/azapi"
      version = "~> 2.0"
    }
  }

  # No backend block: Terraform defaults to local state, which keeps the
  # workshop self-contained for a participant with only RG-scoped Owner
  # access. Organizers who want shared remote state should copy
  # backend.remote.tf.example to backend.tf and fill in their own
  # organizer-provided Azure Blob container. Terraform state can contain
  # sensitive values, so it must never be committed to source control.
}

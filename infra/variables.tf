# Variable contract for the workshop control plane.
#
# Every variable that participants might need to override (region, model
# version/SKU/capacity, container image) is exposed here instead of being
# hard-coded, so that scripts/preflight.sh can validate real values against
# the subscription before terraform apply runs. Defaults are workshop
# defaults, not guarantees: preflight is the source of truth for what is
# actually available in the target subscription/region.

variable "subscription_id" {
  description = "Subscription ID that already contains the participant's resource group. Terraform never creates or deletes resource groups or subscription-scope role assignments."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", var.subscription_id))
    error_message = "subscription_id must be a GUID."
  }
}

variable "resource_group_name" {
  description = "Name of the EXISTING resource group the participant owns. Terraform reads it via a data source and never creates or destroys it."
  type        = string

  validation {
    condition     = length(var.resource_group_name) > 0
    error_message = "resource_group_name must not be empty."
  }
}

variable "location" {
  description = "Azure region for all workshop resources. Only eastus2 (default) and swedencentral (fallback) are supported: these are the two regions scripts/preflight.sh checks for Foundry model quota. Requesting another region will not be validated by preflight."
  type        = string
  default     = "eastus2"

  validation {
    condition     = contains(["eastus2", "swedencentral"], var.location)
    error_message = "location must be one of: eastus2, swedencentral."
  }
}

variable "project_name" {
  description = "Microsoft Foundry project name (child of the Foundry AIServices account)."
  type        = string
  default     = "contoso-travel"

  validation {
    condition     = can(regex("^[a-zA-Z0-9][a-zA-Z0-9_-]{2,32}$", var.project_name))
    error_message = "project_name must be 3-33 characters, start with an alphanumeric character, and contain only letters, numbers, hyphens, or underscores (this mirrors the ARM name pattern for Microsoft.CognitiveServices/accounts/projects)."
  }
}

variable "participant_object_id" {
  description = "Microsoft Entra object ID of the participant to grant workshop RBAC roles to. Leave empty (default) to use the identity Terraform is currently authenticated as (the participant's own `az login` session), which is the expected case for this workshop."
  type        = string
  default     = ""
}

variable "travel_api_image_ref" {
  description = "Full, publicly hosted GHCR image reference for the Travel Ops API container, INCLUDING an immutable @sha256 digest, e.g. ghcr.io/<org>/travel-ops-api@sha256:<64-hex-digest>. Built and published by the Travel Ops API workstream; Terraform only consumes it."
  type        = string

  validation {
    condition     = can(regex("^ghcr\\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$", var.travel_api_image_ref))
    error_message = "travel_api_image_ref must be a ghcr.io reference pinned to an immutable @sha256:<64-hex> digest (tags alone are not accepted)."
  }
}

variable "source_base" {
  description = "Public HTTPS base URL substituted into Travel Ops API policy citations."
  type        = string

  validation {
    condition     = can(regex("^https://[^/]+/.+", var.source_base))
    error_message = "source_base must be an absolute public HTTPS URL."
  }
}

variable "travel_api_container_port" {
  description = "TCP port the Travel Ops API container listens on inside the container (used for Container App ingress target_port)."
  type        = number
  default     = 8080

  validation {
    condition     = var.travel_api_container_port > 0 && var.travel_api_container_port < 65536
    error_message = "travel_api_container_port must be a valid TCP port number."
  }
}

variable "travel_api_cpu" {
  description = "vCPU allocated to the Travel Ops API container app (Consumption workload profile)."
  type        = number
  default     = 0.25
}

variable "travel_api_memory" {
  description = "Memory allocated to the Travel Ops API container app, e.g. '0.5Gi'. Must pair with travel_api_cpu per the Container Apps Consumption allocation table."
  type        = string
  default     = "0.5Gi"
}

# ---------------------------------------------------------------------------
# Model deployments
#
# Three deployments are provisioned on the Foundry AIServices account:
#   1. primary model              -> gpt-5.6-luna (Prompt/Hosted Agent + Foundry IQ)
#   2. optimizer/eval model       -> gpt-5.5 (LLM judges + Agent Optimizer)
#   3. embedding model            -> text-embedding-3-small (Foundry IQ / Azure AI Search vectors)
#
# Exact version/SKU/capacity are overridable and MUST be checked by
# scripts/preflight.sh (via `az cognitiveservices model list`) against the
# target subscription/region before apply. Do not treat these defaults as
# guaranteed available capacity.
# ---------------------------------------------------------------------------

variable "primary_model_name" {
  description = "Model name for the deployment shared by Prompt Agent, Hosted Agent, and Foundry IQ query planning."
  type        = string
  default     = "gpt-5.6-luna"
}

variable "primary_model_version" {
  description = "Model version for the primary/query deployment. Required: use the version discovered by preflight from the same entry as the required SKU; never guess a version."
  type        = string
}

variable "primary_model_sku" {
  description = "Deployment SKU for the primary/query model, e.g. GlobalStandard or Standard."
  type        = string
  default     = "GlobalStandard"
}

variable "primary_model_capacity" {
  description = "Deployment capacity (TPM in thousands) shared by the primary agents and Foundry IQ query planning."
  type        = number
  default     = 40
}

variable "optimizer_model_name" {
  description = "Model name for the deployment shared by configurable LLM evaluation judges and Agent Optimizer. Verify both evaluator and Optimizer support before overriding."
  type        = string
  default     = "gpt-5.5"
}

variable "optimizer_model_version" {
  description = "Model version for the Agent Optimizer deployment. Verify availability with `az cognitiveservices model list --location <location>` before apply -- this is intentionally not guessed and must be confirmed by preflight."
  type        = string
}

variable "optimizer_model_sku" {
  description = "Deployment SKU for the optimizer/evaluation model."
  type        = string
  default     = "GlobalStandard"
}

variable "optimizer_model_capacity" {
  description = "Deployment capacity (TPM in thousands) shared by configurable LLM judges and Agent Optimizer."
  type        = number
  default     = 20
}

variable "embedding_model_name" {
  description = "Model name for the embedding deployment used by Azure AI Search / Foundry IQ vectorization."
  type        = string
  default     = "text-embedding-3-small"
}

variable "embedding_model_version" {
  description = "Model version for the embedding deployment."
  type        = string
  default     = "1"
}

variable "embedding_model_sku" {
  description = "Deployment SKU for the embedding model. GlobalStandard is supported in both workshop regions and shares the larger global quota pool."
  type        = string
  default     = "GlobalStandard"
}

variable "embedding_model_capacity" {
  description = "Deployment capacity (TPM in thousands) for the embedding model."
  type        = number
  default     = 40
}

variable "embedding_dimensions" {
  description = "Vector dimensions produced by the embedding model (1536 for text-embedding-3-small at default dimensions). Used by scripts/bootstrap_data.py to validate the Azure AI Search vector index field."
  type        = number
  default     = 1536
}

variable "tags" {
  description = "Common tags applied to all workshop resources."
  type        = map(string)
  default = {
    workshop   = "foundry-agent-service-handson"
    managed-by = "terraform"
  }
}

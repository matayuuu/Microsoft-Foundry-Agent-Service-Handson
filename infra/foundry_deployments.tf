# Model deployments on the Foundry AIServices account.
#
# Three variable-driven deployments (see variables.tf for the rationale):
#   1. primary   -> gpt-4.1                  (Prompt Agent + eval + Foundry IQ query model)
#   2. optimizer -> gpt-5 family              (Agent Optimizer)
#   3. embedding -> text-embedding-3-small    (Azure AI Search / Foundry IQ vectors)
#
# scripts/preflight.sh must confirm the chosen name/version/sku/capacity are
# actually available via `az cognitiveservices model list --location <region>`
# before apply -- these variables are never silently guessed at apply time.
resource "azapi_resource" "primary_model_deployment" {
  type      = "Microsoft.CognitiveServices/accounts/deployments@2026-05-01"
  name      = "primary"
  parent_id = azapi_resource.ai_services.id

  # Cognitive Services rejects concurrent child PUTs on a fresh account.
  depends_on = [azapi_resource.project]

  body = {
    sku = {
      name     = var.primary_model_sku
      capacity = var.primary_model_capacity
    }
    properties = {
      model = {
        format  = "OpenAI"
        name    = var.primary_model_name
        version = var.primary_model_version
      }
    }
  }
}

resource "azapi_resource" "optimizer_model_deployment" {
  type      = "Microsoft.CognitiveServices/accounts/deployments@2026-05-01"
  name      = "optimizer"
  parent_id = azapi_resource.ai_services.id

  depends_on = [azapi_resource.primary_model_deployment]

  body = {
    sku = {
      name     = var.optimizer_model_sku
      capacity = var.optimizer_model_capacity
    }
    properties = {
      model = {
        format  = "OpenAI"
        name    = var.optimizer_model_name
        version = var.optimizer_model_version
      }
    }
  }
}

resource "azapi_resource" "embedding_model_deployment" {
  type      = "Microsoft.CognitiveServices/accounts/deployments@2026-05-01"
  name      = "embedding"
  parent_id = azapi_resource.ai_services.id

  depends_on = [azapi_resource.optimizer_model_deployment]

  body = {
    sku = {
      name     = var.embedding_model_sku
      capacity = var.embedding_model_capacity
    }
    properties = {
      model = {
        format  = "OpenAI"
        name    = var.embedding_model_name
        version = var.embedding_model_version
      }
    }
  }
}

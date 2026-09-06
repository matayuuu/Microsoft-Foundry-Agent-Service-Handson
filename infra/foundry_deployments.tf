# Model deployments on the Foundry AIServices account.
#
# Three variable-driven deployments (see variables.tf for the rationale):
#   1. primary   -> gpt-5.6-luna             (Prompt/Hosted Agent)
#   2. optimizer -> gpt-5.5                  (Foundry IQ + LLM judges + Agent Optimizer)
#   3. embedding -> text-embedding-3-small    (Azure AI Search / Foundry IQ vectors)
#
# scripts/preflight.sh must confirm the chosen name/version/sku/capacity are
# actually available via `az cognitiveservices model list --location <region>`
# before apply -- these variables are never silently guessed at apply time.
resource "azapi_resource" "primary_model_deployment" {
  type      = "Microsoft.CognitiveServices/accounts/deployments@2026-05-01"
  name      = "gpt-5.6-luna"
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
  name      = "gpt-5.5"
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

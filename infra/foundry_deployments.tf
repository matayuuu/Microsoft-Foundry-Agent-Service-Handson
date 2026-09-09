# Model deployments on the Foundry AIServices account.
#
# Two required deployments and one optional deployment (see variables.tf):
#   1. primary    -> gpt-5.6-luna             (Agents + Foundry IQ + Optimizer)
#   2. evaluation -> gpt-5.6-sol              (optional; Lab 5 LLM judges only)
#   3. embedding  -> text-embedding-3-small   (Azure AI Search / Foundry IQ vectors)
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

resource "azapi_resource" "evaluation_model_deployment" {
  count = var.enable_evaluation_model ? 1 : 0

  type      = "Microsoft.CognitiveServices/accounts/deployments@2026-05-01"
  name      = "gpt-5.6-sol"
  parent_id = azapi_resource.ai_services.id

  depends_on = [azapi_resource.primary_model_deployment]

  body = {
    sku = {
      name     = var.evaluation_model_sku
      capacity = var.evaluation_model_capacity
    }
    properties = {
      model = {
        format  = "OpenAI"
        name    = var.evaluation_model_name
        version = var.evaluation_model_version
      }
    }
  }
}

resource "azapi_resource" "embedding_model_deployment" {
  type      = "Microsoft.CognitiveServices/accounts/deployments@2026-05-01"
  name      = "embedding"
  parent_id = azapi_resource.ai_services.id

  depends_on = [azapi_resource.evaluation_model_deployment]

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

#!/usr/bin/env bash
# Work around Portal index/model picker gaps for either Search pricing model.
# The historical filename is retained for setup.sh compatibility.
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
API_VERSION="2026-08-01-preview"
KNOWLEDGE_BASE_NAME="contoso-travel-knowledge-lab"
TERRAFORM_OUTPUTS=""

usage() {
  cat <<'EOF'
Usage: prepare_serverless_foundry_iq.sh --terraform-outputs <path>

Creates or updates the two search-index knowledge sources and the workshop
knowledge base, then performs one retrieve smoke test. Authentication uses
the current az login session and Microsoft Entra ID only.
The input can be terraform output -json or .workshop/context.json.
Use only for this workshop's named knowledge base, not an unrelated existing base.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --terraform-outputs) TERRAFORM_OUTPUTS="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "${SCRIPT_NAME}: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${TERRAFORM_OUTPUTS}" || ! -s "${TERRAFORM_OUTPUTS}" ]]; then
  echo "${SCRIPT_NAME}: --terraform-outputs must point to Terraform outputs or workshop context" >&2
  exit 1
fi

for tool in az curl jq; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "${SCRIPT_NAME}: '${tool}' is required and was not found on PATH" >&2
    exit 1
  fi
done

SEARCH_ENDPOINT="$(jq -r '(.terraform_outputs // .).search_service_endpoint.value // empty' "${TERRAFORM_OUTPUTS}")"
OPENAI_ENDPOINT="$(jq -r '(.terraform_outputs // .).openai_endpoint.value // empty' "${TERRAFORM_OUTPUTS}")"
MODEL_DEPLOYMENT="$(jq -r '(.terraform_outputs // .).primary_model_deployment_name.value // empty' "${TERRAFORM_OUTPUTS}")"
if [[ -z "${SEARCH_ENDPOINT}" || -z "${OPENAI_ENDPOINT}" || -z "${MODEL_DEPLOYMENT}" ]]; then
  echo "${SCRIPT_NAME}: terraform outputs are missing Search, OpenAI, or primary model values" >&2
  exit 1
fi
MODEL_RESOURCE_URI="${OPENAI_ENDPOINT%/openai/v1/}"

ACCESS_TOKEN="$(az account get-access-token \
  --resource "https://search.azure.com" \
  --query accessToken -o tsv)"
if [[ -z "${ACCESS_TOKEN}" ]]; then
  echo "${SCRIPT_NAME}: Azure CLI did not return an Azure AI Search access token" >&2
  exit 1
fi

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TEMP_DIR}"' EXIT

put_json() {
  local label="$1" url="$2" payload="$3" response_file="$4" status detail
  status="$(printf 'Authorization: Bearer %s\n' "${ACCESS_TOKEN}" |
    curl -sS --connect-timeout 15 --max-time 90 -o "${response_file}" -w '%{http_code}' \
    -X PUT "${url}" \
    -H @- \
    -H "Content-Type: application/json" \
    -H "Prefer: return=representation" \
    --data "${payload}")"
  if [[ "${status}" != "200" && "${status}" != "201" ]]; then
    detail="$(jq -r '.error.message // .message // tostring' "${response_file}" 2>/dev/null || true)"
    echo "${SCRIPT_NAME}: ${label} failed with HTTP ${status}: ${detail}" >&2
    return 1
  fi
  echo "    ${label}: HTTP ${status}" >&2
}

create_search_source() {
  local source_name="$1" index_name="$2" payload
  payload="$(jq -nc \
    --arg source_name "${source_name}" \
    --arg index_name "${index_name}" \
    '{
      name: $source_name,
      kind: "searchIndex",
      resultsProcessing: "rerank",
      searchIndexParameters: {
        searchIndexName: $index_name,
        sourceDataFields: [
          {name: "title"},
          {name: "content"},
          {name: "citation"},
          {name: "source_url"}
        ],
        searchFields: [{name: "content"}],
        semanticConfigurationName: "contoso-travel-policy-semantic-config"
      }
    }')"
  put_json \
    "knowledge source ${source_name}" \
    "${SEARCH_ENDPOINT}/knowledgesources('${source_name}')?api-version=${API_VERSION}" \
    "${payload}" \
    "${TEMP_DIR}/${source_name}.json"
}

create_search_source "contoso-travel-policy-source" "contoso-travel-policy"
create_search_source "contoso-travel-approval-source" "contoso-travel-approval"

KNOWLEDGE_BASE_PAYLOAD="$(jq -nc \
  --arg name "${KNOWLEDGE_BASE_NAME}" \
  --arg resource_uri "${MODEL_RESOURCE_URI}" \
  --arg deployment "${MODEL_DEPLOYMENT}" \
  '{
    name: $name,
    description: "Contoso travel policy knowledge base",
    knowledgeSources: [
      {name: "contoso-travel-policy-source"},
      {name: "contoso-travel-approval-source"}
    ],
    models: [{
      kind: "azureOpenAI",
      azureOpenAIParameters: {
        resourceUri: $resource_uri,
        deploymentId: $deployment,
        modelName: "gpt-5.6-luna"
      }
    }],
    retrievalReasoningEffort: {kind: "medium"},
    outputMode: "extractiveData"
  }')"
put_json \
  "knowledge base ${KNOWLEDGE_BASE_NAME}" \
  "${SEARCH_ENDPOINT}/knowledgebases('${KNOWLEDGE_BASE_NAME}')?api-version=${API_VERSION}" \
  "${KNOWLEDGE_BASE_PAYLOAD}" \
  "${TEMP_DIR}/knowledge-base.json"

RETRIEVE_PAYLOAD="$(jq -nc '{
  messages: [{
    role: "user",
    content: [{
      type: "text",
      text: "東京から大阪へ日帰り出張する場合、食事の日当はいくらですか?"
    }]
  }],
  maxRuntimeInSeconds: 60,
  maxOutputDocuments: 10,
  maxOutputSize: 100000,
  retrievalReasoningEffort: {kind: "medium"},
  includeActivity: true,
  outputMode: "extractiveData"
}')"
RETRIEVE_STATUS="$(printf 'Authorization: Bearer %s\n' "${ACCESS_TOKEN}" |
  curl -sS --connect-timeout 15 --max-time 90 -o "${TEMP_DIR}/retrieve.json" -w '%{http_code}' \
  -X POST \
  "${SEARCH_ENDPOINT}/knowledgebases('${KNOWLEDGE_BASE_NAME}')/retrieve?api-version=${API_VERSION}" \
  -H @- \
  -H "Content-Type: application/json" \
  --data "${RETRIEVE_PAYLOAD}")"
if [[ "${RETRIEVE_STATUS}" != "200" ]]; then
  detail="$(jq -r '.error.message // .message // tostring' "${TEMP_DIR}/retrieve.json" 2>/dev/null || true)"
  echo "${SCRIPT_NAME}: knowledge base smoke retrieve failed with HTTP ${RETRIEVE_STATUS}: ${detail}" >&2
  exit 1
fi

REFERENCE_COUNT="$(jq -r '(.references // []) | length' "${TEMP_DIR}/retrieve.json")"
if [[ "${REFERENCE_COUNT}" -lt 1 ]]; then
  echo "${SCRIPT_NAME}: smoke retrieve returned no references" >&2
  exit 1
fi
echo "    knowledge base smoke retrieve: HTTP 200, references=${REFERENCE_COUNT}" >&2

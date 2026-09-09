#!/usr/bin/env bash
# Calculate workshop quota requests and show the official submission URLs.
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
SUBSCRIPTION_ID=""
LOCATION="japaneast"
PARTICIPANT_COUNT="1"

MODEL_QUOTA_REQUEST_URL="https://aka.ms/oai/stuquotarequest"
SEARCH_QUOTA_URL="https://portal.azure.com/#blade/Microsoft_Azure_Capacity/QuotaMenuBlade/myQuotas"
COGNITIVE_USAGE_API_VERSION="2023-05-01"
SEARCH_USAGE_API_VERSION="2025-05-01"

usage() {
  cat <<'EOF'
Usage: request-quota-increase.sh --subscription <id> [options]

Options:
  --subscription <id>       Azure subscription ID (required).
  --location <region>       Target region. Recommended: japaneast (default),
                            australiaeast, or centralus.
  --participant-count <n>   Concurrent workshop environments. Default: 1.
  -h, --help                Show this help and exit.

This script is read-only. It calculates the minimum requested total limits.
Review and submit model requests in the official form and Search requests in
Azure Quotas.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --subscription)
      SUBSCRIPTION_ID="${2:-}"
      shift 2
      ;;
    --location)
      LOCATION="${2:-}"
      shift 2
      ;;
    --participant-count)
      PARTICIPANT_COUNT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "${SCRIPT_NAME}: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${SUBSCRIPTION_ID}" ]]; then
  echo "${SCRIPT_NAME}: --subscription is required" >&2
  exit 1
fi
if [[ ! "${SUBSCRIPTION_ID}" =~ ^[0-9a-fA-F-]{36}$ ]]; then
  echo "${SCRIPT_NAME}: --subscription must be a GUID" >&2
  exit 1
fi
if [[ "${LOCATION}" != "japaneast" && "${LOCATION}" != "australiaeast" && "${LOCATION}" != "centralus" && "${LOCATION}" != "eastus2" && "${LOCATION}" != "swedencentral" ]]; then
  echo "${SCRIPT_NAME}: --location must be 'japaneast', 'australiaeast', or 'centralus' (legacy: 'eastus2' or 'swedencentral')" >&2
  exit 1
fi
if [[ ! "${PARTICIPANT_COUNT}" =~ ^[1-9][0-9]*$ ]]; then
  echo "${SCRIPT_NAME}: --participant-count must be a positive integer" >&2
  exit 1
fi
for tool in az jq; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "${SCRIPT_NAME}: '${tool}' is required and was not found on PATH" >&2
    exit 1
  fi
done

if ! az account show --subscription "${SUBSCRIPTION_ID}" -o none 2>/dev/null; then
  echo "${SCRIPT_NAME}: unable to access subscription ${SUBSCRIPTION_ID}; run 'az login' first" >&2
  exit 2
fi

models_json="$(az cognitiveservices model list \
  --subscription "${SUBSCRIPTION_ID}" --location "${LOCATION}" -o json)"
cognitive_usage_json="$(az rest --method get --url \
  "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/providers/Microsoft.CognitiveServices/locations/${LOCATION}/usages?api-version=${COGNITIVE_USAGE_API_VERSION}" \
  --subscription "${SUBSCRIPTION_ID}" -o json)"
search_usage_json="$(az rest --method get --url \
  "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/providers/Microsoft.Search/locations/${LOCATION}/usages?api-version=${SEARCH_USAGE_API_VERSION}" \
  --subscription "${SUBSCRIPTION_ID}" -o json)"

declare -A REQUIRED_MODEL_CAPACITY_K=(
  ["gpt-5.6-luna"]="20"
  ["gpt-5.6-sol"]="100"
  ["text-embedding-3-small"]="20"
)
MODEL_REQUESTS="[]"

for model in "gpt-5.6-luna" "gpt-5.6-sol" "text-embedding-3-small"; do
  selected_entry="$(jq -c --arg model "${model}" --arg sku "GlobalStandard" '
    [.[] | select(
      .model.name == $model and
      ([.model.skus[]?.name] | index($sku) != null)
    )] |
    ([.[] | select(.model.isDefaultVersion == true)] | first) //
    ([.[] | select((.model.deprecation.inference // null) == null)] |
      sort_by(.model.version) | last) //
    (sort_by(.model.version) | last)
  ' <<<"${models_json}")"
  if [[ -z "${selected_entry}" || "${selected_entry}" == "null" ]]; then
    echo "${SCRIPT_NAME}: ${model} with GlobalStandard is unavailable in ${LOCATION}" >&2
    exit 2
  fi

  model_version="$(jq -r '.model.version' <<<"${selected_entry}")"
  usage_name="$(jq -r \
    '[.model.skus[] | select(.name == "GlobalStandard") | .usageName] | first' \
    <<<"${selected_entry}")"
  usage_entry="$(jq -c --arg usage_name "${usage_name}" \
    '[.value[]? | select(.name.value == $usage_name)] | first // empty' \
    <<<"${cognitive_usage_json}")"
  if [[ -z "${usage_entry}" ]]; then
    echo "${SCRIPT_NAME}: quota usage '${usage_name}' was not returned for ${LOCATION}" >&2
    exit 2
  fi

  current_k="$(jq -r '.currentValue' <<<"${usage_entry}")"
  current_limit_k="$(jq -r '.limit' <<<"${usage_entry}")"
  per_environment_k="${REQUIRED_MODEL_CAPACITY_K[${model}]}"
  aggregate_required_k=$((per_environment_k * PARTICIPANT_COUNT))
  minimum_requested_limit_k=$((current_k + aggregate_required_k))
  MODEL_REQUESTS="$(jq -c \
    --arg model "${model}" \
    --arg version "${model_version}" \
    --arg sku "GlobalStandard" \
    --arg usage_name "${usage_name}" \
    --argjson current_k "${current_k}" \
    --argjson current_limit_k "${current_limit_k}" \
    --argjson per_environment_k "${per_environment_k}" \
    --argjson aggregate_required_k "${aggregate_required_k}" \
    --argjson minimum_requested_limit_k "${minimum_requested_limit_k}" \
    '. + [{
      model: $model,
      version: $version,
      sku: $sku,
      usage_name: $usage_name,
      current_usage_k_tpm: $current_k,
      current_limit_k_tpm: $current_limit_k,
      per_environment_k_tpm: $per_environment_k,
      aggregate_required_k_tpm: $aggregate_required_k,
      minimum_requested_total_limit_k_tpm: $minimum_requested_limit_k
    }]' <<<"${MODEL_REQUESTS}")"
done

search_entry="$(jq -c \
  '[.value[]? | select((.name.value // "" | ascii_downcase) == "basic")] | first // empty' \
  <<<"${search_usage_json}")"
if [[ -z "${search_entry}" ]]; then
  echo "${SCRIPT_NAME}: Azure AI Search Basic usage was not returned for ${LOCATION}" >&2
  exit 2
fi
search_current="$(jq -r '.currentValue' <<<"${search_entry}")"
search_limit="$(jq -r '.limit' <<<"${search_entry}")"
search_minimum_requested_limit=$((search_current + PARTICIPANT_COUNT))

jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg subscription_id "${SUBSCRIPTION_ID}" \
  --arg location "${LOCATION}" \
  --argjson participant_count "${PARTICIPANT_COUNT}" \
  --argjson model_requests "${MODEL_REQUESTS}" \
  --argjson search_current "${search_current}" \
  --argjson search_limit "${search_limit}" \
  --argjson search_minimum_requested_limit "${search_minimum_requested_limit}" \
  --arg model_quota_request_url "${MODEL_QUOTA_REQUEST_URL}" \
  --arg search_quota_url "${SEARCH_QUOTA_URL}" \
  '{
    generated_at: $generated_at,
    subscription_id: $subscription_id,
    location: $location,
    participant_count: $participant_count,
    submission_mode: "portal-required",
    submission_note: "Review these totals. Submit model TPM increases through the official request form and Search Basic adjustments through Azure Quotas.",
    model_requests: $model_requests,
    search_request: {
      sku: "basic",
      current_service_count: $search_current,
      current_limit: $search_limit,
      aggregate_required_services: $participant_count,
      minimum_requested_total_limit: $search_minimum_requested_limit,
      note: "This service-count limit does not reserve or guarantee live physical SKU capacity."
    },
    portal_urls: {
      model_quota_request_form: $model_quota_request_url,
      search_quota: $search_quota_url
    }
  }'
#!/usr/bin/env bash
# scripts/admin-preflight.sh
#
# Subscription-administrator preflight for the Foundry Agent Service
# hands-on workshop. Read-only by default; pass --apply to register the
# required resource providers. This script NEVER creates or deletes resource
# groups, changes quota/policy, or writes role assignments -- registering
# resource providers is the one subscription-scope action it performs, and
# only when --apply is explicitly given.
#
# --participant-count <n> (default 1) reports model quota/capacity against
# the AGGREGATE headroom the whole event needs: each participant/team gets
# their own resource group and therefore their own set of model
# deployments, so N participants running concurrently need N times the
# per-environment TPM capacity (gpt-5.6-luna 40K, gpt-5.5 20K, text-embedding-3-
# small 40K) in the SAME region/quota pool, not just enough for one
# environment.
#
# Usage:
#   scripts/admin-preflight.sh --subscription <sub-id> [--location eastus2]
#                               [--participant-count <n>] [--apply]
#                               [--format json|markdown] [--output <file>]
#
# Exit codes:
#   0  all required checks passed (or --apply completed registration)
#   1  usage error
#   2  one or more required checks failed
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<'EOF'
Usage: admin-preflight.sh --subscription <subscription-id> [options]

Options:
  --subscription <id>   Azure subscription ID to inspect (required).
  --location <region>   Primary region to validate model/quota availability
                        against. Default: eastus2. The workshop's supported
                        fallback region swedencentral is always checked too.
  --participant-count <n>
                        Number of participants/teams (each with their own
                        resource group and model deployments) the event must
                        support concurrently, in the SAME region/quota pool.
                        Default: 1. Model quota/capacity checks report
                        whether headroom covers this many environments'
                        worth of capacity (per-environment capacity * n),
                        not just one. Must be a positive integer.
  --apply               Register any missing required resource providers.
                        Without this flag the script is strictly read-only.
  --format <fmt>        Output format: json (default) or markdown.
  --output <file>       Write the report to <file> instead of stdout.
  -h, --help            Show this help and exit.

This script never creates/deletes resource groups, changes subscription
quota or Azure Policy, or writes role assignments. Its only mutating action,
gated behind --apply, is `az provider register` for the six resource
providers this workshop depends on.
EOF
}

SUBSCRIPTION_ID=""
LOCATION="eastus2"
APPLY="false"
FORMAT="json"
OUTPUT_FILE=""
PARTICIPANT_COUNT="1"

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
    --apply)
      APPLY="true"
      shift 1
      ;;
    --format)
      FORMAT="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_FILE="${2:-}"
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
  usage >&2
  exit 1
fi

if [[ "${FORMAT}" != "json" && "${FORMAT}" != "markdown" ]]; then
  echo "${SCRIPT_NAME}: --format must be 'json' or 'markdown'" >&2
  exit 1
fi

if [[ ! "${PARTICIPANT_COUNT}" =~ ^[1-9][0-9]*$ ]]; then
  echo "${SCRIPT_NAME}: --participant-count must be a positive integer, got: '${PARTICIPANT_COUNT}'" >&2
  exit 1
fi

if ! command -v az >/dev/null 2>&1; then
  echo "${SCRIPT_NAME}: the Azure CLI ('az') is required and was not found on PATH" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "${SCRIPT_NAME}: 'jq' is required and was not found on PATH" >&2
  exit 1
fi

FALLBACK_LOCATION="swedencentral"
if [[ "${LOCATION}" == "swedencentral" ]]; then
  FALLBACK_LOCATION="eastus2"
fi

REQUIRED_PROVIDERS=(
  "Microsoft.CognitiveServices"
  "Microsoft.Search"
  "Microsoft.Insights"
  "Microsoft.OperationalInsights"
  "Microsoft.App"
)

# Required resource types per provider, used to check regional availability
# (a provider can be registered subscription-wide yet a given resource type
# can still be unavailable in a specific region).
declare -A REQUIRED_RESOURCE_TYPES=(
  ["Microsoft.CognitiveServices"]="accounts"
  ["Microsoft.Search"]="searchServices"
  ["Microsoft.Insights"]="components"
  ["Microsoft.OperationalInsights"]="workspaces"
  ["Microsoft.App"]="containerApps"
)

# Models this workshop deploys, and the exact SKU (deployment type) + TPM
# capacity (thousands) infra/variables.tf requests for each
# (primary/optimizer/embedding_model_capacity). Exact version selection is
# left to scripts/preflight.sh, which must be told a value this script
# confirms actually exists -- but this report DOES verify the specific
# SKU/usageName bucket each model deployment needs, with real headroom
# evidence, so an administrator can see actionable capacity numbers rather
# than a generic "some quota bucket somewhere is tight" signal.
REQUIRED_MODELS=("gpt-5.6-luna" "gpt-5.5" "text-embedding-3-small")
declare -A REQUIRED_MODEL_SKU=(
  ["gpt-5.6-luna"]="GlobalStandard"
  ["gpt-5.5"]="GlobalStandard"
  ["text-embedding-3-small"]="GlobalStandard"
)
declare -A REQUIRED_MODEL_CAPACITY_K=(
  ["gpt-5.6-luna"]="40"
  ["gpt-5.5"]="20"
  ["text-embedding-3-small"]="40"
)

CHECKS_JSON="[]"
OVERALL_STATUS="pass"

add_check() {
  local name="$1" status="$2" detail="$3"
  local entry
  entry="$(jq -n --arg name "${name}" --arg status "${status}" --arg detail "${detail}" \
    '{name: $name, status: $status, detail: $detail}')"
  CHECKS_JSON="$(jq -c --argjson entry "${entry}" '. + [$entry]' <<<"${CHECKS_JSON}")"
  if [[ "${status}" == "fail" ]]; then
    OVERALL_STATUS="fail"
  elif [[ "${status}" == "warn" && "${OVERALL_STATUS}" == "pass" ]]; then
    OVERALL_STATUS="warn"
  fi
}

az_json() {
  # Runs an `az ... -o json` command, tolerating failure by returning the
  # JSON literal null instead of aborting the whole script (each check below
  # decides what a failed/empty call means for its own status).
  local out status
  status=0
  out="$("$@" -o json 2>/dev/null)" || status=$?
  if [[ ${status} -ne 0 || -z "${out}" ]]; then
    echo "null"
  else
    echo "${out}"
  fi
}

echo "Checking subscription access..." >&2
if ! ACCOUNT_JSON="$(az account show --subscription "${SUBSCRIPTION_ID}" -o json 2>&1)"; then
  echo "${SCRIPT_NAME}: unable to access subscription ${SUBSCRIPTION_ID}. Run 'az login' as a subscription administrator first." >&2
  echo "${ACCOUNT_JSON}" >&2
  exit 2
fi
az account set --subscription "${SUBSCRIPTION_ID}"
add_check "subscription-access" "pass" "Authenticated and able to read subscription ${SUBSCRIPTION_ID}."

# ---------------------------------------------------------------------------
# Resource provider registration
# ---------------------------------------------------------------------------

MAX_REGISTER_POLLS=40   # 40 * 15s = 10 minutes max wait per provider
POLL_INTERVAL_SECONDS=15

for provider in "${REQUIRED_PROVIDERS[@]}"; do
  state="$(az provider show --namespace "${provider}" --subscription "${SUBSCRIPTION_ID}" --query registrationState -o tsv 2>/dev/null || echo "Unknown")"

  if [[ "${state}" == "Registered" ]]; then
    add_check "provider:${provider}" "pass" "Registered."
    continue
  fi

  if [[ "${APPLY}" != "true" ]]; then
    add_check "provider:${provider}" "fail" "Registration state is '${state}'. Re-run with --apply to register it, or register it manually: az provider register --namespace ${provider}."
    continue
  fi

  echo "Registering ${provider} (--apply was given)..." >&2
  az provider register --namespace "${provider}" --subscription "${SUBSCRIPTION_ID}" >/dev/null

  attempt=0
  final_state="Registering"
  while [[ ${attempt} -lt ${MAX_REGISTER_POLLS} ]]; do
    final_state="$(az provider show --namespace "${provider}" --subscription "${SUBSCRIPTION_ID}" --query registrationState -o tsv 2>/dev/null || echo "Unknown")"
    if [[ "${final_state}" == "Registered" ]]; then
      break
    fi
    attempt=$((attempt + 1))
    sleep "${POLL_INTERVAL_SECONDS}"
  done

  if [[ "${final_state}" == "Registered" ]]; then
    add_check "provider:${provider}" "pass" "Registered by this run (--apply)."
  else
    add_check "provider:${provider}" "fail" "Registration did not reach 'Registered' within $((MAX_REGISTER_POLLS * POLL_INTERVAL_SECONDS))s (last state: ${final_state}). Re-run this script, or check the Azure portal Activity Log for this provider registration."
  fi
done

# ---------------------------------------------------------------------------
# Regional resource-type availability (East US 2 primary, Sweden Central fallback)
# ---------------------------------------------------------------------------

for provider in "${REQUIRED_PROVIDERS[@]}"; do
  resource_type="${REQUIRED_RESOURCE_TYPES[${provider}]}"
  locations_json="$(az provider show --namespace "${provider}" --subscription "${SUBSCRIPTION_ID}" -o json 2>/dev/null | \
    jq -c --arg rt "${resource_type}" '[.resourceTypes[]? | select(.resourceType == $rt) | .locations[]?]')"

  if [[ -z "${locations_json}" || "${locations_json}" == "null" ]]; then
    add_check "region-support:${provider}/${resource_type}" "warn" "Could not determine supported locations for ${provider}/${resource_type} (provider may not be registered yet)."
    continue
  fi

  for loc in "${LOCATION}" "${FALLBACK_LOCATION}"; do
    # az provider location names are display names ("East US 2"), not the
    # short form ("eastus2"); match case-insensitively against a normalized
    # (spaces/case removed) comparison.
    normalized_loc="$(echo "${loc}" | tr -d ' ' | tr '[:upper:]' '[:lower:]')"
    supported="$(jq --arg loc "${normalized_loc}" '[.[] | gsub(" ";"") | ascii_downcase] | any(. == $loc)' <<<"${locations_json}")"
    if [[ "${supported}" == "true" ]]; then
      add_check "region-support:${provider}/${resource_type}/${loc}" "pass" "Available in ${loc}."
    else
      add_check "region-support:${provider}/${resource_type}/${loc}" "warn" "Not listed as available in ${loc} for this subscription; verify manually before choosing this region."
    fi
  done
done

# ---------------------------------------------------------------------------
# Model quota / capacity (gpt-5.6-luna, gpt-5.5, text-embedding-3-small)
#
# Reports headroom against the AGGREGATE requirement for the whole event:
# each of --participant-count participants/teams gets their own resource
# group and therefore their own set of model deployments in the SAME
# region/quota pool, so the required capacity is
# per-environment-capacity * participant-count, not just one environment's
# worth. Never silently treats unknown quota as sufficient: any call
# failure, missing SKU, or missing/insufficient usage bucket is reported as
# "warn" (this report is informational across both regions and does not
# itself select one -- scripts/preflight.sh does that, for a single
# participant's own environment, and there it is a hard "fail"), never
# silently skipped or assumed sufficient.
#
# Model entries are filtered down to only the ones that expose the required
# SKU in their OWN model.skus[] list BEFORE a "resolved" version is chosen
# for evidence (never the highest version across every entry followed by a
# separate SKU search on any entry, which could report a version that does
# not itself support the SKU). Among the SKU-supporting versions, the one
# Azure reports as model.isDefaultVersion == true is preferred; failing that,
# the highest version with no reported inference deprecation date; only
# failing both signals does this fall back to the highest (lexicographically
# last) SKU-supporting version -- same selection logic as
# scripts/preflight.sh, so the evidence shown to an administrator matches
# what a participant's own environment would actually resolve to.
# ---------------------------------------------------------------------------

for loc in "${LOCATION}" "${FALLBACK_LOCATION}"; do
  models_json="$(az_json az cognitiveservices model list --location "${loc}" --subscription "${SUBSCRIPTION_ID}")"
  usage_json="$(az_json az cognitiveservices usage list --location "${loc}" --subscription "${SUBSCRIPTION_ID}")"

  if [[ "${models_json}" == "null" ]]; then
    add_check "model-list:${loc}" "fail" "'az cognitiveservices model list --location ${loc}' failed. Cannot verify model availability for this region."
    continue
  fi
  if [[ "${usage_json}" == "null" ]]; then
    add_check "quota-usage-fetch:${loc}" "warn" "'az cognitiveservices usage list --location ${loc}' failed. TPM quota headroom for every model/SKU below is UNKNOWN in this region; do not assume it is sufficient."
  fi

  for model in "${REQUIRED_MODELS[@]}"; do
    required_sku="${REQUIRED_MODEL_SKU[${model}]}"
    per_environment_capacity="${REQUIRED_MODEL_CAPACITY_K[${model}]}"
    required_capacity=$((per_environment_capacity * PARTICIPANT_COUNT))

    matches="$(jq -c --arg m "${model}" '[.[] | select(.model.name == $m)]' <<<"${models_json}")"
    count="$(jq 'length' <<<"${matches}")"
    if [[ "${count}" -eq 0 ]]; then
      add_check "model:${model}/${loc}" "warn" "Model '${model}' was not returned by 'az cognitiveservices model list --location ${loc}'. It may not be offered in this region for this subscription."
      continue
    fi
    versions="$(jq -r '[.[].model.version] | unique | join(", ")' <<<"${matches}")"
    all_skus="$(jq -r '[.[].model.skus[]?.name] | unique | join(", ")' <<<"${matches}")"

    # Filter to only the entries that actually expose the required SKU in
    # their OWN model.skus[] list BEFORE picking a "resolved" version --
    # picking the highest version across every entry and separately grepping
    # any entry for the SKU (the previous approach) could report a version
    # that does not itself support the SKU Terraform requests for this model.
    sku_matches="$(jq -c --arg sku "${required_sku}" \
      '[.[] | select([.model.skus[]?.name] | index($sku) != null)]' <<<"${matches}")"
    sku_count="$(jq 'length' <<<"${sku_matches}")"
    if [[ "${sku_count}" -eq 0 ]]; then
      add_check "model-sku:${model}/${loc}" "warn" "Model '${model}' is offered in ${loc} (versions=[${versions}], skus=[${all_skus}]) but does not expose the required SKU '${required_sku}' this workshop's Terraform requests. Required aggregate capacity ${per_environment_capacity}K * ${PARTICIPANT_COUNT} participant(s) = ${required_capacity}K TPM cannot be validated in this region."
      continue
    fi
    sku_versions="$(jq -r '[.[].model.version] | unique | join(", ")' <<<"${sku_matches}")"

    # Among the SKU-supporting versions: prefer the one Azure itself reports
    # as isDefaultVersion=true; otherwise prefer one with no reported
    # inference deprecation date (model.deprecation.inference -- best effort,
    # since this exact nesting is not exhaustively documented for every model
    # at authoring time; absent/unparseable data never fails the check, it
    # only stops being usable as a tie-breaker); otherwise fall back to the
    # highest (lexicographically last) version string among the
    # SKU-supporting entries. Selecting a single `selected_entry` up front
    # (rather than a version and a usageName independently, as before)
    # guarantees `chosen_version` and `usage_name` below always come from the
    # SAME model.skus[] entry, so a mismatched version/SKU pairing can never
    # be reported.
    selected_entry="$(jq -c '[.[] | select(.model.isDefaultVersion == true)] | first // empty' <<<"${sku_matches}")"
    selection_basis="isDefaultVersion=true"
    if [[ -z "${selected_entry}" || "${selected_entry}" == "null" ]]; then
      selected_entry="$(jq -c '[.[] | select((.model.deprecation.inference // null) == null)] | sort_by(.model.version) | last // empty' <<<"${sku_matches}")"
      selection_basis="no reported isDefaultVersion; highest non-deprecated version"
      if [[ -z "${selected_entry}" || "${selected_entry}" == "null" ]]; then
        selected_entry="$(jq -c '. | sort_by(.model.version) | last' <<<"${sku_matches}")"
        selection_basis="no reported isDefaultVersion or non-deprecated version; highest available version (verify deprecation status manually)"
      fi
    fi

    chosen_version="$(jq -r '.model.version' <<<"${selected_entry}")"

    # Read the required SKU's usageName from the SAME selected_entry's own
    # skus[] entry (never guessed/constructed from the model name -- usageName
    # naming is inconsistent across models, e.g. gpt-4.1's bucket is
    # "...gpt4.1" without the hyphen -- and never from a different version's
    # entry than the one just chosen).
    usage_name="$(jq -r --arg sku "${required_sku}" \
      '[.model.skus[] | select(.name == $sku) | .usageName] | first' <<<"${selected_entry}")"

    if [[ "${usage_json}" == "null" ]]; then
      add_check "model-sku:${model}/${loc}" "warn" "Model '${model}' offers required SKU '${required_sku}' (usageName='${usage_name}', resolved version='${chosen_version}' [${selection_basis}], SKU-supporting version(s)=[${sku_versions}]) in ${loc}, but TPM headroom is UNKNOWN there ('az cognitiveservices usage list' failed) -- required aggregate ${per_environment_capacity}K * ${PARTICIPANT_COUNT} participant(s) = ${required_capacity}K TPM is not confirmed."
      continue
    fi

    quota_result="$(jq -c --arg un "${usage_name}" --argjson req "${required_capacity}" '
      ([.[] | select(.name.value == $un)] | first) as $u |
      if $u == null then
        {found: false}
      else
        {found: true, limit: $u.limit, current: $u.currentValue, headroom: ($u.limit - $u.currentValue), sufficient: (($u.limit - $u.currentValue) >= $req)}
      end
    ' <<<"${usage_json}")"
    found="$(jq -r '.found' <<<"${quota_result}")"
    if [[ "${found}" != "true" ]]; then
      add_check "model-sku:${model}/${loc}" "warn" "Model '${model}' offers required SKU '${required_sku}' (usageName='${usage_name}', resolved version='${chosen_version}' [${selection_basis}]) in ${loc}, but that quota bucket was not present in 'az cognitiveservices usage list --location ${loc}' output; headroom is UNKNOWN, not assumed sufficient."
      continue
    fi

    sufficient="$(jq -r '.sufficient' <<<"${quota_result}")"
    limit_k="$(jq -r '.limit' <<<"${quota_result}")"
    current_k="$(jq -r '.current' <<<"${quota_result}")"
    headroom_k="$(jq -r '.headroom' <<<"${quota_result}")"
    if [[ "${sufficient}" == "true" ]]; then
      add_check "model-sku:${model}/${loc}" "pass" "Model '${model}' resolved version='${chosen_version}' (${selection_basis}), SKU='${required_sku}', usageName='${usage_name}': headroom=${headroom_k}K (limit=${limit_k}K, current=${current_k}K) >= required aggregate ${per_environment_capacity}K * ${PARTICIPANT_COUNT} participant(s) = ${required_capacity}K TPM."
    else
      add_check "model-sku:${model}/${loc}" "warn" "Model '${model}' resolved version='${chosen_version}' (${selection_basis}), SKU='${required_sku}', usageName='${usage_name}': headroom=${headroom_k}K (limit=${limit_k}K, current=${current_k}K) is BELOW the required aggregate ${per_environment_capacity}K * ${PARTICIPANT_COUNT} participant(s) = ${required_capacity}K TPM in ${loc}. Request a quota increase, reduce concurrent participant count, or rely on the fallback region."
    fi
  done
done

# ---------------------------------------------------------------------------
# Azure Policy: best-effort deny-effect scan
#
# This is explicitly best-effort: policy evaluation is scope- and
# condition-dependent, and this script cannot simulate every possible
# request. It only flags assignments with effect "deny" visible from this
# subscription so an administrator can investigate further; it never claims
# to be exhaustive.
# ---------------------------------------------------------------------------

policy_json="$(az_json az policy assignment list --disable-scope-strict-match --subscription "${SUBSCRIPTION_ID}")"
if [[ "${policy_json}" == "null" ]]; then
  add_check "policy-scan" "warn" "'az policy assignment list' failed; Azure Policy deny-effect scan skipped (best-effort check, not exhaustive)."
else
  deny_json="$(jq -c '[.[] | select((.enforcementMode // "Default") != "DoNotEnforce")]' <<<"${policy_json}")"
  deny_count="$(jq 'length' <<<"${deny_json}")"
  if [[ "${deny_count}" -gt 0 ]]; then
    deny_names="$(jq -r '[.[].displayName] | join(", ")' <<<"${deny_json}")"
    add_check "policy-scan" "warn" "Found ${deny_count} enforced policy assignment(s) visible from this subscription that may restrict Foundry/Search/Storage/Container Apps resource creation (best-effort scan, not exhaustive -- inspect each policy's actual effect and scope): ${deny_names}."
  else
    add_check "policy-scan" "pass" "No enforced policy assignments found in this best-effort scan (not exhaustive: management-group-level policies with narrower conditions may still apply)."
  fi
fi

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

REPORT_JSON="$(jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg subscription_id "${SUBSCRIPTION_ID}" \
  --arg location "${LOCATION}" \
  --arg fallback_location "${FALLBACK_LOCATION}" \
  --arg apply "${APPLY}" \
  --argjson participant_count "${PARTICIPANT_COUNT}" \
  --arg overall_status "${OVERALL_STATUS}" \
  --argjson checks "${CHECKS_JSON}" \
  '{
    generated_at: $generated_at,
    subscription_id: $subscription_id,
    location: $location,
    fallback_location: $fallback_location,
    apply: ($apply == "true"),
    participant_count: $participant_count,
    overall_status: $overall_status,
    checks: $checks
  }')"

render_markdown() {
  local status_icon
  echo "# Admin preflight report"
  echo
  echo "- Subscription: \`${SUBSCRIPTION_ID}\`"
  echo "- Region: \`${LOCATION}\` (fallback: \`${FALLBACK_LOCATION}\`)"
  echo "- Generated: $(jq -r '.generated_at' <<<"${REPORT_JSON}")"
  echo "- Apply mode: $(jq -r '.apply' <<<"${REPORT_JSON}")"
  echo "- Participant/team count (aggregate quota target): \`${PARTICIPANT_COUNT}\`"
  echo "- **Overall status: $(jq -r '.overall_status' <<<"${REPORT_JSON}")**"
  echo
  echo "| Check | Status | Detail |"
  echo "| --- | --- | --- |"
  jq -r '.checks[] | "| " + .name + " | " + .status + " | " + (.detail | gsub("\\|";"\\\\|")) + " |"' <<<"${REPORT_JSON}"
}

if [[ "${FORMAT}" == "json" ]]; then
  RENDERED="$(jq '.' <<<"${REPORT_JSON}")"
else
  RENDERED="$(render_markdown)"
fi

if [[ -n "${OUTPUT_FILE}" ]]; then
  echo "${RENDERED}" > "${OUTPUT_FILE}"
  echo "Report written to ${OUTPUT_FILE}" >&2
else
  echo "${RENDERED}"
fi

if [[ "${OVERALL_STATUS}" == "fail" ]]; then
  exit 2
fi
exit 0

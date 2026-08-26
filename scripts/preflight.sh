#!/usr/bin/env bash
# scripts/preflight.sh
#
# Participant-facing preflight for the Foundry Agent Service hands-on
# workshop. ALWAYS strictly read-only: it never registers resource
# providers, never changes quota/policy, never creates or deletes anything.
# It exists to tell the participant (and scripts/setup.sh) whether the
# existing resource group, its identity's role, resource-provider
# registration state, and model/quota availability look workable BEFORE
# terraform apply runs -- and to auto-discover a real, available
# optimizer_model_version instead of guessing one.
#
# Usage:
#   scripts/preflight.sh --subscription <sub-id> --resource-group <rg-name>
#                         [--location eastus2] [--format json|markdown]
#                         [--output <file>]
#
# Exit codes:
#   0  all required checks passed
#   1  usage error
#   2  one or more required checks failed (participant should not proceed)
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

usage() {
  cat <<'EOF'
Usage: preflight.sh --subscription <subscription-id> --resource-group <name> [options]

Options:
  --subscription <id>     Azure subscription ID (required).
  --resource-group <name> EXISTING resource group name the participant owns (required).
  --location <region>     Preferred region. Default: eastus2. Falls back to
                          swedencentral automatically if eastus2 does not
                          have the required model/quota availability.
  --format <fmt>          Output format: json (default) or markdown.
  --output <file>         Write the report to <file> instead of stdout.
  -h, --help              Show this help and exit.

This script is strictly read-only. It never runs `az provider register`,
`az group create/delete`, or any role/policy-writing command. Registering
resource providers is the subscription administrator's job
(scripts/admin-preflight.sh --apply).
EOF
}

SUBSCRIPTION_ID=""
RESOURCE_GROUP_NAME=""
PREFERRED_LOCATION="eastus2"
FORMAT="json"
OUTPUT_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --subscription)
      SUBSCRIPTION_ID="${2:-}"
      shift 2
      ;;
    --resource-group)
      RESOURCE_GROUP_NAME="${2:-}"
      shift 2
      ;;
    --location)
      PREFERRED_LOCATION="${2:-}"
      shift 2
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

if [[ -z "${SUBSCRIPTION_ID}" || -z "${RESOURCE_GROUP_NAME}" ]]; then
  echo "${SCRIPT_NAME}: --subscription and --resource-group are required" >&2
  usage >&2
  exit 1
fi

if [[ "${FORMAT}" != "json" && "${FORMAT}" != "markdown" ]]; then
  echo "${SCRIPT_NAME}: --format must be 'json' or 'markdown'" >&2
  exit 1
fi

if [[ "${PREFERRED_LOCATION}" != "eastus2" && "${PREFERRED_LOCATION}" != "swedencentral" ]]; then
  echo "${SCRIPT_NAME}: --location must be 'eastus2' or 'swedencentral'" >&2
  exit 1
fi

for tool in az jq; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "${SCRIPT_NAME}: '${tool}' is required and was not found on PATH" >&2
    exit 1
  fi
done

SUPPORTED_LOCATIONS=("eastus2" "swedencentral")
REQUIRED_PROVIDERS=(
  "Microsoft.CognitiveServices"
  "Microsoft.Search"
  "Microsoft.Storage"
  "Microsoft.Insights"
  "Microsoft.OperationalInsights"
  "Microsoft.App"
)
REQUIRED_MODELS=("gpt-4.1" "gpt-5" "text-embedding-3-small")
# The exact SKU (deployment type) and TPM capacity (in thousands) this
# workshop's Terraform requests for each model (infra/variables.tf:
# primary/optimizer/embedding_model_capacity). A region is only resolved when
# every required model's SPECIFIC sku/usageName bucket has this much reported
# headroom -- a generic cross-bucket floor is not sufficient, because a
# region can be "not tight" overall while still lacking the one bucket this
# workshop actually deploys into.
declare -A REQUIRED_MODEL_SKU=(
  ["gpt-4.1"]="GlobalStandard"
  ["gpt-5"]="GlobalStandard"
  ["text-embedding-3-small"]="GlobalStandard"
)
declare -A REQUIRED_MODEL_CAPACITY_K=(
  ["gpt-4.1"]="40"
  ["gpt-5"]="20"
  ["text-embedding-3-small"]="40"
)

CHECKS_JSON="[]"
OVERALL_STATUS="pass"
RESOLVED_LOCATION=""
declare -A RESOLVED_MODEL_VERSION
declare -A RESOLVED_MODEL_SKU
declare -A RESOLVED_MODEL_USAGE_NAME

add_check() {
  local name="$1" status="$2" detail="$3" affects_overall="${4:-true}"
  local entry
  entry="$(jq -n --arg name "${name}" --arg status "${status}" --arg detail "${detail}" \
    '{name: $name, status: $status, detail: $detail}')"
  CHECKS_JSON="$(jq -c --argjson entry "${entry}" '. + [$entry]' <<<"${CHECKS_JSON}")"
  if [[ "${affects_overall}" != "true" ]]; then
    return
  fi
  if [[ "${status}" == "fail" ]]; then
    OVERALL_STATUS="fail"
  elif [[ "${status}" == "warn" && "${OVERALL_STATUS}" == "pass" ]]; then
    OVERALL_STATUS="warn"
  fi
}

az_json() {
  local out status
  status=0
  out="$("$@" -o json 2>/dev/null)" || status=$?
  if [[ ${status} -ne 0 || -z "${out}" ]]; then
    echo "null"
  else
    echo "${out}"
  fi
}

# ---------------------------------------------------------------------------
# Identity / login
# ---------------------------------------------------------------------------

echo "Checking az login and subscription access..." >&2
if ! ACCOUNT_JSON="$(az account show -o json 2>&1)"; then
  echo "${SCRIPT_NAME}: not logged in. Run 'az login' first." >&2
  echo "${ACCOUNT_JSON}" >&2
  exit 2
fi

CURRENT_SUB_ID="$(jq -r '.id' <<<"${ACCOUNT_JSON}")"
if [[ "${CURRENT_SUB_ID}" != "${SUBSCRIPTION_ID}" ]]; then
  if ! az account set --subscription "${SUBSCRIPTION_ID}" 2>/dev/null; then
    add_check "subscription-access" "fail" "Cannot access subscription ${SUBSCRIPTION_ID} with the current 'az login' session."
  else
    add_check "subscription-access" "pass" "Switched az CLI context to subscription ${SUBSCRIPTION_ID}."
  fi
else
  add_check "subscription-access" "pass" "Already scoped to subscription ${SUBSCRIPTION_ID}."
fi

CURRENT_USER_JSON="$(az_json az ad signed-in-user show)"
CURRENT_PRINCIPAL_ID=""
if [[ "${CURRENT_USER_JSON}" != "null" ]]; then
  CURRENT_PRINCIPAL_ID="$(jq -r '.id // empty' <<<"${CURRENT_USER_JSON}")"
fi
if [[ -z "${CURRENT_PRINCIPAL_ID}" ]]; then
  # az ad signed-in-user show fails for service-principal logins; fall back
  # to the object ID already present on the account/token claims.
  CURRENT_PRINCIPAL_ID="$(az account show --query 'user.name' -o tsv 2>/dev/null || echo "")"
  add_check "identity-lookup" "warn" "Could not resolve a Microsoft Entra object ID via 'az ad signed-in-user show' (expected for service-principal logins). Falling back to '${CURRENT_PRINCIPAL_ID}'; Owner-role verification below may be inconclusive."
else
  add_check "identity-lookup" "pass" "Resolved signed-in identity object ID."
fi

# ---------------------------------------------------------------------------
# Resource group existence + Owner role
# ---------------------------------------------------------------------------

RG_JSON="$(az_json az group show --name "${RESOURCE_GROUP_NAME}")"
if [[ "${RG_JSON}" == "null" ]]; then
  add_check "resource-group-exists" "fail" "Resource group '${RESOURCE_GROUP_NAME}' was not found (or is not visible) in subscription ${SUBSCRIPTION_ID}. This workshop never creates resource groups; ask your administrator to provision one and grant you Owner on it."
else
  add_check "resource-group-exists" "pass" "Resource group '${RESOURCE_GROUP_NAME}' exists."
fi

RG_ID="$(jq -r '.id // empty' <<<"${RG_JSON}")"
if [[ -n "${RG_ID}" && -n "${CURRENT_PRINCIPAL_ID}" ]]; then
  ROLE_JSON="$(az_json az role assignment list --scope "${RG_ID}" --assignee "${CURRENT_PRINCIPAL_ID}" --include-inherited)"
  has_owner="false"
  if [[ "${ROLE_JSON}" != "null" ]]; then
    has_owner="$(jq '[.[] | select(.roleDefinitionName == "Owner")] | length > 0' <<<"${ROLE_JSON}")"
  fi
  if [[ "${has_owner}" == "true" ]]; then
    add_check "owner-role" "pass" "Signed-in identity has Owner on '${RESOURCE_GROUP_NAME}' (directly or inherited)."
  else
    add_check "owner-role" "fail" "Signed-in identity does not have Owner on '${RESOURCE_GROUP_NAME}'. Owner is required so Terraform can create role assignments scoped to this resource group."
  fi
elif [[ -n "${RG_ID}" ]]; then
  add_check "owner-role" "warn" "Could not resolve the signed-in identity's object ID, so Owner-role verification was skipped; confirm manually with 'az role assignment list --scope ${RG_ID}'."
fi

# ---------------------------------------------------------------------------
# Resource provider registration (report-only -- never registers here)
# ---------------------------------------------------------------------------

for provider in "${REQUIRED_PROVIDERS[@]}"; do
  state="$(az provider show --namespace "${provider}" --query registrationState -o tsv 2>/dev/null || echo "Unknown")"
  if [[ "${state}" == "Registered" ]]; then
    add_check "provider:${provider}" "pass" "Registered."
  else
    add_check "provider:${provider}" "fail" "Registration state is '${state}'. Ask your subscription administrator to run scripts/admin-preflight.sh --apply (participants cannot register resource providers)."
  fi
done

# ---------------------------------------------------------------------------
# Region + model/SKU/quota resolution: eastus2 first, swedencentral fallback.
#
# For each candidate region, every required model must:
#   1. Be offered at all (model.name match), and
#   2. Expose the SPECIFIC sku required by infra/variables.tf
#      (REQUIRED_MODEL_SKU) on AT LEAST ONE of its reported versions --
#      entries are filtered down to only the SKU-supporting ones BEFORE a
#      version is chosen (never the highest version across every entry
#      followed by a separate SKU search on any entry), so the version this
#      script resolves is guaranteed to itself support the required SKU. Among
#      the SKU-supporting versions, the one Azure reports as
#      `model.isDefaultVersion == true` is preferred; if none is marked
#      default, the highest version with no reported inference deprecation
#      date is preferred; only if neither signal is available does this fall
#      back to the highest (lexicographically last) SKU-supporting version.
#      usageName is then read from that SAME chosen entry's own
#      `model.skus[].usageName` -- usageName strings are NOT derived/guessed
#      from the model name (e.g. gpt-4.1's usageName bucket is "...gpt4.1",
#      without the hyphen), and
#   3. Have that exact usageName bucket present in
#      `az cognitiveservices usage list` with headroom
#      (limit - currentValue) >= REQUIRED_MODEL_CAPACITY_K for that model.
#
# Any of these being false, OR the usage-list call itself failing, is a hard
# "fail" check for that candidate region -- never a "warn" that still lets the
# region be selected. Candidate failures do not fail the whole preflight when
# another region resolves successfully; region-resolution below owns that
# aggregate decision. The FIRST region (starting with --location) where every
# required model clears all three checks is selected as RESOLVED_LOCATION.
# Model versions/skus/usageNames actually confirmed there are recorded in
# RESOLVED_MODEL_VERSION / RESOLVED_MODEL_SKU / RESOLVED_MODEL_USAGE_NAME so
# setup.sh can pass real, discovered values to Terraform instead of guessing.
# ---------------------------------------------------------------------------

ordered_locations=("${PREFERRED_LOCATION}")
for loc in "${SUPPORTED_LOCATIONS[@]}"; do
  if [[ "${loc}" != "${PREFERRED_LOCATION}" ]]; then
    ordered_locations+=("${loc}")
  fi
done

for loc in "${ordered_locations[@]}"; do
  models_json="$(az_json az cognitiveservices model list --location "${loc}")"
  usage_json="$(az_json az cognitiveservices usage list --location "${loc}")"

  if [[ "${models_json}" == "null" ]]; then
    add_check "model-list:${loc}" "fail" "'az cognitiveservices model list --location ${loc}' failed; cannot verify model availability in ${loc}." "false"
    continue
  fi

  loc_ok="true"
  declare -A loc_versions
  declare -A loc_skus
  declare -A loc_usage_names

  for model in "${REQUIRED_MODELS[@]}"; do
    required_sku="${REQUIRED_MODEL_SKU[${model}]}"
    required_capacity="${REQUIRED_MODEL_CAPACITY_K[${model}]}"

    matches="$(jq -c --arg m "${model}" '[.[] | select(.model.name == $m)]' <<<"${models_json}")"
    count="$(jq 'length' <<<"${matches}")"
    if [[ "${count}" -eq 0 ]]; then
      add_check "model:${model}/${loc}" "fail" "Model '${model}' is not offered in ${loc} for this subscription." "false"
      loc_ok="false"
      continue
    fi

    # Filter to only the entries that actually expose the required SKU in
    # their OWN model.skus[] list BEFORE picking a version. Picking the
    # highest version across every entry and separately grepping any entry
    # for the SKU (the previous approach) could resolve a version that does
    # not itself support the SKU Terraform requests for this model.
    sku_matches="$(jq -c --arg sku "${required_sku}" \
      '[.[] | select([.model.skus[]?.name] | index($sku) != null)]' <<<"${matches}")"
    sku_count="$(jq 'length' <<<"${sku_matches}")"
    if [[ "${sku_count}" -eq 0 ]]; then
      offered_versions="$(jq -r '[.[].model.version] | unique | join(", ")' <<<"${matches}")"
      add_check "model-sku:${model}/${loc}" "fail" "Model '${model}' is offered in ${loc} (version(s)=[${offered_versions}]) but none of those versions expose the required SKU '${required_sku}' in their skus[] list. This workshop's Terraform requests '${required_sku}' capacity for this model; ${loc} cannot satisfy it." "false"
      loc_ok="false"
      continue
    fi

    # Among the SKU-supporting versions: prefer the one Azure itself reports
    # as isDefaultVersion=true; otherwise prefer one with no reported
    # inference deprecation date (model.deprecation.inference -- best effort:
    # this exact nesting is not exhaustively documented for every model at
    # authoring time, so absent/unparseable data never fails the check, it
    # only stops being usable as a tie-breaker); otherwise fall back to the
    # highest (lexicographically last) version string among the
    # SKU-supporting entries, same as the previous behavior. Selecting a
    # single `selected_entry` up front (rather than a version and a usageName
    # independently) guarantees `chosen_version` and `usage_name` below always
    # come from the SAME model.skus[] entry, so a mismatched version/SKU
    # pairing can never be resolved.
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
    # skus[] entry -- never constructed from the model name string, since
    # usageName naming is not consistent across models (e.g. gpt-4.1's
    # usageName bucket is "...gpt4.1", without the hyphen), and never from a
    # different version's entry than the one just chosen.
    usage_name="$(jq -r --arg sku "${required_sku}" \
      '[.model.skus[] | select(.name == $sku) | .usageName] | first' <<<"${selected_entry}")"

    if [[ "${usage_json}" == "null" ]]; then
      add_check "quota-usage:${model}/${loc}" "fail" "'az cognitiveservices usage list --location ${loc}' failed; TPM headroom for usageName='${usage_name}' (required ${required_capacity}K) is UNKNOWN in ${loc} -- not treated as sufficient." "false"
      loc_ok="false"
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
      add_check "quota-usage:${model}/${loc}" "fail" "Quota bucket usageName='${usage_name}' (SKU '${required_sku}' for model '${model}') was not present in 'az cognitiveservices usage list --location ${loc}' output; headroom is UNKNOWN, not treated as sufficient." "false"
      loc_ok="false"
      continue
    fi

    sufficient="$(jq -r '.sufficient' <<<"${quota_result}")"
    limit_k="$(jq -r '.limit' <<<"${quota_result}")"
    current_k="$(jq -r '.current' <<<"${quota_result}")"
    headroom_k="$(jq -r '.headroom' <<<"${quota_result}")"
    if [[ "${sufficient}" != "true" ]]; then
      add_check "quota-usage:${model}/${loc}" "fail" "Insufficient TPM headroom for usageName='${usage_name}' in ${loc}: headroom=${headroom_k}K (limit=${limit_k}K, current=${current_k}K) < required ${required_capacity}K." "false"
      loc_ok="false"
      continue
    fi

    loc_versions["${model}"]="${chosen_version}"
    loc_skus["${model}"]="${required_sku}"
    loc_usage_names["${model}"]="${usage_name}"
    add_check "model:${model}/${loc}" "pass" "Offered, resolved version='${chosen_version}' (${selection_basis}), sku='${required_sku}', usageName='${usage_name}', headroom=${headroom_k}K (limit=${limit_k}K, current=${current_k}K) >= required ${required_capacity}K TPM." "false"
  done

  if [[ "${loc_ok}" == "true" && -z "${RESOLVED_LOCATION}" ]]; then
    RESOLVED_LOCATION="${loc}"
    for model in "${REQUIRED_MODELS[@]}"; do
      RESOLVED_MODEL_VERSION["${model}"]="${loc_versions[${model}]:-}"
      RESOLVED_MODEL_SKU["${model}"]="${loc_skus[${model}]:-}"
      RESOLVED_MODEL_USAGE_NAME["${model}"]="${loc_usage_names[${model}]:-}"
    done
  fi
  unset loc_versions loc_skus loc_usage_names
done

if [[ -z "${RESOLVED_LOCATION}" ]]; then
  add_check "region-resolution" "fail" "Neither ${ordered_locations[*]} had every required model with sufficient reported headroom. Ask your subscription administrator to check quota (scripts/admin-preflight.sh) or request a quota increase."
else
  add_check "region-resolution" "pass" "Resolved region: ${RESOLVED_LOCATION}."
fi

# ---------------------------------------------------------------------------
# Azure Policy: best-effort deny scan (same caveat as admin-preflight.sh)
# ---------------------------------------------------------------------------

policy_json="$(az_json az policy assignment list --disable-scope-strict-match --scope "${RG_ID:-/subscriptions/${SUBSCRIPTION_ID}}")"
if [[ "${policy_json}" == "null" ]]; then
  add_check "policy-scan" "warn" "'az policy assignment list' failed; Azure Policy deny-effect scan skipped (best-effort check, not exhaustive)."
else
  deny_json="$(jq -c '[.[] | select((.enforcementMode // "Default") != "DoNotEnforce")]' <<<"${policy_json}")"
  deny_count="$(jq 'length' <<<"${deny_json}")"
  if [[ "${deny_count}" -gt 0 ]]; then
    deny_names="$(jq -r '[.[].displayName] | join(", ")' <<<"${deny_json}")"
    add_check "policy-scan" "warn" "Found ${deny_count} enforced policy assignment(s) visible at/above this resource group (best-effort scan, not exhaustive): ${deny_names}."
  else
    add_check "policy-scan" "pass" "No enforced policy assignments found in this best-effort scan (not exhaustive)."
  fi
fi

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

MODEL_VERSIONS_JSON="$(jq -n \
  --arg gpt41 "${RESOLVED_MODEL_VERSION[gpt-4.1]:-}" \
  --arg gpt5 "${RESOLVED_MODEL_VERSION[gpt-5]:-}" \
  --arg emb "${RESOLVED_MODEL_VERSION[text-embedding-3-small]:-}" \
  '{"gpt-4.1": $gpt41, "gpt-5": $gpt5, "text-embedding-3-small": $emb}')"

# Per-model SKU/usageName evidence for the resolved region (empty object
# fields when no region resolved), so setup.sh/participants can see exactly
# which quota bucket was validated -- not just that "something" passed.
MODEL_CAPACITY_EVIDENCE_JSON="$(jq -n \
  --arg gpt41_sku "${RESOLVED_MODEL_SKU[gpt-4.1]:-}" \
  --arg gpt41_usage "${RESOLVED_MODEL_USAGE_NAME[gpt-4.1]:-}" \
  --argjson gpt41_capacity "${REQUIRED_MODEL_CAPACITY_K[gpt-4.1]}" \
  --arg gpt5_sku "${RESOLVED_MODEL_SKU[gpt-5]:-}" \
  --arg gpt5_usage "${RESOLVED_MODEL_USAGE_NAME[gpt-5]:-}" \
  --argjson gpt5_capacity "${REQUIRED_MODEL_CAPACITY_K[gpt-5]}" \
  --arg emb_sku "${RESOLVED_MODEL_SKU[text-embedding-3-small]:-}" \
  --arg emb_usage "${RESOLVED_MODEL_USAGE_NAME[text-embedding-3-small]:-}" \
  --argjson emb_capacity "${REQUIRED_MODEL_CAPACITY_K[text-embedding-3-small]}" \
  '{
    "gpt-4.1": {sku: $gpt41_sku, usage_name: $gpt41_usage, required_capacity_k: $gpt41_capacity},
    "gpt-5": {sku: $gpt5_sku, usage_name: $gpt5_usage, required_capacity_k: $gpt5_capacity},
    "text-embedding-3-small": {sku: $emb_sku, usage_name: $emb_usage, required_capacity_k: $emb_capacity}
  }')"

REPORT_JSON="$(jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg subscription_id "${SUBSCRIPTION_ID}" \
  --arg resource_group_name "${RESOURCE_GROUP_NAME}" \
  --arg preferred_location "${PREFERRED_LOCATION}" \
  --arg resolved_location "${RESOLVED_LOCATION}" \
  --arg overall_status "${OVERALL_STATUS}" \
  --argjson model_versions "${MODEL_VERSIONS_JSON}" \
  --argjson model_capacity_evidence "${MODEL_CAPACITY_EVIDENCE_JSON}" \
  --argjson checks "${CHECKS_JSON}" \
  '{
    generated_at: $generated_at,
    subscription_id: $subscription_id,
    resource_group_name: $resource_group_name,
    preferred_location: $preferred_location,
    resolved_location: $resolved_location,
    overall_status: $overall_status,
    resolved_model_versions: $model_versions,
    resolved_model_capacity_evidence: $model_capacity_evidence,
    checks: $checks
  }')"

render_markdown() {
  echo "# Participant preflight report"
  echo
  echo "- Subscription: \`${SUBSCRIPTION_ID}\`"
  echo "- Resource group: \`${RESOURCE_GROUP_NAME}\`"
  echo "- Resolved region: \`${RESOLVED_LOCATION:-none}\`"
  echo "- Generated: $(jq -r '.generated_at' <<<"${REPORT_JSON}")"
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

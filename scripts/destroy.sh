#!/usr/bin/env bash
# scripts/destroy.sh
#
# Tears down everything scripts/setup.sh created, in the correct order:
#   1. SDK-managed Foundry data-plane objects (Hosted Agent versions, and
#      similar) via optional helper scripts. Terraform does not manage these
#      objects, so they must be deleted before `terraform destroy` removes
#      their parent Foundry account/project. Missing optional scripts are
#      reported explicitly and skipped -- never silently ignored.
#   2. `terraform destroy` for everything infra/ manages.
#   3. Verification that no workshop-managed Azure resource remains in the
#      resource group (via `az resource list`, filtered by this workshop's
#      tag and name-prefix convention). If any are found -- or the
#      verification call itself fails -- the script exits non-zero WITHOUT
#      touching any local state, so a partial/failed teardown is never
#      masked by deleting the evidence needed to retry or investigate it.
#   4. Local, non-secret .workshop/ state AND the local Terraform state
#      files (terraform.tfstate[.backup]) -- deleted ONLY after steps 1-3
#      above all succeed.
#
# The resource group itself is NEVER deleted (Terraform only ever read it via
# a data source; it does not own it).
#
# Usage:
#   scripts/destroy.sh [--subscription <id>] [--resource-group <name>]
#                       [--travel-api-image-ref <ref>] [--location <region>]
#                       [--source-base <url>]
#                       [--optimizer-model-version <version>]
#                       [--primary-model-version <version>]
#                       [--embedding-model-version <version>] [--auto-approve]
#
# When inputs are omitted, they are read from .workshop/context.json. If setup
# did not reach its final validation step, destroy falls back to the resolved
# inputs saved in .workshop/terraform-inputs.json before Terraform started.
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"
WORKSHOP_DIR="${REPO_ROOT}/.workshop"
CONTEXT_FILE="${WORKSHOP_DIR}/context.json"
RECOVERY_CONTEXT_FILE="${WORKSHOP_DIR}/terraform-inputs.json"
PYTHON_BIN="${WORKSHOP_PYTHON:-${REPO_ROOT}/.venv/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi

# Must match infra/variables.tf's `tags` default (`workshop` key) and
# infra/locals.tf's name prefix. If an organizer overrode either via a
# Terraform variable, update these to match before running destroy.sh, or
# the post-destroy remnant check below may under- or over-report.
WORKSHOP_TAG_VALUE="foundry-agent-service-handson"
WORKSHOP_NAME_PREFIX="fdyws"

usage() {
  cat <<'EOF'
Usage: destroy.sh [options]

Options:
  --subscription <id>          Azure subscription ID. Defaults to the value
                                recorded by setup.sh.
  --resource-group <name>      Resource group name. Defaults to the value
                                recorded by setup.sh.
  --travel-api-image-ref <ref> Same image ref used at setup time. Defaults to
                                the value recorded by setup.sh.
                                May also be supplied via TRAVEL_API_IMAGE_REF.
  --location <region>          Same Azure region used at setup time.
  --source-base <url>          Same public citation base URL used at setup time.
  --optimizer-model-version <version>
                                Same optimizer model version used at setup time.
  --primary-model-version <version>
                                Same primary model version used at setup time.
  --embedding-model-version <version>
                                Same embedding model version used at setup time.
                                These values default to .workshop/context.json
                                or its pre-Terraform recovery file. Pass them
                                explicitly only if neither file is available.
  --auto-approve                Skip the terraform destroy confirmation prompt.
  -h, --help                    Show this help and exit.

The resource group itself is never deleted. After `terraform destroy`, this
script verifies (via `az resource list`) that no workshop-managed resource
remains in the resource group; local Terraform state and .workshop/ state are
only removed once that verification passes. On any failure -- including the
verification call itself failing, or it finding leftover resources -- all
local state is left in place so you can investigate and retry safely.
EOF
}

SUBSCRIPTION_ID=""
RESOURCE_GROUP_NAME=""
TRAVEL_API_IMAGE_REF="${TRAVEL_API_IMAGE_REF:-}"
LOCATION=""
SOURCE_BASE=""
OPTIMIZER_MODEL_VERSION=""
PRIMARY_MODEL_VERSION=""
EMBEDDING_MODEL_VERSION=""
AUTO_APPROVE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --subscription) SUBSCRIPTION_ID="${2:-}"; shift 2 ;;
    --resource-group) RESOURCE_GROUP_NAME="${2:-}"; shift 2 ;;
    --travel-api-image-ref) TRAVEL_API_IMAGE_REF="${2:-}"; shift 2 ;;
    --location) LOCATION="${2:-}"; shift 2 ;;
    --source-base) SOURCE_BASE="${2:-}"; shift 2 ;;
    --optimizer-model-version) OPTIMIZER_MODEL_VERSION="${2:-}"; shift 2 ;;
    --primary-model-version) PRIMARY_MODEL_VERSION="${2:-}"; shift 2 ;;
    --embedding-model-version) EMBEDDING_MODEL_VERSION="${2:-}"; shift 2 ;;
    --auto-approve) AUTO_APPROVE="true"; shift 1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "${SCRIPT_NAME}: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

for tool in terraform jq az; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "${SCRIPT_NAME}: '${tool}' is required and was not found on PATH" >&2
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# Resolve required inputs from CLI args, then complete context, then the
# pre-Terraform recovery file written before setup can create any resources.
# ---------------------------------------------------------------------------

read_context_defaults() {
  local source_file="$1"
  [[ -z "${SUBSCRIPTION_ID}" ]] && SUBSCRIPTION_ID="$(jq -r '.subscription_id // empty' "${source_file}")"
  [[ -z "${RESOURCE_GROUP_NAME}" ]] && RESOURCE_GROUP_NAME="$(jq -r '.resource_group_name // empty' "${source_file}")"
  [[ -z "${TRAVEL_API_IMAGE_REF}" ]] && TRAVEL_API_IMAGE_REF="$(jq -r '.terraform_inputs.travel_api_image_ref // empty' "${source_file}")"
  [[ -z "${LOCATION}" ]] && LOCATION="$(jq -r '.location // empty' "${source_file}")"
  [[ -z "${SOURCE_BASE}" ]] && SOURCE_BASE="$(jq -r '.source_base // empty' "${source_file}")"
  [[ -z "${OPTIMIZER_MODEL_VERSION}" ]] && OPTIMIZER_MODEL_VERSION="$(jq -r '.terraform_inputs.optimizer_model_version // empty' "${source_file}")"
  [[ -z "${PRIMARY_MODEL_VERSION}" ]] && PRIMARY_MODEL_VERSION="$(jq -r '.terraform_inputs.primary_model_version // empty' "${source_file}")"
  [[ -z "${EMBEDDING_MODEL_VERSION}" ]] && EMBEDDING_MODEL_VERSION="$(jq -r '.terraform_inputs.embedding_model_version // empty' "${source_file}")"
  return 0
}

if [[ -f "${CONTEXT_FILE}" ]]; then
  echo "==> Reading defaults from ${CONTEXT_FILE}..." >&2
  read_context_defaults "${CONTEXT_FILE}"
fi
if [[ -f "${RECOVERY_CONTEXT_FILE}" ]]; then
  if [[ ! -f "${CONTEXT_FILE}" ]]; then
    echo "==> No complete ${CONTEXT_FILE} found; reading cleanup inputs from ${RECOVERY_CONTEXT_FILE}..." >&2
  fi
  read_context_defaults "${RECOVERY_CONTEXT_FILE}"
fi
if [[ ! -f "${CONTEXT_FILE}" && ! -f "${RECOVERY_CONTEXT_FILE}" ]]; then
  echo "==> No ${CONTEXT_FILE} or ${RECOVERY_CONTEXT_FILE} found; relying solely on CLI arguments." >&2
fi

if [[ -z "${SUBSCRIPTION_ID}" || -z "${RESOURCE_GROUP_NAME}" || -z "${TRAVEL_API_IMAGE_REF}" ]]; then
  echo "${SCRIPT_NAME}: could not resolve --subscription/--resource-group/--travel-api-image-ref from arguments or setup context files." >&2
  usage >&2
  exit 1
fi
if [[ -z "${LOCATION}" ]]; then
  echo "${SCRIPT_NAME}: could not resolve the deployment location. Pass --location, restore a setup context file, or re-run scripts/setup.sh." >&2
  exit 1
fi
if [[ -z "${SOURCE_BASE}" ]]; then
  echo "${SCRIPT_NAME}: could not resolve source_base. Pass --source-base or restore a setup context file." >&2
  exit 1
fi
if [[ -z "${OPTIMIZER_MODEL_VERSION}" ]]; then
  echo "${SCRIPT_NAME}: could not resolve optimizer_model_version. Pass --optimizer-model-version or restore a setup context file; it has no Terraform default and must match what was applied." >&2
  exit 1
fi
if [[ -z "${PRIMARY_MODEL_VERSION}" ]]; then
  echo "${SCRIPT_NAME}: could not resolve primary_model_version. Pass --primary-model-version or restore a setup context file; it has no Terraform default and must match what was applied." >&2
  exit 1
fi

retry() {
  local max_attempts="$1" sleep_seconds="$2"
  shift 2
  local attempt=1
  until "$@"; do
    if [[ ${attempt} -ge ${max_attempts} ]]; then
      echo "${SCRIPT_NAME}: command failed after ${attempt} attempt(s): $*" >&2
      return 1
    fi
    echo "${SCRIPT_NAME}: attempt ${attempt} failed, retrying in ${sleep_seconds}s: $*" >&2
    sleep "${sleep_seconds}"
    attempt=$((attempt + 1))
  done
}

# ---------------------------------------------------------------------------
# Step 1: SDK-managed data-plane objects that Terraform does not own.
#
# Each optional script is called if present; if absent, this is reported
# explicitly (never silently skipped) so the participant knows whether
# manual cleanup of that object class may be required.
# ---------------------------------------------------------------------------

echo "==> [1/4] Deleting SDK-managed data-plane objects (Hosted Agent versions, etc.)..." >&2

OPTIONAL_CLEANUP_SCRIPTS=(
  "delete_hosted_agent.py"
  "delete_evaluation_runs.py"
  "delete_toolbox_versions.py"
)

for script_name in "${OPTIONAL_CLEANUP_SCRIPTS[@]}"; do
  script_path="${SCRIPT_DIR}/${script_name}"
  if [[ -f "${script_path}" ]]; then
    echo "    Running ${script_name}..." >&2
    if [[ -z "${PYTHON_BIN}" || ! -x "${PYTHON_BIN}" ]]; then
      echo "${SCRIPT_NAME}: workshop Python environment is required to run ${script_name}. Rebuild the Codespace or run 'make install'." >&2
      exit 1
    fi
    "${PYTHON_BIN}" "${script_path}" --subscription "${SUBSCRIPTION_ID}" --resource-group "${RESOURCE_GROUP_NAME}"
  else
    echo "    SKIPPED: optional helper ${script_name} is not available; continuing with the remaining cleanup steps." >&2
    echo "    If Azure reports an object-reference error, see docs/participant/troubleshooting.md#cleanup." >&2
  fi
done

# ---------------------------------------------------------------------------
# Step 2: terraform destroy
# ---------------------------------------------------------------------------

echo "==> [2/4] Running terraform destroy..." >&2

TF_VAR_ARGS=(
  -var "subscription_id=${SUBSCRIPTION_ID}"
  -var "resource_group_name=${RESOURCE_GROUP_NAME}"
  -var "location=${LOCATION}"
  -var "travel_api_image_ref=${TRAVEL_API_IMAGE_REF}"
  -var "source_base=${SOURCE_BASE}"
  -var "optimizer_model_version=${OPTIMIZER_MODEL_VERSION}"
  -var "primary_model_version=${PRIMARY_MODEL_VERSION}"
)
if [[ -n "${EMBEDDING_MODEL_VERSION}" ]]; then
  TF_VAR_ARGS+=(-var "embedding_model_version=${EMBEDDING_MODEL_VERSION}")
fi

retry 3 10 terraform -chdir="${INFRA_DIR}" init -input=false -upgrade=false

DESTROY_ARGS=(-input=false "${TF_VAR_ARGS[@]}")
if [[ "${AUTO_APPROVE}" == "true" ]]; then
  DESTROY_ARGS+=(-auto-approve)
fi

retry 2 15 terraform -chdir="${INFRA_DIR}" destroy "${DESTROY_ARGS[@]}"

# ---------------------------------------------------------------------------
# Step 3: verify no workshop-managed resource remains in the resource group.
#
# `terraform destroy` can partially fail (a single resource stuck deleting,
# an eventually-consistent RBAC/lock issue, etc.) and still exit 0 for the
# rest of the plan in rare cases, or a participant may have run an earlier,
# manual partial cleanup. This is a defense-in-depth check, independent of
# Terraform's own state, before any local state is deleted: it lists every
# resource actually present in the resource group and fails loudly if any of
# them still carry this workshop's tag or name-prefix. A failed `az resource
# list` call is treated the same as "resources remain" (fail-safe default:
# never assume success when the check itself could not run).
# ---------------------------------------------------------------------------

echo "==> [3/4] Verifying no workshop-managed resources remain in '${RESOURCE_GROUP_NAME}'..." >&2

verify_no_remnants() {
  local resources_json remnants_json remnant_count remnant_names
  if ! resources_json="$(az resource list --resource-group "${RESOURCE_GROUP_NAME}" --subscription "${SUBSCRIPTION_ID}" -o json 2>&1)"; then
    echo "${SCRIPT_NAME}: 'az resource list' failed while verifying teardown; leaving local Terraform state and .workshop/ context in place so you can investigate safely. Error:" >&2
    echo "${resources_json}" >&2
    return 1
  fi

  remnants_json="$(jq -c --arg tag "${WORKSHOP_TAG_VALUE}" --arg prefix "${WORKSHOP_NAME_PREFIX}" \
    '[.[] | select((.tags.workshop // "") == $tag or (.name // "" | contains($prefix)))]' <<<"${resources_json}")" || {
    echo "${SCRIPT_NAME}: could not parse 'az resource list' output while verifying teardown; leaving local Terraform state and .workshop/ context in place. Raw output:" >&2
    echo "${resources_json}" >&2
    return 1
  }
  remnant_count="$(jq 'length' <<<"${remnants_json}")"

  if [[ "${remnant_count}" -gt 0 ]]; then
    remnant_names="$(jq -r '[.[].name] | join(", ")' <<<"${remnants_json}")"
    echo "${SCRIPT_NAME}: ${remnant_count} workshop-managed resource(s) still exist in resource group '${RESOURCE_GROUP_NAME}' after 'terraform destroy': ${remnant_names}. Leaving local Terraform state and .workshop/ context in place; investigate and re-run scripts/destroy.sh once these are removed." >&2
    return 2
  fi

  echo "    No workshop-managed resources remain (matched by tag 'workshop=${WORKSHOP_TAG_VALUE}' or name containing '${WORKSHOP_NAME_PREFIX}')." >&2
  return 0
}

VERIFY_STATUS=0
# ARM's resource list can briefly lag behind successful deletion.
retry 6 10 verify_no_remnants || VERIFY_STATUS=$?
if [[ ${VERIFY_STATUS} -ne 0 ]]; then
  exit "${VERIFY_STATUS}"
fi

# ---------------------------------------------------------------------------
# Step 4: remove local, non-secret .workshop/ state and the local Terraform
# state files -- only after every step above succeeded (bash -e already
# aborted the script on any earlier failure, and Step 3's verification is
# checked explicitly above since it is a function call, not a bare command).
# The resource group itself was never touched.
# ---------------------------------------------------------------------------

echo "==> [4/4] Removing local .workshop/ state and Terraform state files..." >&2
rm -f "${WORKSHOP_DIR}/context.json" "${RECOVERY_CONTEXT_FILE}" "${WORKSHOP_DIR}/.env" "${WORKSHOP_DIR}/tfplan" "${WORKSHOP_DIR}/preflight-report.json"
rm -f "${INFRA_DIR}/terraform.tfstate" "${INFRA_DIR}/terraform.tfstate.backup"

echo "Destroy complete. Resource group '${RESOURCE_GROUP_NAME}' was preserved (never deleted by this workshop's automation)." >&2

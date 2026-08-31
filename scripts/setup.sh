#!/usr/bin/env bash
# scripts/setup.sh
#
# One-command workshop environment setup for a participant who already has
# `az login` access and Owner on an EXISTING resource group. Orchestrates:
#   1. scripts/preflight.sh (read-only; resolves region + real model versions)
#   2. terraform init/plan/apply against infra/ (bounded retries)
#   3. scripts/bootstrap_data.py (seeds Azure AI Search directly from data/manifest.json;
#      bounded retries to absorb fresh RBAC/data-plane propagation)
#   4. scripts/validate_environment.py (confirms the deployed environment,
#      including ARM resource existence and a Travel Ops API /health check;
#      bounded retries for the same propagation reason as step 3)
#   5. writes non-secret .workshop/context.json and .workshop/.env
#   6. prints portal links
#
# Safe to re-run: setup recovers deterministic workshop resources that Azure
# created without a local Terraform state entry, terraform apply reconciles the
# resulting state, and bootstrap_data.py merge-or-uploads Search documents by id.
#
# --travel-api-image-ref is OPTIONAL. When omitted, this script resolves the
# immutable @sha256 digest for a public default GHCR tag itself (anonymous
# OCI registry token + manifest lookup via curl+jq -- no docker/az login
# needed), so the whole workshop stays a single command once the Travel Ops
# API image has been published. It never falls back to a mutable tag: if the
# default image/tag is not yet publicly pullable, it fails before Terraform
# with an admin-facing publish instruction (see resolve_ghcr_digest() below).
#
# Usage:
#   scripts/setup.sh --subscription <sub-id> --resource-group <rg-name> \
#                     [--travel-api-image-ref ghcr.io/org/travel-ops-api@sha256:<digest>] \
#                     [--location eastus2] [--auto-approve] [--skip-bootstrap]
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
INFRA_DIR="${REPO_ROOT}/infra"
WORKSHOP_DIR="${REPO_ROOT}/.workshop"

usage() {
  cat <<'EOF'
Usage: setup.sh --subscription <id> --resource-group <name> [options]

Required:
  --subscription <id>          Azure subscription ID.
  --resource-group <name>      EXISTING resource group name you own (Owner role).

Options:
  --travel-api-image-ref <ref> ghcr.io image reference pinned to an immutable
                                @sha256 digest for the Travel Ops API
                                container (published by another workstream).
                                May also be supplied via the
                                TRAVEL_API_IMAGE_REF environment variable.
                                OPTIONAL: when omitted, this script resolves
                                the immutable digest for the default public
                                image/tag itself (see below) via an
                                anonymous GHCR OCI registry lookup -- it
                                never falls back to a mutable tag.
  --travel-api-image-repo <repo>
                                GHCR repository to resolve the default image
                                from when --travel-api-image-ref is not
                                given, e.g. ghcr.io/org/travel-ops-api.
                                Defaults to ghcr.io/<owner>/travel-ops-api,
                                where <owner> is derived from `git remote
                                get-url origin` (matching
                                .github/workflows/publish-travel-api.yml's
                                own lower-cased github.repository_owner
                                convention), falling back to
                                ghcr.io/matayuuu/travel-ops-api if origin
                                cannot be resolved. May also be supplied via
                                the TRAVEL_API_IMAGE_REPO environment
                                variable.
  --travel-api-image-tag <tag> Tag to resolve to an immutable digest when
                                --travel-api-image-ref is not given. Defaults
                                to v1.0.3 (the latest validated workshop
                                release). May also be supplied via the
                                TRAVEL_API_IMAGE_TAG environment variable.
  --location <region>   Preferred region: eastus2 (default) or swedencentral.
                        scripts/preflight.sh may resolve to the other region
                        if the preferred one lacks required model/quota.
  --source-base <url>   Public base URL substituted for data/manifest.json's
                        source_url_base_placeholder token (used for citations
                        and each indexed chunk's source_url field). Must be a
                        real, publicly reachable URL -- never a Codespace-local
                        file:// path. Defaults to this repository's own GitHub
                        main-branch "blob/main" URL, derived from `git remote
                        get-url origin` when available, or the fixed
                        https://github.com/matayuuu/Microsoft-Foundry-Agent-
                        Service-Handson/blob/main fallback otherwise.
  --auto-approve        Skip the terraform plan confirmation prompt.
  --skip-bootstrap      Skip scripts/bootstrap_data.py (useful for
                        infra-only re-runs).
  --skip-validate       Skip scripts/validate_environment.py.
  -h, --help            Show this help and exit.
EOF
}

SUBSCRIPTION_ID=""
RESOURCE_GROUP_NAME=""
PREFERRED_LOCATION="eastus2"
TRAVEL_API_IMAGE_REF="${TRAVEL_API_IMAGE_REF:-}"
TRAVEL_API_IMAGE_REPO="${TRAVEL_API_IMAGE_REPO:-}"
TRAVEL_API_IMAGE_TAG="${TRAVEL_API_IMAGE_TAG:-v1.0.3}"
SOURCE_BASE=""
AUTO_APPROVE="false"
SKIP_BOOTSTRAP="false"
SKIP_VALIDATE="false"
DEFAULT_SOURCE_BASE_FALLBACK="https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/main"
DEFAULT_TRAVEL_API_IMAGE_REPO_FALLBACK="ghcr.io/matayuuu/travel-ops-api"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --subscription) SUBSCRIPTION_ID="${2:-}"; shift 2 ;;
    --resource-group) RESOURCE_GROUP_NAME="${2:-}"; shift 2 ;;
    --location) PREFERRED_LOCATION="${2:-}"; shift 2 ;;
    --travel-api-image-ref) TRAVEL_API_IMAGE_REF="${2:-}"; shift 2 ;;
    --travel-api-image-repo) TRAVEL_API_IMAGE_REPO="${2:-}"; shift 2 ;;
    --travel-api-image-tag) TRAVEL_API_IMAGE_TAG="${2:-}"; shift 2 ;;
    --source-base) SOURCE_BASE="${2:-}"; shift 2 ;;
    --auto-approve) AUTO_APPROVE="true"; shift 1 ;;
    --skip-bootstrap) SKIP_BOOTSTRAP="true"; shift 1 ;;
    --skip-validate) SKIP_VALIDATE="true"; shift 1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "${SCRIPT_NAME}: unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "${SUBSCRIPTION_ID}" || -z "${RESOURCE_GROUP_NAME}" ]]; then
  echo "${SCRIPT_NAME}: --subscription and --resource-group are both required" >&2
  usage >&2
  exit 1
fi

if [[ -n "${TRAVEL_API_IMAGE_REF}" && ( -n "${TRAVEL_API_IMAGE_REPO}" || "${TRAVEL_API_IMAGE_TAG}" != "v1.0.3" ) ]]; then
  echo "${SCRIPT_NAME}: --travel-api-image-repo/--travel-api-image-tag are ignored because --travel-api-image-ref was given explicitly" >&2
fi

for tool in az terraform jq curl git; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "${SCRIPT_NAME}: '${tool}' is required and was not found on PATH" >&2
    exit 1
  fi
done

# ---------------------------------------------------------------------------
# Derive the GitHub owner/repo once from git remote origin. Reused by both
# --source-base's default (repo's own "blob/main" URL) and the default
# Travel Ops API GHCR repository (ghcr.io/<owner>/travel-ops-api, matching
# .github/workflows/publish-travel-api.yml's own lower-cased
# github.repository_owner convention). Always falls back to this
# repository's own known values if origin cannot be resolved -- never to an
# arbitrary/local path.
# ---------------------------------------------------------------------------

GITHUB_REPO_HTTPS=""
GIT_ORIGIN_URL="$(git -C "${REPO_ROOT}" remote get-url origin 2>/dev/null || true)"
if [[ -n "${GIT_ORIGIN_URL}" ]]; then
  # Normalize git@github.com:org/repo.git and https://github.com/org/repo.git
  # (with or without a trailing .git) to https://github.com/org/repo.
  CANDIDATE_REPO_HTTPS="$(sed -E \
    -e 's#^git@github\.com:#https://github.com/#' \
    -e 's#\.git$##' \
    <<<"${GIT_ORIGIN_URL}")"
  if [[ "${CANDIDATE_REPO_HTTPS}" =~ ^https://github\.com/[^/]+/[^/]+$ ]]; then
    GITHUB_REPO_HTTPS="${CANDIDATE_REPO_HTTPS}"
  fi
fi
if [[ -n "${GITHUB_REPO_HTTPS}" ]]; then
  GITHUB_OWNER_LOWER="$(sed -E 's#^https://github\.com/([^/]+)/.*#\1#' <<<"${GITHUB_REPO_HTTPS}" | tr '[:upper:]' '[:lower:]')"
else
  GITHUB_OWNER_LOWER="matayuuu"
fi

# ---------------------------------------------------------------------------
# Resolve --travel-api-image-ref when it was not given explicitly: look up
# the immutable @sha256 digest for the default (or overridden) public
# GHCR repo:tag via an anonymous OCI registry token + manifest request.
# Never falls back to a mutable tag -- if the image/tag is not yet
# anonymously pullable, fail here with an admin-facing publish instruction,
# before terraform ever runs.
# ---------------------------------------------------------------------------

resolve_ghcr_digest() {
  # resolve_ghcr_digest <owner>/<image> <tag>
  # Prints "sha256:<64-hex>" on stdout and returns 0 on success.
  # Returns 2 if the image/tag is not anonymously pullable (private, not yet
  # published, or does not exist) -- the caller must fail before Terraform
  # with an admin-facing publish instruction, never fall back to a mutable
  # tag. Returns 1 on an unexpected/network-level failure.
  local repo_path="$1" tag="$2"
  local token_response token accept manifest_response status_line status digest

  token_response="$(curl -sS "https://ghcr.io/token?scope=repository:${repo_path}:pull&service=ghcr.io")" || {
    echo "${SCRIPT_NAME}: could not reach ghcr.io to request an anonymous pull token for ${repo_path}" >&2
    return 1
  }
  token="$(jq -r '.token // empty' <<<"${token_response}" 2>/dev/null || true)"
  if [[ -z "${token}" ]]; then
    # ghcr.io's token endpoint itself denies (HTTP 403 "DENIED") when a
    # repository/package does not exist or is not public yet -- this is the
    # common "not published yet" case, not a network failure.
    return 2
  fi

  accept="application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json"

  manifest_response="$(curl -sS -D - -o /dev/null \
    -H "Authorization: Bearer ${token}" \
    -H "Accept: ${accept}" \
    "https://ghcr.io/v2/${repo_path}/manifests/${tag}")" || {
    echo "${SCRIPT_NAME}: could not reach ghcr.io to look up the manifest for ${repo_path}:${tag}" >&2
    return 1
  }

  status_line="$(head -n1 <<<"${manifest_response}" | tr -d '\r')"
  status="$(awk '{print $2}' <<<"${status_line}")"

  if [[ "${status}" == "404" ]]; then
    return 2
  elif [[ "${status}" != "200" ]]; then
    echo "${SCRIPT_NAME}: unexpected HTTP ${status} from ghcr.io manifest lookup for ${repo_path}:${tag}" >&2
    return 1
  fi

  digest="$(grep -i '^docker-content-digest:' <<<"${manifest_response}" | tr -d '\r' | awk '{print $2}' | tail -n1 || true)"
  if [[ -z "${digest}" || ! "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]]; then
    echo "${SCRIPT_NAME}: ghcr.io manifest response for ${repo_path}:${tag} did not include a valid Docker-Content-Digest header" >&2
    return 1
  fi

  echo "${digest}"
  return 0
}

TRAVEL_API_IMAGE_RESOLUTION="explicit"
if [[ -z "${TRAVEL_API_IMAGE_REF}" ]]; then
  if [[ -z "${TRAVEL_API_IMAGE_REPO}" ]]; then
    if [[ -n "${GITHUB_REPO_HTTPS}" ]]; then
      TRAVEL_API_IMAGE_REPO="ghcr.io/${GITHUB_OWNER_LOWER}/travel-ops-api"
    else
      TRAVEL_API_IMAGE_REPO="${DEFAULT_TRAVEL_API_IMAGE_REPO_FALLBACK}"
    fi
  fi
  if [[ ! "${TRAVEL_API_IMAGE_REPO}" =~ ^ghcr\.io/[a-z0-9._/-]+$ ]]; then
    echo "${SCRIPT_NAME}: --travel-api-image-repo must be a bare ghcr.io/<owner>/<image> path (no tag/digest), got: ${TRAVEL_API_IMAGE_REPO}" >&2
    exit 1
  fi

  echo "==> Resolving immutable digest for ${TRAVEL_API_IMAGE_REPO}:${TRAVEL_API_IMAGE_TAG} (no --travel-api-image-ref given)..." >&2
  REPO_PATH="${TRAVEL_API_IMAGE_REPO#ghcr.io/}"
  if RESOLVED_DIGEST="$(resolve_ghcr_digest "${REPO_PATH}" "${TRAVEL_API_IMAGE_TAG}")"; then
    TRAVEL_API_IMAGE_REF="${TRAVEL_API_IMAGE_REPO}@${RESOLVED_DIGEST}"
    TRAVEL_API_IMAGE_RESOLUTION="auto:${TRAVEL_API_IMAGE_TAG}"
    echo "    Resolved: ${TRAVEL_API_IMAGE_REF}" >&2
  else
    RESOLVE_STATUS=$?
    if [[ ${RESOLVE_STATUS} -eq 2 ]]; then
      cat <<EOF >&2
${SCRIPT_NAME}: the default Travel Ops API image '${TRAVEL_API_IMAGE_REPO}:${TRAVEL_API_IMAGE_TAG}' is
not publicly pullable yet (anonymous ghcr.io token/manifest lookup was denied
or returned not-found). This is expected before the maintainer has published
a release image. This script never falls back to a mutable tag, so it is
stopping here, before Terraform runs.

To fix this, a repository maintainer/administrator must:
  1. Push a git tag matching travel-api-v<version> (e.g. travel-api-v1.0.0),
     or manually run the "Publish Travel Ops API" workflow
     (.github/workflows/publish-travel-api.yml) via workflow_dispatch.
  2. Confirm the resulting GHCR package's visibility is Public: open
     https://github.com/${GITHUB_OWNER_LOWER}?tab=packages, select
     travel-ops-api > Package settings, and set visibility to Public if it
     is not already (newly published GHCR packages can default to private).
  3. Re-run this script, or pass --travel-api-image-ref (or
     --travel-api-image-repo/--travel-api-image-tag) explicitly once the
     image is confirmed public.
EOF
    else
      echo "${SCRIPT_NAME}: could not resolve an immutable digest for ${TRAVEL_API_IMAGE_REPO}:${TRAVEL_API_IMAGE_TAG} (unexpected error above); aborting rather than falling back to a mutable tag." >&2
    fi
    exit 2
  fi
fi

if [[ ! "${TRAVEL_API_IMAGE_REF}" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]]; then
  echo "${SCRIPT_NAME}: --travel-api-image-ref must be a ghcr.io reference pinned to an immutable @sha256:<64-hex> digest, got: ${TRAVEL_API_IMAGE_REF}" >&2
  exit 1
fi

if [[ -z "${SOURCE_BASE}" ]]; then
  # Always resolves to the repo's main branch (never the current, possibly
  # unpushed/private, workstream branch) so citation/source_url links are
  # stable and valid for every participant, per "actual repo main URL".
  if [[ -n "${GITHUB_REPO_HTTPS}" ]]; then
    SOURCE_BASE="${GITHUB_REPO_HTTPS}/blob/main"
  else
    SOURCE_BASE="${DEFAULT_SOURCE_BASE_FALLBACK}"
    echo "${SCRIPT_NAME}: could not derive --source-base from git remote origin; using fallback: ${SOURCE_BASE}" >&2
  fi
fi
echo "    Using --source-base: ${SOURCE_BASE}" >&2
if [[ "${SOURCE_BASE}" == file://* ]]; then
  echo "${SCRIPT_NAME}: --source-base must be a real public URL, not a local file:// path: ${SOURCE_BASE}" >&2
  exit 1
fi

mkdir -p "${WORKSHOP_DIR}"

retry() {
  # retry <max-attempts> <sleep-seconds> -- <command...>
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

TERRAFORM_APPLY_ATTEMPT=0
prepare_terraform_plan() {
  "${PYTHON_BIN}" "${SCRIPT_DIR}/prepare_terraform_plan.py" \
    --terraform-dir "${INFRA_DIR}" \
    --plan-file "${WORKSHOP_DIR}/tfplan" \
    --subscription "${SUBSCRIPTION_ID}" \
    --resource-group "${RESOURCE_GROUP_NAME}" \
    -- "${TF_VAR_ARGS[@]}"
}

apply_terraform_plan() {
  TERRAFORM_APPLY_ATTEMPT=$((TERRAFORM_APPLY_ATTEMPT + 1))

  # A partial apply changes state, so the original saved plan becomes stale.
  # Refresh it before every retry while preserving the participant-confirmed
  # plan for the first attempt.
  if [[ ${TERRAFORM_APPLY_ATTEMPT} -gt 1 ]]; then
    echo "    Refreshing Terraform plan before apply attempt ${TERRAFORM_APPLY_ATTEMPT}..." >&2
    if ! prepare_terraform_plan; then
      return 1
    fi
  fi

  terraform -chdir="${INFRA_DIR}" apply -input=false -auto-approve "${WORKSHOP_DIR}/tfplan"
}

# ---------------------------------------------------------------------------
# Step 1: preflight (read-only)
# ---------------------------------------------------------------------------

echo "==> [1/5] Running participant preflight..." >&2
PREFLIGHT_REPORT="${WORKSHOP_DIR}/preflight-report.json"
PREFLIGHT_EXIT=0
"${SCRIPT_DIR}/preflight.sh" \
  --subscription "${SUBSCRIPTION_ID}" \
  --resource-group "${RESOURCE_GROUP_NAME}" \
  --location "${PREFERRED_LOCATION}" \
  --format json \
  --output "${PREFLIGHT_REPORT}" || PREFLIGHT_EXIT=$?

if [[ ! -s "${PREFLIGHT_REPORT}" ]]; then
  echo "${SCRIPT_NAME}: preflight did not produce a report at ${PREFLIGHT_REPORT}; aborting." >&2
  exit 2
fi

OVERALL_STATUS="$(jq -r '.overall_status' "${PREFLIGHT_REPORT}")"
if [[ "${OVERALL_STATUS}" == "fail" || ${PREFLIGHT_EXIT} -eq 2 ]]; then
  echo "${SCRIPT_NAME}: preflight reported failing checks. See ${PREFLIGHT_REPORT} for details. Not proceeding." >&2
  jq -r '.checks[] | select(.status == "fail") | "  [FAIL] " + .name + ": " + .detail' "${PREFLIGHT_REPORT}" >&2
  exit 2
elif [[ ${PREFLIGHT_EXIT} -ne 0 ]]; then
  echo "${SCRIPT_NAME}: preflight exited with code ${PREFLIGHT_EXIT} unexpectedly; aborting." >&2
  exit "${PREFLIGHT_EXIT}"
fi

RESOLVED_LOCATION="$(jq -r '.resolved_location' "${PREFLIGHT_REPORT}")"
OPTIMIZER_MODEL_VERSION="$(jq -r '.resolved_model_versions["gpt-5"] // empty' "${PREFLIGHT_REPORT}")"
PRIMARY_MODEL_VERSION="$(jq -r '.resolved_model_versions["gpt-4.1"] // empty' "${PREFLIGHT_REPORT}")"
EMBEDDING_MODEL_VERSION="$(jq -r '.resolved_model_versions["text-embedding-3-small"] // empty' "${PREFLIGHT_REPORT}")"

if [[ -z "${RESOLVED_LOCATION}" || "${RESOLVED_LOCATION}" == "null" ]]; then
  echo "${SCRIPT_NAME}: preflight did not resolve a usable region; aborting." >&2
  exit 2
fi
if [[ -z "${OPTIMIZER_MODEL_VERSION}" || "${OPTIMIZER_MODEL_VERSION}" == "null" ]]; then
  echo "${SCRIPT_NAME}: preflight could not discover an available optimizer (gpt-5 family) model version in ${RESOLVED_LOCATION}; aborting rather than guessing one." >&2
  exit 2
fi

echo "    Resolved region: ${RESOLVED_LOCATION}" >&2
echo "    Resolved optimizer model version: ${OPTIMIZER_MODEL_VERSION}" >&2

PYTHON_BIN="${WORKSHOP_PYTHON:-${REPO_ROOT}/.venv/bin/python}"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi
if [[ -z "${PYTHON_BIN}" || ! -x "${PYTHON_BIN}" ]]; then
  echo "${SCRIPT_NAME}: workshop Python environment not found. Rebuild the Codespace or run 'make install'." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Step 2: terraform init/plan/apply
# ---------------------------------------------------------------------------

echo "==> [2/5] Running terraform init/plan/apply..." >&2

TF_VAR_ARGS=(
  -var "subscription_id=${SUBSCRIPTION_ID}"
  -var "resource_group_name=${RESOURCE_GROUP_NAME}"
  -var "location=${RESOLVED_LOCATION}"
  -var "travel_api_image_ref=${TRAVEL_API_IMAGE_REF}"
  -var "source_base=${SOURCE_BASE}"
  -var "optimizer_model_version=${OPTIMIZER_MODEL_VERSION}"
)
if [[ -n "${PRIMARY_MODEL_VERSION}" && "${PRIMARY_MODEL_VERSION}" != "null" ]]; then
  TF_VAR_ARGS+=(-var "primary_model_version=${PRIMARY_MODEL_VERSION}")
fi
if [[ -n "${EMBEDDING_MODEL_VERSION}" && "${EMBEDDING_MODEL_VERSION}" != "null" ]]; then
  TF_VAR_ARGS+=(-var "embedding_model_version=${EMBEDDING_MODEL_VERSION}")
fi

retry 3 10 terraform -chdir="${INFRA_DIR}" init -input=false -upgrade=false

prepare_terraform_plan

if [[ "${AUTO_APPROVE}" != "true" ]]; then
  read -r -p "Apply the plan above to resource group '${RESOURCE_GROUP_NAME}'? [y/N] " CONFIRM
  if [[ ! "${CONFIRM}" =~ ^[Yy]$ ]]; then
    echo "${SCRIPT_NAME}: apply cancelled by participant." >&2
    exit 1
  fi
fi

retry 3 15 apply_terraform_plan

TF_OUTPUTS_JSON="$(terraform -chdir="${INFRA_DIR}" output -json)"

# Written once to a stable file (not a process substitution) because both
# bootstrap_data.py and validate_environment.py below are wrapped in
# retry() -- a process substitution's underlying pipe is only readable once,
# so re-invoking a command against the same `<(...)` path on a retry attempt
# would see EOF instead of the real content. Non-secret (identical to the
# `terraform_outputs` field later written to .workshop/context.json);
# removed on exit regardless of success or failure.
TF_OUTPUTS_FILE="$(mktemp "${WORKSHOP_DIR}/tf-outputs.XXXXXX.json")"
echo "${TF_OUTPUTS_JSON}" >"${TF_OUTPUTS_FILE}"
trap 'rm -f "${TF_OUTPUTS_FILE}"' EXIT

# ---------------------------------------------------------------------------
# Step 3: bootstrap_data.py
# ---------------------------------------------------------------------------

MANIFEST_PATH="${REPO_ROOT}/data/manifest.json"
if [[ "${SKIP_BOOTSTRAP}" == "true" ]]; then
  echo "==> [3/5] Skipping bootstrap_data.py (--skip-bootstrap)." >&2
elif [[ ! -f "${MANIFEST_PATH}" ]]; then
  echo "==> [3/5] WARNING: ${MANIFEST_PATH} does not exist yet (owned by the data workstream)." >&2
  echo "    Skipping RAG data bootstrap. Re-run this script (or just:" >&2
  echo "    .venv/bin/python scripts/bootstrap_data.py ...) once data/manifest.json is available." >&2
else
  echo "==> [3/5] Running bootstrap_data.py..." >&2
  SEARCH_ENDPOINT="$(jq -r '.search_service_endpoint.value' <<<"${TF_OUTPUTS_JSON}")"
  OPENAI_ENDPOINT="$(jq -r '.openai_endpoint.value' <<<"${TF_OUTPUTS_JSON}")"
  EMBEDDING_DEPLOYMENT_NAME="$(jq -r '.embedding_model_deployment_name.value' <<<"${TF_OUTPUTS_JSON}")"

  # --embedding-dimensions and --max-tokens/--overlap-tokens are intentionally
  # omitted: bootstrap_data.py defaults them to data/manifest.json's own
  # embedding.default_dimensions / chunking.max_tokens / chunking.overlap_tokens
  # contract values, so this orchestration script never hardcodes/duplicates
  # values that could drift from the manifest.
  #
  # Wrapped in a bounded retry: role assignments Terraform just created
  # (Search index-data roles and Foundry User on the project) can take up to a
  # couple of minutes to propagate through Entra/RBAC. Search writes are
  # idempotent (merge-or-upload by id), so retrying the whole invocation on a
  # transient auth/data-plane failure is safe.
  retry 5 20 "${PYTHON_BIN}" "${SCRIPT_DIR}/bootstrap_data.py" \
    --manifest "${MANIFEST_PATH}" \
    --search-endpoint "${SEARCH_ENDPOINT}" \
    --openai-endpoint "${OPENAI_ENDPOINT}" \
    --embedding-deployment "${EMBEDDING_DEPLOYMENT_NAME}" \
    --source-base "${SOURCE_BASE}" \
    --index-name "contoso-travel-policy"
fi

# ---------------------------------------------------------------------------
# Step 4: validate_environment.py
# ---------------------------------------------------------------------------

if [[ "${SKIP_VALIDATE}" == "true" ]]; then
  echo "==> [4/5] Skipping validate_environment.py (--skip-validate)." >&2
else
  echo "==> [4/5] Running validate_environment.py..." >&2
  # Wrapped in a bounded retry for the same reason as bootstrap_data.py
  # above: RBAC propagation and the Travel Ops Container App's own cold
  # start/first health probe can both still be settling for a short window
  # right after `terraform apply`. validate_environment.py is read-only, so
  # retrying it is always safe; retry() itself prints every failed attempt,
  # so a real (non-transient) validation failure is still visible, just
  # after this bounded number of attempts rather than immediately.
  retry 5 15 "${PYTHON_BIN}" "${SCRIPT_DIR}/validate_environment.py" \
    --subscription "${SUBSCRIPTION_ID}" \
    --resource-group "${RESOURCE_GROUP_NAME}" \
    --terraform-outputs "${TF_OUTPUTS_FILE}"
fi

# ---------------------------------------------------------------------------
# Step 5: write non-secret context + print portal links
# ---------------------------------------------------------------------------

echo "==> [5/5] Writing .workshop/context.json and .workshop/.env..." >&2

CONTEXT_JSON="$(jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg subscription_id "${SUBSCRIPTION_ID}" \
  --arg resource_group_name "${RESOURCE_GROUP_NAME}" \
  --arg location "${RESOLVED_LOCATION}" \
  --arg travel_api_image_ref "${TRAVEL_API_IMAGE_REF}" \
  --arg travel_api_image_resolution "${TRAVEL_API_IMAGE_RESOLUTION}" \
  --arg optimizer_model_version "${OPTIMIZER_MODEL_VERSION}" \
  --arg primary_model_version "${PRIMARY_MODEL_VERSION}" \
  --arg embedding_model_version "${EMBEDDING_MODEL_VERSION}" \
  --arg source_base "${SOURCE_BASE}" \
  --argjson terraform_outputs "${TF_OUTPUTS_JSON}" \
  '{
    generated_at: $generated_at,
    subscription_id: $subscription_id,
    resource_group_name: $resource_group_name,
    location: $location,
    source_base: $source_base,
    terraform_inputs: {
      travel_api_image_ref: $travel_api_image_ref,
      travel_api_image_resolution: $travel_api_image_resolution,
      optimizer_model_version: $optimizer_model_version,
      primary_model_version: $primary_model_version,
      embedding_model_version: $embedding_model_version
    },
    terraform_outputs: $terraform_outputs
  }')"
echo "${CONTEXT_JSON}" | jq '.' > "${WORKSHOP_DIR}/context.json"

{
  echo "# Generated by scripts/setup.sh -- non-secret values only. Do not commit."
  echo "AZURE_SUBSCRIPTION_ID=${SUBSCRIPTION_ID}"
  echo "AZURE_RESOURCE_GROUP=${RESOURCE_GROUP_NAME}"
  echo "AZURE_LOCATION=${RESOLVED_LOCATION}"
  echo "WORKSHOP_SOURCE_BASE=${SOURCE_BASE}"
  jq -r 'to_entries[] | "\(.key | ascii_upcase)=\(.value.value)"' <<<"${TF_OUTPUTS_JSON}"
} > "${WORKSHOP_DIR}/.env"

FOUNDRY_PORTAL_URL="$(jq -r '.foundry_portal_url.value' <<<"${TF_OUTPUTS_JSON}")"
AI_SERVICES_ACCOUNT_NAME="$(jq -r '.ai_services_account_name.value' <<<"${TF_OUTPUTS_JSON}")"
FOUNDRY_PROJECT_NAME="$(jq -r '.foundry_project_name.value' <<<"${TF_OUTPUTS_JSON}")"
FOUNDRY_PROJECT_ENDPOINT="$(jq -r '.foundry_project_endpoint.value' <<<"${TF_OUTPUTS_JSON}")"
TRAVEL_API_FQDN="$(jq -r '.travel_api_fqdn.value' <<<"${TF_OUTPUTS_JSON}")"

cat <<EOF

Setup complete.

Foundry portal:   ${FOUNDRY_PORTAL_URL}
  Account:        ${AI_SERVICES_ACCOUNT_NAME}
  Project:        ${FOUNDRY_PROJECT_NAME}
  Project endpoint: ${FOUNDRY_PROJECT_ENDPOINT}
  (No officially confirmed direct deep-link URL format was found; open the
  portal above and select the account/project by name.)

Travel Ops API:   https://${TRAVEL_API_FQDN}

Non-secret context written to:
  ${WORKSHOP_DIR}/context.json
  ${WORKSHOP_DIR}/.env
EOF

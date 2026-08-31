# infra/

Terraform control plane for the Foundry Agent Service hands-on workshop.
This directory is owned by the Azure/Terraform and lifecycle workstream; see
the repository root `AGENTS.md` for full ownership boundaries.

## Design constraints this directory encodes

- **Existing resource group only.** `data.azurerm_resource_group.workshop`
  reads a resource group the participant already owns; Terraform never
  creates, renames, or destroys a resource group, registers resource
  providers, changes quota/policy, or writes role assignments outside that
  resource group.
- **Provider auto-registration disabled.** `providers.tf` sets
  `resource_provider_registrations = "none"` on the `azurerm` provider (the
  default for azurerm >= 4.x, pinned explicitly here so this doesn't regress
  on a provider upgrade) and `skip_provider_registration = true` on `azapi`.
  Provider registration is the subscription administrator's job
  (`scripts/admin-preflight.sh --apply`), never the participant's.
- **Public endpoints + Microsoft Entra ID / RBAC only.** No VNet, Private
  Link, or customer-managed keys. Every data-plane credential is either a
  system-assigned managed identity or the participant's own `az login`
  session; local/shared-key auth is disabled wherever the resource supports
  it (Search `local_authentication_enabled = false`, Foundry account
  `disableLocalAuth = true`).
- **Basic Agent Setup only.** No Cosmos DB, no Agent capability host, no
  ACR, no Key Vault. Matches
  `foundry-samples`' Basic Agent Setup template, not the Standard/BYO-Cosmos
  setup.
- **AzureRM vs AzAPI split.**
  - `azurerm` (~> 5.0): resource group data source, Azure AI Search service,
    Log Analytics workspace, Application Insights, Container Apps
    environment/app, and all role assignments -- resources with stable,
    well-supported azurerm coverage.
  - `azapi` (~> 2.0): the Foundry `AIServices` account, its `projects`
    sub-resource, `deployments` (model deployments), and `projects/connections`
    -- the new Foundry resource model, which azurerm does not yet reliably
    expose. Pinned to ARM API version **2026-05-01** (the current GA,
    non-preview version for these resource types as of the 2026-08-21
    retrieval date recorded in `foundry_account.tf`).
- **Model deployments are variable-driven, not guessed.** Three deployments
  (`primary` = gpt-4.1, `optimizer` = a supported gpt-5-family model,
  `embedding` = text-embedding-3-small) have overridable
  name/version/sku/capacity variables. `optimizer_model_version` has
  intentionally no default: `scripts/preflight.sh` must discover a real,
  available version via `az cognitiveservices model list` before it is
  supplied to Terraform.
- **State is local by default and treated as sensitive.** No backend block
  is declared in `versions.tf`, so Terraform defaults to a local state file
  (already gitignored). `backend.remote.tf.example` documents how an
  organizer can opt into a shared Azure Blob backend; it is inert until
  copied to `backend.tf`.
- **No secret outputs.** `outputs.tf` only exposes resource/service names,
  endpoints (including the Foundry project endpoint and its three model
  deployment names), and the container app's public FQDN -- never keys,
  connection strings, or tokens.

## File layout

| File | Purpose |
| --- | --- |
| `versions.tf` | Terraform + provider version pins, backend note |
| `providers.tf` | `azurerm`/`azapi` provider configuration |
| `variables.tf` | All overridable inputs, with validation blocks |
| `locals.tf` | Deterministic naming, role-definition GUID map |
| `data.tf` | Existing resource group + current client config |
| `search.tf` | Azure AI Search (Basic, keyless, system-assigned identity) |
| `monitoring.tf` | Log Analytics workspace + Application Insights |
| `container_apps.tf` | Container Apps environment + Travel Ops API app |
| `foundry_account.tf` | Foundry `AIServices` account (AzAPI) |
| `foundry_project.tf` | Foundry project (AzAPI, Basic Agent Setup) |
| `foundry_deployments.tf` | Three model deployments (AzAPI) |
| `foundry_connections.tf` | Project connections to Search and Application Insights |
| `rbac.tf` | All role assignments (participant + managed identities) |
| `outputs.tf` | Non-secret outputs consumed by `scripts/setup.sh` |
| `backend.remote.tf.example` | Inert example of an organizer-managed remote state backend |
| `terraform.tfvars.example` | Example variable values (copy to `terraform.tfvars`, gitignored) |

## Validating locally

```bash
terraform -chdir=infra fmt -recursive
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
```

These are also what `make terraform-validate` runs. `terraform validate`
does not evaluate custom variable `validation` blocks for variables without
a default and no `-var`/tfvars supplied, so `optimizer_model_version` (which
intentionally has no default) does not block a bare `validate` run; it is
enforced at `plan`/`apply` time once `scripts/preflight.sh` supplies a real
value.

## Known/documented uncertainties

- The exact `ai.azure.com` deep-link URL format for a specific Foundry
  project could not be confirmed against an official source at authoring
  time. `outputs.tf` and `scripts/setup.sh` print the guaranteed-correct
  generic portal URL plus resource names/IDs a participant can use to
  navigate manually.
- Exact default version/capacity for the optimizer's `gpt-5`-family
  deployment are intentionally left without a hardcoded default
  (`optimizer_model_version` has no default) and must be resolved by
  `scripts/preflight.sh` against the live subscription/region.

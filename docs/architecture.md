# Architecture

## Goal

The workshop must be repeatable from a GitHub Codespace by a participant who can run
`az login` and is Owner only on an existing Azure resource group. Subscription-level
preparation is deliberately separated from participant setup.

The core path is intentionally a **Basic Agent Setup**. Azure AI Search is provisioned
for workshop knowledge, but Agent Service state remains platform-managed. This avoids
Cosmos DB, capability hosts, ACR, and private networking in the limited workshop slot.

## Runtime view

```mermaid
flowchart LR
    browser[Participant browser] --> portal[Microsoft Foundry portal]
    browser --> codespace[GitHub Codespaces]
    codespace -->|az login| azure[Azure control and data planes]
    codespace -->|Terraform| foundry[Foundry account and project]
    codespace -->|Terraform| search[Azure AI Search]
    codespace -->|Terraform| storage[Storage]
    codespace -->|Terraform| monitor[Application Insights]
    codespace -->|Terraform| api[Travel Ops API]
    codespace -->|Python bootstrap| search
    portal --> prompt[Prompt Agent]
    prompt --> iq[Foundry IQ knowledge base]
    iq --> search
    prompt --> toolbox[Toolbox]
    toolbox --> api
    codespace -->|Python SDK source deploy| hosted[Hosted Agent]
    prompt --> monitor
    hosted --> monitor
```

## Resource ownership

| Object | Owner | Lifecycle |
|---|---|---|
| Existing resource group | Workshop administrator | Never created or deleted by this repository |
| Foundry account/project and model deployments | Terraform | `setup.sh` / `destroy.sh` |
| Search, Storage, Application Insights, Container Apps | Terraform | `setup.sh` / `destroy.sh` |
| Search index documents | Bootstrap adapter | Idempotent upsert after Terraform |
| Prompt Agent and Foundry IQ knowledge base | Participant in portal | Deleted with the parent project |
| Toolbox versions and evaluation runs | Python SDK wrapper | Created in labs; deleted explicitly when supported or with parent project |
| Hosted Agent and immutable versions | Python SDK wrapper | Created in Lab 7; deleted before Terraform |

Terraform and SDK wrappers must not manage the same object.

## Resource set

Core infrastructure in the participant resource group:

- Microsoft Foundry account (`AIServices`) with project management enabled
- Microsoft Foundry project
- `gpt-4.1` deployment for agent inference, evaluation, and Foundry IQ query planning
- a supported `gpt-5` family deployment for Agent Optimizer
- `text-embedding-3-small` deployment for the seeded vector index
- Azure AI Search Basic, one replica and one partition
- Storage Standard_LRS for synthetic source documents
- Log Analytics and workspace-based Application Insights
- Container Apps consumption environment and scale-to-zero Travel Ops API

The exact model version, deployment SKU, and capacity are inputs. The subscription
administrator preflight verifies them before participants start.

## Authentication and authorization

The participant authenticates interactively with Azure CLI. Terraform and Python use
the same cached Entra identity through `DefaultAzureCredential`.

- No client secrets or service-principal credentials are required.
- Local/shared keys are disabled where supported.
- The participant receives Foundry and data-plane roles inside the existing resource
  group through Terraform.
- The project and Search managed identities receive only the roles required to call
  models and read or update workshop data.
- Terraform state can contain provider-computed credentials and is treated as
  sensitive even when runtime access is keyless.

## Control-plane and data-plane split

AzureRM is used for stable Azure resources. AzAPI is used for the current Foundry
account/project/deployment/connection resource shapes when AzureRM does not expose the
required contract. Terraform provider auto-registration is disabled because a resource
group Owner cannot register resource providers.

Data-plane operations remain in typed Python adapters:

- upload synthetic documents
- generate embeddings
- create/update the semantic vector index
- merge-or-upload indexed chunks
- create toolbox and evaluation objects
- deploy/delete Hosted Agent versions from source

Pure configuration, chunking, validation, and policy logic is kept independent from
Azure clients so tests run without Azure access.

## Network posture

The workshop uses public service endpoints protected by Entra ID/RBAC. It does not
configure VNet injection, private endpoints, private DNS, customer-managed keys, or
network-isolated evaluation. These are production design topics, not hidden defaults.

## Failure boundaries

1. `admin-preflight.sh` reports subscription blockers before the event.
2. `preflight.sh` fails before Terraform when identity, RG, provider, region, quota
   evidence, or policy is missing.
3. Terraform failure leaves state for a safe retry.
4. Bootstrap uses upsert semantics and validates the final index.
5. Hosted remote build polls to a bounded terminal status and exposes build failure
   details.
6. Cleanup removes data-plane children before their Terraform-managed parent and only
   deletes local state after Azure cleanup succeeds.

## Maintainability checks

- Business rules in the mock API and Hosted workflow are testable without HTTP or Azure.
- Preview API shapes are isolated behind adapters and contract tests.
- Generated resource values have one source of truth: `.workshop/context.json`.
- Optional Fabric IQ, Work IQ, A2A, ACR, and CI/CD material cannot alter the core setup.

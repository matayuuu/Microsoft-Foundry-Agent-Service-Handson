[日本語](README.md) | **English**

# Microsoft Foundry Agent Service Hands-on

This 3-hour-and-50-minute hands-on workshop covers the key features of Microsoft
Foundry Agent Service through a single "Contoso internal travel and expense
assistance" scenario.

Using GitHub Codespaces and Microsoft Foundry (new), participants work through
environment setup, Prompt Agent, Azure AI Search/Foundry IQ, Tools/Toolbox,
evaluation, Agent Optimizer, a multi-agent Hosted Agent built with Microsoft Agent
Framework, observability, and cleanup.

## Prerequisites

- A GitHub account with access to Codespaces
- The ability to run `az login` with Azure CLI
- A pre-provisioned Azure subscription and an existing resource group
- **Owner** access to the assigned resource group
- A subscription administrator who has completed the
  [administrator prerequisites](docs/admin/prerequisites.md)

Resource provider registration and model quota are subscription-scoped, so a
resource group Owner cannot prepare them alone. This workshop fully supports
environments where participants cannot make subscription-level changes by separating
the administrator and participant preflight checks.

## Quick start

Before distributing resource groups to participants, a subscription administrator
or coordinator checks the aggregate quota. The following example checks quota for 20
environments in a shared subscription:

```bash
./scripts/admin-preflight.sh \
  --subscription "<subscription-id>" \
  --participant-count 20
```

1. Create a Codespace from this repository.
2. Sign in to Azure from the Codespace terminal.
3. Run setup with the assigned subscription and resource group.

```bash
az login --use-device-code

./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>"
```

Open the Microsoft Foundry portal link shown after provisioning, then proceed from
[Lab 0](labs/00-overview.md).

By default, the public Travel Ops API image's `v1.0.2` tag is automatically resolved
to an immutable digest. If the maintainer has not published the image yet, setup
stops before Terraform runs and displays publishing instructions that use
`.github/workflows/publish-travel-api.yml`.

At the end of the workshop, remove all resources, including data-plane objects such
as the Hosted Agent. This command does not delete the resource group itself.

```bash
./scripts/destroy.sh
```

## Agenda

| Time | Topic |
|---|---|
| 00:00-00:10 | Opening and architecture overview |
| 00:10-00:30 | One-command provisioning with Codespaces and Terraform |
| 00:30-00:50 | Prompt Agent |
| 00:50-01:25 | Azure AI Search and Foundry IQ |
| 01:25-01:35 | Break |
| 01:35-02:10 | Tools, Tool Catalog, and Toolbox |
| 02:10-02:35 | Agent evaluation |
| 02:35-02:55 | Agent Optimizer and version comparison |
| 02:55-03:40 | Deploying an Agent Framework workflow as a Hosted Agent |
| 03:40-03:50 | Observability, governance, and cleanup |

## Design principles

- **Portal-first**: Use Foundry Toolkit/Python SDK only for operations unavailable in
  the portal.
- **Existing RG only**: Terraform never writes outside the specified resource group.
- **Keyless**: Runtime access uses Microsoft Entra ID/RBAC.
- **Repeatable**: Setup, bootstrap, and destroy operations are safe to rerun.
- **Synthetic data**: No real-world data or personal information is used.
- **Current path**: The main multi-agent lab uses Microsoft Agent Framework instead
  of Workflow Designer, which is scheduled for retirement on December 1, 2026.

For details, see the [architecture](docs/architecture.md) and
[feature support matrix](docs/feature-support-matrix.md).

## Repository validation

The root SDK/Travel API and Hosted Agent require different compatible versions of
`azure-ai-projects`, so they use separate Python 3.13 virtual environments.
Codespaces creates both environments automatically.

```bash
make install
make install-hosted
make validate
```

## Core and optional scope

Fabric IQ and Work IQ require additional licenses, published Fabric items, Microsoft
Entra tenant administrator consent, and other prerequisites, so they are provided as
optional labs rather than part of the core workshop. Private Link/VNet, ACR container
deployment, A2A, Routines, Teams/Microsoft 365 publishing, and CI/CD are also outside
the core scope.

- [Optional labs index](labs/optional/README.md)
- [Instructor runbook](instructor/README.md)

# Workshop architecture

![Workshop architecture](images/workshop-architecture.svg)

Editable source: [workshop-architecture.excalidraw](diagrams/workshop-architecture.excalidraw).
Learning flow: [SVG](images/workshop-learning-flow.svg) /
[editable source](diagrams/workshop-learning-flow.excalidraw).
These explain the design; they are not deployment evidence.

## Ownership

| Owner | Responsibility |
|---|---|
| Participant / Azure Portal | Manually create one dedicated RG; select that existing RG in the custom template; keep other defaults; verify success; delete the RG at the end |
| Bicep / generated ARM | Foundry, models, Search, API, monitoring, connections and scoped RBAC within the existing RG |
| Deployment Scripts | Seed two Search indexes, prepare evaluation data and rubric, validate, then return completed context |
| GitHub | Shared Skill ZIPs and OpenAPI under `assets/`; notebooks, scripts and Python source |
| Foundry Portal | Prompt Agent, Foundry IQ, Toolbox, evaluation, optimizer and traces |
| Codespaces / local Dev Container | The same Notebook environment for Labs 7/8; personal Azure CLI sign-in and Hosted lifecycle commands |

The Portal template is generated from `infra/main.bicep`. Bootstrap prepares data, not the learning
Agent, knowledge base or Toolbox. Participants create those in the labs.

## Azure services

One dedicated **Japan East** RG contains:

- Foundry project `contoso-travel`, **Basic Agent Setup**
- GlobalStandard: `gpt-5.6-luna` **40K TPM**, `gpt-5.5` **100K TPM**,
  `embedding` / `text-embedding-3-small` **40K TPM**
- Search **Basic** with `contoso-travel-policy` and `contoso-travel-approval`
- Public Container Apps Travel Ops API
- Log Analytics and Application Insights
- System identities, scoped RBAC and a dedicated bootstrap user-assigned identity

`contoso-travel-search` is the AAD Search resource connection.
`contoso-travel-knowledge-lab-mcp` and `contoso-travel-appinsights` use **Project Managed Identity**.
Foundry and Search local auth stay disabled; public endpoints remain enabled.

Infrastructure and bootstrap implementation details are in [infra/README.md](../infra/README.md).
Release defaults and publication checks are in [administrator prerequisites](admin/prerequisites.md).

## Materials and connection settings

- Lab 4 downloads `assets/skills/travel-estimation.zip`, `assets/skills/preapproval-simulation.zip`
  and `assets/openapi/travel-ops.openapi.json` directly from GitHub.
  Each Skill ZIP contains `SKILL.md` at its root; source text stays in `data/skills/`.
  Only OpenAPI `servers[0].url` changes, using the participant's ARM `travelApiBaseUrl`.
- ARM exposes `resourceOutputs`, `workshopContext`, `travelApiBaseUrl` and `foundryPortalUrl`.
  `workshopContext.setup_status = complete` is available only after initialization succeeds.
- In the container, `notebooks/00-setup.ipynb` uses `scripts/configure_workshop.py` to retrieve that
  successful context from subscription ID and RG name and write `.workshop/context.json`.
  Schema `2.0` keeps the canonical `resource_outputs.<key>.value` structure.
- Dev Container post-create prepares separate Python **3.12** management and **3.13** Hosted venvs
  outside the checkout. It does not sign in or provision Azure. The participant signs in once
  with Azure CLI before running notebooks; GitHub and Portal logins are separate.
- Setup uses **Python (Foundry Workshop)**. Labs 7/8 use **Python (Foundry Hosted Agent)**;
  deploy/delete cells explicitly call the management venv and require confirmation.

Shared Skill ZIPs and the Hosted API's source-code ZIP serve different purposes; both remain in use.
There is no environment-specific workshop archive to download.

## Finish

Save/export results → delete Hosted Agent versions → stop/delete the Codespace →
Azure Portal **Delete resource group** for only the participant's RG → verify deletion.
Deleting deployment history does not delete resources. Follow [Lab 9](../labs/09-observability-cleanup.md).

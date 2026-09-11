[日本語](README.md) | **English**

# Microsoft Foundry Agent Service Hands-on

Build a synthetic Contoso travel and expense agent through ten labs using Azure Portal,
Microsoft Foundry Portal, and Azure Machine Learning Studio. Explore retrieval, tools,
Skills, evaluation, optimization, Agent Framework, Hosted Agents, traces, and cleanup.
The workshop never performs real bookings, approvals, or payments.

[Start with Lab 0](labs/00-overview.md) ·
[Prerequisites](docs/participant/prerequisites.md) ·
[Custom template guide](docs/participant/environments/custom-template.md) ·
[Azure ML guide](docs/participant/environments/azure-ml.md)

## Participant flow

1. In Azure Portal, use **Resource groups > Create** to **manually create exactly one
   dedicated resource group** in Japan East. Wait for creation to finish.
2. **Only then**, open **Deploy a custom template > Build your own template in the editor >
   Load file** and upload the administrator-provided
   [infra/azuredeploy.json](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/azuredeploy.json).
3. **Select the already-created RG**, enter the administrator-verified parameters, and
   choose **Review + create > Create**. Do not use **Create new** in the template form.
4. Bicep / ARM creates the standard resources. Deployment Scripts initializes the two
   Search indexes, evaluation assets, environment validation, live Portal assets, and
   the handoff ZIP. Wait for the entire deployment, including bootstrap, to succeed.
5. In the Azure ML backing Storage account, open **Storage browser > Blob containers >
   workshop-files**, use **Microsoft Entra user account**, and **Download** the private
   `foundry-workshop-files.zip` once to your PC. Extract it locally; never use a public
   blob link, account key, or shared SAS.
6. Complete Labs 2–6 in Microsoft Foundry Portal. Use the extracted `portal-assets/` in Lab 4.
7. **Only when starting Lab 7**, create an Azure ML **Standard_DS3_v2** Compute instance
   with **Idle shutdown** enabled. Upload the extracted top-level folder to
   **Notebooks > User files**. Run `notebooks/00-azureml-setup.ipynb` first with
   **Python 3.10 - SDK v2**, then use **Python (Foundry Hosted Agent)** for Labs 7–8.
8. In Lab 9: **Export → delete Hosted Agent / versions → Compute Stop / Delete →
   Azure Portal Delete resource group → verify deletion**.

The generated bundle path is `.workshop/download/foundry-workshop-files.zip`; its
top-level folder is `Microsoft-Foundry-Agent-Service-Handson`. Configuration stays in
`.workshop/context.json` under `resource_outputs.<key>.value`. Participant provisioning
requires no local CLI.
The ZIP excludes `infra/` and `instructor/`. Links to those files open the public GitHub
`dev-custom-template` branch rather than a missing local file. Administrators must verify
publication before distributing the template; if it is not published yet, obtain the JSON
file from the administrator instead of assuming that the link is available.

## Agenda

| Lab | Topic | Estimate |
|---|---|---:|
| [Lab 0](labs/00-overview.md) | Overview, safety, costs, and data boundaries | 5 min |
| [Lab 1](labs/01-setup.md) | Manual RG, custom template, private ZIP download | Not yet measured |
| [Lab 2](labs/02-prompt-agent.md) | Prompt Agent and Azure AI Search | 20 min |
| [Lab 3](labs/03-rag-foundry-iq.md) | Foundry IQ | 25 min |
| — | Break | 10 min |
| [Lab 4](labs/04-tools-toolbox.md) | Toolbox, OpenAPI, Skills, and Tool Search | 30 min |
| [Lab 5](labs/05-evaluation.md) | Portal evaluation | 15 min |
| [Lab 6](labs/06-optimization.md) | Agent Optimizer | 20 min |
| [Lab 7](labs/07-agent-framework-harness.md) | Azure ML setup and plain / Harness Agents | 50 min |
| [Lab 8](labs/08-hosted-multi-agent.md) | Hosted sequential workflow | 30 min |
| [Lab 9](labs/09-observability-cleanup.md) | Traces and cleanup | 20 min |

Lab 1 timing must be measured through the new real Portal workflow. Previous preparation
timings are not evidence for this path.

## Fixed architecture and prerequisites

- Japan East; Foundry Basic Agent Setup project `contoso-travel`.
- `gpt-5.6-luna` 40K TPM, `gpt-5.5` 100K TPM, and
  `embedding` / `text-embedding-3-small` 40K TPM; Search **Basic** only.
- Public endpoints; Foundry / Search local auth disabled; system identities and scoped RBAC.
- `contoso-travel-search` uses an AAD resource connection.
  `contoso-travel-knowledge-lab-mcp` and `contoso-travel-appinsights` use **Project Managed Identity**.
- Container Apps Travel Ops API, monitoring, Azure ML workspace / Storage / Key Vault.
  No Cosmos DB, Agent capability host, ACR, or private networking.
- A dedicated bootstrap user-assigned identity and temporary Deployment Scripts ACI /
  Azure Files Storage. Supporting resources are cleaned up on success with finite failure
  retention; the identity and scoped grants remain until RG cleanup.

The template creates neither RGs nor Compute instances. The participant needs permission
to create the RG manually and Owner-equivalent permission **inside that RG**, including
role assignments. Runtime identities receive no subscription-wide roles.

Administrators verify Japan East quota, model versions / SKU, the GHCR `@sha256` image,
and the published 40-character `sourceRevision` before the event. Model or regional
capacity is not reserved by that check; failures must stop deployment, not trigger a fallback.
For delegated deployment or redeployment, set `participantObjectIdOverride` to the intended
participant's Entra object ID; otherwise the root deployer's ID is used.
Change `bootstrapRunId` only for an intentional bootstrap retry.

The backing Storage keeps Shared Key compatibility for Azure ML, but the workshop blob
container remains private with OAuth-default browser access. See
[architecture](docs/architecture.md) and [administrator prerequisites](docs/admin/prerequisites.md).

> [!WARNING]
> Azure resources and model operations incur charges. Closing the browser, stopping Compute,
> or deleting deployment history does not delete the deployed resources. Export wanted
> results, delete the dedicated RG, and verify its removal. Never share real data, secrets,
> tokens, or device codes in notebooks, traces, or screenshots.

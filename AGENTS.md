# AGENTS.md

## Project

Japanese Microsoft Foundry Agent Service workshop using Azure Portal custom-template
provisioning and Azure ML execution. Keep current English UI labels.

## Ownership

- Azure Portal: participant manually creates exactly one dedicated workload resource
  group before running the custom template. Select that existing group in the template.
- Bicep/ARM: Foundry account/project, fixed model deployments, Search, monitoring,
  Container Apps API, scoped RBAC/connections, Azure ML workspace and backing resources.
  It creates neither resource groups nor Azure ML Compute instances.
- Deployment Scripts: a dedicated user-assigned identity runs Python setup adapters for
  Search documents, evaluation assets, validation, live Portal assets, and one handoff ZIP.
- Storage browser: participant downloads the ZIP from a private container in the Azure ML
  storage account using Microsoft Entra ID, never a public blob or a shared SAS.
- Foundry Portal: Prompt Agent, Foundry IQ, Toolbox, evaluation, optimizer, traces.
- Azure ML: Labs 7/8 notebooks and Hosted Agent data-plane work.
- Canonical context key: `.workshop/context.json` → `resource_outputs`.

## Provisioning invariants

- Bicep is the source of truth; commit its generated Portal-ready ARM JSON.
- No Terraform or Cloud Shell provisioning, cleanup, or fallback implementation.
- Use administrator-verified model versions and immutable source/image revisions.
  Capacity or policy failures must stop deployment, not silently select another region/model.
- Pass the intended participant object ID into RBAC and validation. The bootstrap
  managed identity is not the participant and must not use signed-in-user Graph lookup.
- Keep bootstrap idempotent, retries bounded, and failures visible in the deployment.
- Only publish a complete, non-secret `foundry-workshop-files.zip` after initialization.
- Temporary Deployment Scripts ACI/Storage use success cleanup and finite failure retention.
  The dedicated bootstrap identity and its scoped grants remain until workload cleanup.
- Preserve Azure ML backing Storage compatibility; OAuth-default blob access is not the
  same as disabling Shared Key required by the workspace's existing datastore setup.

## Azure ML invariants

- Create `Standard_DS3_v2` Compute with idle shutdown only when starting Lab 7.
- Upload the extracted top-level bundle folder to **Notebooks > User files**.
- Run `notebooks/00-azureml-setup.ipynb` first with built-in
  **Python 3.10 - SDK v2** to create two kernels.
- Labs 7/8 use **Python (Foundry Hosted Agent)**.

## Fixed service constraints

- Foundry project `contoso-travel`, Basic Agent Setup.
- `gpt-5.6-luna` 40K TPM; `gpt-5.5` 100K TPM;
  `embedding` / `text-embedding-3-small` 40K TPM.
- Connection `contoso-travel-search` is the AAD Search resource connection.
  `contoso-travel-knowledge-lab-mcp` and `contoso-travel-appinsights` use Project
  Managed Identity.
- Public endpoints, Foundry/Search local auth disabled, system identities, scoped RBAC.
- A dedicated user-assigned identity is used only for deployment bootstrap.
- No Cosmos DB, Agent capability host, ACR, or private networking.

## Safety and cleanup

Use synthetic data only. Never expose credentials, tokens, device codes, or state.
Export notebooks; remove Hosted Agent versions; stop/delete Compute; delete the dedicated
workload resource group in Azure Portal and verify deletion. Deleting a deployment record
does not delete its resources.

Never delete existing user state, caches, or unrelated Azure resources when removing old
implementation files. Keep credential/state exclusions even after retiring the old tools.
Participant docs must never include capacity scheduling schemes.

## Portal E2E

Use Playwright against the actual Azure Portal, Foundry Portal, and Azure ML Studio.
Exercise resource group creation, template deployment, authenticated ZIP download,
representative labs, redeployment, and cleanup through the UI. Do not substitute direct
CLI/REST/SDK calls or simulated fixtures for participant-facing Portal operations.
Keep account-specific parameters and non-secret evidence outside the repository.

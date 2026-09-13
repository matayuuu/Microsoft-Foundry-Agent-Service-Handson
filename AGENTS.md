# AGENTS.md

## Project

Japanese Microsoft Foundry Agent Service workshop using Azure Portal custom-template
provisioning and a shared Codespaces/local Dev Container. Keep current English UI labels.

## Ownership

- Azure Portal: participant manually creates exactly one dedicated workload resource
  group before running the custom template. Select that existing group in the template.
- Bicep/ARM: Foundry account/project, fixed model deployments, Search, monitoring,
  Container Apps API and scoped RBAC/connections. It creates no resource groups,
  Azure ML workspace, or permanent workshop Storage/Key Vault.
- Deployment Scripts: a dedicated user-assigned identity runs Python setup adapters for
  Search documents, evaluation assets and validation, then returns non-secret ARM context.
- GitHub: common Skill ZIPs, OpenAPI template, Notebooks, and Python source.
- Foundry Portal: Prompt Agent, Foundry IQ, Toolbox, evaluation, optimizer, traces.
- Codespaces / local Dev Container: Labs 7/8 notebooks and Hosted Agent data-plane work.
- Canonical context key: `.workshop/context.json` → `resource_outputs`.

## Provisioning invariants

- Bicep is the source of truth; commit its generated Portal-ready ARM JSON.
- Prepopulate all parameters with release defaults; participants select only their
  subscription and existing RG. Keep the self-deployment participant override empty.
- No Terraform or Cloud Shell provisioning, cleanup, or fallback implementation.
- Use administrator-verified model versions and immutable source/image revisions.
  Update Bicep defaults, the parameter example, and documentation together at release.
  Capacity or policy failures must stop deployment, not silently select another region/model.
- Pass the intended participant object ID into RBAC and validation. The bootstrap
  managed identity is not the participant and must not use signed-in-user Graph lookup.
- Keep bootstrap idempotent, retries bounded, and failures visible in the deployment.
- No environment-specific participant ZIP or Blob handoff. Shared Skill ZIPs and
  Hosted source-code archives remain necessary for their respective API formats.
- Only expose completed, non-secret workshop context after initialization succeeds.
- Temporary Deployment Scripts ACI/Storage use success cleanup and finite failure retention.
  The dedicated bootstrap identity and its scoped grants remain until workload cleanup.

## Development environment invariants

- Use the same Dev Container in Codespaces and local VS Code/Docker.
- Keep Python 3.12 management and Python 3.13 Hosted SDK environments separate.
- Store container environments outside the repository; never overwrite host `.venv` folders.
- Post-create prepares dependencies/kernels only; it must not authenticate or provision Azure.
- After personal Azure CLI sign-in, `notebooks/00-setup.ipynb` reads the successful
  deployment using subscription ID and RG name and writes `.workshop/context.json`.
- Labs 7/8 use **Python (Foundry Hosted Agent)**.
- Management actions explicitly use the management interpreter, not the Hosted SDK.
- Common OpenAPI needs only its server URL replaced with the participant's API endpoint.

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
Save notebooks; remove Hosted Agent versions; stop/delete the test Codespace; delete the
dedicated workload RG in Azure Portal and verify deletion. Deleting a deployment record
does not delete its resources. Do not delete unrelated local containers, data, or environments.

Never delete existing user state, caches, or unrelated Azure resources when removing old
implementation files. Keep credential/state exclusions even after retiring the old tools.
Participant docs must never include capacity scheduling schemes.

## Portal E2E

Real E2E uses the actual Azure Portal, Foundry Portal, and Codespaces/VS Code Notebook UI.
Confirm target, costs, and personal authentication before creating test resources.
Exercise RG creation, template deployment, common-material access, representative labs,
redeployment, and cleanup. Do not treat CI or simulated fixtures as live UI evidence.
Keep account-specific parameters and non-secret evidence outside the repository.

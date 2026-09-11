# AGENTS.md

## Project

Japanese Microsoft Foundry Agent Service workshop using a hybrid Cloud Shell
provisioning and Azure ML execution architecture. Keep current English UI labels.

## Ownership

- Azure Portal: participant deletes exactly one workload resource group and later
  creates/deletes the Azure ML Compute instance.
- Azure Cloud Shell Bash: participant creates exactly one workload resource group with
  Azure CLI, then provisions/downloads from a verified persistent `clouddrive`.
- Terraform: Foundry account/project, fixed model deployments, Search, monitoring,
  Container Apps API, scoped RBAC/connections, Azure ML workspace and Storage/Key Vault/
  Application Insights. It does not create Compute.
- Python setup adapters: Search documents, evaluation assets, validation, live Portal
  assets, and the single handoff ZIP.
- Foundry Portal: Prompt Agent, Foundry IQ, Toolbox, evaluation, optimizer, traces.
- Azure ML: Labs 7/8 notebooks and Hosted Agent data-plane work.
- Canonical context key: `.workshop/context.json` → `resource_outputs`.

## Cloud Shell invariants

- On first launch, let the standard Cloud Shell UI create persistent storage, then
  verify the Azure Files-backed `~/clouddrive` mount before Lab 1 timing starts.
- A missing, read-only, or unverifiable `clouddrive` mount is a hard stop. Never provision
  from an ephemeral Cloud Shell session.
- Repository, `.workshop`, and Terraform state remain under `~/clouddrive`. The lightweight
  Python virtual environment is session-local and recreated by `setup-cloud-shell.sh` after
  reconnecting.
- Run `bash scripts/setup-cloud-shell.sh`, then
  `source scripts/activate-cloud-shell.sh`, then `./scripts/setup.sh`.
- Do not install/run Jupyter, Graphviz, Hosted Agent dependencies, web preview, or
  notebooks in Cloud Shell.
- Download exactly `.workshop/download/foundry-workshop-files.zip`, then `exit`.

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
- Public endpoints, local auth disabled, system identities, scoped RBAC.
- No Cosmos DB, Agent capability host, ACR, or private networking.

## Safety and cleanup

Use synthetic data only. Never expose credentials, tokens, device codes, or state.
Export notebooks; stop/delete Compute; reopen the same persistent `clouddrive` repository,
rerun Cloud Shell setup, source activation, run `./scripts/destroy.sh`; verify workload RG
empty; delete it in Azure Portal; `exit`. Cloud Shell storage has a separate lifecycle.

Participant docs must never include capacity scheduling schemes. The Cloud Shell tenant
concurrency limit belongs only in administrator/instructor capacity planning.

# Custom-template architecture

![Workshop architecture](images/workshop-architecture.svg)

Editable source: [workshop-architecture.excalidraw](diagrams/workshop-architecture.excalidraw).
Learning flow: [SVG](images/workshop-learning-flow.svg) /
[editable source](diagrams/workshop-learning-flow.excalidraw).
These are architecture diagrams, not screenshots or proof of a completed deployment.

## Ownership

| Owner | Responsibility |
|---|---|
| Azure Portal / participant | Manually create exactly one dedicated RG first; load the template; select that existing RG; verify deployment; authenticated ZIP download; delete the RG |
| Bicep / generated ARM JSON | Foundry / project / models, Search, monitoring, Container Apps API, connections, scoped RBAC, Azure ML workspace / backing resources |
| Deployment Scripts / bootstrap UAMI | Run Python adapters: two Search indexes, evaluation assets, validation, live Portal assets, ZIP publication |
| Azure ML backing Storage | Private `workshop-files` container holding `foundry-workshop-files.zip` |
| Foundry Portal | Labs 2–6: Prompt Agent, Foundry IQ, Toolbox, evaluation, optimizer; Hosted Agent checks and traces |
| Azure Machine Learning Studio | Create Compute only in Lab 7; upload folder; kernels; Labs 7/8 and Hosted data-plane lifecycle |

`infra/main.bicep` is the source of truth and `infra/azuredeploy.json` is its generated artifact.
The template has resource-group scope: it creates neither RGs nor Compute instances.

## Participant lifecycle

1. **Resource groups > Create**: manually create one dedicated Japan East RG and verify it.
2. **Only after creation**, open **Deploy a custom template > Build your own template in the editor >
   Load file**, upload `infra/azuredeploy.json`, and select the already-created RG.
3. Enter administrator-verified parameters and choose **Review + create > Create**.
4. Wait for deployment and Deployment Scripts initialization / validation to succeed.
5. **Storage browser > Blob containers > workshop-files** with **Microsoft Entra user account**:
   **Download** the private ZIP once and extract it on the PC.
6. Foundry Portal Labs 2–6 use the context and extracted `portal-assets/`.
7. At Lab 7, create **Standard_DS3_v2** with **Idle shutdown**, upload the top-level folder to
   **Notebooks > User files**, and run `notebooks/00-azureml-setup.ipynb` in
   **Python 3.10 - SDK v2**. Labs 7/8 use **Python (Foundry Hosted Agent)**.
8. **Export → Hosted Agent / versions cleanup → Compute Stop / Delete →
   Delete resource group → verify deletion**.

## Handoff boundary

Bootstrap creates `.workshop/download/foundry-workshop-files.zip`, then uploads that one artifact
to the private Blob container. It is not a public URL or a file in temporary script Storage.
The extracted root is exactly `Microsoft-Foundry-Agent-Service-Handson`.

Canonical configuration is `.workshop/context.json`:

- `provisioning_method: azure-custom-template`
- `setup_status: complete` only after successful initialization
- `source_revision`: the actual published, immutable 40-character source SHA
- `participant_object_id`: the intended participant, not the bootstrap identity
- `resource_outputs.<key>.value`: non-secret actual resource values used by all later labs

The ZIP includes context, live `portal-assets/travel-ops.openapi.json`,
`portal-assets/travel-estimation.zip`, `portal-assets/preapproval-simulation.zip`,
`portal-assets/portal-values.json`, notebooks, Hosted source, and required scripts / tests.
It excludes `infra/`, `instructor/`, and administrator / bootstrap / packaging scripts;
links to that source use public GitHub pages rather than paths inside the extracted bundle.
Keep the relative paths and hidden `.workshop` folder intact on Azure ML upload.
`bundle-manifest.json` records the actual source revision and individual file hashes.
The bootstrap output `sha256` identifies the whole ZIP, not the manifest itself. Credentials, tokens, state,
`.env`, authentication caches, private parameter files, and local environments are excluded.

## Resource topology

One dedicated Japan East workload RG contains:

- Foundry resource and Basic Agent Setup project `contoso-travel`
- GlobalStandard deployments: `gpt-5.6-luna` **40K TPM**, `gpt-5.5` **100K TPM**,
  `embedding` / `text-embedding-3-small` **40K TPM**
- Search **Basic**, seeded `contoso-travel-policy` and `contoso-travel-approval` indexes
- Log Analytics and workspace-based Application Insights
- Public Container Apps Travel Ops API with an administrator-verified GHCR `@sha256` image
- Azure ML workspace, Storage, Key Vault, and monitoring association
- System identities for existing services, scoped RBAC, and a dedicated bootstrap UAMI
- Deployment Scripts with temporary ACI / Azure Files Storage support

No Cosmos DB, Agent capability host, ACR, or private networking is added.
The 3 model deployments retain ordered dependencies; bootstrap waits for resources,
connections, and role assignments rather than racing their creation.

## Connections and authentication

`contoso-travel-search` is the AAD Search resource connection.
`contoso-travel-knowledge-lab-mcp` and `contoso-travel-appinsights` use
**Project Managed Identity**. Runtime identities have no subscription-wide roles.
Foundry and Search local auth are disabled; public endpoints remain enabled.

The participant needs permission to manually create the RG, then Owner-equivalent permission
inside it for resource management and role assignments. The root template resolves the deployer's
object ID once. For delegated deployment or redeployment by another actor,
`participantObjectIdOverride` must explicitly name the intended participant's Entra User object ID.

Deployment Scripts uses its dedicated UAMI login, not an interactive user lookup. Its scoped
permissions cover required data operations, resource / RBAC reads, and artifact writes.
Azure ML retains its existing interactive Azure CLI authentication when needed.

The artifact container is private with `allowBlobPublicAccess: false` and
`defaultToOAuthAuthentication: true`. Participants use Microsoft Entra ID through Storage browser,
not account keys, SAS, or anonymous URLs. OAuth default does **not** disable Shared Key:
the AML backing Storage keeps Shared Key compatibility for the workspace datastore.

## Initialization, retries, and cleanup

Bootstrap prepares data and evaluation assets but does not create the learning Agent, knowledge
base, or Toolbox, or run evaluations. It validates participant RBAC, API health, and Search
schema / counts before publishing a complete ZIP. Output contains `status: complete`,
`storage_account_name`, `container_name`, `blob_name`, `sha256`, and `source_revision`.

Retries are bounded and adapters must be idempotent. `bootstrapRunId` is changed only for an
intentional rerun. A deployment is not a transaction: failed runs can leave resources or data.
Do not treat a previously published ZIP as proof that a failed redeployment succeeded.

Deployment Scripts uses **OnSuccess** cleanup and **P1D** retention. Temporary supporting
resources are removed on success; failure diagnostics have a finite retention period.
The bootstrap UAMI and scoped grants persist for retries and are removed with the final RG.
Deleting deployment history is **not** deleting resources. After Hosted and Compute cleanup,
delete the dedicated RG with its remaining resources and verify removal.

## Publication and evidence

Administrators verify model versions / SKU / quota, image digest, and published source before
the event. Capacity is not reserved; failures stop instead of switching region or model.
Manual **Load file** is canonical. Do not advertise an absent artifact or unpublished branch URL.
No Lab 1 timing is claimed until the new actual Portal flow has been measured.
Real Portal E2E requires Playwright UI observations, not simulated fixtures or direct API calls.

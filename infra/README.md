# Azure Portal custom-template infrastructure

`main.bicep` is the source of truth. `azuredeploy.json` is its compiled,
Portal-ready ARM template, not a separately maintained implementation.
Participants need neither a local CLI nor Cloud Shell.

## Deployment boundary

1. In Azure Portal, use **Resource groups > Create** to create one dedicated,
   disposable workload resource group.
2. Open **Deploy a custom template > Build your own template in the editor >
   Load file** and load `azuredeploy.json`.
3. Select the **existing** group and enter administrator-verified parameters.
   Do not use **Create new** in the template screen.
4. Use **Review + create > Create**. Wait for the deployment, including the
   `ds-fdyws-bootstrap-*` Deployment Script, to succeed.
5. Open the Storage account indicated by `participantDownload`, then **Storage
   browser > Microsoft Entra user account > Blob containers > workshop-files**.
   Select `foundry-workshop-files.zip` and **Download**.

The root `targetScope = 'resourceGroup'` reads `resourceGroup()`; it creates
neither a resource group nor a subscription-scoped deployment or role assignment.
Resource names derive only from that group's ID and `japaneast`, not from the
deployment name, source commit, execution time, or run ID. Role assignment GUIDs
are deterministic. This is for a new dedicated group, not an automatic migration
of existing resources or local state.

## Template parameters

`azuredeploy.parameters.example.json` is an **inert example**: replace every
placeholder before using it. It contains no working model versions, image digest,
source revision, or account-specific values.

| Parameter | Requirement |
| --- | --- |
| `location` | Only `japaneast` is accepted; default `japaneast`. The group's metadata location does not override it. |
| `primaryModelVersion` | Required administrator-verified version for `gpt-5.6-luna` / GlobalStandard in Japan East. |
| `evaluationModelVersion` | Required administrator-verified version for `gpt-5.5` / GlobalStandard in Japan East. |
| `embeddingModelVersion` | Required administrator-verified version for `text-embedding-3-small` / GlobalStandard in Japan East. |
| `travelApiImageRef` | Required public `ghcr.io/<owner>/<image>@sha256:<64 lowercase hexadecimal characters>` reference. No tags, private registry secrets, or fallback image. |
| `sourceRevision` | Required published lowercase 40-character commit SHA in `matayuuu/Microsoft-Foundry-Agent-Service-Handson`. No branch names or alternate source repositories. |
| `participantObjectIdOverride` | Default empty: root `deployer().objectId` is the participant. For administrator/automation deployment or redeployment, supply the intended participant's Entra **User** object ID. |
| `bootstrapRunId` | Default `1`. Keep stable for ordinary redeployment; change deliberately to rerun initialization. |

The participant identity is resolved once at the root and passed to every
participant grant and the canonical context. It is not inferred from a UPN, the
script identity, or a Microsoft Graph signed-in-user lookup. Preserve that ID when
someone else redeploys the environment.

Model names, SKUs and capacities are fixed, not fallback parameters:

| Deployment | Model | SKU | Capacity (K TPM) |
| --- | --- | --- | --- |
| `gpt-5.6-luna` | `gpt-5.6-luna` | GlobalStandard | 40 |
| `gpt-5.5` | `gpt-5.5` | GlobalStandard | 100 |
| `embedding` | `text-embedding-3-small` | GlobalStandard | 40 |

Evaluation and optimizer outputs are aliases for the same `gpt-5.5` deployment.
Quota, model availability, policy, and image/source publication are administrator
prerequisites, not promises made by this template. A capacity failure stops the
deployment; it never switches region or model. ARM string parameters have no
regex constraint, so explicit character/length checks with `fail()` reject
non-immutable image and source inputs before they can be consumed.

## Preserved resources and authentication

- Foundry AIServices account and system-assigned project `contoso-travel`, using
  Basic Agent Setup and local authentication disabled. Child writes are ordered
  **project → primary → evaluation → embedding → connections**.
- Dedicated Search **Basic**, one replica/partition, free semantic search,
  system-assigned identity, public endpoint and `disableLocalAuth: true`.
  `authOptions` is deliberately absent; those properties cannot coexist.
- Log Analytics (`PerGB2018`, 30-day retention), workspace-based Application
  Insights with local authentication disabled, and the existing monitoring grants.
- Public Container Apps Travel Ops API: port 8080, HTTPS ingress, 0.25 vCPU /
  0.5 GiB, scale 0–1, anonymous pull of the required public GHCR digest.
  Policy citations use the same immutable `sourceRevision` as bootstrap.
- Azure ML workspace with Storage, Key Vault and the same Application Insights.
  No Compute instance is created; participants create Compute in Lab 7.
  Key Vault retains soft delete with seven-day retention. The optional
  `enablePurgeProtection` property is omitted: the service rejects an explicit
  `false`, and enabling irreversible purge protection is not a deployment workaround.
- No Cosmos DB, capability host, ACR, virtual network or private endpoint.

Azure ML backing Storage deliberately keeps `allowSharedKeyAccess: true` for
its default datastore compatibility. The handoff container is private:
`allowBlobPublicAccess: false`, container `publicAccess: 'None'`, and
`defaultToOAuthAuthentication: true`. OAuth-default Portal access is **not**
the same as disabling Shared Key. ZIP upload and participant download use Entra
ID, never keys, public blobs or shared SAS links.

All eight participant grants and the Foundry project, Search and Azure ML
identity grants are preserved at their resource scopes. Azure ML itself adds
Storage Blob Data Contributor for its workspace identity: redeclaring that grant
races the platform and causes `RoleAssignmentExists`. Only the additional
workspace identity Key Vault Secrets User grant is declared here.

### Connection schema exception

Foundry account/project/deployments and the `CognitiveSearch` / `AAD` connection
use `2026-05-01`. The two existing Project Managed Identity connections retain
their exact `2026-05-15-preview` wire contract:

| Connection | Preserved settings |
| --- | --- |
| `contoso-travel-search` | `CognitiveSearch`, `AAD`, Search resource ID/location metadata. |
| `contoso-travel-knowledge-lab-mcp` | `RemoteTool`, `ProjectManagedIdentity`, `useWorkspaceManagedIdentity: true`, audience `https://search.azure.com`, knowledge-base MCP URL using `2026-08-01-preview`. |
| `contoso-travel-appinsights` | `AppInsights`, `ProjectManagedIdentity`, Application Insights resource ID and internal connection-string routing metadata. |

All connections are project-scoped (`isSharedToAll: false`). The official
[preview reference](https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/2026-05-15-preview/accounts/projects/connections)
still omits the `ProjectManagedIdentity` discriminator and MCP `audience`.
Bicep 0.46.1 reports **BCP036 only at the two `authType` properties**. Exactly
those two warnings are locally suppressed and the complete emitted connection
objects are covered by static contracts. There is no global diagnostic
suppression or `any()` cast. Do not replace this mode with `ManagedIdentity`,
which has a different credentials contract. Confirm these preview operations in
the real Portal E2E before distributing a release.

Application Insights connection-string metadata and the Container Apps
Log Analytics shared-key association are internal resource wiring only.
Neither is copied to bootstrap environment/context, outputs or the ZIP.

## Managed-identity bootstrap

`Microsoft.Resources/deploymentScripts@2023-08-01`, kind `AzureCLI`, embeds the
actual `scripts/bootstrap-custom-template.sh` via `loadTextContent`. It downloads
only the fixed repository at the specified SHA, prepares an isolated Python
environment and runs `scripts/bootstrap_custom_template.py`. Deployment Scripts
performs managed-identity login; the adapters use `AzureCliCredential`.
Source extraction, the virtual environment, and package builds use container-local
`/tmp`, not the Azure Files-backed script directory. Only the service output JSON
and the uploaded private ZIP cross that temporary filesystem boundary.

The pinned Azure CLI version is **2.87.0**, an Azure Linux release published
before the embedded Python 3.14 change in CLI 2.88. It is listed in the
[Microsoft Artifact Registry](https://mcr.microsoft.com/v2/azure-cli/tags/list);
see the [CLI release notes](https://learn.microsoft.com/cli/azure/release-notes-azure-cli).
CI builds an isolated environment in that exact CLI image and imports the
provisioning dependencies without Azure authentication. This is not proof of
current regional Deployment Scripts certification or Portal E2E success.
Before release, verify the actual service accepts the pin and that its runtime
has Python 3.10–3.13, `venv`, `ensurepip`, TLS, and can install the project's
provisioning dependencies. The wrapper fails explicitly if these prerequisites
are unavailable. Do not modify Azure CLI's interpreter or assume the service
supports an arbitrary GHCR bootstrap image. Changes to the shell require
recompiling `azuredeploy.json`. The template normalizes CRLF to LF before Linux
execution; keep the source LF-terminated as well for reproducible source bytes.

The dedicated bootstrap UAMI receives only:

| Scope | Role |
| --- | --- |
| Foundry account | Foundry User (required data operations). |
| Search service | Search Service Contributor and Search Index Data Contributor. |
| Existing workload resource group | Reader for resource validation and ARM role-assignment reads. |
| Private `workshop-files` container | Storage Blob Data Contributor for the handoff artifact. |

It has no Owner, role-assignment write permission, subscription grant, storage
account-wide data grant, or deployment-resource creation role. The **deployment
principal**, not the script identity, must be authorized to create the declared
resources, scoped roles, UAMI association and supporting ACI/Storage resources.
Participants also need RG/resource management read permissions to navigate
Storage browser; data-plane access alone does not provide that Portal access.

The script depends on the required resources, all connections and all role
assignments. Its only template-supplied environment variables are:

- `WORKSHOP_SOURCE_REVISION`: validated source commit.
- `WORKSHOP_CONTEXT_JSON`: serialized non-secret canonical context.
- `WORKSHOP_ARTIFACT_CONTAINER`: `workshop-files`.

The context has `schema_version: "1.0"`,
`provisioning_method: "azure-custom-template"`, `setup_status: "infrastructure-ready"`, subscription,
RG, location, source base/revision, participant ID, and all 30 existing
`resource_outputs.<key>.value` fields. Only successful initialization marks the
ZIP context complete and writes the successful JSON to `AZ_SCRIPTS_OUTPUT_PATH`.
Packaging requires `setup_status: "complete"` and actual generated Portal assets,
not a static-asset fallback. The manifest records `source_revision`, not
`source_branch`. The ZIP's script/test selection keeps runtime scripts,
`scripts/lib`, and Hosted Agent tests; bootstrap, packager, and administrator code
are excluded.

`participantDownload` allowlists that output's `status`, `storage_account_name`,
`container_name`, `blob_name`, `sha256`, and `source_revision`. It never invents a
success value or emits a SAS/connection string. `resourceOutputs` preserves the
canonical mapping; `storagePortalUrl` is a non-secret navigation convenience.

### Retry, supporting resources and cleanup

`forceUpdateTag = guid(sourceRevision, bootstrapRunId)` is stable. Changing the
commit or run ID explicitly reruns bootstrap without renaming workload resources.
Script content changes, or redeployment after the script's retention expires,
can also cause a rerun, so initialization must remain idempotent.

The service auto-creates **separate temporary ACI and Azure Files backing
Storage**. `storageAccountSettings` is intentionally absent: the AML Storage
account is the ZIP destination, not script backing storage. Provider registration
and policy/quota must permit Microsoft.Resources Deployment Scripts,
Microsoft.ManagedIdentity, Microsoft.ContainerInstance and Microsoft.Storage,
including supporting Azure Files/shared-key access.

`timeout: PT1H`, `cleanupPreference: OnSuccess`, and `retentionInterval: P1D`
bound execution and failed-run retention. Supporting resources are cleaned on
success; failures retain diagnostic information for the configured interval.
The UAMI and scoped assignments remain for reruns until the dedicated group is
deleted. Monitor actual cleanup: retained resources remain billable.

A failed deployment is not a transaction rollback: already-created resources or
seeded data can remain. Inspect deployment/script errors, correct the verified
inputs or prerequisite, and redeploy the same group with the same participant
ID; change `bootstrapRunId` when a forced rerun is needed. Never treat a partial
bootstrap or stale ZIP as a successful handoff.

For final cleanup, export work, remove Hosted Agent versions, stop/delete Compute,
then delete the **dedicated resource group** in Azure Portal and verify removal.
Deleting only the deployment record does not delete workload resources.
Do not delete unrelated resources, existing local state or caches.

## Reproduce and validate locally (maintainers only)

From the repository root in PowerShell, using the existing developer environment:

```powershell
az bicep build --file .\infra\main.bicep --outfile .\infra\azuredeploy.json
python -m pytest .\tests\contract\test_custom_template_contract.py -q
```

Pin the Bicep CLI to **v0.46.1 (545b338e2c)**, recorded as **0.46.1.21595** in
the generated ARM metadata. No compiler upgrade is required for this template.
Use the same compiler and source bytes for byte-reproducible output; a compiler
upgrade can change generator metadata and must be reviewed with the artifact.
Static tests parse ARM structure, dependency graphs, immutable-input expressions,
RBAC scopes, connection payloads, embedded shell, outputs and context. They do
not prove Azure runtime availability or substitute for real Portal E2E.

### Official references

- [Deployer identity](https://learn.microsoft.com/azure/azure-resource-manager/bicep/bicep-functions-deployment#deployer)
- [Deployment Scripts API](https://learn.microsoft.com/azure/templates/microsoft.resources/2023-08-01/deploymentscripts)
- [Runtime, identity and cleanup](https://learn.microsoft.com/azure/azure-resource-manager/bicep/deployment-script-develop)
- [Foundry account](https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/2026-05-01/accounts)
- [Search Basic and authentication](https://learn.microsoft.com/azure/templates/microsoft.search/2025-05-01/searchservices)
- [Azure ML workspace](https://learn.microsoft.com/azure/templates/microsoft.machinelearningservices/2025-06-01/workspaces)
- [Portal Blob authorization](https://learn.microsoft.com/azure/storage/blobs/authorize-data-operations-portal)

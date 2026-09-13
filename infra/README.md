# Azure Portal custom-template infrastructure

`main.bicep` is the source of truth. `azuredeploy.json` is its compiled,
Portal-ready ARM template, not a separately maintained implementation.
Portal provisioning does not require a local CLI. Labs 7/8 run in the shared Dev Container.

## Deployment boundary

1. In Azure Portal, use **Resource groups > Create** to create one dedicated,
   disposable workload resource group.
2. Open **Deploy a custom template > Build your own template in the editor >
   Load file** and load `azuredeploy.json`.
3. Select **Subscription** and the **existing** resource group; keep all template
   parameters at their release defaults, including the empty participant ID override.
   Do not use **Create new** in the template screen.
4. Use **Review + create > Create**. Wait for the deployment, including the
   `ds-fdyws-bootstrap-*` Deployment Script, to succeed.
5. Confirm `workshopContext.setup_status = complete`. Use the shared materials in
   GitHub; there is no per-environment download or participant Blob container.

The root `targetScope = 'resourceGroup'` reads `resourceGroup()`; it creates
neither a resource group nor a subscription-scoped deployment or role assignment.
Resource names derive only from that group's ID and `japaneast`, not from the
deployment name, source commit, execution time, or run ID. Role assignment GUIDs
are deterministic. This is for a new dedicated group, not an automatic migration
of existing resources or local state.

## Template parameters

All eight parameters have release defaults in `main.bicep`, compiled into
`azuredeploy.json`. Participants deploying for themselves select only
**Subscription** and the existing **Resource group**. They do not need to look up
model versions, image digests, source SHAs, or their object ID.

`azuredeploy.parameters.example.json` mirrors those defaults without placeholders
or account-specific values. It is an optional administrator reference, not another
file participants must load.

| Parameter | Default / override requirement |
| --- | --- |
| `location` | Only `japaneast` is accepted; default `japaneast`. The group's metadata location does not override it. |
| `primaryModelVersion` | `2026-07-09` for `gpt-5.6-luna` / GlobalStandard in Japan East. |
| `evaluationModelVersion` | `2026-04-24` for `gpt-5.5` / GlobalStandard in Japan East. |
| `embeddingModelVersion` | `1` for `text-embedding-3-small` / GlobalStandard in Japan East. |
| `travelApiImageRef` | `ghcr.io/matayuuu/travel-ops-api@sha256:173f7e954cd284057bf2a2fe10d53efae83547a060ec2ac23172dd5458816dcf`. Overrides must be public GHCR digest references; no tags, private registry secrets, or fallback image. |
| `sourceRevision` | `223a74f219078ededb21a27258501182da7a6432`. Overrides must be published lowercase 40-character commit SHAs in `matayuuu/Microsoft-Foundry-Agent-Service-Handson`, not branch names or alternate repositories. |
| `participantObjectIdOverride` | Default empty: root `deployer().objectId` is the participant. For administrator/automation deployment or redeployment, supply the intended participant's Entra **User** object ID. |
| `bootstrapRunId` | Default `1`. Keep stable for ordinary redeployment; change deliberately to rerun initialization. |

The model defaults are the latest versions available for these three models in
Japan East / GlobalStandard as of **2026-09-12**, pinned as concrete values rather
than dynamically resolving `latest`. The public Travel API image is the digest
published for `v1.0.4`; the source default is the
[published workshop revision](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/commit/223a74f219078ededb21a27258501182da7a6432).

For a new release, administrators verify current model availability / quota and
publish the compatible source and public image first. Update `main.bicep`, the
parameter example, and the documented defaults together, then regenerate the ARM
artifact using the build instructions below. The source SHA must already be
published; it need not be the commit containing the template itself. Do not ask
participants to invent values or change regions / models when deployment fails.

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
- Codespaces and local VS Code use the same Dev Container. This template does not
  create an Azure ML workspace, Compute, or permanent workshop Storage / Key Vault.
- No Cosmos DB, capability host, ACR, virtual network or private endpoint.

The six participant grants and the Foundry project / Search identities retain
their resource-scoped access. Removed execution and distribution resources have
no leftover role assignments. No storage data role is needed by the bootstrap identity.

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
Neither is copied to bootstrap environment/context or participant-facing outputs.

## Managed-identity bootstrap

`Microsoft.Resources/deploymentScripts@2023-08-01`, kind `AzureCLI`, embeds the
actual `scripts/bootstrap-custom-template.sh` via `loadTextContent`. It downloads
only the fixed repository at the specified SHA, prepares an isolated Python
environment and runs `scripts/bootstrap_custom_template.py`. Deployment Scripts
performs managed-identity login; the adapters use `AzureCliCredential`.
Source extraction, the virtual environment, and package builds use container-local
`/tmp`, not the Azure Files-backed script directory. Only the service output JSON
crosses that temporary filesystem boundary.

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

It has no Owner, role-assignment write permission, subscription grant, storage
account-wide data grant, or deployment-resource creation role. The **deployment
principal**, not the script identity, must be authorized to create the declared
resources, scoped roles, UAMI association and supporting ACI/Storage resources.
Participants need RG deployment read access so the initial Notebook can retrieve
their non-secret setup context after personal Azure CLI sign-in.

The script depends on the required resources, all connections and all role
assignments. Its only template-supplied environment variables are:

- `WORKSHOP_SOURCE_REVISION`: validated source commit.
- `WORKSHOP_CONTEXT_JSON`: serialized non-secret canonical context.

The context has `schema_version: "2.0"`,
`provisioning_method: "azure-custom-template"`, `setup_status: "infrastructure-ready"`, subscription,
RG, location, source base/revision, participant ID, and 24
`resource_outputs.<key>.value` fields. Bootstrap seeds the two Search indexes,
prepares the evaluation dataset/rubric, and validates the environment. Only after
all stages pass does it write `status: complete` and `source_revision` to
`AZ_SCRIPTS_OUTPUT_PATH`. It does not build assets, package a participant ZIP, or
read/write Blob Storage.

ARM exposes four non-secret outputs:

| Output | Use |
| --- | --- |
| `workshopContext` | Completed schema 2.0 context, gated by bootstrap success |
| `resourceOutputs` | Canonical resource-name/endpoint mapping |
| `travelApiBaseUrl` | Replace `servers[0].url` in the common OpenAPI JSON |
| `foundryPortalUrl` | Open the workshop project in Foundry |

After `az login --use-device-code` in the Dev Container,
`scripts/configure_workshop.py --subscription <id> --resource-group <name>` reads
the deployment and writes `.workshop/context.json`. It validates deployment state,
scope, schema and endpoints, rejects ambiguous environments, and does not overwrite
a context for another project. `--deployment <name>` is available for explicit selection.
No credentials, SAS links, or participant configuration are published to GitHub.

### Retry, supporting resources and cleanup

`forceUpdateTag = guid(sourceRevision, bootstrapRunId)` is stable. Changing the
commit or run ID explicitly reruns bootstrap without renaming workload resources.
Script content changes, or redeployment after the script's retention expires,
can also cause a rerun, so initialization must remain idempotent.

The service auto-creates **separate temporary ACI and Azure Files backing
Storage**. `storageAccountSettings` is intentionally absent. Provider registration
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
bootstrap as a completed environment.

For final cleanup, save work, remove Hosted Agent versions, stop/delete the Codespace,
then delete the **dedicated resource group** in Azure Portal and verify removal.
Deleting only the deployment record does not delete workload resources.
Do not delete unrelated resources, existing local state or caches.

## Reproduce and validate locally (maintainers only)

From the repository root, using the shared Dev Container:

```bash
az bicep build --file infra/main.bicep --outfile infra/azuredeploy.json
python -m pytest tests/contract/test_custom_template_contract.py -q
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

# Feature support matrix

| Area | Core workshop |
|---|---|
| Workload RG | Participant manually creates one using Azure Portal Resource groups > Create, before opening the template |
| Template entry | Deploy a custom template > Build your own template in the editor > Load file; upload `infra/azuredeploy.json`, select the existing RG |
| Provisioning | Bicep / generated ARM JSON; no RG or Compute creation |
| Initialization | Deployment Scripts using a dedicated UAMI; seed, evaluation assets, validation, live assets, complete ZIP |
| Success gate | Entire deployment succeeds, validation passes, bootstrap `status = complete` |
| Temporary resources | ACI / Azure Files Storage; OnSuccess cleanup and P1D retention; UAMI / grants remain until RG cleanup |
| Handoff | Private `workshop-files/foundry-workshop-files.zip`; Storage browser / Microsoft Entra user account / Download once |
| Generated ZIP path | `.workshop/download/foundry-workshop-files.zip` |
| Bundle root | `Microsoft-Foundry-Agent-Service-Handson` |
| Portal labs | Foundry Portal Labs 2–6 |
| Azure ML | Template-created workspace; participant creates Compute only at Lab 7 |
| Compute | `Standard_DS3_v2`, Idle shutdown, then Stop / Delete before RG deletion |
| Upload | Extracted folder, including `.workshop`, into Notebooks > User files |
| Kernel setup | `notebooks/00-azureml-setup.ipynb` in Python 3.10 - SDK v2; creates two kernels |
| Lab 7/8 kernel | Python (Foundry Hosted Agent); the other kernel is Python (Foundry Workshop) |
| Context | `.workshop/context.json`, canonical `resource_outputs.<key>.value` |
| Region / models | Japan East; `gpt-5.6-luna` 40K TPM, `gpt-5.5` 100K TPM, `embedding` / `text-embedding-3-small` 40K TPM |
| Model / source inputs | Administrator-verified versions / GlobalStandard SKU / quota, GHCR `@sha256`, published 40-character sourceRevision; no fallback |
| Search | Basic only; two seeded indexes |
| Portal assets | Live OpenAPI and Skill ZIPs in `portal-assets/` |
| Connections | `contoso-travel-search` AAD resource connection; `contoso-travel-knowledge-lab-mcp` / `contoso-travel-appinsights` Project Managed Identity |
| Identity | Existing system identities and scoped RBAC; separate bootstrap UAMI; intended participant ID passed to RBAC and validation |
| Network | Public endpoints; Foundry / Search local auth disabled |
| Storage | Private Blob, allowBlobPublicAccess false, OAuth-default browser; Shared Key retained for AML compatibility |
| Cleanup | Export → Hosted Agent / versions → Compute Stop / Delete → Delete resource group → verify deletion |
| Timing / evidence | Lab 1 unmeasured; actual Playwright Portal E2E required, simulated assets are not execution evidence |

Not included: Cosmos DB, Agent capability host, ACR, private networking, model / region fallback,
public or SAS ZIP distribution, production data, real booking / approval / payment, shared credentials.
Deleting deployment history does not delete resources.

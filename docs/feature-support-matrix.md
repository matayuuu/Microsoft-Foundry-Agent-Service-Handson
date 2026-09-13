# Feature support matrix

| Area | Core workshop |
|---|---|
| Workload RG | Participant manually creates one in Azure Portal before opening the template |
| Template | Load `infra/azuredeploy.json`; select only Subscription / existing RG; keep verified release defaults |
| Initialization | Deployment Scripts seeds Search, prepares evaluation data / rubric and validates |
| Success | Entire deployment succeeds; `workshopContext.setup_status = complete` |
| Common materials | GitHub `assets/skills/*.zip`, `assets/openapi/travel-ops.openapi.json`; change only `servers[0].url` to `travelApiBaseUrl` |
| Portal labs | Foundry Portal Labs 2–6 |
| Notebook environment | GitHub Codespaces by default; the same Dev Container in local VS Code / Docker |
| Dependencies | Post-create prepares separate venvs outside the checkout; no Azure login or provisioning |
| Setup kernel | Python (Foundry Workshop), Python 3.12, `foundry-workshop` |
| Labs 7/8 kernel | Python (Foundry Hosted Agent), Python 3.13, `foundry-hosted-agent` |
| Authentication | Personal Azure CLI sign-in in the container before notebooks; separate from GitHub / Portal |
| Context | `00-setup.ipynb`: subscription ID + RG name → successful ARM output → `.workshop/context.json`, schema `2.0`, `resource_outputs.<key>.value` |
| Hosted lifecycle | Source-code remote build; confirmed deploy/delete through the management venv |
| Region / models | Japan East / GlobalStandard; `gpt-5.6-luna` 40K TPM, `gpt-5.5` 100K TPM, `embedding` / `text-embedding-3-small` 40K TPM |
| Search | Basic; two seeded indexes |
| Connections | `contoso-travel-search` AAD resource connection; `contoso-travel-knowledge-lab-mcp` / `contoso-travel-appinsights` Project Managed Identity |
| Identity / network | System identities, separate bootstrap identity, scoped RBAC; public endpoints; Foundry / Search local auth disabled |
| Monitoring / API | Log Analytics / Application Insights; Container Apps Travel Ops API |
| Cleanup | Save/export → Hosted versions → Codespace Stop / Delete → Portal Delete resource group → verify deletion |

No environment-specific archive distribution, Cosmos DB, Agent capability host, ACR or private networking
is part of the core flow. No region/model fallback or real booking, approval or payment is performed.
Details: [architecture](architecture.md), [administrator prerequisites](admin/prerequisites.md),
[cleanup](costs-and-cleanup.md).

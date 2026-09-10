# Feature support matrix

| Area | Core workshop |
|---|---|
| Workload RG | participant creates/deletes one via Azure Portal |
| Provisioning | Terraform from Azure Cloud Shell Bash |
| Cloud Shell | first-run Storage auto-creation; verified persistent HOME; provisioning/download/destroy only |
| Handoff | one `.workshop/download/foundry-workshop-files.zip` |
| Portal labs | Foundry Portal Labs 2–6 |
| Azure ML | Terraform-created workspace; participant-created Compute for Labs 7/8 |
| Compute | `Standard_DS3_v2`, Idle shutdown, Stop/Delete before destroy |
| Kernel setup | `00-azureml-setup.ipynb` in Python 3.10 - SDK v2 |
| Lab 7/8 kernel | Python (Foundry Hosted Agent) |
| Context | canonical `resource_outputs` |
| Models | Luna 40K, GPT-5.5 100K, embedding 40K |
| Search | Basic; two seeded indexes |
| Portal assets | generated live OpenAPI + static Skills inside downloaded `portal-assets` |
| Connections | Search/AAD resource connection; Foundry IQ MCP and App Insights via Project Managed Identity |
| Identity | Azure CLI, managed identities, scoped RBAC |
| Network | public endpoints; local auth disabled |
| Cleanup | data plane → Compute → Terraform → workload RG |

Not included: Notebook/Jupyter in Cloud Shell、private networking、Cosmos DB、Agent capability host、
ACR、production data、real booking/approval/payment、shared secrets。

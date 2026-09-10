[日本語](README.md) | **English**

# Microsoft Foundry Agent Service Hands-on

This ten-lab workshop uses a hybrid participant path:

1. Create one dedicated workload resource group in Azure Portal.
2. Open Azure Cloud Shell Bash, let its standard first-run UI create persistent
   storage, verify the Azure Files-backed HOME, and use it only for provisioning
   and one download.
3. Terraform creates Foundry, models, Search, monitoring, the Container Apps API,
   scoped RBAC/connections, and an Azure ML workspace with backing resources.
4. Download `.workshop/download/foundry-workshop-files.zip` once and immediately
   run `exit`.
5. Complete Labs 2–6 in Microsoft Foundry Portal.
6. For Labs 7–8, create an Azure ML `Standard_DS3_v2` Compute instance with idle
   shutdown, upload the extracted folder, and run `notebooks/00-azureml-setup.ipynb`.
7. Export wanted notebooks, stop/delete compute, reopen the same persistent Cloud
   Shell repository and state, destroy resources, delete the workload resource group,
   and verify removal.

[Start with Lab 0](labs/00-overview.md) ·
[Prerequisites](docs/participant/prerequisites.md) ·
[Cloud Shell guide](docs/participant/environments/cloud-shell.md) ·
[Azure ML guide](docs/participant/environments/azure-ml.md)

> [!NOTE]
> The previous Codespaces / Cloud Shell implementation remains at the
> [`codespaces-cloud-shell-v1`](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/tree/codespaces-cloud-shell-v1)
> tag. Do not mix it with the current workflow.

Cloud Shell is never used for notebooks, Jupyter, Graphviz, web preview, or the Hosted
Agent environment. Lab 1 targets 10–15 minutes; 8–10 minutes is only a prepared warm
best case. The documented first-run storage creation and mount check happen before
that timing starts.

All workshop data is synthetic. Azure resources and model operations incur charges.
Never enter real customer/employee data, secrets, or device codes. Closing the browser
does not delete resources.

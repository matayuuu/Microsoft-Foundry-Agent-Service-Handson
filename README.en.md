[日本語](README.md) | **English**

# Microsoft Foundry Agent Service Hands-on

Build a synthetic Contoso travel and expense assistant in ten labs.
Explore retrieval, tools, evaluation, optimization, and Hosted Agents.

[**Start with Lab 0**](labs/00-overview.md) ·
[Prerequisites](docs/participant/prerequisites.md) ·
[Setup guide](docs/participant/environments/custom-template.md)

## Workshop flow

1. **Lab 1**: In Azure Portal, **manually create exactly one dedicated RG first**,
   then deploy the administrator-provided template into that existing RG.
   Wait for initialization to succeed, then download and extract the private workshop ZIP
   using **Microsoft Entra user account**.
2. **Labs 2–6**: Build the agent in Microsoft Foundry Portal.
3. **Labs 7–8**: Follow the [Azure ML guide](docs/participant/environments/azure-ml.md)
   and run the notebooks. Create Compute **only when starting Lab 7**.
4. **Lab 9**: Export your results, delete Hosted Agents, stop/delete Compute,
   then delete your dedicated RG and verify its removal.

## Agenda

| Lab | Topic | Estimate |
|---|---|---:|
| [Lab 0](labs/00-overview.md) | Overview and safety | 5 min |
| [Lab 1](labs/01-setup.md) | Create the environment and download workshop files | Not yet measured |
| [Lab 2](labs/02-prompt-agent.md) | Prompt Agent and Azure AI Search | 20 min |
| [Lab 3](labs/03-rag-foundry-iq.md) | Foundry IQ | 25 min |
| — | Break | 10 min |
| [Lab 4](labs/04-tools-toolbox.md) | Toolbox, OpenAPI, Skills, and Tool Search | 30 min |
| [Lab 5](labs/05-evaluation.md) | Agent evaluation | 15 min |
| [Lab 6](labs/06-optimization.md) | Agent Optimizer | 20 min |
| [Lab 7](labs/07-agent-framework-harness.md) | Azure ML setup, Agent Framework, and Harness Agents | 50 min |
| [Lab 8](labs/08-hosted-multi-agent.md) | Hosted Agent workflow | 30 min |
| [Lab 9](labs/09-observability-cleanup.md) | Traces and cleanup | 20 min |

[Administrator checklist and models](docs/admin/prerequisites.md) ·
[Architecture](docs/architecture.md) ·
[Troubleshooting](docs/participant/troubleshooting.md)

> [!IMPORTANT]
> Use synthetic data only and never share credentials. Azure usage incurs charges.
> Follow Lab 9 to delete **only your dedicated RG** and verify that deletion completed.

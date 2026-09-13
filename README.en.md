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
   Select **only Subscription and Resource group**, keep the other defaults, and wait for
   data preparation and validation to succeed.
2. **Labs 2–6**: Build the agent in Microsoft Foundry Portal.
   Download the shared Skill ZIPs and OpenAPI for Lab 4 directly from GitHub.
3. **Labs 7–8**: Use [GitHub Codespaces](docs/participant/environments/codespaces.md),
   sign in to Azure in the container, and enter your subscription ID and RG name in the setup notebook.
   The [local Dev Container](docs/participant/environments/local-dev-container.md) uses the same steps.
4. **Lab 9**: Save/export your results, delete Hosted Agents, stop/delete your Codespace,
   then delete only your dedicated RG and verify its removal.

The repository already contains the notebooks and Python source; no manual folder upload is needed.
The browser-based Codespaces route requires no local Docker or Python installation.

## Agenda

| Lab | Topic | Estimate |
|---|---|---:|
| [Lab 0](labs/00-overview.md) | Overview and safety | 5 min |
| [Lab 1](labs/01-setup.md) | Create the environment and verify initialization | — |
| [Lab 2](labs/02-prompt-agent.md) | Prompt Agent and Azure AI Search | 20 min |
| [Lab 3](labs/03-rag-foundry-iq.md) | Foundry IQ | 25 min |
| — | Break | 10 min |
| [Lab 4](labs/04-tools-toolbox.md) | Toolbox, OpenAPI, Skills, and Tool Search | 30 min |
| [Lab 5](labs/05-evaluation.md) | Agent evaluation | 15 min |
| [Lab 6](labs/06-optimization.md) | Agent Optimizer | 20 min |
| [Lab 7](labs/07-agent-framework-harness.md) | Codespaces setup, Agent Framework, and Harness Agents | 50 min |
| [Lab 8](labs/08-hosted-multi-agent.md) | Hosted Agent workflow | 30 min |
| [Lab 9](labs/09-observability-cleanup.md) | Traces and cleanup | 20 min |

[Administrator checklist and models](docs/admin/prerequisites.md) ·
[Architecture](docs/architecture.md) ·
[Troubleshooting](docs/participant/troubleshooting.md)

> [!IMPORTANT]
> Use synthetic data only; never share or save credentials or tokens.
> Azure and Codespaces usage may incur charges.
> Follow Lab 9 to delete **only your dedicated RG** and verify that deletion completed.

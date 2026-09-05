[日本語](README.md) | **English**

# Microsoft Foundry Agent Service Hands-on

This workshop builds a synthetic Contoso travel and expense assistant with Prompt Agents,
Foundry IQ, Toolbox and Skills, evaluation, optimization, Hosted Agents, and observability.
The step-by-step labs are written in Japanese.

![Workshop architecture](docs/images/workshop-architecture.svg)

## Prerequisites

- A GitHub account with Codespaces access
- An Azure account that can run `az login`
- An existing resource group assigned by the workshop administrator
- **Owner** on that resource group

See [participant prerequisites](docs/participant/prerequisites.md) for the checklist.

## Start

**Begin with [Lab 0 — Overview](labs/00-overview.md).**

## Agenda

| Lab | Topic | Estimated time |
|---|---|---:|
| [Lab 0](labs/00-overview.md) | Overview and workshop flow | 5 min |
| [Lab 1](labs/01-setup.md) | Codespaces and Terraform setup | 20 min |
| [Lab 2](labs/02-prompt-agent.md) | Create a Prompt Agent | 10 min |
| [Lab 3](labs/03-rag-foundry-iq.md) | Azure AI Search and Foundry IQ | 35 min |
| — | Break | 10 min |
| [Lab 4](labs/04-tools-toolbox.md) | Create Toolbox and Skills in the Portal | 30 min |
| [Lab 5](labs/05-evaluation.md) | Portal agent evaluation | 15 min |
| [Lab 6](labs/06-optimization.md) | Agent Optimizer | 20 min |
| [Lab 7](labs/07-hosted-multi-agent.md) | Agent Framework Hosted Agent | 40 min |
| [Lab 8](labs/08-observability-cleanup.md) | Observability and cleanup | 10 min |

> [!WARNING]
> Azure resources continue to incur charges until removed. Complete the cleanup in
> [Lab 8](labs/08-observability-cleanup.md).

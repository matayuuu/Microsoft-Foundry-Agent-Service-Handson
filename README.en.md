[日本語](README.md) | **English**

# Microsoft Foundry Agent Service Hands-on

“What is the hotel allowance for a trip to Osaka?” “Can you calculate the travel costs?”
Build an AI assistant for these requests from employees of the fictional company Contoso.
Start with conversation, add policy retrieval and API calculations, then evaluate and improve
the answers. No prior AI agent development experience is required.

The step-by-step labs use **Japanese explanations and the English UI of Foundry (new)
in dark mode**.

![Learning flow: Labs 0–1 prepare the environment, Labs 2–6 extend one Prompt Agent, Lab 7 explores an independent three-agent simulation, and Lab 8 inspects execution history and cleans up](docs/images/workshop-learning-flow.svg)

[Editable learning-flow diagram](docs/diagrams/workshop-learning-flow.excalidraw)

The left-hand path extends **one Prompt Agent in Labs 2–6**. The right-hand path is
**a separate implementation in Lab 7**, not an integrated final application. Lab 7 does not
connect to the earlier Foundry IQ, Toolbox, or Travel Ops API. All data is synthetic;
the workshop does not make real bookings, approvals, or reimbursements.

## What you will learn

| Concept | Meaning and observable outcome |
|---|---|
| **Agent / Prompt Agent** | An AI assistant that follows instructions and can use connected capabilities. A Prompt Agent is configured through written instructions. Save its role and response guidelines |
| **Knowledge / Foundry IQ** | Knowledge is the reference material behind an answer. Foundry IQ retrieves information across sources. Search travel policies, then inspect citations |
| **Tool / Skill / Toolbox** | A Tool performs an operation, a Skill describes how to use it, and a Toolbox packages both for an Agent. Obtain cost breakdowns from the Travel Ops API, a programmatic interface for calculations |
| **Evaluation / Optimizer** | Evaluation checks answers against a shared question set and criteria. Optimizer tests alternative instructions. Read scores and reasons before deciding whether to adopt a candidate |
| **Hosted Agent** | Your own code running in Foundry. In Lab 7, build an independent simulation that passes a request through policy, planning, and review agents |

For example, Lab 3 checks that an answer about Osaka lodging cites the synthetic policy's
JPY 15,000-per-night limit. Lab 4 checks the cost breakdown and total returned by the API.
These are examples of what to verify, not fixed wording that the model must reproduce.

## Where you work

- **GitHub Codespaces in your browser:** open files in browser-based VS Code.
  Its **Terminal** runs commands. A **Notebook** combines explanations with small executable
  Python cells; the required Notebook exercise is in Lab 7.
- **Microsoft Foundry Portal in another browser tab:** configure Agents, chat, evaluate,
  optimize, and inspect execution history using **English UI and dark mode**.
- **Your local PC:** use the browser and save files needed for Portal uploads.
  Run workshop commands in the **Codespace Terminal**, not your PC's PowerShell or terminal.

The workshop uses **three model deployments** (named model instances you can call):
Prompt / Hosted Agents share **Luna (`gpt-5.6-luna`)**;
Foundry IQ query planning, configurable evaluation judges, and Optimizer share **`gpt-5.5`**;
**`text-embedding-3-small`**, deployed as `embedding`, converts text into numbers for search.
[Lab 0](labs/00-overview.md) explains the names used in the Portal and generated configuration.

## Prerequisites

- A GitHub account with Codespaces access
- An Azure account that can run `az login`
- An existing resource group assigned by the workshop administrator
- **Owner** on that resource group

See [participant prerequisites](docs/participant/prerequisites.md) for the checklist.

## Start

**Begin with [Lab 0 — Overview](labs/00-overview.md).**
Then prepare your Codespace with the [participant prerequisites](docs/participant/prerequisites.md).
Lab 1 provides the Azure setup commands. Check each lab's completion conditions before
following its next-lab link.

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

## Azure architecture

This is the service layout prepared in Lab 1, not the learning sequence.
You do not need to memorize every service before starting.

![Microsoft Foundry, Azure AI Search, and Travel Ops API resources inside an existing resource group](docs/images/workshop-architecture.svg)

[Editable architecture diagram](docs/diagrams/workshop-architecture.excalidraw)

## Help

- [Participant troubleshooting](docs/participant/troubleshooting.md)
- [Administrator prerequisites](docs/admin/prerequisites.md)
- [Optional labs](labs/optional/README.md)

> [!WARNING]
> Model calls, evaluation, optimization, Azure resources, and Codespaces can incur charges.
> Closing your browser does not remove Azure resources. Complete the cleanup in
> [Lab 8](labs/08-observability-cleanup.md), then stop your Codespace.

[日本語](README.md) | **English**

![Build agents. Go beyond prompts. — 10 Microsoft Foundry labs, about 4 hours including a break. From Portal to Python and a Hosted workflow](docs/images/workshop-cover.svg)

# Microsoft Foundry Agent Service Hands-on

**Start with conversation. Add evidence, tools, and an orchestrated workflow.**

“What is the hotel allowance for a trip to Osaka?” “Can you calculate the travel costs?”
Build an AI assistant for these requests from employees of the fictional company Contoso.
Start with conversation, add policy retrieval and API calculations, then evaluate and improve
the answers. No prior AI agent development experience is required.

The step-by-step labs use **Japanese explanations and the English UI of Foundry (new)
in dark mode**.

[**Start the workshop →**](labs/00-overview.md) · [Prerequisites](docs/participant/prerequisites.md) · [Agenda](#agenda) · [Help](#help)

## Learning path

**Grow one Prompt Agent, then bring its resources into code.**
Labs 0–1 prepare the environment. Labs 2–6 work mainly in the Portal; Labs 7–8 use Python
Notebooks. Lab 9 compares traces and cleans up.

![Learning flow: Labs 0–1 prepare the environment, Labs 2–6 extend one Prompt Agent, Lab 7 reuses its Foundry IQ, Toolbox, and Skills in a plain Agent and then a Harness Agent, Lab 8 deploys that Harness factory in a sequential workflow, and Lab 9 compares traces and cleans up](docs/images/workshop-learning-flow.svg)

[Full-size diagram (SVG)](docs/images/workshop-learning-flow.svg) · [Editable source (Excalidraw)](docs/diagrams/workshop-learning-flow.excalidraw)

<details>
<summary>Implementation notes for Labs 7–8</summary>

Lab 7 reuses Foundry IQ, Toolbox, and Skills, progressing from a plain Agent to a Harness
Agent. Lab 8 places the same checked-in factory between intake and review participants and
deploys the sequential workflow. Lab 8 does not depend on Lab 7 session state.

</details>

All content uses **synthetic data**. The workshop does not make real bookings, approvals,
or reimbursements.

## What you will learn

| Concept | Meaning and observable outcome |
|---|---|
| **Agent / Prompt Agent** | An AI assistant that follows instructions and can use connected capabilities. A Prompt Agent is configured through written instructions. Save its role and response guidelines |
| **Knowledge / Foundry IQ** | Knowledge is the reference material behind an answer. Foundry IQ retrieves information across sources. Search travel policies, then inspect citations |
| **Tool / Skill / Toolbox / Tool Search** | Tools provide API, calculation, and web-search capabilities; Skills explain how to use them; a Toolbox packages both. Tool Search discovers the needed capability dynamically before Travel Ops or another tool runs |
| **Evaluation / Optimizer** | Evaluation checks answers against a shared question set and criteria. Optimizer tests alternative instructions. Read scores and reasons before deciding whether to adopt a candidate |
| **Agent Framework / Harness Agent / Hosted Agent** | Lab 7 reuses Foundry IQ and Toolbox Tools/Skills in code and adds planning, todos, and memory with a Harness Agent. Lab 8 deploys the same factory as the specialist in a sequential Hosted workflow |

For example, Lab 3 checks that an answer about Osaka lodging cites the synthetic policy's
JPY 15,000-per-night limit. Lab 4 checks the cost breakdown and total returned by the API.
These are examples of what to verify, not fixed wording that the model must reproduce.

## Where you work

- **GitHub Codespaces in your browser:** open files in browser-based VS Code.
  Its **Terminal** runs commands. A **Notebook** combines explanations with small executable
  Python cells; the required Notebook exercises are in Labs 7 and 8.
- **Microsoft Foundry Portal in another browser tab:** configure Agents, chat, evaluate,
  optimize, and inspect execution history using **English UI and dark mode**.
- **Your local PC:** use the browser and save files needed for Portal uploads.
  Run workshop commands in the **Codespace Terminal**, not your PC's PowerShell or terminal.

The workshop uses **three model deployments** (named model instances you can call):
**Luna (`gpt-5.6-luna`)** is shared by Prompt/Hosted Agents and Foundry IQ and is
the only model this workshop permits for either Optimizer role;
**Sol (`gpt-5.6-sol`)** is used only by the configurable evaluation judges in Lab 5;
**`text-embedding-3-small`**, deployed as `embedding`, converts text into numbers for search.
If Sol quota is unavailable, its deployment and Lab 5 can be skipped. As of 2026-09-09,
Agent Optimizer does not accept Luna as an optimization model, so Lab 6 uses a compatibility
gate and is skipped without adding another model.
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

**10 labs · About 4 hours (including a 10-minute break)**

| Lab | Topic | Estimated time |
|---|---|---:|
| [Lab 0](labs/00-overview.md) | Overview and workshop flow | 5 min |
| [Lab 1](labs/01-setup.md) | Codespaces and Terraform setup | 20 min |
| [Lab 2](labs/02-prompt-agent.md) | Prompt Agent and Azure AI Search | 20 min |
| [Lab 3](labs/03-rag-foundry-iq.md) | Foundry IQ | 25 min |
| — | Break | 10 min |
| [Lab 4](labs/04-tools-toolbox.md) | Toolbox with multiple tools, Skills, and Tool Search | 30 min |
| [Lab 5](labs/05-evaluation.md) | Portal agent evaluation | 15 min |
| [Lab 6](labs/06-optimization.md) | Agent Optimizer | 20 min |
| [Lab 7](labs/07-agent-framework-harness.md) | Agent Framework Agent and Harness Agent | 45 min |
| [Lab 8](labs/08-hosted-multi-agent.md) | Hosted workflow with the Harness Agent | 40 min |
| [Lab 9](labs/09-observability-cleanup.md) | Trace comparison and cleanup | 10 min |

## Azure architecture

This diagram shows the services, agents, and call paths in the architecture completed
through Lab 8, rather than the learning sequence.
You do not need to memorize every service before starting.

![Microsoft Foundry, shared Foundry IQ and Toolbox resources, Travel Ops API, and monitoring inside an existing resource group](docs/images/workshop-architecture.drawio.svg)

[Edit the architecture in draw.io](docs/diagrams/workshop-architecture.drawio) ·
[Open the SVG](docs/images/workshop-architecture.drawio.svg)

## Help

- [Participant troubleshooting](docs/participant/troubleshooting.md)
- [Administrator prerequisites](docs/admin/prerequisites.md)
- [Optional labs](labs/optional/README.md)

> [!WARNING]
> Model calls, evaluation, optimization, Azure resources, and Codespaces can incur charges.
> Closing your browser does not remove Azure resources. Complete the cleanup in
> [Lab 9](labs/09-observability-cleanup.md), then stop your Codespace.

# Feature support matrix

This matrix targets Microsoft Foundry **new** as of 2026-09-01. Preview surfaces and
portal labels can change; use the linked official documentation as the source of truth.

| Capability | Portal | Toolkit | Python SDK/REST | Status and workshop treatment |
|---|---:|---:|---:|---|
| Create/version/test Prompt Agent | Yes | Yes | Yes | Core, portal-first |
| Attach Azure AI Search to Agent | Yes | Yes | Yes | Core; index and connection are prebuilt |
| Create Foundry IQ Knowledge Base | Yes | N/A | Yes | Core; portal agentic retrieval remains preview |
| Create Toolbox | No | Yes | Yes | Core; Python Notebook uses the SDK |
| Full Toolbox version lifecycle | No | Partial | Yes | Notebook reuses the default version when unchanged |
| Web Search | Agent config | Yes | Yes | Outside the core workshop |
| Code Interpreter | Agent config | Yes | Yes | Outside the core workshop |
| OpenAPI in Toolbox | No | No | Yes | Core; Notebook uses a validated OpenAPI 3.1 definition |
| Tool Search | No | Yes | Yes | Preview; outside the core workshop |
| Submit agent evaluation | Yes | N/A | Yes | Core uses Portal with a prepared synthetic dataset |
| View evaluation results | Yes | Yes | Yes | Core, portal |
| Prompt Agent Optimizer | Yes | N/A | Service-managed | Preview; portal wizard |
| Hosted Agent Optimizer | No | Yes | azd/SDK integration | Optional |
| Agent Framework Hosted Agent authoring | No | Yes | Code | Core, Codespaces |
| Hosted Agent source deployment | No | Yes | Yes | Core uses SDK to keep `az login` as sole auth |
| Hosted Agent Playground | Yes | Yes | Yes | Core, portal after version is active |
| Prompt/Hosted traces | Yes | Yes | OpenTelemetry | Core; Application Insights is preconnected |
| Workflow Designer | Yes | N/A | N/A | Retires 2026-12-01; comparison only |
| Fabric IQ | Agent config | Yes | Yes | Optional; license/capacity/permissions required |
| Work IQ | Agent config | Yes | Yes | Optional; Copilot Credits/admin consent required |

## Core prerequisites

| Area | Requirement |
|---|---|
| Region | East US 2; Sweden Central is the first documented fallback |
| Prompt/evaluation model | `gpt-4.1` deployment |
| Foundry IQ query planning / Optimizer | Supported `gpt-5` family deployment |
| Embeddings | `text-embedding-3-small` deployment |
| Search | Azure AI Search Basic or higher |
| Identity | Participant is Owner on the existing RG; Foundry roles are assigned in that RG |
| Observability | Workspace-based Application Insights connected to the project |
| Development | Python 3.13 Codespace and Azure CLI authentication |

## Important status notes

- Foundry Tool Catalog and Toolboxes are generally available, but individual tools can
  be preview.
- The Microsoft Foundry and Azure portal paths for agentic retrieval provide preview
  access even where newer Search REST API operations are generally available.
- Agent Optimizer is preview and uses both an evaluation model and a supported
  optimization model. Its portal wizard currently accepts custom evaluators.
- Hosted Agents and source-code remote build are the supported path for custom Agent
  Framework orchestration.
- Foundry Workflow Designer is retiring on 2026-12-01. New orchestration work should
  use Microsoft Agent Framework.

## Official references

- [Types of tools in Foundry Agent Service](https://learn.microsoft.com/azure/foundry/agents/concepts/tool-catalog)
- [Create and manage a toolbox](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox)
- [What is Foundry IQ?](https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq)
- [Agentic retrieval overview](https://learn.microsoft.com/azure/search/agentic-retrieval-overview)
- [Evaluate your AI agents](https://learn.microsoft.com/azure/foundry/observability/how-to/evaluate-agent)
- [Agent Optimizer overview](https://learn.microsoft.com/azure/foundry/agents/concepts/agent-optimizer-overview)
- [Hosted agents](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents)
- [Build a workflow in Foundry](https://learn.microsoft.com/azure/foundry/agents/concepts/workflow)
- [Fabric IQ tool](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq)
- [Work IQ tool](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/work-iq)

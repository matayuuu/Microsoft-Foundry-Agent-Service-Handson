# Feature support matrix

This matrix targets Microsoft Foundry **new**. Toolbox UI entries were updated from
participant-supplied Portal screenshots on **2026-09-05**; other entries retain the
2026-09-01 baseline. Preview surfaces and portal labels can change. The official
toolbox article currently documents SDK/Toolkit flows more fully than the observed
web Portal; do not interpret a missing Portal column as proof that the UI is unavailable.

| Capability | Portal | Toolkit | Python SDK/REST | Status and workshop treatment |
|---|---:|---:|---:|---|
| Create/version/test Prompt Agent | Yes | Yes | Yes | Core, portal-first |
| Attach Azure AI Search to Agent | Yes | Yes | Yes | Core; index and connection are prebuilt |
| Create Foundry IQ Knowledge Base | Yes | N/A | Yes | Core; portal agentic retrieval remains preview |
| Create Toolbox | Yes, observed | Yes | Yes | Core; web Portal Build > Tools > Create toolbox |
| Full Toolbox version lifecycle | Publish observed; other controls vary | Partial | Yes | SDK fallback preserves existing Skills, tools, metadata and guardrails |
| Web Search | Agent config | Yes | Yes | Outside the core workshop |
| Code Interpreter | Agent config | Yes | Yes | Outside the core workshop |
| OpenAPI in Toolbox | Yes, observed | UI advertised; Learn table differs | Yes | Core; Add tool > Custom > OpenAPI tool; paste live OpenAPI 3.1 |
| Create/upload and attach Skills | Yes, observed | Documented in Skills article | Yes | Core; Add skill > Upload skill, then include both workshop Skills |
| Consume Toolbox Skills | Client-dependent | Client-dependent | MCP Resources / Skill provider | Preview; registration is not proof of runtime loading |
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
| Prompt/Hosted Agent | Shared `gpt-5.6-luna` deployment; `primary_model_deployment_name` |
| Foundry IQ query planning / configurable LLM judges / Agent Optimizer | Shared `gpt-5.5` deployment; `optimizer_model_deployment_name` |
| Embeddings | `text-embedding-3-small`, deployment `embedding` |
| Search | Azure AI Search Basic or higher |
| Identity | Participant is Owner on the existing RG; Foundry roles are assigned in that RG |
| Observability | Workspace-based Application Insights connected to the project |
| Development | Python 3.13 Codespace and Azure CLI authentication |

## Important status notes

- Model roles were checked in the new Portal on **2026-09-06**. The core creates exactly three
  deployments; chat versions and same-SKU quota evidence are discovered by preflight,
  not pinned or inferred from model names. The knowledge-base Chat completions model
  picker offered the deployed GPT-5.5, not Luna, even with Medium retrieval effort.
  The Agent picker offered Luna and agent inference succeeded. These are observations
  of the checked Portal, not a universal claim about every Search API's model support.
- GPT-5.5 is used for Foundry IQ query planning, the rubric/configurable LLM judges, and both Optimizer model
  selections. Service-managed evaluators such as Violence keep their own model.
- Foundry Tool Catalog and Toolboxes are generally available, but individual tools can
  be preview.
- Skills and Toolbox skill discovery are preview. Skill references are separate from
  `tools[]` and require compatible MCP Resources consumption. The Lab 7 Python workflow
  does not currently include a Skill provider; do not claim that adding a Toolbox to
  a Prompt Agent alone proves Skills were loaded.
- Lab 4 records the observed web Portal paths with screenshots. Local preparation only
  exports the live OpenAPI definition and Skill ZIPs; it does not create remote objects.
- Toolkit release notes announce OpenAPI custom tools and Skills in Toolboxes, whereas
  the Learn Toolbox table still lists some of these Toolkit entries as unavailable.
  Follow the observed Portal path in the core lab rather than using that table to
  infer web Portal support.
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
- [Use skills with Foundry agents (preview)](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills)
- [Observed Portal steps and screenshots](../labs/04-tools-toolbox.md)
- [Foundry Toolkit release notes](https://github.com/microsoft/foundry-dev-tools/blob/6bf72ba71785202fe2d972a4b564a6fbaeb5db0e/WHATS_NEW.md)
- [What is Foundry IQ?](https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq)
- [Agentic retrieval overview](https://learn.microsoft.com/azure/search/agentic-retrieval-overview)
- [Knowledge base query-planning models and API support](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base)
- [Choose a rubric LLM judge](https://learn.microsoft.com/azure/foundry/concepts/evaluation-evaluators/rubric-evaluators#choose-an-llm-judge-model)
- [Evaluate your AI agents](https://learn.microsoft.com/azure/foundry/observability/how-to/evaluate-agent)
- [Agent Optimizer overview](https://learn.microsoft.com/azure/foundry/agents/concepts/agent-optimizer-overview)
- [Hosted agents](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents)
- [Build a workflow in Foundry](https://learn.microsoft.com/azure/foundry/agents/concepts/workflow)
- [Fabric IQ tool](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq)
- [Work IQ tool](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/work-iq)

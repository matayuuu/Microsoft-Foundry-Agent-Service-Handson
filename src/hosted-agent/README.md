# Contoso Travel Sequential Workflow

This Hosted Agent is intentionally small enough to explain during a workshop.
Three Agent Framework participants share one conversation and run in order:

```text
intake_agent -> travel_harness_agent -> reviewer_agent
```

`travel_agents.py` owns the shared Harness Agent factory used by Labs 7 and 8.
`workflow.py` reuses that factory as the specialist participant:

```python
intake_agent = chat_client.as_agent(...)
travel_harness_agent = build_environment_harness_agent(
    default_mode="execute",
    hosted=True,
)
reviewer_agent = chat_client.as_agent(...)

participants = [intake_agent, travel_harness_agent, reviewer_agent]
workflow = SequentialBuilder(participants=participants).build()
```

Each participant sees the original request and earlier agent messages. The Harness
Agent retrieves policy through Foundry IQ, loads Toolbox Skills, and selects Travel
Ops tools. The Hosted Agent returns only `reviewer_agent`'s final answer.

> This is a training simulation. It does not book travel, approve requests, or
> connect to a production system. Foundry IQ and Toolbox use the workshop's
> synthetic remote resources.

## Files

```text
src/hosted-agent/
├── workflow.py       # Creates the agents and builds/runs the sequence
├── travel_agents.py  # Builds the plain Agent and shared Harness Agent
├── main.py           # Serves the workflow through the Responses protocol
├── requirements.txt  # Pinned remote-build dependencies
└── .agentignore      # Excludes local files from source deployment
```

## Local setup

Use the dedicated Python 3.13 environment because the Hosted Agent and root
deployment scripts require different `azure-ai-projects` versions.

```bash
cd src/hosted-agent
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt pytest ruff ipykernel
cp .env.example .env
```

Set these values in `.env`:

```dotenv
FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
FOUNDRY_MODEL=<model-deployment-name>
AZURE_AI_SEARCH_SERVICE_ENDPOINT=https://<search>.search.windows.net
AZURE_AI_SEARCH_KNOWLEDGE_BASE_NAME=contoso-travel-knowledge-lab
TOOLBOX_NAME=contoso-travel-toolbox
PORT=8088
```

Run `az login` before local execution. `DefaultAzureCredential` uses that
session locally and the managed identity when the code runs as a Hosted Agent.

## Build and inspect the agents and workflow in notebooks

Open [the Lab 7 Harness notebook](../../notebooks/07-agent-framework-harness.ipynb) to
compare a plain Agent with the Harness Agent. Then open
[the Lab 8 workflow notebook](../../notebooks/08-hosted-agent.ipynb) with the
**Python (Foundry Hosted Agent)** kernel. It explicitly creates the three agents,
connects them with `SequentialBuilder`, renders the actual graph using
`WorkflowViz` and local Graphviz, and shows intermediate responses before the
final output. It then exercises missing-input and overseas-business requests
and runs network-free contract tests.

Codespace setup installs Graphviz. For an older Codespace, install it with
`sudo apt-get update && sudo apt-get install -y graphviz`. No graph content is
sent to an external rendering service.

The Lab 8 notebook imports instructions from `workflow.py`. Its explicit construction
mirrors `build_workflow()`; contract tests execute the saved notebook cells with a
fake client to enforce this parity.
Only the notebook selects `intermediate_output_from="all_other"` for observation;
the deployed agent still exposes just the final response.

Notebook-only edits and Lab 7 session state are not deployed. Lab 8 deploys the
checked-in `travel_agents.py` and `workflow.py`, and depends on the remote resources
created in Labs 3 and 4. It can therefore be completed without running the Lab 7
notebook.

## Run the sequence directly

```bash
python workflow.py
```

This executes:

```python
result = await workflow.run(SAMPLE_REQUEST)
```

and prints the final reviewer's response.

## Serve the Responses protocol

```bash
python main.py
```

From another terminal:

```bash
curl -s http://localhost:8088/responses \
  -H "content-type: application/json" \
  -d '{"input":"2026年9月10日から11日まで、東京から大阪へ1名で社内レビューに行きます。座席クラスは economy、予算は100,000円です。規程の根拠、費用見積もり、予算との差額と消化率をまとめてください。予約や承認シミュレーションは不要です。"}' \
  | python -m json.tool
```

The response `output_text` contains the final text from `reviewer_agent`.

## Test without Azure

```bash
cd ../..
src/hosted-agent/.venv/bin/python -m pytest tests/contract/hosted_agent -q
```

The tests replace the chat client and remote MCP boundaries. They execute the
real `SequentialBuilder` workflow and verify participant order, Harness Agent
compatibility, conversation handoff, and the final response without Azure.

## Deploy

From the repository root:

```bash
.venv/bin/python scripts/deploy_hosted_agent.py --output json
```

The script packages `main.py`, `workflow.py`, `travel_agents.py`, and
`requirements.txt`, then creates an immutable source-deployed Hosted Agent
version. It injects the model, Search endpoint, knowledge-base name, and
Toolbox name; the platform injects `FOUNDRY_PROJECT_ENDPOINT`. After the agent
identity exists, the script grants resource-scoped Search Index Data Reader,
Foundry User, and Monitoring Metrics Publisher roles for retrieval, Toolbox
Skills, and tracing.

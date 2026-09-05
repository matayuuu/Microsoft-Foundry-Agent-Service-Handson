# Contoso Travel Sequential Workflow

This Hosted Agent is intentionally small enough to explain during a workshop.
Three Foundry-backed agents share one conversation and run in order:

```text
policy_agent -> planner_agent -> reviewer_agent
```

The important code is in `workflow.py`:

```python
policy_agent = chat_client.as_agent(...)
planner_agent = chat_client.as_agent(...)
reviewer_agent = chat_client.as_agent(...)

participants = [policy_agent, planner_agent, reviewer_agent]
workflow = SequentialBuilder(participants=participants).build()
```

Each participant sees the original request and earlier agent messages. The
Hosted Agent returns only `reviewer_agent`'s final answer without postprocessing.
The reviewer's instructions request a simulation notice; the notebook checks
whether it was included, rather than appending it automatically.

> This is a training simulation. It does not book travel, approve requests, or
> connect to a production system. The policy values in `workflow.py` are
> synthetic and deliberately simplified.

## Files

```text
src/hosted-agent/
├── workflow.py       # Creates the agents and builds/runs the sequence
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
PORT=8088
```

Run `az login` before local execution. `DefaultAzureCredential` uses that
session locally and the managed identity when the code runs as a Hosted Agent.

## Build and inspect the workflow in a notebook

Open [the Lab 7 notebook](../../notebooks/07-hosted-agent.ipynb) with the
**Python (Foundry Hosted Agent)** kernel. It explicitly creates the three agents,
connects them with `SequentialBuilder`, renders the actual graph using
`WorkflowViz` and local Graphviz, and shows intermediate responses before the
final output. It then exercises missing-input and overseas-business requests
and runs network-free contract tests.

Codespace setup installs Graphviz. For an older Codespace, install it with
`sudo apt-get update && sudo apt-get install -y graphviz`. No graph content is
sent to an external rendering service.

The notebook imports the policy and instructions from
`workflow.py`. Its explicit construction mirrors `build_workflow()`; contract
tests execute the saved notebook cells with a fake client to enforce this parity.
Only the notebook selects `intermediate_output_from="all_other"` for observation;
the deployed agent still exposes just the final response.

Notebook-only edits are not deployed. To deploy an experiment, update
`workflow.py` as well, save the notebook, restart its kernel, and rerun the
notebook and tests. The deployment command at the end is guidance, not an
automatically executed cell.

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
  -d '{"input":"2026年9月10日から11日まで、東京から大阪へ1名で社内レビューに行きます。座席クラスは economy です。規程確認と概算を作ってください。"}' \
  | python -m json.tool
```

The response `output_text` contains the final text from `reviewer_agent`.

## Test without Azure

```bash
cd ../..
src/hosted-agent/.venv/bin/python -m pytest tests/contract/hosted_agent -q
```

The tests replace only the chat client. They execute the real
`SequentialBuilder` workflow and verify participant order, conversation
handoff, and the final response.

## Deploy

From the repository root:

```bash
.venv/bin/python scripts/deploy_hosted_agent.py --output json
```

The script packages `main.py`, `workflow.py`, and `requirements.txt`, then
creates an immutable source-deployed Hosted Agent version. It injects
`FOUNDRY_MODEL` from the Terraform `primary_model_deployment_name` output;
the platform injects `FOUNDRY_PROJECT_ENDPOINT`.

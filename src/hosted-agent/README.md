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
Hosted Agent returns only `reviewer_agent`'s final answer.

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
python -m pip install -r requirements.txt pytest ruff
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

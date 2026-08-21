# Contoso Travel Expense Planner -- Hosted Agent

A Microsoft Agent Framework **workflow** deployed as a Microsoft Foundry
**Hosted Agent**, served over the Responses protocol on port 8088. It is used
by [`labs/07-hosted-multi-agent.md`](../../labs/07-hosted-multi-agent.md).

This directory is a **self-contained, independently deployable** source
tree, in the same spirit as `src/travel-api/`: it owns its own
`requirements.txt` and is deployed via direct source-code remote build
(`scripts/deploy_hosted_agent.py`), not via the repository-root
`pyproject.toml`.

## What it does

A sequential workflow simulates a Contoso travel pre-approval check, using
**real Microsoft Agent Framework agents** backed by a Foundry model
deployment for every named role -- this workshop step genuinely calls an
LLM, it is not a deterministic function pretending to be one:

```
intake_agent (real Agent, structured extraction) --> intake_gate (deterministic bridge)
     |(missing required fields)
     v
missing_info_responder [terminal]
     |(complete request, default)
     v
policy_agent -> planner_agent -> approval_agent   (each a real Agent)
                                       |
                    (requires simulated preapproval)--> approval_required_responder [terminal]
                                       |(within policy, default)
                                       v
                              auto_within_policy_responder [terminal]
```

- **intake_agent** (an `agent_framework.Agent` wrapped in an
  `AgentExecutor`, the workflow's `start_executor`) reads the conversation
  and extracts a structured trip request as JSON (`IntakeAgentOutput`,
  native `response_format` structured output). A deterministic bridge
  executor (`IntakeGateExecutor`) then hands that extraction to
  `domain.parse_trip_request`, which is the actual, sole source of truth
  for what counts as "missing" or "invalid" -- the model is asked to find
  fields, never to decide completeness.
- **policy_agent**, **planner_agent**, **approval_agent** are each a real
  `Agent` invoked directly by their own `Executor`. Every one of them is
  first handed an already-computed, deterministic result from `domain.py`
  (`check_policy` / `estimate_cost` / `decide_approval`, against a small,
  bundled *synthetic* policy excerpt and rate table that mirror -- but do
  not import -- the real documents in `data/policies/`) and asked only to
  write one short, fact-grounded Japanese sentence on top of it
  (`NarrativeAgentOutput`). **No agent is ever allowed to invent a number,
  a policy citation, or the approval decision itself** -- those all come
  from `domain.py`'s pure functions, never from the model.

**This workflow never calls a real approval or booking system**, even
though it does call a real LLM. Every response carries an explicit Japanese
disclaimer (`domain.SIMULATION_DISCLAIMER_JA`) stating that it is a training
simulation without real approval authority -- exactly like the Travel Ops
API's own `POST /preapprovals` (see `data/policies/09-approval-process.md`),
and every agent's instructions explicitly forbid claiming a real
approval/booking occurred.

## Architecture

- `domain.py` -- pure, deterministic Python: dataclasses and functions only.
  No `agent_framework`, no `azure-*`, no I/O, no model calls. Fully
  unit-testable (see `tests/unit/hosted_agent/test_domain.py`) and remains
  the sole source of truth for every branch-critical decision and number.
- `workflow.py` -- the only module that imports `agent_framework`
  (core) and, in production, `agent_framework_foundry`. Builds a real
  `Agent`/`AgentExecutor` for intake_agent as the workflow's
  `start_executor`, and three more custom `Executor`s (policy/planner/
  approval) that each hold and invoke their own real `Agent`. All four
  share one `agent_framework_foundry.FoundryChatClient` instance backed by
  the deployment named by `AZURE_AI_MODEL_DEPLOYMENT_NAME`. Accepts an
  optional `chat_client` override so every unit/contract test injects a
  scripted fake client instead (see "Testing without Azure" below) --
  still exercising the real `Agent`/`AgentExecutor`/`WorkflowBuilder` code
  paths end-to-end, with only the network boundary faked.
- `main.py` -- the only module that imports `agent_framework_foundry_hosting`.
  Wraps the built workflow as an agent and serves it with
  `ResponsesHostServer` (Responses protocol, port 8088 by default).

### Two Python environments

`agent-framework-foundry`'s `azure-ai-projects<2.4.0` constraint conflicts
with the repository root's `azure-ai-projects>=2.5.0` (needed by
`scripts/deploy_hosted_agent.py`/`scripts/delete_hosted_agent.py` for the
current `create_version_from_code`/`HostedAgentDefinition` APIs) -- so this
directory's runtime/test dependencies are deliberately **never** installed
into the repository root's virtual environment, and vice versa. Always run
this agent's own dependencies, tests, and smoke test from a **separate,
isolated virtual environment** created inside `src/hosted-agent/` (see
"Local run and smoke test" and "Pure-logic tests" below); use the repo
root's `.venv`/`pyproject.toml` only for the deploy/delete scripts
themselves.

### Sub-agent spans and tracing

Because every named role is a real `agent_framework.Agent` call, a Foundry
Playground/trace view of a single request shows **four distinct model
invocations** in sequence (`intake_agent`, `policy_agent`, `planner_agent`,
`approval_agent`), each with its own instructions and structured-output
schema -- not one opaque function call. This is what the workshop's
Playground trace-inspection step (`labs/07-hosted-multi-agent.md`) is
demonstrating: participants can open a version's trace and see each
sub-agent's prompt/response pair individually, confirming this is a genuine
multi-agent workflow rather than a single monolithic prompt.

## Request format

Send a single JSON object as the user turn's text:

```json
{
  "origin": "Tokyo",
  "destination": "London",
  "departure_date": "2026-05-10",
  "return_date": "2026-05-14",
  "cabin_class": "business",
  "purpose": "partner summit",
  "traveler_count": 1
}
```

Required fields: `origin`, `destination`, `departure_date`, `return_date`
(ISO-8601 `YYYY-MM-DD`), `cabin_class` (`economy` / `premium_economy` /
`business` / `first`), `purpose`. `traveler_count` is optional (defaults to
`1`). Missing/invalid fields route into the missing-information branch,
which asks for exactly what is missing.

**Multi-turn conversations can combine fields across turns.** Because
intake_agent's `AgentExecutor` threads the full conversation history into
every call (as long as the client keeps reusing the same conversation/
session), you can supply the required fields except one in your first
message and then supply just the missing field in your next message of the
*same* conversation -- intake_agent will combine both turns rather than
requiring you to resubmit the complete JSON object every time (see
`tests/contract/hosted_agent/test_workflow_agents.py`'s multi-turn tests,
which prove this empirically with a scripted fake client). A field that was
never supplied in *any* turn still correctly stays on the
missing-information branch.

## Local run and smoke test

This agent genuinely calls a Foundry model deployment, so a local run
requires `az login` and two environment variables. Use a Python 3.13
virtual environment **isolated from the repository root's** (see "Two
Python environments" above):

```bash
cd src/hosted-agent
python3.13 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
az login                            # or az login --use-device-code in a Codespace
cp .env.example .env
# Edit .env and set:
#   FOUNDRY_PROJECT_ENDPOINT=<your project's endpoint, e.g. from .workshop/context.json>
#   AZURE_AI_MODEL_DEPLOYMENT_NAME=<the primary_model_deployment_name Terraform output>
python main.py
```

The server listens on `http://localhost:8088` (Responses protocol). From
another terminal:

```bash
curl -s http://localhost:8088/responses \
  -H "content-type: application/json" \
  -d '{"input": "{\"origin\": \"Tokyo\", \"destination\": \"London\", \"departure_date\": \"2026-05-10\", \"return_date\": \"2026-05-14\", \"cabin_class\": \"business\", \"purpose\": \"partner summit\"}"}' \
  | python3 -m json.tool
```

Try an incomplete request to see the missing-information branch, and a
low-cost domestic economy trip to see the auto-within-policy branch (see
`labs/07-hosted-multi-agent.md` for more example prompts and the expected
branch for each).

> [!NOTE]
> **Anonymous requests without a `conversation`/`agent_session_id` are not
> guaranteed to be independent on this local dev host.** This package's
> hosting SDK (`azure-ai-agentserver-responses`, still beta) resolves a fresh
> random `agent_session_id` per request when the caller supplies none, but
> `intake_agent`'s `AgentExecutor` (`context_mode="full"`) still threads in
> whatever conversation history the host attaches for that request -- and in
> local/`is_hosted=False` runs, two consecutive requests with no explicit
> `conversation`/`agent_session_id` field can still see each other's fields.
> Empirically: sending the complete request above and *then* an incomplete
> one (same running `python main.py` process, no session fields on either
> request) may resolve the incomplete one as complete instead of routing to
> missing-information. Sending the incomplete request **first** on a freshly
> started server reliably reproduces the missing-information branch. If you
> want to test both branches from raw `curl` predictably, either restart
> `python main.py` between them, or test the missing-information/
> over-threshold payloads before the complete one. This is a local-run
> curl-testing nuance of the beta hosting SDK's session resolution, not a
> `workflow.py`/`domain.py` bug -- the deterministic and multi-turn contract
> tests (which construct their own fake sessions explicitly) are unaffected
> and confirm the intended per-conversation behavior described above.

## Testing without Azure

Every unit and contract test in this repository injects a scripted fake
chat client (`tests/contract/hosted_agent/fakes.py`'s `ScriptedChatClient`)
in place of `agent_framework_foundry.FoundryChatClient`, so `pytest` never
needs `az login`, network access, or a real model deployment -- only the
network boundary is faked; the real `agent_framework`
`Agent`/`AgentExecutor`/`WorkflowBuilder`/`WorkflowAgent` code paths run
end-to-end, exactly as they would against a real Foundry model. All
*decision-critical* routing and numbers still come from `domain.py`'s pure
functions, so those stay fully deterministic and assertable.

Run against the **repository root's** `.venv` (matches CI/`make test`):

```bash
python -m pytest tests/unit/hosted_agent tests/contract/hosted_agent
```

This works because `agent_framework`/`agent_framework-core` (which provides
`Agent`, `AgentExecutor`, `WorkflowBuilder`, etc.) is a normal root
dependency; only the concrete `agent_framework_foundry.FoundryChatClient` is
never imported during tests (see `workflow.py`'s `_default_chat_client`
docstring for the lazy-import seam that makes this possible).

### Running under the exact hosted requirements (isolated venv)

If your global/root environment ever fails to collect these tests (for
example, an older `agent-framework-core` incompatible with this directory's
pins), run them under this directory's own isolated environment instead --
this is also the only way to run a **live** local Responses smoke test
against a real Foundry model deployment:

```bash
cd src/hosted-agent
python3.13 -m venv .venv           # if not already created
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt pytest ruff
python -m pytest .                 # or: python -m pytest ../../tests/unit/hosted_agent ../../tests/contract/hosted_agent
ruff format . && ruff check .
```

## Deploying

See [`scripts/deploy_hosted_agent.py`](../../scripts/deploy_hosted_agent.py)
and `labs/07-hosted-multi-agent.md`. In short:

```bash
python3 scripts/deploy_hosted_agent.py --output json
```

Run this from the **repository root's** `.venv` (it needs
`azure-ai-projects>=2.5.0`, not this directory's own venv). It reads
`.workshop/context.json` (written by `./scripts/setup.sh`) for the Foundry
project endpoint -- no `--subscription`/`--resource-group` flags are
needed. It auto-injects `AZURE_AI_MODEL_DEPLOYMENT_NAME` into the deployed
container's environment variables from the `primary_model_deployment_name`
Terraform output (pass `--env AZURE_AI_MODEL_DEPLOYMENT_NAME=<name>` to
override); `FOUNDRY_PROJECT_ENDPOINT` is injected automatically by the
Hosted Agent platform itself once deployed, so the deploy script never sets
it. This zips this directory (respecting `.agentignore`), uploads it via
`azure-ai-projects`' `create_version_from_code` with
`dependency_resolution=remote_build`, and polls the new agent version until
it is `active` or `failed` (surfacing the service's structured `error`
details when it returns one).

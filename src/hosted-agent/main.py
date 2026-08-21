"""Hosted Agent entry point (Responses protocol, port 8088 by default).

Run locally for a smoke test:

    cd src/hosted-agent
    python3.13 -m venv .venv && source .venv/bin/activate   # or .venv\\Scripts\\activate on Windows
    pip install -r requirements.txt
    az login
    cp .env.example .env   # then fill in FOUNDRY_PROJECT_ENDPOINT and
                            # AZURE_AI_MODEL_DEPLOYMENT_NAME (see .env.example)
    python main.py

See README.md in this folder for the exact request payload shape, a curl
smoke-test example, and how each field routes through the workflow's
branches.

This workflow genuinely calls the Foundry model deployment: intake_agent,
policy_agent, planner_agent, and approval_agent are each a real
``agent_framework.Agent`` backed by ``agent_framework_foundry.FoundryChatClient``
(see workflow.py). Running it -- locally or once deployed -- therefore
requires ``az login`` plus ``FOUNDRY_PROJECT_ENDPOINT`` and
``AZURE_AI_MODEL_DEPLOYMENT_NAME`` to be set. Once deployed as a Hosted
Agent, ``FOUNDRY_PROJECT_ENDPOINT`` is injected automatically by the
platform and ``AZURE_AI_MODEL_DEPLOYMENT_NAME`` is injected automatically by
``scripts/deploy_hosted_agent.py`` (from the ``primary_model_deployment_name``
Terraform output) -- neither needs to be set by hand outside local runs.
"""

from __future__ import annotations

from agent_framework_foundry_hosting import ResponsesHostServer
from workflow import WORKFLOW_DESCRIPTION, WORKFLOW_NAME, build_workflow


def main() -> None:
    workflow = build_workflow()
    agent = workflow.as_agent(name=WORKFLOW_NAME, description=WORKFLOW_DESCRIPTION)
    server = ResponsesHostServer(agent)
    # host="0.0.0.0", port=None -> resolves to the PORT env var if set, else
    # the Responses protocol default of 8088.
    server.run()


if __name__ == "__main__":
    main()

"""Serve the sequential travel workflow through the Responses protocol."""

from __future__ import annotations

import os

from agent_framework_foundry_hosting import ResponsesHostServer
from workflow import WORKFLOW_DESCRIPTION, WORKFLOW_NAME, build_workflow


def main() -> None:
    # The host's rate-limited sampler can drop individual workflow/model spans.
    # Keep the workshop trace complete unless sampling was explicitly configured.
    os.environ.setdefault("OTEL_TRACES_SAMPLER", "always_on")

    workflow_agent = build_workflow().as_agent(
        name=WORKFLOW_NAME,
        description=WORKFLOW_DESCRIPTION,
    )
    ResponsesHostServer(workflow_agent).run()


if __name__ == "__main__":
    main()

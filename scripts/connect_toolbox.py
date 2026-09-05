#!/usr/bin/env python3
"""Optional keyless connection fallback for an already published Portal toolbox.

Does not create or change Toolbox versions, Skills, or existing agent knowledge.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from azure.ai.projects import AIProjectClient
from azure.core.exceptions import HttpResponseError
from create_toolbox import (
    DEFAULT_TOOLBOX_CONNECTION_NAME,
    attach_toolbox_to_agent,
    ensure_toolbox_connection,
    mcp_endpoints,
)
from lib.workshop_context import (
    DEFAULT_AGENT_NAME,
    DEFAULT_CONTEXT_PATH,
    DEFAULT_TOOLBOX_NAME,
    WorkshopContextError,
    build_credential,
    load_context,
    project_endpoint,
    terraform_output,
)


def connect_existing_toolbox(
    client: AIProjectClient,
    *,
    credential: Any,
    context: dict[str, Any],
    toolbox_name: str,
    agent_name: str,
    connection_name: str,
) -> dict[str, str]:
    """Require a published toolbox before changing any connection or agent."""
    toolbox = client.toolboxes.get(toolbox_name)
    client.toolboxes.get_version(toolbox_name, toolbox.default_version)
    endpoint = mcp_endpoints(project_endpoint(context), toolbox_name, toolbox.default_version)[
        "consumer"
    ]
    ensure_toolbox_connection(
        credential=credential,
        project_resource_id=terraform_output(context, "foundry_project_id"),
        connection_name=connection_name,
        toolbox_endpoint=endpoint,
    )
    return attach_toolbox_to_agent(
        client,
        agent_name=agent_name,
        connection_name=connection_name,
        toolbox_endpoint=endpoint,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", type=Path, default=DEFAULT_CONTEXT_PATH)
    parser.add_argument("--toolbox-name", default=DEFAULT_TOOLBOX_NAME)
    parser.add_argument("--agent-name", default=DEFAULT_AGENT_NAME)
    parser.add_argument("--connection-name", default=DEFAULT_TOOLBOX_CONNECTION_NAME)
    args = parser.parse_args(argv)

    try:
        context = load_context(args.context)
        with (
            build_credential("azure-cli") as credential,
            AIProjectClient(endpoint=project_endpoint(context), credential=credential) as client,
        ):
            result = connect_existing_toolbox(
                client,
                credential=credential,
                context=context,
                toolbox_name=args.toolbox_name,
                agent_name=args.agent_name,
                connection_name=args.connection_name,
            )
    except (WorkshopContextError, HttpResponseError) as exc:
        print(f"connect_toolbox.py: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Network-free tests for shared travel Agent wiring."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import travel_agents


class _Credential:
    def get_token(self, scope: str) -> SimpleNamespace:
        assert scope == travel_agents.SEARCH_TOKEN_SCOPE
        return SimpleNamespace(token="synthetic-token")


class _Toolbox:
    def __init__(self) -> None:
        self.skills_options: dict[str, Any] | None = None
        self.skills_provider = object()

    def as_skills_provider(self, **kwargs: Any) -> object:
        self.skills_options = kwargs
        return self.skills_provider


def test_search_auth_adds_current_bearer_token() -> None:
    auth = travel_agents.AzureTokenCredentialAuth(_Credential(), travel_agents.SEARCH_TOKEN_SCOPE)
    request = httpx.Request("POST", "https://search.example.invalid")

    [authenticated] = list(auth.auth_flow(request))

    assert authenticated.headers["Authorization"] == "Bearer synthetic-token"


def test_foundry_iq_tool_builds_expected_knowledge_base_endpoint() -> None:
    async def run() -> None:
        tool = travel_agents.FoundryIQTool(
            _Credential(),
            search_endpoint="https://search.example.invalid/",
            knowledge_base_name="travel-kb",
        )
        try:
            assert tool.url == (
                "https://search.example.invalid/knowledgebases/travel-kb/"
                "mcp?api-version=2026-05-01-preview"
            )
            assert tool.allowed_tools == ["knowledge_base_retrieve"]
        finally:
            await tool.close()

    asyncio.run(run())


def test_create_toolbox_uses_workshop_name_and_explicit_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def create(credential: Any, **kwargs: Any) -> object:
        captured.update({"credential": credential, **kwargs})
        return object()

    monkeypatch.setattr(travel_agents, "FoundryToolbox", create)
    credential = object()

    travel_agents.create_toolbox(
        credential,  # type: ignore[arg-type]
        toolbox_name="travel-tools",
        toolbox_endpoint="https://project.example.invalid/toolboxes/travel-tools/mcp",
    )

    assert captured == {
        "credential": credential,
        "name": "travel-tools",
        "url": "https://project.example.invalid/toolboxes/travel-tools/mcp",
        "load_tools": True,
        "approval_mode": "never_require",
    }


def test_harness_wires_iq_toolbox_skills_modes_todos_and_bounded_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    sentinel_agent = object()

    def create_harness_agent(**kwargs: Any) -> object:
        captured.update(kwargs)
        return sentinel_agent

    monkeypatch.setattr(travel_agents, "create_harness_agent", create_harness_agent)
    toolbox = _Toolbox()
    client = object()
    iq_tool = object()
    history = object()
    memory = object()

    result = travel_agents.build_harness_travel_agent(
        chat_client=client,
        foundry_iq_tool=iq_tool,
        toolbox=toolbox,
        default_mode="execute",
        history_provider=history,
        file_memory_store=memory,
        default_options={"store": False},
    )

    assert result is sentinel_agent
    assert captured["client"] is client
    assert captured["tools"] == [iq_tool, toolbox]
    assert captured["skills_provider"] is toolbox.skills_provider
    assert captured["history_provider"] is history
    assert captured["file_memory_store"] is memory
    assert captured["mode_provider"].default_mode == "execute"
    assert captured["disable_web_search"] is True
    assert captured["disable_tool_auto_approval"] is True
    assert captured["loop_max_iterations"] == 6
    assert captured["default_options"] == {"store": False}
    assert toolbox.skills_options == {
        "disable_load_skill_approval": True,
        "disable_read_skill_resource_approval": True,
    }


def test_agent_instructions_keep_source_and_action_boundaries_visible() -> None:
    instructions = travel_agents.HARNESS_AGENT_INSTRUCTIONS

    for required in (
        "Foundry IQ",
        "Skill",
        "tool_search",
        "call_tool",
        "Travel Ops API",
        "Code Interpreter",
        "Web Search",
        "実際の承認とは区別",
    ):
        assert required in instructions


def test_hosted_harness_uses_response_history_as_single_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential = object()
    client = object()
    iq_tool = object()
    toolbox = object()
    captured: dict[str, Any] = {}
    sentinel = object()
    monkeypatch.setattr(travel_agents, "create_credential", lambda: credential)
    monkeypatch.setattr(
        travel_agents,
        "create_chat_client",
        lambda supplied: client if supplied is credential else None,
    )
    monkeypatch.setattr(
        travel_agents,
        "create_foundry_iq_tool",
        lambda supplied: iq_tool if supplied is credential else None,
    )
    monkeypatch.setattr(
        travel_agents,
        "create_toolbox",
        lambda supplied: toolbox if supplied is credential else None,
    )

    def build(**kwargs: Any) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(travel_agents, "build_harness_travel_agent", build)

    result = travel_agents.build_environment_harness_agent(
        default_mode="execute",
        hosted=True,
        file_memory_store="memory-store",
    )

    assert result is sentinel
    assert captured["chat_client"] is client
    assert captured["foundry_iq_tool"] is iq_tool
    assert captured["toolbox"] is toolbox
    assert captured["default_mode"] == "execute"
    assert captured["history_provider"].load_messages is False
    assert captured["file_memory_store"] == "memory-store"
    assert captured["default_options"] == {"store": False}

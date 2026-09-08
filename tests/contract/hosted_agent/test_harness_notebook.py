"""Execute the new Harness learning notebook without Azure or network calls."""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import agent_framework
import pytest
import travel_agents
from agent_framework import AgentSession, get_agent_mode

REPO_ROOT = Path(__file__).resolve().parents[3]
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "07-agent-framework-harness.ipynb"


class _Credential:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _Response:
    def __init__(self, text: str, *actions: str) -> None:
        self.text = text
        self.messages = [
            SimpleNamespace(contents=[SimpleNamespace(name=action) for action in actions])
        ]


class _PlainAgent:
    def __init__(self) -> None:
        self.requests: list[str] = []
        self.closed = False

    async def __aenter__(self) -> _PlainAgent:
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.closed = True

    async def run(self, prompt: str) -> _Response:
        self.requests.append(prompt)
        return _Response("Foundry IQ に基づく回答", "knowledge_base_retrieve")


class _Toolbox:
    def __init__(self) -> None:
        self.skills_provider = object()
        self.skills_options: dict[str, Any] | None = None

    def as_skills_provider(self, **kwargs: Any) -> object:
        self.skills_options = kwargs
        return self.skills_provider


class _HarnessAgent:
    def __init__(self) -> None:
        self.requests: list[str] = []
        self.closed = False

    async def __aenter__(self) -> _HarnessAgent:
        return self

    async def __aexit__(self, *_: Any) -> None:
        self.closed = True

    def create_session(self) -> AgentSession:
        return AgentSession()

    async def run(self, prompt: str, *, session: AgentSession) -> _Response:
        self.requests.append(prompt)
        if get_agent_mode(session) == "plan":
            session.state["todo"] = {
                "items": [
                    {
                        "id": 1,
                        "title": "規程と費用を確認する",
                        "description": "Foundry IQ と Toolbox を使う",
                        "is_complete": False,
                    }
                ],
                "next_id": 2,
            }
            return _Response("実行計画", "todos_add")

        session.state["todo"]["items"][0]["is_complete"] = True
        return _Response(
            "根拠・見積もり・現在情報をまとめた最終回答",
            "load_skill",
            "knowledge_base_retrieve",
            "tool_search",
            "call_tool",
            "todos_complete",
        )


async def _execute_notebook(namespace: dict[str, Any]) -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    for cell in notebook["cells"]:
        if cell["cell_type"] != "code":
            continue
        code = compile(
            "".join(cell["source"]),
            f"{NOTEBOOK_PATH.name}:{cell['id']}",
            "exec",
            flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
        )
        result = eval(code, namespace)
        if inspect.isawaitable(result):
            await result


def test_notebook_builds_plain_then_harness_agent_with_shared_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "src" / "hosted-agent"
    source.mkdir(parents=True)
    source.joinpath("travel_agents.py").write_text("# marker\n", encoding="utf-8")
    context_dir = tmp_path / ".workshop"
    context_dir.mkdir()
    context_dir.joinpath("context.json").write_text(
        json.dumps(
            {
                "terraform_outputs": {
                    "foundry_project_endpoint": {"value": "https://project.example.invalid"},
                    "primary_model_deployment_name": {"value": "synthetic-model"},
                    "search_service_endpoint": {"value": "https://search.example.invalid"},
                    "foundry_project_name": {"value": "synthetic-project"},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", sys.path.copy())

    credential = _Credential()
    plain_agent = _PlainAgent()
    harness_agent = _HarnessAgent()
    toolbox = _Toolbox()
    plain_chat_client = object()
    harness_chat_client = object()
    chat_clients = iter([plain_chat_client, harness_chat_client])
    iq_tools: list[object] = []
    captured_harness: dict[str, Any] = {}

    monkeypatch.setattr(travel_agents, "create_credential", lambda: credential)
    monkeypatch.setattr(
        travel_agents,
        "create_chat_client",
        lambda supplied: next(chat_clients) if supplied is credential else None,
    )

    def create_iq_tool(supplied: object) -> object:
        assert supplied is credential
        tool = object()
        iq_tools.append(tool)
        return tool

    monkeypatch.setattr(travel_agents, "create_foundry_iq_tool", create_iq_tool)
    monkeypatch.setattr(
        travel_agents,
        "build_plain_travel_agent",
        lambda **kwargs: (
            plain_agent
            if kwargs
            == {
                "chat_client": plain_chat_client,
                "foundry_iq_tool": iq_tools[-1],
            }
            else None
        ),
    )
    monkeypatch.setattr(
        travel_agents,
        "create_toolbox",
        lambda supplied: toolbox if supplied is credential else None,
    )

    def create_harness_agent(**kwargs: Any) -> _HarnessAgent:
        captured_harness.update(kwargs)
        return harness_agent

    monkeypatch.setattr(agent_framework, "create_harness_agent", create_harness_agent)
    namespace: dict[str, Any] = {}

    asyncio.run(_execute_notebook(namespace))

    assert len(iq_tools) == 2
    assert plain_agent.requests and "片道12時間" in plain_agent.requests[0]
    assert harness_agent.requests[0] == namespace["complex_request"]
    assert "この計画を承認します" in harness_agent.requests[1]
    assert namespace["execute_actions"] == [
        "load_skill",
        "knowledge_base_retrieve",
        "tool_search",
        "call_tool",
        "todos_complete",
    ]
    assert namespace["todos_after_execute"][0]["is_complete"] is True
    assert captured_harness["tools"] == [iq_tools[1], toolbox]
    assert captured_harness["client"] is harness_chat_client
    assert captured_harness["skills_provider"] is toolbox.skills_provider
    assert captured_harness["todo_provider"] is namespace["todo_provider"]
    assert captured_harness["mode_provider"] is namespace["mode_provider"]
    assert captured_harness["disable_web_search"] is True
    assert captured_harness["loop_max_iterations"] == 6
    assert toolbox.skills_options == {
        "disable_load_skill_approval": True,
        "disable_read_skill_resource_approval": True,
    }
    assert plain_agent.closed is True
    assert harness_agent.closed is True
    assert credential.closed is True

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
import agent_framework.foundry as agent_framework_foundry
import azure.identity
import pytest
from agent_framework import AgentSession, get_agent_mode

from scripts.lib import workshop_runtime as runtime

REPO_ROOT = Path(__file__).resolve().parents[3]
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "07-agent-framework-harness.ipynb"


class _Credential:
    def __init__(self) -> None:
        self.closed = False
        self.scopes: list[str] = []

    def get_token(self, scope: str) -> SimpleNamespace:
        self.scopes.append(scope)
        return SimpleNamespace(token="synthetic-token")

    def close(self) -> None:
        self.closed = True


class _Response:
    def __init__(self, text: str, *actions: str) -> None:
        self.text = text
        self.messages = [
            SimpleNamespace(contents=[SimpleNamespace(name=action) for action in actions])
        ]


class _StandardAgent:
    def __init__(self) -> None:
        self.requests: list[str] = []
        self.closed = False

    async def __aenter__(self) -> _StandardAgent:
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


def test_notebook_builds_standard_then_harness_agent_with_direct_framework_wiring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tmp_path.joinpath("pyproject.toml").write_text("[project]\nname = 'test'\n", encoding="utf-8")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    scripts.joinpath("configure_workshop.py").write_text("# marker\n", encoding="utf-8")
    context_dir = tmp_path / ".workshop"
    context_dir.mkdir()
    context_dir.joinpath("context.json").write_text(
        (REPO_ROOT / "tests" / "fixtures" / "workshop-context.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "path", sys.path.copy())

    def check_kernel(spec: runtime.EnvironmentSpec) -> None:
        assert spec == runtime.HOSTED_ENVIRONMENT

    monkeypatch.setattr(runtime, "require_current_runtime", check_kernel)

    credential = _Credential()
    standard_agent = _StandardAgent()
    harness_agent = _HarnessAgent()
    toolbox = _Toolbox()
    standard_chat_client = object()
    harness_chat_client = object()
    chat_clients = iter([standard_chat_client, harness_chat_client])
    iq_tools: list[object] = []
    captured_clients: list[dict[str, Any]] = []
    captured_iq_tools: list[dict[str, Any]] = []
    captured_standard: dict[str, Any] = {}
    captured_toolbox: dict[str, Any] = {}
    captured_harness: dict[str, Any] = {}

    monkeypatch.setattr(azure.identity, "AzureCliCredential", lambda: credential)

    def create_chat_client(**kwargs: Any) -> object:
        captured_clients.append(kwargs)
        return next(chat_clients)

    monkeypatch.setattr(agent_framework_foundry, "FoundryChatClient", create_chat_client)

    def create_iq_tool(**kwargs: Any) -> object:
        tool = object()
        iq_tools.append(tool)
        captured_iq_tools.append(kwargs)
        return tool

    monkeypatch.setattr(agent_framework, "MCPStreamableHTTPTool", create_iq_tool)

    def create_standard_agent(**kwargs: Any) -> _StandardAgent:
        captured_standard.update(kwargs)
        return standard_agent

    monkeypatch.setattr(agent_framework, "Agent", create_standard_agent)

    def create_toolbox(*args: Any, **kwargs: Any) -> _Toolbox:
        captured_toolbox.update({"args": args, **kwargs})
        return toolbox

    monkeypatch.setattr(agent_framework_foundry, "FoundryToolbox", create_toolbox)

    def create_harness_agent(**kwargs: Any) -> _HarnessAgent:
        captured_harness.update(kwargs)
        return harness_agent

    monkeypatch.setattr(agent_framework, "create_harness_agent", create_harness_agent)
    namespace: dict[str, Any] = {}

    asyncio.run(_execute_notebook(namespace))

    assert len(captured_clients) == 2
    for client in captured_clients:
        assert client["project_endpoint"] == namespace["project_endpoint"]
        assert client["model"] == namespace["model_deployment"]
        assert client["credential"] is credential
        assert client["middleware"] == [namespace["request_pacer"]]

    assert len(iq_tools) == 2
    for iq_tool in captured_iq_tools:
        assert iq_tool["url"] == namespace["foundry_iq_url"]
        assert iq_tool["allowed_tools"] == ["knowledge_base_retrieve"]
        assert iq_tool["header_provider"] is namespace["search_headers"]
        assert iq_tool["approval_mode"] == "never_require"

    assert captured_standard["client"] is standard_chat_client
    assert captured_standard["tools"] == [iq_tools[0]]
    assert captured_standard["name"] == "travel_policy_agent"
    assert "Foundry IQ" in captured_standard["instructions"]
    assert standard_agent.requests and "片道12時間" in standard_agent.requests[0]
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
    assert captured_toolbox == {
        "args": (credential,),
        "name": namespace["toolbox_name"],
        "url": namespace["toolbox_url"],
        "load_tools": True,
        "approval_mode": "never_require",
    }
    assert toolbox.skills_options == {
        "disable_load_skill_approval": True,
        "disable_read_skill_resource_approval": True,
    }
    assert standard_agent.closed is True
    assert harness_agent.closed is True
    assert credential.closed is True

"""Shared fakes for hosted-agent contract tests.

``ScriptedChatClient`` is the single fake chat client every contract test in
this package injects via ``build_workflow(chat_client=...)`` /
``run_workflow_once(text, chat_client=...)`` /
``run_workflow_agent_turns(texts, chat_client=...)``. No test in this
package ever makes a real network call, needs Azure credentials, or needs a
model deployment: it implements exactly the ``agent_framework``
"SupportsChatGetResponse" protocol -- a plain (non-``async``)
``get_response(messages, *, stream=False, options=None, **kwargs)`` method
that returns an *awaitable* ``ChatResponse`` when ``stream=False`` and a
synchronously-returned ``ResponseStream`` when ``stream=True`` -- which is all
``agent_framework.Agent``/``AgentExecutor`` require of a chat client (see
``src/hosted-agent/workflow.py``'s module docstring and README.md's
"Testing without Azure" section). Both branches matter: the non-streaming
``run_workflow_once``/``run_workflow_agent_turns`` unit-level helpers only
exercise ``stream=False``, but the real Responses-protocol host
(``ResponsesHostServer``) runs the workflow's ``WorkflowAgent`` in streaming
mode, so only a live smoke test against a running server exercises the
``stream=True`` branch end-to-end.

This is a genuine exercise of the real Agent Framework code paths (``Agent``,
``AgentExecutor``, ``WorkflowBuilder``, structured ``response_format``
parsing via ``ChatResponse.value``/``AgentResponse.value``) -- only the
network boundary (the concrete chat client) is faked, exactly like a real
Foundry-backed run would look from the workflow's point of view.
"""

from __future__ import annotations

import json
from typing import Any

from workflow import IntakeAgentOutput

_KNOWN_INTAKE_FIELDS = {
    "origin",
    "destination",
    "departure_date",
    "return_date",
    "cabin_class",
    "purpose",
    "traveler_count",
}


class ScriptedChatClient:
    """Deterministic stand-in for ``agent_framework_foundry.FoundryChatClient``.

    Records every call (for assertions that every named agent was actually
    invoked -- see ``test_workflow_agents.py``) and answers according to the
    ``response_format`` the caller requested:

    * ``IntakeAgentOutput`` -- merges every JSON-parseable *user* message
      across the whole conversation given so far and echoes back only the
      recognized trip-request fields. This mirrors
      ``INTAKE_INSTRUCTIONS``' "carry forward a field from an earlier turn"
      contract closely enough to empirically test multi-turn behavior (a
      real model would do the same, just less predictably) without this
      fake ever inventing a field value it was not given.
    * anything else (``NarrativeAgentOutput``) -- returns a fixed,
      schema-conformant Japanese sentence identifying which named agent was
      asked (via its ``instructions``), so assertions can confirm
      policy/planner/approval narratives all differ and are attached to the
      final output.
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get_response(
        self, messages: Any = None, *, stream: bool = False, options: Any = None, **_: Any
    ) -> Any:
        # Mirrors agent_framework's SupportsChatGetResponse protocol exactly: this
        # is a *plain* (non-async) method that dispatches on ``stream`` -- when
        # stream=True it must return a real ``ResponseStream`` synchronously (the
        # caller in agent_framework._agents._call_chat_client does NOT await this
        # branch), and when stream=False it returns an awaitable. Declaring this
        # method itself as ``async def`` (an earlier version of this fake did)
        # breaks the stream=True path: calling an async function always yields a
        # coroutine, and the framework then calls ``.map()`` on it expecting a
        # ResponseStream, raising ``AttributeError: 'coroutine' object has no
        # attribute 'map'`` -- caught only by a live Responses-protocol smoke test
        # (WorkflowAgent runs agents in streaming mode), not by the non-streaming
        # unit-level ``run_workflow_once``/``run_workflow_agent_turns`` helpers.
        options = options or {}
        response_format = options.get("response_format")
        instructions = options.get("instructions") or ""
        self.calls.append({"instructions": instructions, "response_format": response_format})

        if response_format is IntakeAgentOutput:
            text = self._intake_text(messages or [])
        else:
            text = json.dumps(
                {"narrative_ja": self._narrative_for(instructions)}, ensure_ascii=False
            )

        if stream:
            from agent_framework import ChatResponseUpdate, Content, ResponseStream

            async def _stream() -> Any:
                yield ChatResponseUpdate(contents=[Content.from_text(text)], role="assistant")

            return ResponseStream(_stream())

        async def _response() -> Any:
            from agent_framework import ChatResponse, Message

            return ChatResponse(messages=[Message(role="assistant", contents=[text])])

        return _response()

    @staticmethod
    def _narrative_for(instructions: str) -> str:
        if "policy_agent" in instructions:
            return "テスト用のポリシー説明です。"
        if "planner_agent" in instructions:
            return "テスト用の見積もり説明です。"
        if "approval_agent" in instructions:
            return "テスト用の承認シミュレーション説明です。"
        return "テスト用の説明です。"

    @staticmethod
    def _intake_text(messages: list[Any]) -> str:
        merged: dict[str, Any] = {}
        for message in messages:
            if getattr(message, "role", None) != "user":
                continue
            try:
                payload = json.loads(message.text)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(payload, dict):
                merged.update({k: v for k, v in payload.items() if k in _KNOWN_INTAKE_FIELDS})
        return json.dumps(merged, ensure_ascii=False)

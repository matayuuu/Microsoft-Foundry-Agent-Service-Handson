"""Network-free chat client used by the sequential workflow tests."""

from __future__ import annotations

from typing import Any

from agent_framework import Agent
from travel_agents import HARNESS_AGENT_INSTRUCTIONS, HARNESS_AGENT_NAME
from workflow import (
    INTAKE_AGENT_INSTRUCTIONS,
    REVIEWER_AGENT_INSTRUCTIONS,
    SIMULATION_NOTICE,
)

INTAKE_RESPONSE = "受付整理: 東京から大阪、2026-09-10〜2026-09-11、1名、economy、予算100,000円。"
HARNESS_RESPONSE = (
    "Foundry IQ の規程を確認し、Travel Ops API で45,000円と算出しました。"
    "Code Interpreter による予算消化率は45%です。"
)
REVIEWER_RESPONSE = (
    "規程確認: Foundry IQ の引用を確認しました。\n"
    "概算: Travel Ops API の見積もりは45,000円、予算消化率は45%です。\n"
    f"次のアクション: 見積もり内容を確認してください。\n{SIMULATION_NOTICE}"
)


def build_scripted_harness_agent(client: ScriptedChatClient) -> Agent:
    """Build a plain test double at the Harness Agent's SupportsAgentRun boundary."""
    return Agent(
        client=client,
        name=HARNESS_AGENT_NAME,
        instructions=HARNESS_AGENT_INSTRUCTIONS,
    )


class ScriptedChatClient:
    """Implements the same ``as_agent`` boundary as ``FoundryChatClient``."""

    def __init__(self) -> None:
        self.created_agents: list[str] = []
        self.calls: list[dict[str, Any]] = []
        self.include_harness_tool_events = False

    def as_agent(self, *, name: str, instructions: str) -> Agent:
        self.created_agents.append(name)
        return Agent(client=self, name=name, instructions=instructions)

    def get_response(
        self,
        messages: Any = None,
        *,
        stream: bool = False,
        options: Any = None,
        **_: Any,
    ) -> Any:
        options = options or {}
        instructions = options.get("instructions") or ""
        message_texts = [message.text for message in (messages or [])]
        self.calls.append(
            {
                "instructions": instructions,
                "messages": message_texts,
            }
        )
        text = self._response_for(instructions)

        if stream:
            from agent_framework import ChatResponseUpdate, Content, ResponseStream

            async def _stream() -> Any:
                if self.include_harness_tool_events and HARNESS_AGENT_INSTRUCTIONS in instructions:
                    for name in (
                        "load_skill",
                        "knowledge_base_retrieve",
                        "tool_search",
                        "call_tool",
                    ):
                        yield ChatResponseUpdate(
                            contents=[
                                Content.from_function_call(
                                    call_id=f"synthetic-{name}", name=name, arguments="{}"
                                )
                            ],
                            role="assistant",
                        )
                midpoint = len(text) // 2
                for chunk in (text[:midpoint], text[midpoint:]):
                    yield ChatResponseUpdate(
                        contents=[Content.from_text(chunk)],
                        role="assistant",
                    )

            return ResponseStream(_stream())

        async def _response() -> Any:
            from agent_framework import ChatResponse, Message

            return ChatResponse(messages=[Message(role="assistant", contents=[text])])

        return _response()

    @staticmethod
    def _response_for(instructions: str) -> str:
        if instructions == INTAKE_AGENT_INSTRUCTIONS:
            return INTAKE_RESPONSE
        if HARNESS_AGENT_INSTRUCTIONS in instructions:
            return HARNESS_RESPONSE
        if instructions == REVIEWER_AGENT_INSTRUCTIONS:
            return REVIEWER_RESPONSE
        raise AssertionError(f"Unexpected agent instructions: {instructions}")

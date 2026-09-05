"""Network-free chat client used by the sequential workflow tests."""

from __future__ import annotations

from typing import Any

from agent_framework import Agent
from workflow import (
    PLANNER_AGENT_INSTRUCTIONS,
    POLICY_AGENT_INSTRUCTIONS,
    REVIEWER_AGENT_INSTRUCTIONS,
    SIMULATION_NOTICE,
)

POLICY_RESPONSE = "規程確認: 必要情報は揃っており、国内出張のため economy を利用します。"
PLANNER_RESPONSE = "出張案: 食事 6,000 円、宿泊 15,000 円、航空券は要見積もりです。"
REVIEWER_RESPONSE = (
    "規程確認: 国内出張規程内です。\n"
    "概算: 食事 6,000 円、宿泊 15,000 円、航空券は要見積もりです。\n"
    f"次のアクション: 正式な予約手続きを確認してください。\n{SIMULATION_NOTICE}"
)


class ScriptedChatClient:
    """Implements the same ``as_agent`` boundary as ``FoundryChatClient``."""

    def __init__(self) -> None:
        self.created_agents: list[str] = []
        self.calls: list[dict[str, Any]] = []

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
        if instructions == POLICY_AGENT_INSTRUCTIONS:
            return POLICY_RESPONSE
        if instructions == PLANNER_AGENT_INSTRUCTIONS:
            return PLANNER_RESPONSE
        if instructions == REVIEWER_AGENT_INSTRUCTIONS:
            return REVIEWER_RESPONSE
        raise AssertionError(f"Unexpected agent instructions: {instructions}")

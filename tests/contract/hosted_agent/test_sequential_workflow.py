"""Contract tests for the workshop's simple sequential workflow."""

from __future__ import annotations

import asyncio

from fakes import (
    PLANNER_RESPONSE,
    POLICY_RESPONSE,
    REVIEWER_RESPONSE,
    ScriptedChatClient,
)
from workflow import (
    PLANNER_AGENT_INSTRUCTIONS,
    POLICY_AGENT_INSTRUCTIONS,
    REVIEWER_AGENT_INSTRUCTIONS,
    SAMPLE_REQUEST,
    SIMULATION_NOTICE,
    WORKFLOW_NAME,
    build_workflow,
    ensure_simulation_notice,
    run_workflow,
)


def test_build_workflow_creates_three_agents_in_readable_order(
    chat_client: ScriptedChatClient,
) -> None:
    build_workflow(chat_client=chat_client)

    assert chat_client.created_agents == [
        "policy_agent",
        "planner_agent",
        "reviewer_agent",
    ]


def test_sequential_workflow_passes_each_agent_output_to_the_next(
    chat_client: ScriptedChatClient,
) -> None:
    final_text = asyncio.run(run_workflow(SAMPLE_REQUEST, chat_client=chat_client))

    assert final_text == REVIEWER_RESPONSE
    assert [call["instructions"] for call in chat_client.calls] == [
        POLICY_AGENT_INSTRUCTIONS,
        PLANNER_AGENT_INSTRUCTIONS,
        REVIEWER_AGENT_INSTRUCTIONS,
    ]
    assert SAMPLE_REQUEST in chat_client.calls[0]["messages"]
    assert POLICY_RESPONSE in chat_client.calls[1]["messages"]
    assert POLICY_RESPONSE in chat_client.calls[2]["messages"]
    assert PLANNER_RESPONSE in chat_client.calls[2]["messages"]


def test_workflow_as_agent_returns_only_the_final_review(
    chat_client: ScriptedChatClient,
) -> None:
    workflow_agent = build_workflow(chat_client=chat_client).as_agent(name=WORKFLOW_NAME)

    response = asyncio.run(workflow_agent.run(SAMPLE_REQUEST))

    assert response.text == REVIEWER_RESPONSE


def test_final_reviewer_is_instructed_to_include_simulation_notice() -> None:
    assert SIMULATION_NOTICE in REVIEWER_AGENT_INSTRUCTIONS
    assert SIMULATION_NOTICE in REVIEWER_RESPONSE


def test_simulation_notice_postprocessor_is_idempotent() -> None:
    assert ensure_simulation_notice(REVIEWER_RESPONSE) == REVIEWER_RESPONSE


def test_workflow_appends_notice_when_reviewer_omits_it() -> None:
    class OmittingNoticeClient(ScriptedChatClient):
        @staticmethod
        def _response_for(instructions: str) -> str:
            if instructions == REVIEWER_AGENT_INSTRUCTIONS:
                return "規程確認\n概算\n次のアクション"
            return ScriptedChatClient._response_for(instructions)

    workflow_agent = build_workflow(chat_client=OmittingNoticeClient()).as_agent(name=WORKFLOW_NAME)

    response = asyncio.run(workflow_agent.run(SAMPLE_REQUEST))

    assert response.text.endswith(SIMULATION_NOTICE)


def test_final_reviewer_must_not_invent_airfare() -> None:
    assert "航空券価格" in REVIEWER_AGENT_INSTRUCTIONS
    assert "要見積もり" in REVIEWER_AGENT_INSTRUCTIONS
    assert "金額を創作しない" in REVIEWER_AGENT_INSTRUCTIONS
    assert "航空券は要見積もり" in REVIEWER_RESPONSE

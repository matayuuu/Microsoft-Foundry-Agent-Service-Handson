"""Contract tests for the workshop's normal-agent sequential workflow."""

from __future__ import annotations

import asyncio

import pytest
import workflow as workflow_module
from fakes import (
    INTAKE_RESPONSE,
    POLICY_RESPONSE,
    REVIEWER_RESPONSE,
    ScriptedChatClient,
)
from workflow import (
    INTAKE_AGENT_INSTRUCTIONS,
    POLICY_AGENT_INSTRUCTIONS,
    REVIEWER_AGENT_INSTRUCTIONS,
    SAMPLE_REQUEST,
    SIMULATION_NOTICE,
    WORKFLOW_NAME,
    build_workflow,
    run_workflow,
)


def _policy_lookup(query: str) -> str:
    return f"synthetic policy for {query}"


def test_build_workflow_creates_three_normal_agents_with_policy_tool_only(
    chat_client: ScriptedChatClient,
) -> None:
    policy_tool = _policy_lookup

    build_workflow(chat_client=chat_client, foundry_iq_tool=policy_tool)

    assert chat_client.created_agents == [
        "intake_agent",
        "policy_agent",
        "reviewer_agent",
    ]
    assert chat_client.created_agent_tools == {
        "intake_agent": [],
        "policy_agent": [policy_tool],
        "reviewer_agent": [],
    }


def test_sequential_workflow_passes_each_agent_output_to_the_next(
    chat_client: ScriptedChatClient,
) -> None:
    final_text = asyncio.run(
        run_workflow(
            SAMPLE_REQUEST,
            chat_client=chat_client,
            foundry_iq_tool=_policy_lookup,
        )
    )

    assert final_text == REVIEWER_RESPONSE
    assert [call["instructions"] for call in chat_client.calls] == [
        INTAKE_AGENT_INSTRUCTIONS,
        POLICY_AGENT_INSTRUCTIONS,
        REVIEWER_AGENT_INSTRUCTIONS,
    ]
    assert SAMPLE_REQUEST in chat_client.calls[0]["messages"]
    assert INTAKE_RESPONSE in chat_client.calls[1]["messages"]
    assert INTAKE_RESPONSE in chat_client.calls[2]["messages"]
    assert POLICY_RESPONSE in chat_client.calls[2]["messages"]


def test_build_workflow_creates_runtime_dependencies_when_not_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    credential = object()
    client = ScriptedChatClient()
    policy_tool = object()
    monkeypatch.setattr(workflow_module, "create_credential", lambda: credential)
    monkeypatch.setattr(
        workflow_module,
        "create_chat_client",
        lambda supplied: client if supplied is credential else None,
    )
    monkeypatch.setattr(
        workflow_module,
        "create_foundry_iq_tool",
        lambda supplied: policy_tool if supplied is credential else None,
    )

    build_workflow()

    assert client.created_agent_tools["policy_agent"] == [policy_tool]


def test_workflow_as_agent_returns_only_the_final_review(
    chat_client: ScriptedChatClient,
) -> None:
    workflow_agent = build_workflow(
        chat_client=chat_client,
        foundry_iq_tool=_policy_lookup,
    ).as_agent(name=WORKFLOW_NAME)

    response = asyncio.run(workflow_agent.run(SAMPLE_REQUEST))

    assert response.text == REVIEWER_RESPONSE


def test_final_reviewer_is_instructed_to_include_simulation_notice() -> None:
    assert SIMULATION_NOTICE in REVIEWER_AGENT_INSTRUCTIONS
    assert SIMULATION_NOTICE in REVIEWER_RESPONSE


def test_reviewer_final_sentence_instruction_points_only_to_the_notice() -> None:
    final_instruction = REVIEWER_AGENT_INSTRUCTIONS.rsplit("\n\n", 1)[-1]
    assert final_instruction == (
        f"回答の末尾には、以下の固定文をそのまま一度だけ付けてください。\n{SIMULATION_NOTICE}"
    )
    assert REVIEWER_AGENT_INSTRUCTIONS.count(SIMULATION_NOTICE) == 1


def test_agent_responsibilities_are_narrow_and_non_overlapping() -> None:
    assert "規程判断は次の policy_agent に委ねます" in INTAKE_AGENT_INSTRUCTIONS
    assert "knowledge_base_retrieve" in POLICY_AGENT_INSTRUCTIONS
    assert "費用見積もり、予算計算、予約、申請、承認、精算は実行しない" in (
        POLICY_AGENT_INSTRUCTIONS
    )
    assert "Foundry IQ の根拠がある内容だけ" in REVIEWER_AGENT_INSTRUCTIONS


def test_workflow_as_agent_streams_only_the_final_review(
    chat_client: ScriptedChatClient,
) -> None:
    workflow_agent = build_workflow(
        chat_client=chat_client,
        foundry_iq_tool=_policy_lookup,
    ).as_agent(name=WORKFLOW_NAME)

    async def collect() -> str:
        chunks = [update.text async for update in workflow_agent.run(SAMPLE_REQUEST, stream=True)]
        assert len(chunks) >= 2
        return "".join(chunks)

    assert asyncio.run(collect()) == REVIEWER_RESPONSE


def test_observation_mode_surfaces_intake_and_policy_before_reviewer(
    chat_client: ScriptedChatClient,
) -> None:
    travel_workflow = build_workflow(
        chat_client=chat_client,
        foundry_iq_tool=_policy_lookup,
        observe_intermediate=True,
    )

    async def collect() -> tuple[list[str], list[str]]:
        intermediate: list[str] = []
        output: list[str] = []
        async for event in travel_workflow.run(SAMPLE_REQUEST, stream=True):
            if event.type == "intermediate":
                intermediate.append(event.executor_id)
            elif event.type == "output":
                output.append(event.executor_id)
        return intermediate, output

    intermediate, output = asyncio.run(collect())

    assert set(intermediate) == {"intake_agent", "policy_agent"}
    assert set(output) == {"reviewer_agent"}


@pytest.mark.parametrize("stream", [False, True])
def test_workflow_preserves_reviewer_answer_when_notice_is_omitted(stream: bool) -> None:
    class OmittingNoticeClient(ScriptedChatClient):
        @staticmethod
        def _response_for(instructions: str) -> str:
            if instructions == REVIEWER_AGENT_INSTRUCTIONS:
                return "依頼の整理\n規程確認\n次のアクション"
            return ScriptedChatClient._response_for(instructions)

    client = OmittingNoticeClient()
    workflow_agent = build_workflow(
        chat_client=client,
        foundry_iq_tool=_policy_lookup,
    ).as_agent(name=WORKFLOW_NAME)

    async def collect() -> str:
        if stream:
            return "".join(
                [update.text async for update in workflow_agent.run(SAMPLE_REQUEST, stream=True)]
            )
        return (await workflow_agent.run(SAMPLE_REQUEST)).text

    assert asyncio.run(collect()) == "依頼の整理\n規程確認\n次のアクション"


def test_run_workflow_rejects_an_empty_reviewer_response() -> None:
    class EmptyReviewerClient(ScriptedChatClient):
        @staticmethod
        def _response_for(instructions: str) -> str:
            if instructions == REVIEWER_AGENT_INSTRUCTIONS:
                return ""
            return ScriptedChatClient._response_for(instructions)

    with pytest.raises(RuntimeError, match="without a final reviewer response"):
        client = EmptyReviewerClient()
        asyncio.run(
            run_workflow(
                SAMPLE_REQUEST,
                chat_client=client,
                foundry_iq_tool=_policy_lookup,
            )
        )


def test_final_reviewer_must_not_invent_policy_or_costs() -> None:
    assert "規程の文書 ID" in REVIEWER_AGENT_INSTRUCTIONS
    assert "費用見積もりや予算計算を追加せず" in REVIEWER_AGENT_INSTRUCTIONS
    assert "成功したように書き換えてはいけません" in REVIEWER_AGENT_INSTRUCTIONS

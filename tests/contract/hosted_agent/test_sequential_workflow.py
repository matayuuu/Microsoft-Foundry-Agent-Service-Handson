"""Contract tests for the workshop's simple sequential workflow."""

from __future__ import annotations

import asyncio

import pytest
import travel_agents
from agent_framework import AgentModeProvider, HistoryProvider, create_harness_agent
from fakes import (
    HARNESS_RESPONSE,
    INTAKE_RESPONSE,
    REVIEWER_RESPONSE,
    ScriptedChatClient,
    build_scripted_harness_agent,
)
from travel_agents import HARNESS_AGENT_INSTRUCTIONS
from workflow import (
    INTAKE_AGENT_INSTRUCTIONS,
    REVIEWER_AGENT_INSTRUCTIONS,
    SAMPLE_REQUEST,
    SIMULATION_NOTICE,
    WORKFLOW_NAME,
    build_workflow,
    run_workflow,
)


def test_build_workflow_creates_plain_agents_around_injected_harness(
    chat_client: ScriptedChatClient,
) -> None:
    build_workflow(
        chat_client=chat_client,
        harness_agent=build_scripted_harness_agent(chat_client),
    )

    assert chat_client.created_agents == [
        "intake_agent",
        "reviewer_agent",
    ]


def test_sequential_workflow_passes_each_agent_output_to_the_next(
    chat_client: ScriptedChatClient,
) -> None:
    final_text = asyncio.run(
        run_workflow(
            SAMPLE_REQUEST,
            chat_client=chat_client,
            harness_agent=build_scripted_harness_agent(chat_client),
        )
    )

    assert final_text == REVIEWER_RESPONSE
    assert [call["instructions"] for call in chat_client.calls] == [
        INTAKE_AGENT_INSTRUCTIONS,
        HARNESS_AGENT_INSTRUCTIONS,
        REVIEWER_AGENT_INSTRUCTIONS,
    ]
    assert SAMPLE_REQUEST in chat_client.calls[0]["messages"]
    assert INTAKE_RESPONSE in chat_client.calls[1]["messages"]
    assert INTAKE_RESPONSE in chat_client.calls[2]["messages"]
    assert HARNESS_RESPONSE in chat_client.calls[2]["messages"]


def test_real_harness_agent_can_run_as_a_sequential_participant(
    chat_client: ScriptedChatClient,
) -> None:
    harness_agent = create_harness_agent(
        client=chat_client,
        name="travel_harness_agent",
        agent_instructions=HARNESS_AGENT_INSTRUCTIONS,
        disable_file_memory=True,
        disable_todo=True,
        disable_web_search=True,
        disable_tool_auto_approval=True,
        mode_provider=AgentModeProvider(default_mode="execute"),
    )

    final_text = asyncio.run(
        run_workflow(
            SAMPLE_REQUEST,
            chat_client=chat_client,
            harness_agent=harness_agent,
        )
    )

    assert final_text == REVIEWER_RESPONSE
    assert HARNESS_AGENT_INSTRUCTIONS in chat_client.calls[1]["instructions"]
    assert INTAKE_RESPONSE in chat_client.calls[1]["messages"]


def test_hosted_factory_does_not_inject_a_duplicate_history_provider(
    chat_client: ScriptedChatClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(travel_agents, "create_credential", object)
    monkeypatch.setattr(travel_agents, "create_chat_client", lambda _: chat_client)
    monkeypatch.setattr(travel_agents, "create_foundry_iq_tool", lambda _: None)
    monkeypatch.setattr(travel_agents, "create_toolbox", lambda _: None)

    def build_without_network_tools(**kwargs):
        return create_harness_agent(
            client=kwargs["chat_client"],
            agent_instructions=HARNESS_AGENT_INSTRUCTIONS,
            history_provider=kwargs["history_provider"],
            default_options=kwargs["default_options"],
            mode_provider=AgentModeProvider(default_mode=kwargs["default_mode"]),
            disable_file_memory=True,
            disable_todo=True,
            disable_web_search=True,
            disable_tool_auto_approval=True,
        )

    monkeypatch.setattr(travel_agents, "build_harness_travel_agent", build_without_network_tools)
    harness = travel_agents.build_environment_harness_agent(default_mode="execute", hosted=True)
    asyncio.run(harness.run(SAMPLE_REQUEST, session=harness.create_session()))

    providers = [p for p in harness.context_providers if isinstance(p, HistoryProvider)]
    assert len(providers) == 1
    assert providers[0].load_messages
    assert harness.default_options["store"] is False


def test_workflow_as_agent_returns_only_the_final_review(
    chat_client: ScriptedChatClient,
) -> None:
    workflow_agent = build_workflow(
        chat_client=chat_client,
        harness_agent=build_scripted_harness_agent(chat_client),
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


def test_responsibilities_do_not_duplicate_policy_or_tool_results() -> None:
    assert "規程判断や費用計算は次の専門 Agent に委ねます" in INTAKE_AGENT_INSTRUCTIONS
    assert "Foundry IQ" in HARNESS_AGENT_INSTRUCTIONS
    assert "Tool Search" in HARNESS_AGENT_INSTRUCTIONS
    assert "根拠と tool 結果がある内容だけ" in REVIEWER_AGENT_INSTRUCTIONS


def test_workflow_as_agent_streams_only_the_final_review(
    chat_client: ScriptedChatClient,
) -> None:
    workflow_agent = build_workflow(
        chat_client=chat_client,
        harness_agent=build_scripted_harness_agent(chat_client),
    ).as_agent(name=WORKFLOW_NAME)

    async def collect() -> str:
        chunks = [update.text async for update in workflow_agent.run(SAMPLE_REQUEST, stream=True)]
        assert len(chunks) >= 2
        return "".join(chunks)

    assert asyncio.run(collect()) == REVIEWER_RESPONSE


def test_observation_mode_surfaces_intake_and_harness_before_reviewer(
    chat_client: ScriptedChatClient,
) -> None:
    travel_workflow = build_workflow(
        chat_client=chat_client,
        harness_agent=build_scripted_harness_agent(chat_client),
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

    assert set(intermediate) == {"intake_agent", "travel_harness_agent"}
    assert set(output) == {"reviewer_agent"}


@pytest.mark.parametrize("stream", [False, True])
def test_workflow_preserves_reviewer_answer_when_notice_is_omitted(stream: bool) -> None:
    class OmittingNoticeClient(ScriptedChatClient):
        @staticmethod
        def _response_for(instructions: str) -> str:
            if instructions == REVIEWER_AGENT_INSTRUCTIONS:
                return "規程確認\n概算\n次のアクション"
            return ScriptedChatClient._response_for(instructions)

    client = OmittingNoticeClient()
    workflow_agent = build_workflow(
        chat_client=client,
        harness_agent=build_scripted_harness_agent(client),
    ).as_agent(name=WORKFLOW_NAME)

    async def collect() -> str:
        if stream:
            return "".join(
                [update.text async for update in workflow_agent.run(SAMPLE_REQUEST, stream=True)]
            )
        return (await workflow_agent.run(SAMPLE_REQUEST)).text

    assert asyncio.run(collect()) == "規程確認\n概算\n次のアクション"


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
                harness_agent=build_scripted_harness_agent(client),
            )
        )


def test_final_reviewer_must_not_invent_airfare() -> None:
    assert "金額は Travel Ops API" in REVIEWER_AGENT_INSTRUCTIONS
    assert "成功したように書き換えてはいけません" in REVIEWER_AGENT_INSTRUCTIONS

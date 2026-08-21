"""Contract tests proving the hardened Agent Framework architecture:

1. Terminal output is genuinely valid JSON when served through the same
   ``WorkflowAgent``/``AgentResponse.text`` path ``ResponsesHostServer``
   uses (not a Python ``str(dict)`` repr) -- the fix for the JSON
   serialization bug, and the "e2e served/WorkflowAgent contract coverage
   proving output_text round-trips as JSON" the task requires.
2. All four named roles (intake_agent, policy_agent, planner_agent,
   approval_agent) are genuinely invoked as real ``agent_framework`` agents
   for a single full run -- not deterministic Python functions with no model
   call.
3. Multi-turn conversation history lets intake_agent combine a field
   supplied in an earlier turn with one supplied in a later turn of the
   *same* conversation (empirically tested, not assumed) -- and the
   alternative (a field never supplied in any turn) still correctly stays
   on the missing-information branch.
4. ``IntakeGateExecutor`` falls back to "no fields extracted" (not a crash)
   when intake_agent's structured output does not validate.

All of these run the real ``agent_framework`` ``Agent``/``AgentExecutor``/
``WorkflowBuilder``/``WorkflowAgent`` code paths with only the chat client
faked (see ``fakes.ScriptedChatClient``) -- no Azure credentials, network
access, or model deployment required.
"""

from __future__ import annotations

import json

from fakes import ScriptedChatClient
from workflow import (
    APPROVAL_INSTRUCTIONS,
    INTAKE_INSTRUCTIONS,
    PLANNER_INSTRUCTIONS,
    POLICY_INSTRUCTIONS,
    run_workflow_agent_turns,
    run_workflow_once,
)


def _payload(**overrides: object) -> str:
    base: dict[str, object] = {
        "origin": "Tokyo",
        "destination": "Osaka",
        "departure_date": "2026-05-10",
        "return_date": "2026-05-11",
        "cabin_class": "economy",
        "purpose": "client visit",
    }
    base.update(overrides)
    return json.dumps(base)


def test_served_workflow_agent_output_text_round_trips_as_json(
    chat_client: ScriptedChatClient,
) -> None:
    """Runs the workflow via the exact ``WorkflowAgent.run`` path
    ``main.py``/``ResponsesHostServer`` uses (not the lower-level
    ``Workflow.run``), and asserts the returned ``AgentResponse.text`` is
    valid JSON -- proving the item-1 regression (raw dicts stringified via
    Python repr, not ``json.dumps``) is fixed end-to-end, not just at the
    unit level of the terminal executors.
    """
    [output_text] = run_workflow_agent_turns([_payload()], chat_client=chat_client)

    parsed = json.loads(output_text)  # must not raise json.JSONDecodeError

    assert parsed["status"] == "auto_within_policy"
    assert "agent_narratives" in parsed


def test_served_workflow_agent_output_text_round_trips_as_json_for_missing_info_branch(
    chat_client: ScriptedChatClient,
) -> None:
    """Same as above, for the other terminal branch -- ``MissingInfoResponder``
    is a distinct executor with its own ``ctx.yield_output`` call site, so it
    needs its own regression coverage.
    """
    [output_text] = run_workflow_agent_turns(
        [json.dumps({"origin": "Tokyo"})], chat_client=chat_client
    )

    parsed = json.loads(output_text)

    assert parsed["status"] == "missing_information"


def test_all_four_named_agents_are_invoked_for_a_full_within_policy_run(
    chat_client: ScriptedChatClient,
) -> None:
    """Proves this is a *real* multi-agent Agent Framework workflow: a single
    complete, within-policy request must call the chat client once for each
    of intake_agent, policy_agent, planner_agent, and approval_agent (in
    that order), each with its own distinct instructions -- not a
    deterministic Python function standing in for any of them.
    """
    output = run_workflow_once(_payload(), chat_client=chat_client)
    assert output["status"] == "auto_within_policy"

    instructions_seen = [call["instructions"] for call in chat_client.calls]
    assert instructions_seen == [
        INTAKE_INSTRUCTIONS,
        POLICY_INSTRUCTIONS,
        PLANNER_INSTRUCTIONS,
        APPROVAL_INSTRUCTIONS,
    ]

    narratives = output["agent_narratives"]
    assert narratives["policy_agent_ja"] == "テスト用のポリシー説明です。"
    assert narratives["planner_agent_ja"] == "テスト用の見積もり説明です。"
    assert narratives["approval_agent_ja"] == "テスト用の承認シミュレーション説明です。"


def test_all_four_named_agents_are_invoked_for_a_full_approval_required_run(
    chat_client: ScriptedChatClient,
) -> None:
    """Same proof as above, for the other post-intake branch (approval_agent
    still runs either way -- only the terminal responder differs)."""
    output = run_workflow_once(
        _payload(destination="London", cabin_class="business"), chat_client=chat_client
    )
    assert output["status"] == "approval_required"

    instructions_seen = [call["instructions"] for call in chat_client.calls]
    assert instructions_seen == [
        INTAKE_INSTRUCTIONS,
        POLICY_INSTRUCTIONS,
        PLANNER_INSTRUCTIONS,
        APPROVAL_INSTRUCTIONS,
    ]


def test_missing_information_branch_never_calls_policy_planner_or_approval_agents(
    chat_client: ScriptedChatClient,
) -> None:
    """The missing-information branch must short-circuit *before*
    policy_agent -- otherwise the pure ``domain.check_policy``/etc. would be
    invoked on an incomplete request."""
    output = run_workflow_once(json.dumps({"origin": "Tokyo"}), chat_client=chat_client)
    assert output["status"] == "missing_information"

    instructions_seen = [call["instructions"] for call in chat_client.calls]
    assert instructions_seen == [INTAKE_INSTRUCTIONS]


def test_multi_turn_conversation_lets_intake_agent_combine_fields_across_turns(
    chat_client: ScriptedChatClient,
) -> None:
    """Empirically proves the lab's multi-turn claim (item 6): supplying the
    complete request except one field in turn 1, then supplying *only* the
    missing field in turn 2 of the *same* conversation, must complete the
    request -- intake_agent does not need every field resubmitted every
    turn, because ``AgentExecutor``'s default ``context_mode="full"``
    threads the whole prior conversation into each subsequent call.
    """
    incomplete = json.loads(_payload())
    del incomplete["cabin_class"]

    turn_1_text, turn_2_text = run_workflow_agent_turns(
        [json.dumps(incomplete), json.dumps({"cabin_class": "economy"})],
        chat_client=chat_client,
    )

    turn_1 = json.loads(turn_1_text)
    assert turn_1["status"] == "missing_information"
    assert "cabin_class" in turn_1["missing_fields"]

    turn_2 = json.loads(turn_2_text)
    assert turn_2["status"] == "auto_within_policy"
    assert turn_2["request"]["cabin_class"] == "economy"
    assert turn_2["request"]["destination"] == "Osaka"


def test_multi_turn_conversation_still_reports_missing_information_if_a_field_is_never_supplied(
    chat_client: ScriptedChatClient,
) -> None:
    """The counterpart to the previous test: if a field is never supplied in
    *any* turn, the request must stay incomplete even across multiple turns
    of the same conversation -- multi-turn history helps intake_agent
    combine fields it was actually given, it does not let it invent one it
    was never given.
    """
    incomplete = json.loads(_payload())
    del incomplete["cabin_class"]

    turn_1_text, turn_2_text = run_workflow_agent_turns(
        [json.dumps(incomplete), "still no cabin class here"],
        chat_client=chat_client,
    )

    assert json.loads(turn_1_text)["status"] == "missing_information"
    assert json.loads(turn_2_text)["status"] == "missing_information"


def test_intake_gate_falls_back_to_no_fields_when_structured_output_does_not_validate(
    chat_client: ScriptedChatClient,
) -> None:
    """If intake_agent's raw text does not parse as ``IntakeAgentOutput``
    (e.g. a non-compliant model response), ``IntakeGateExecutor`` must treat
    it as "no fields extracted" (routing to missing-information) rather than
    raising -- see ``_structured_value``'s narrow ``ValidationError`` catch.
    """

    class _NonCompliantChatClient:
        async def get_response(self, messages=None, *, options=None, **_: object):
            from agent_framework import ChatResponse, Message

            # Not valid JSON at all -- forces IntakeAgentOutput.model_validate_json
            # to raise pydantic.ValidationError when `.value` is accessed.
            return ChatResponse(messages=[Message(role="assistant", contents=["not json"])])

    output = run_workflow_once(_payload(), chat_client=_NonCompliantChatClient())

    assert output["status"] == "missing_information"

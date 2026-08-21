"""Contract tests for src/hosted-agent/workflow.py's branching behavior.

These run the *real* agent_framework ``Agent``/``AgentExecutor``/
``WorkflowBuilder`` graph end-to-end, with a scripted fake chat client (see
``fakes.ScriptedChatClient`` / the ``chat_client`` fixture in ``conftest.py``)
standing in for ``agent_framework_foundry.FoundryChatClient`` -- the only
thing faked is the network boundary, so this requires no Azure credentials,
network access, or model deployment. All *decision-critical* routing
(missing-information vs. complete, over-threshold vs. auto-within-policy)
still flows entirely through ``src/hosted-agent/domain.py``'s pure functions,
so it stays deterministic and assertable exactly as before this module
started calling real agents. This is the "pure workflow/policy/branching
configuration testable without Azure" contract the task requires: given a
Responses-protocol-shaped user turn, the workflow must route to the
documented branch and produce the documented structured output shape.

See ``test_workflow_agents.py`` for coverage specific to the real-agent
architecture itself: JSON round-tripping through the served
``WorkflowAgent`` path, multi-turn conversation history, and proof that all
four named agents are genuinely invoked.
"""

from __future__ import annotations

import json

import pytest
from fakes import ScriptedChatClient
from workflow import run_workflow_once


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


def test_missing_information_branch_is_reached_for_incomplete_input(
    chat_client: ScriptedChatClient,
) -> None:
    output = run_workflow_once(json.dumps({"origin": "Tokyo"}), chat_client=chat_client)

    assert output["status"] == "missing_information"
    assert "destination" in output["missing_fields"]
    assert "disclaimer_ja" in output


def test_missing_information_branch_is_reached_for_non_json_input(
    chat_client: ScriptedChatClient,
) -> None:
    output = run_workflow_once("this is not JSON at all", chat_client=chat_client)

    assert output["status"] == "missing_information"


def test_sequential_chain_reaches_auto_within_policy_for_low_cost_domestic_trip(
    chat_client: ScriptedChatClient,
) -> None:
    output = run_workflow_once(_payload(), chat_client=chat_client)

    assert output["status"] == "auto_within_policy"
    assert output["approval_decision"]["requires_preapproval"] is False
    assert output["policy_check"]["is_international"] is False
    assert output["cost_plan"]["total_estimate_jpy"] > 0
    assert output["disclaimer_ja"]


def test_over_threshold_branch_is_reached_for_international_business_trip(
    chat_client: ScriptedChatClient,
) -> None:
    output = run_workflow_once(
        _payload(destination="London", cabin_class="business", purpose="board meeting"),
        chat_client=chat_client,
    )

    assert output["status"] == "approval_required"
    assert output["approval_decision"]["requires_preapproval"] is True
    assert set(output["approval_decision"]["approvers"]) == {"manager", "department_vp"}
    assert output["policy_check"]["is_international"] is True


def test_over_threshold_branch_is_reached_for_high_cost_domestic_trip(
    chat_client: ScriptedChatClient,
) -> None:
    output = run_workflow_once(_payload(traveler_count=5), chat_client=chat_client)

    assert output["status"] == "approval_required"
    assert output["approval_decision"]["requires_preapproval"] is True
    assert "domestic_total_exceeds_100000_jpy" in output["approval_decision"]["reasons"]


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {"destination": "London", "cabin_class": "business"},
        {"traveler_count": 5},
    ],
)
def test_final_response_always_carries_the_simulation_disclaimer(
    overrides: dict[str, object], chat_client: ScriptedChatClient
) -> None:
    output = run_workflow_once(_payload(**overrides), chat_client=chat_client)

    assert "実際の承認・予約権限は" in output["disclaimer_ja"]


def test_final_response_never_claims_a_real_booking_or_approval_was_made(
    chat_client: ScriptedChatClient,
) -> None:
    output = run_workflow_once(
        _payload(destination="London", cabin_class="business"), chat_client=chat_client
    )

    # The recommendation text must read as a simulated recommendation, not a
    # confirmation of a real action.
    assert "承認されました" not in output["recommendation_ja"]
    assert "予約されました" not in output["recommendation_ja"]
    assert "シミュレーション" in output["recommendation_ja"]


def test_build_workflow_as_agent_accepts_list_message_start_input(
    chat_client: ScriptedChatClient,
) -> None:
    """``Workflow.as_agent()`` raises ``ValueError`` if the start executor
    cannot handle ``list[Message]`` input (see the agent_framework docstring
    on ``as_agent``). Asserting this succeeds pins down that intake_agent's
    ``AgentExecutor`` keeps that contract across future refactors.
    """
    from workflow import WORKFLOW_NAME, build_workflow

    workflow = build_workflow(chat_client=chat_client)

    agent = workflow.as_agent(name=WORKFLOW_NAME)

    assert agent.name == WORKFLOW_NAME

"""Microsoft Agent Framework workflow wiring for the travel-expense planner.

This module is the only place in ``src/hosted-agent`` that imports
``agent_framework``. It wires **real** Microsoft Agent Framework agents --
``agent_framework.Agent`` backed by ``agent_framework_foundry.FoundryChatClient``
-- for all four named roles (``intake_agent``, ``policy_agent``,
``planner_agent``, ``approval_agent``), so every role genuinely calls the
Foundry model deployment at runtime. It never calls a real approval/booking
system: all *decision-critical* logic and numbers (missing-field detection,
policy thresholds, cost math, the preapproval decision itself) stay in the
pure, deterministic functions in :mod:`domain` -- the model is only asked to
extract structured fields (``intake_agent``) or write a short, fact-grounded
Japanese narrative on top of an already-computed, deterministic result
(``policy_agent``/``planner_agent``/``approval_agent``). See "Architecture" in
README.md for the full rationale.

Workflow shape (see labs/07-hosted-multi-agent.md for the full narrative):

    intake_agent (AgentExecutor, real Agent+FoundryChatClient)
        --> intake_gate (deterministic bridge: AgentExecutorResponse -> IntakeResult)
    intake_gate
        --(missing required fields)--> missing_info_responder   [terminal]
        --(request is complete, default)--> policy_agent
    policy_agent --> planner_agent --> approval_agent   (each a real Agent, invoked
                                                          inline by its executor)
    approval_agent
        --(requires_preapproval)--> approval_required_responder [terminal]
        --(within policy, default)--> auto_within_policy_responder [terminal]

``build_workflow()`` returns a plain ``agent_framework.Workflow``. It accepts
an optional ``chat_client`` override (any object implementing
``agent_framework``'s ``SupportsChatGetResponse`` protocol -- just an async
``get_response(messages, *, options=None, ...)`` method): unit/contract tests
always pass a scripted fake client, so they run the *real* ``Agent`` /
``AgentExecutor`` / ``WorkflowBuilder`` code paths end-to-end with no Azure
credentials, network access, or model deployment. Only when ``chat_client``
is omitted (production use from ``main.py``) does this module import
``agent_framework_foundry``/``azure-identity`` and read
``FOUNDRY_PROJECT_ENDPOINT``/``AZURE_AI_MODEL_DEPLOYMENT_NAME`` -- see
``_default_chat_client`` below for why that import is deliberately lazy.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Never

import domain
from agent_framework import (
    Agent,
    AgentExecutor,
    AgentExecutorResponse,
    Case,
    Default,
    Executor,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    handler,
)
from pydantic import BaseModel, ValidationError

WORKFLOW_NAME = "contoso-travel-expense-planner"
WORKFLOW_DESCRIPTION = (
    "Sequential intake -> policy -> planner -> approval workflow, backed by "
    "real Agent Framework agents calling the Foundry model, that produces a "
    "simulated travel pre-approval recommendation. Never performs a real "
    "approval or booking."
)

# Required environment variables for the production (non-test) chat client.
# FOUNDRY_PROJECT_ENDPOINT is populated by the Hosted Agent platform once
# deployed (see the microsoft-foundry skill's "Expected env-var fingerprint"
# reference); AZURE_AI_MODEL_DEPLOYMENT_NAME is set explicitly by
# scripts/deploy_hosted_agent.py (from the primary_model_deployment_name
# Terraform output) or, for a local run, by hand in .env (see .env.example).
ENV_FOUNDRY_PROJECT_ENDPOINT = "FOUNDRY_PROJECT_ENDPOINT"
ENV_AZURE_AI_MODEL_DEPLOYMENT_NAME = "AZURE_AI_MODEL_DEPLOYMENT_NAME"


# ---------------------------------------------------------------------------
# Structured-output contracts for each agent (agent_framework's native
# ``response_format`` mechanism: the SDK parses the model's JSON text into
# these Pydantic models automatically -- see ``ChatResponse.value`` /
# ``AgentResponse.value``). Kept minimal and role-specific.
# ---------------------------------------------------------------------------


class IntakeAgentOutput(BaseModel):
    """intake_agent's structured extraction of a trip request from user text.

    Mirrors ``domain.REQUIRED_FIELDS`` plus the optional ``traveler_count``.
    Any field the model could not find in the conversation must be omitted
    (or ``null``) -- ``domain.parse_trip_request`` is the deterministic
    source of truth for what counts as "missing".
    """

    origin: str | None = None
    destination: str | None = None
    departure_date: str | None = None
    return_date: str | None = None
    cabin_class: str | None = None
    purpose: str | None = None
    traveler_count: int | None = None


class NarrativeAgentOutput(BaseModel):
    """Shared structured-output contract for the three narrative agents.

    Each of policy_agent/planner_agent/approval_agent is asked to produce
    exactly one short, fact-grounded Japanese sentence on top of an
    already-computed deterministic result -- never new numbers, never a real
    approval/booking claim.
    """

    narrative_ja: str


INTAKE_INSTRUCTIONS = (
    "You are intake_agent in a Contoso travel pre-approval simulation. "
    "Read the conversation and extract a structured trip request. Respond "
    "with ONLY a JSON object matching the given schema "
    "(origin, destination, departure_date as YYYY-MM-DD, return_date as "
    "YYYY-MM-DD, cabin_class as one of economy/premium_economy/business/"
    "first, purpose, traveler_count). If the user has provided a field in an "
    "earlier turn of this same conversation, carry it forward even if the "
    "latest message only supplies the remaining field(s). Omit (set to null) "
    "any field you cannot find anywhere in the conversation -- never guess "
    "or invent a value. Never state that a trip has been booked or approved."
)

POLICY_INSTRUCTIONS = (
    "You are policy_agent in a Contoso travel pre-approval simulation. You "
    "will be given a trip request and the deterministic policy-check result "
    "already computed for it (international/domestic, cabin-class "
    "allowance, and manager/VP preapproval flags, with policy citations). "
    "Respond with ONLY a JSON object matching the given schema: "
    "narrative_ja must be exactly one short, natural Japanese sentence that "
    "restates those already-decided facts for a traveler. Do not invent new "
    "facts, numbers, or policy citations, and never claim a real approval "
    "was granted -- this is always a simulation."
)

PLANNER_INSTRUCTIONS = (
    "You are planner_agent in a Contoso travel pre-approval simulation. You "
    "will be given a trip request and the deterministic illustrative cost "
    "plan already computed for it (flight/lodging/meal estimates in JPY, "
    "nights, total). Respond with ONLY a JSON object matching the given "
    "schema: narrative_ja must be exactly one short, natural Japanese "
    "sentence summarizing that already-computed estimate for a traveler. Do "
    "not invent or recompute any number -- use only the figures you were "
    "given, and never claim a real booking was made."
)

APPROVAL_INSTRUCTIONS = (
    "You are approval_agent in a Contoso travel pre-approval simulation. You "
    "will be given a trip request, policy check, cost plan, and the "
    "deterministic simulated approval decision already made for it "
    "(whether preapproval is required, and by whom). Respond with ONLY a "
    "JSON object matching the given schema: narrative_ja must be exactly "
    "one short, natural Japanese sentence presenting that already-decided "
    "recommendation to the traveler. Never state that a real approval or "
    "booking occurred -- always frame this as a training simulation."
)


# ---------------------------------------------------------------------------
# Internal message envelopes threaded between executors.
#
# All decision-critical logic and numbers come from the pure domain.*
# functions; the *_narrative_ja fields are the LLM-authored gloss layered on
# top of an already-final, deterministic result.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _PolicyBundle:
    request: domain.TripRequest
    policy: domain.PolicyCheckResult
    policy_narrative_ja: str


@dataclass(frozen=True)
class _PlanBundle:
    request: domain.TripRequest
    policy: domain.PolicyCheckResult
    cost_plan: domain.CostPlan
    policy_narrative_ja: str
    planner_narrative_ja: str


@dataclass(frozen=True)
class _FinalBundle:
    request: domain.TripRequest
    policy: domain.PolicyCheckResult
    cost_plan: domain.CostPlan
    decision: domain.ApprovalDecision
    policy_narrative_ja: str
    planner_narrative_ja: str
    approval_narrative_ja: str


def _structured_value(response: AgentExecutorResponse, model: type[BaseModel]) -> BaseModel | None:
    """Safely read ``response.agent_response.value``.

    ``ChatResponse.value``/``AgentResponse.value`` lazily calls
    ``model.model_validate_json(text)`` the first time it is accessed (see
    ``agent_framework._types._parse_structured_response_value``) and raises
    ``pydantic.ValidationError`` if the model's text is not valid JSON
    matching the schema. Callers here always have a safe, deterministic
    fallback (treat the field(s) as missing/absent), so this narrowly
    catches only that specific, expected exception -- never a bare
    ``except Exception``.
    """
    try:
        value = response.agent_response.value
    except ValidationError:
        return None
    return value if isinstance(value, model) else None


# ---------------------------------------------------------------------------
# intake_agent -- a real Agent Framework AgentExecutor, backed by a
# FoundryChatClient-powered Agent, as the literal workflow start_executor.
# ---------------------------------------------------------------------------


def _build_intake_agent_executor(chat_client: Any) -> AgentExecutor:
    """Wrap a real ``Agent`` (structured-output extraction) as an
    ``AgentExecutor`` -- the literal ``start_executor`` of the workflow graph.

    ``AgentExecutor``'s default ``context_mode="full"`` threads the full
    conversation history (across separate top-level turns sharing the same
    ``AgentSession``, e.g. a Playground multi-turn conversation) into every
    call, which is what lets intake_agent combine a field supplied in an
    earlier turn with one supplied in the current turn -- see
    ``run_workflow_agent_turns`` and
    ``tests/contract/hosted_agent/test_workflow_agents.py`` for a test that
    proves this empirically with a fake chat client.
    """
    agent = Agent(
        client=chat_client,
        name="intake_agent",
        instructions=INTAKE_INSTRUCTIONS,
        default_options={"response_format": IntakeAgentOutput},
    )
    return AgentExecutor(agent, id="intake_agent")


class IntakeGateExecutor(Executor):
    """Deterministic bridge: ``AgentExecutorResponse`` -> ``IntakeResult``.

    intake_agent's job ends at structured field extraction; every decision
    about what counts as "missing" or "invalid" is made by the pure
    ``domain.parse_trip_request`` (unchanged from before this module used a
    real agent), so the missing-information branch stays fully deterministic
    and testable without ever depending on the model behaving a particular
    way.
    """

    def __init__(self, id: str = "intake_gate") -> None:
        super().__init__(id=id)

    @handler
    async def handle(
        self, response: AgentExecutorResponse, ctx: WorkflowContext[domain.IntakeResult]
    ) -> None:
        value = _structured_value(response, IntakeAgentOutput)
        raw: dict[str, Any] = value.model_dump(exclude_none=True) if value is not None else {}
        result = domain.parse_trip_request(raw)
        await ctx.send_message(result)


class MissingInfoResponder(Executor):
    """Terminal branch: asks the user for the fields intake_agent could not find."""

    def __init__(self, id: str = "missing_info_responder") -> None:
        super().__init__(id=id)

    @handler
    async def handle(self, result: domain.IntakeResult, ctx: WorkflowContext[Never, str]) -> None:
        # json.dumps (not str()) is required here: agent_framework's
        # WorkflowAgent._extract_contents wraps a yielded str as Content
        # verbatim, but falls back to Python's str()/repr for any other
        # type -- which is not valid JSON. See README.md's "Structured
        # output over Responses" section and
        # tests/contract/hosted_agent/test_workflow_agents.py.
        await ctx.yield_output(json.dumps(domain.missing_info_response(result), ensure_ascii=False))


# ---------------------------------------------------------------------------
# policy_agent / planner_agent / approval_agent -- each a custom Executor
# holding a real Agent (same chat client, distinct instructions/name/
# response_format), invoked directly inside the executor's own handler. This
# is the same underlying mechanism AgentExecutor itself uses internally
# (Agent.run against a chat client); it is used here instead of a second/
# third/fourth AgentExecutor graph node purely so the already-final,
# deterministic domain.* bundle keeps flowing between executors as ordinary
# Python dataclasses (see module docstring's "Architecture" note and
# README.md), rather than needing every hop to re-derive or have the model
# echo back numbers it must not be trusted to reproduce exactly.
# ---------------------------------------------------------------------------


async def _run_narrative_agent(agent: Agent, prompt: str) -> str:
    response = await agent.run(prompt)
    value = response.value
    if isinstance(value, NarrativeAgentOutput):
        return value.narrative_ja
    # Fall back to the raw text if structured parsing didn't yield the
    # expected model (e.g. a non-compliant fake client in a test) -- the
    # narrative is cosmetic, never branch-critical, so this never blocks the
    # deterministic pipeline.
    return response.text


class PolicyExecutor(Executor):
    """Checks the structured request against the bundled synthetic policy
    excerpt (``domain.check_policy``, deterministic), then asks the real
    policy_agent to write a short grounded Japanese narrative on top of it.
    """

    def __init__(self, chat_client: Any, id: str = "policy_agent") -> None:
        super().__init__(id=id)
        self._agent = Agent(
            client=chat_client,
            name="policy_agent",
            instructions=POLICY_INSTRUCTIONS,
            default_options={"response_format": NarrativeAgentOutput},
        )

    @handler
    async def handle(
        self, result: domain.IntakeResult, ctx: WorkflowContext[_PolicyBundle]
    ) -> None:
        # The missing-information switch-case guarantees only complete
        # results reach this executor.
        request = result.request
        assert request is not None, "policy_agent reached with an incomplete IntakeResult"
        policy = domain.check_policy(request)
        narrative_ja = await _run_narrative_agent(
            self._agent,
            "Trip request: "
            f"{request.origin} -> {request.destination}, cabin_class={request.cabin_class}. "
            f"Deterministic policy check: is_international={policy.is_international}, "
            f"cabin_class_allowed={policy.cabin_class_allowed}, "
            f"requires_manager_preapproval={policy.requires_manager_preapproval}, "
            f"requires_vp_preapproval={policy.requires_vp_preapproval}, "
            f"reasons={list(policy.reasons)}, citations={list(policy.citations)}.",
        )
        await ctx.send_message(
            _PolicyBundle(request=request, policy=policy, policy_narrative_ja=narrative_ja)
        )


# ---------------------------------------------------------------------------
# planner_agent
# ---------------------------------------------------------------------------


class PlannerExecutor(Executor):
    """Builds an illustrative cost plan for the trip (``domain.estimate_cost``,
    deterministic), then asks the real planner_agent to write a short
    grounded Japanese narrative on top of it."""

    def __init__(self, chat_client: Any, id: str = "planner_agent") -> None:
        super().__init__(id=id)
        self._agent = Agent(
            client=chat_client,
            name="planner_agent",
            instructions=PLANNER_INSTRUCTIONS,
            default_options={"response_format": NarrativeAgentOutput},
        )

    @handler
    async def handle(self, bundle: _PolicyBundle, ctx: WorkflowContext[_PlanBundle]) -> None:
        cost_plan = domain.estimate_cost(bundle.request, bundle.policy)
        narrative_ja = await _run_narrative_agent(
            self._agent,
            "Deterministic illustrative cost plan (JPY): "
            f"nights={cost_plan.nights}, is_day_trip={cost_plan.is_day_trip}, "
            f"flight_estimate_jpy={cost_plan.flight_estimate_jpy}, "
            f"lodging_estimate_jpy={cost_plan.lodging_estimate_jpy}, "
            f"meal_estimate_jpy={cost_plan.meal_estimate_jpy}, "
            f"total_estimate_jpy={cost_plan.total_estimate_jpy}, notes={list(cost_plan.notes)}.",
        )
        await ctx.send_message(
            _PlanBundle(
                request=bundle.request,
                policy=bundle.policy,
                cost_plan=cost_plan,
                policy_narrative_ja=bundle.policy_narrative_ja,
                planner_narrative_ja=narrative_ja,
            )
        )


# ---------------------------------------------------------------------------
# approval_agent
# ---------------------------------------------------------------------------


class ApprovalExecutor(Executor):
    """Produces the final *simulated* pre-approval recommendation
    (``domain.decide_approval``, deterministic), then asks the real
    approval_agent to write a short grounded Japanese narrative on top of it.
    """

    def __init__(self, chat_client: Any, id: str = "approval_agent") -> None:
        super().__init__(id=id)
        self._agent = Agent(
            client=chat_client,
            name="approval_agent",
            instructions=APPROVAL_INSTRUCTIONS,
            default_options={"response_format": NarrativeAgentOutput},
        )

    @handler
    async def handle(self, bundle: _PlanBundle, ctx: WorkflowContext[_FinalBundle]) -> None:
        decision = domain.decide_approval(bundle.request, bundle.policy, bundle.cost_plan)
        narrative_ja = await _run_narrative_agent(
            self._agent,
            "Deterministic simulated approval decision: "
            f"requires_preapproval={decision.requires_preapproval}, "
            f"approvers={list(decision.approvers)}, reasons={list(decision.reasons)}. "
            "This is always a simulation -- never state a real approval or booking "
            "occurred.",
        )
        await ctx.send_message(
            _FinalBundle(
                request=bundle.request,
                policy=bundle.policy,
                cost_plan=bundle.cost_plan,
                decision=decision,
                policy_narrative_ja=bundle.policy_narrative_ja,
                planner_narrative_ja=bundle.planner_narrative_ja,
                approval_narrative_ja=narrative_ja,
            )
        )


def _terminal_response(bundle: _FinalBundle) -> dict[str, Any]:
    """Build the terminal structured output, augmented with the three real
    agents' narrative text (see module docstring's "Architecture" note)."""
    result = domain.final_response(bundle.request, bundle.policy, bundle.cost_plan, bundle.decision)
    result["agent_narratives"] = {
        "policy_agent_ja": bundle.policy_narrative_ja,
        "planner_agent_ja": bundle.planner_narrative_ja,
        "approval_agent_ja": bundle.approval_narrative_ja,
    }
    return result


class ApprovalRequiredResponder(Executor):
    """Terminal branch: the trip needs a (simulated) manager/VP preapproval."""

    def __init__(self, id: str = "approval_required_responder") -> None:
        super().__init__(id=id)

    @handler
    async def handle(self, bundle: _FinalBundle, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(json.dumps(_terminal_response(bundle), ensure_ascii=False))


class AutoWithinPolicyResponder(Executor):
    """Terminal branch: the trip is within policy without further preapproval."""

    def __init__(self, id: str = "auto_within_policy_responder") -> None:
        super().__init__(id=id)

    @handler
    async def handle(self, bundle: _FinalBundle, ctx: WorkflowContext[Never, str]) -> None:
        await ctx.yield_output(json.dumps(_terminal_response(bundle), ensure_ascii=False))


def _default_chat_client() -> Any:
    """Construct the real Foundry-backed chat client used in production.

    Deliberately imports ``agent_framework_foundry``/``azure.identity``
    lazily, and only runs when ``build_workflow()`` is called with no
    explicit ``chat_client`` override (i.e. from ``main.py`` -- production,
    or an isolated-venv smoke test; see README.md's "Two Python
    environments"). Every unit/contract test injects a fake chat client, so
    this path -- and therefore this import -- is never exercised by
    ``pytest tests/`` in this repo's main (deploy-side) virtual environment,
    which does not have ``agent-framework-foundry`` installed (its
    ``azure-ai-projects<2.4.0`` constraint conflicts with the
    ``azure-ai-projects>=2.5.0`` the deploy scripts require).

    ``DefaultAzureCredential`` (not ``AzureCliCredential``) is used here on
    purpose: locally it still resolves to the participant's ``az login``
    session (the workshop's only supported auth method), but once deployed
    to a Hosted Agent container it also transparently picks up the
    platform's managed identity -- there is no interactive ``az login``
    inside the running container.
    """
    from agent_framework_foundry import FoundryChatClient
    from azure.identity import DefaultAzureCredential

    endpoint = os.environ.get(ENV_FOUNDRY_PROJECT_ENDPOINT)
    model = os.environ.get(ENV_AZURE_AI_MODEL_DEPLOYMENT_NAME)
    missing = [
        name
        for name, value in (
            (ENV_FOUNDRY_PROJECT_ENDPOINT, endpoint),
            (ENV_AZURE_AI_MODEL_DEPLOYMENT_NAME, model),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s) for the Foundry-backed chat "
            f"client: {', '.join(missing)}. FOUNDRY_PROJECT_ENDPOINT is normally "
            "injected automatically once this agent is deployed as a Hosted Agent; "
            "for a local run, copy .env.example to .env and set both (see "
            "README.md and labs/07-hosted-multi-agent.md)."
        )
    return FoundryChatClient(
        project_endpoint=endpoint, model=model, credential=DefaultAzureCredential()
    )


def build_workflow(*, chat_client: Any | None = None) -> Any:
    """Construct the sequential workflow with its two branches.

    ``chat_client`` is any object implementing ``agent_framework``'s
    ``SupportsChatGetResponse`` protocol (an async ``get_response(messages,
    *, options=None, ...)`` method). Tests always pass a scripted fake
    client here. When omitted, :func:`_default_chat_client` builds the real
    ``FoundryChatClient`` from environment variables (production use only).

    Returns an ``agent_framework.Workflow`` (typed ``Any`` here to avoid a
    hard import-time dependency on the exact SDK-internal return type name).
    """
    client = chat_client if chat_client is not None else _default_chat_client()

    intake = _build_intake_agent_executor(client)
    intake_gate = IntakeGateExecutor()
    missing_info = MissingInfoResponder()
    policy = PolicyExecutor(client)
    planner = PlannerExecutor(client)
    approval = ApprovalExecutor(client)
    approval_required = ApprovalRequiredResponder()
    auto_within_policy = AutoWithinPolicyResponder()

    builder = WorkflowBuilder(
        name=WORKFLOW_NAME,
        description=WORKFLOW_DESCRIPTION,
        start_executor=intake,
        output_from=[missing_info, approval_required, auto_within_policy],
    )

    # intake_agent (real Agent) -> intake_gate (deterministic bridge).
    builder.add_edge(intake, intake_gate)

    # Branch 1: missing-information. intake_gate's IntakeResult routes to
    # missing_info_responder when incomplete, otherwise (default) continues
    # the sequential chain into policy_agent.
    builder.add_switch_case_edge_group(
        intake_gate,
        [
            Case(condition=lambda result: not result.is_complete, target=missing_info),
            Default(target=policy),
        ],
    )

    # Sequential core: policy_agent -> planner_agent -> approval_agent.
    builder.add_edge(policy, planner)
    builder.add_edge(planner, approval)

    # Branch 2: over-threshold/approval. approval_agent's ApprovalDecision
    # routes to approval_required_responder when a (simulated) preapproval
    # is needed, otherwise (default) to auto_within_policy_responder.
    builder.add_switch_case_edge_group(
        approval,
        [
            Case(
                condition=lambda bundle: bundle.decision.requires_preapproval,
                target=approval_required,
            ),
            Default(target=auto_within_policy),
        ],
    )

    return builder.build()


def run_workflow_once(user_text: str, *, chat_client: Any | None = None) -> dict[str, Any]:
    """Run the workflow once with a single user turn and return its output.

    Convenience wrapper used by local smoke tests and unit/contract tests.
    With a fake ``chat_client``, requires no Azure credentials, network
    access, or model deployment.
    """

    async def _run() -> dict[str, Any]:
        workflow = build_workflow(chat_client=chat_client)
        result = await workflow.run([Message("user", [user_text])])
        outputs = result.get_outputs()
        if not outputs:
            raise RuntimeError("Workflow completed without yielding a structured output.")
        return json.loads(outputs[-1])  # type: ignore[no-any-return]

    return asyncio.run(_run())


def run_workflow_agent_turns(user_texts: list[str], *, chat_client: Any | None = None) -> list[str]:
    """Run the workflow *as an agent* (the same ``WorkflowAgent`` code path
    ``ResponsesHostServer``/``main.py`` uses) across one or more sequential
    turns sharing a single conversation session, returning each turn's raw
    ``AgentResponse.text``.

    This is the seam used to (a) prove the served output round-trips as
    valid JSON (``json.loads(text)`` on turn 1, item 1's regression test),
    and (b) empirically test multi-turn behavior (item 6): whether
    intake_agent can complete a request using a field supplied in an earlier
    turn plus one supplied in a later turn of the *same* conversation.
    """
    from agent_framework import AgentSession

    async def _run() -> list[str]:
        workflow = build_workflow(chat_client=chat_client)
        agent = workflow.as_agent(name=WORKFLOW_NAME, description=WORKFLOW_DESCRIPTION)
        session = AgentSession()
        outputs: list[str] = []
        for text in user_texts:
            response = await agent.run(text, session=session)
            outputs.append(response.text)
        return outputs

    return asyncio.run(_run())

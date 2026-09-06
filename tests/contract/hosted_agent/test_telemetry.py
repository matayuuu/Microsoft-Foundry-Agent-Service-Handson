"""Real framework spans with an in-memory exporter and no model/network calls."""

from __future__ import annotations

import asyncio

import pytest
from agent_framework.observability import ChatTelemetryLayer
from fakes import REVIEWER_RESPONSE, ScriptedChatClient
from opentelemetry import trace
from workflow import SAMPLE_REQUEST, WORKFLOW_NAME, build_workflow


class InstrumentedScriptedChatClient(ChatTelemetryLayer, ScriptedChatClient):
    """Use the same SDK telemetry layer as FoundryChatClient, not handmade spans."""

    model = "scripted-test-model"


@pytest.mark.parametrize("stream", [False, True])
def test_complete_workflow_trace_preserves_three_agent_hierarchy(
    monkeypatch: pytest.MonkeyPatch, stream: bool
) -> None:
    trace_sdk = pytest.importorskip(
        "opentelemetry.sdk.trace",
        reason="The telemetry SDK is installed by src/hosted-agent/requirements.txt, not root dev.",
    )
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_on")
    exporter = InMemorySpanExporter()
    provider = trace_sdk.TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    # Avoid replacing OpenTelemetry's process-wide write-once provider in the test suite.
    monkeypatch.setattr(trace, "get_tracer_provider", lambda: provider)
    client = InstrumentedScriptedChatClient()
    agent = build_workflow(chat_client=client).as_agent(name=WORKFLOW_NAME)

    async def run() -> str:
        with trace.get_tracer("test-host").start_as_current_span("hosted-request"):
            if stream:
                return "".join(
                    [update.text async for update in agent.run(SAMPLE_REQUEST, stream=True)]
                )
            return (await agent.run(SAMPLE_REQUEST)).text

    try:
        assert asyncio.run(run()) == REVIEWER_RESPONSE
        spans = exporter.get_finished_spans()
        workflows = [span for span in spans if span.name == "workflow.run"]
        assert len(workflows) == 1
        workflow_span = workflows[0]
        host_span = next(span for span in spans if span.name == "hosted-request")
        assert workflow_span.parent.span_id == host_span.context.span_id

        agent_spans = sorted(
            (span for span in spans if span.name.startswith("invoke_agent ")),
            key=lambda span: span.start_time,
        )
        assert [span.name for span in agent_spans] == [
            "invoke_agent policy_agent",
            "invoke_agent planner_agent",
            "invoke_agent reviewer_agent",
        ]
        chat_spans = [span for span in spans if span.name == "chat scripted-test-model"]
        assert len(chat_spans) == 3
        assert {span.parent.span_id for span in chat_spans} == {
            span.context.span_id for span in agent_spans
        }
        for name, agent_span in zip(client.created_agents, agent_spans, strict=True):
            executor_span = next(span for span in spans if span.name == f"executor.process {name}")
            assert agent_span.parent.span_id == executor_span.context.span_id
            assert executor_span.parent.span_id == workflow_span.context.span_id
        assert {span.context.trace_id for span in [workflow_span, *agent_spans, *chat_spans]} == {
            host_span.context.trace_id
        }
    finally:
        provider.shutdown()

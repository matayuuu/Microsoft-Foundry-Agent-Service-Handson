"""Network-free contracts for Responses host startup."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

_MAIN_PATH = Path(__file__).resolve().parents[3] / "src" / "hosted-agent" / "main.py"


@pytest.mark.parametrize("configured_sampler", [None, "parentbased_always_on", "always_off"])
def test_sampling_is_configured_before_workflow_and_host_creation(
    monkeypatch: pytest.MonkeyPatch, configured_sampler: str | None
) -> None:
    if configured_sampler is None:
        monkeypatch.delenv("OTEL_TRACES_SAMPLER", raising=False)
    else:
        monkeypatch.setenv("OTEL_TRACES_SAMPLER", configured_sampler)
    monkeypatch.setenv("OTEL_TRACES_SAMPLER_ARG", "0.25")
    expected_sampler = configured_sampler or "always_on"
    events: list[str] = []
    workflow = Mock()
    host = Mock()

    def build_workflow() -> Mock:
        assert os.environ["OTEL_TRACES_SAMPLER"] == expected_sampler
        events.append("build")
        return workflow

    def create_host(agent: object) -> Mock:
        assert agent is workflow.as_agent.return_value
        assert os.environ["OTEL_TRACES_SAMPLER"] == expected_sampler
        events.append("host")
        return host

    hosting_module = ModuleType("agent_framework_foundry_hosting")
    hosting_module.ResponsesHostServer = create_host  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "agent_framework_foundry_hosting", hosting_module)
    spec = importlib.util.spec_from_file_location("hosted_agent_main", _MAIN_PATH)
    assert spec is not None and spec.loader is not None
    main = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main)
    monkeypatch.setattr(main, "build_workflow", build_workflow)

    main.main()

    assert events == ["build", "host"]
    workflow.as_agent.assert_called_once_with(
        name=main.WORKFLOW_NAME, description=main.WORKFLOW_DESCRIPTION
    )
    host.run.assert_called_once_with()
    assert os.environ["OTEL_TRACES_SAMPLER_ARG"] == "0.25"

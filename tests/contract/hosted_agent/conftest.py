"""Make src/hosted-agent importable without installing it (contract tests).

See tests/unit/hosted_agent/conftest.py for the rationale; duplicated here
because pytest conftest.py discovery is directory-scoped, not shared across
tests/unit and tests/contract.
"""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_HOSTED_AGENT_SRC = _REPO_ROOT / "src" / "hosted-agent"
if str(_HOSTED_AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(_HOSTED_AGENT_SRC))

from fakes import ScriptedChatClient  # noqa: E402  (path must be set up first)


@pytest.fixture
def chat_client() -> ScriptedChatClient:
    """A fresh scripted fake chat client for a single test.

    Injected into ``build_workflow``/``run_workflow_once``/
    ``run_workflow_agent_turns`` so every contract test in this package runs
    the real ``agent_framework`` ``Agent``/``AgentExecutor``/
    ``WorkflowBuilder`` code paths without Azure credentials, network
    access, or a real model deployment. See ``fakes.py``.
    """
    return ScriptedChatClient()

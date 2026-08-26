"""Unit tests for scripts/deploy_hosted_agent.py.

scripts/ is intentionally not a Python package (see scripts/lib), so the
module under test is loaded directly from its file path via importlib,
matching tests/unit/test_create_toolbox.py. No live Azure credential,
azure-ai-projects network call, or real zip file on disk is required: the
zip/ignore-pattern logic is exercised against a real temporary directory
(fast, no mocking needed for pure filesystem operations), and the SDK call
sequence is exercised against a simple fake ``agents`` operations object.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest
from azure.ai.projects.models import AgentVersionStatus

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "deploy_hosted_agent.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("deploy_hosted_agent", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


deploy_hosted_agent = _load_module()


# ---------------------------------------------------------------------------
# parse_ignore_patterns
# ---------------------------------------------------------------------------


def test_parse_ignore_patterns_skips_blank_lines_and_comments() -> None:
    text = "\n# a comment\n\n*.log\n  \nvenv/\n"

    assert deploy_hosted_agent.parse_ignore_patterns(text) == ["*.log", "venv/"]


def test_parse_ignore_patterns_rejects_negation() -> None:
    with pytest.raises(deploy_hosted_agent.WorkshopContextError, match="negation"):
        deploy_hosted_agent.parse_ignore_patterns("!keep_me.txt")


def test_parse_ignore_patterns_rejects_double_star() -> None:
    with pytest.raises(deploy_hosted_agent.WorkshopContextError, match=r"\*\*"):
        deploy_hosted_agent.parse_ignore_patterns("**/node_modules/")


# ---------------------------------------------------------------------------
# is_ignored
# ---------------------------------------------------------------------------


def test_is_ignored_matches_basename_glob_anywhere() -> None:
    assert deploy_hosted_agent.is_ignored("a/b/c.log", ["*.log"])
    assert deploy_hosted_agent.is_ignored("c.log", ["*.log"])
    assert not deploy_hosted_agent.is_ignored("c.txt", ["*.log"])


def test_is_ignored_matches_directory_pattern_at_any_depth() -> None:
    assert deploy_hosted_agent.is_ignored("__pycache__/x.pyc", ["__pycache__/"])
    assert deploy_hosted_agent.is_ignored("a/__pycache__/x.pyc", ["__pycache__/"])
    assert not deploy_hosted_agent.is_ignored("__pycache__.py", ["__pycache__/"])


def test_is_ignored_full_path_pattern_requires_exact_relative_match() -> None:
    assert deploy_hosted_agent.is_ignored("agent.yaml", ["agent.yaml"])
    assert not deploy_hosted_agent.is_ignored("sub/agent.yaml", ["nested/agent.yaml"])


# ---------------------------------------------------------------------------
# iter_source_files / validate_required_files / build_zip_bytes / sha256_hex
# ---------------------------------------------------------------------------


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_iter_source_files_excludes_ignored_and_sorts(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "print(1)")
    _write(tmp_path / "requirements.txt", "agent-framework-core==1.14.0")
    _write(tmp_path / "domain.py", "x = 1")
    _write(tmp_path / "workflow.py", "y = 2")
    _write(tmp_path / "__pycache__" / "main.cpython-313.pyc", "junk")
    _write(tmp_path / ".env", "SECRET=1")

    patterns = ["__pycache__/", ".env"]
    files = deploy_hosted_agent.iter_source_files(tmp_path, patterns)
    relatives = [f.relative_to(tmp_path).as_posix() for f in files]

    assert relatives == sorted(relatives)
    assert "__pycache__/main.cpython-313.pyc" not in relatives
    assert ".env" not in relatives
    assert "main.py" in relatives


def test_validate_required_files_raises_when_missing(tmp_path: Path) -> None:
    _write(tmp_path / "main.py")

    with pytest.raises(deploy_hosted_agent.WorkshopContextError, match=r"requirements\.txt"):
        deploy_hosted_agent.validate_required_files(tmp_path, [tmp_path / "main.py"])


def test_validate_required_files_passes_when_all_present(tmp_path: Path) -> None:
    files = []
    for name in deploy_hosted_agent.REQUIRED_SOURCE_FILES:
        path = tmp_path / name
        _write(path)
        files.append(path)

    deploy_hosted_agent.validate_required_files(tmp_path, files)  # must not raise


def test_build_zip_bytes_contains_relative_arcnames(tmp_path: Path) -> None:
    _write(tmp_path / "main.py", "print('hi')")
    sub = tmp_path / "sub"
    _write(sub / "nested.txt", "nested")

    files = [tmp_path / "main.py", sub / "nested.txt"]
    zip_bytes = deploy_hosted_agent.build_zip_bytes(tmp_path, files)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = set(archive.namelist())
    assert names == {"main.py", "sub/nested.txt"}


def test_build_zip_stream_exposes_zip_filename() -> None:
    stream = deploy_hosted_agent.build_zip_stream(b"zip-data", "planner.zip")

    assert stream.name == "planner.zip"
    assert stream.read() == b"zip-data"


def test_build_zip_stream_rejects_non_zip_filename() -> None:
    with pytest.raises(deploy_hosted_agent.WorkshopContextError, match=r"must end with '\.zip'"):
        deploy_hosted_agent.build_zip_stream(b"zip-data", "planner.bin")


def test_sha256_hex_is_deterministic() -> None:
    a = deploy_hosted_agent.sha256_hex(b"same bytes")
    b = deploy_hosted_agent.sha256_hex(b"same bytes")
    c = deploy_hosted_agent.sha256_hex(b"different bytes")

    assert a == b
    assert a != c
    assert len(a) == 64


# ---------------------------------------------------------------------------
# validate_cpu_memory
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cpu,memory", [("0.5", "1Gi"), ("1", "2Gi"), ("2", "4Gi")])
def test_validate_cpu_memory_accepts_documented_tiers(cpu: str, memory: str) -> None:
    deploy_hosted_agent.validate_cpu_memory(cpu, memory)  # must not raise


def test_validate_cpu_memory_rejects_undocumented_tier() -> None:
    with pytest.raises(deploy_hosted_agent.WorkshopContextError, match="unsupported"):
        deploy_hosted_agent.validate_cpu_memory("4", "8Gi")


def test_validate_cpu_memory_rejects_the_retired_quarter_cpu_tier() -> None:
    """0.25/0.5Gi was the smallest documented tier before the Hosted Agent
    platform's current minimum moved to 0.5/1Gi -- must now be rejected."""
    with pytest.raises(deploy_hosted_agent.WorkshopContextError, match="unsupported"):
        deploy_hosted_agent.validate_cpu_memory("0.25", "0.5Gi")


# ---------------------------------------------------------------------------
# build_definition
# ---------------------------------------------------------------------------


def test_build_definition_uses_remote_build_and_responses_protocol() -> None:
    definition = deploy_hosted_agent.build_definition(cpu="1", memory="2Gi")

    assert definition.cpu == "1"
    assert definition.memory == "2Gi"
    assert definition.code_configuration.runtime == "python_3_13"
    assert definition.code_configuration.entry_point == ["python", "main.py"]
    assert (
        str(definition.code_configuration.dependency_resolution)
        == "CodeDependencyResolution.REMOTE_BUILD"
    )
    assert len(definition.protocol_versions) == 1
    assert str(definition.protocol_versions[0].protocol) == "AgentEndpointProtocol.RESPONSES"
    assert definition.protocol_versions[0].version == "1.0.0"


def test_build_definition_passes_through_environment_variables() -> None:
    definition = deploy_hosted_agent.build_definition(
        cpu="1", memory="2Gi", environment_variables={"FOO": "bar"}
    )

    assert definition.environment_variables == {"FOO": "bar"}


# ---------------------------------------------------------------------------
# resolve_environment_variables (AZURE_AI_MODEL_DEPLOYMENT_NAME auto-injection)
# ---------------------------------------------------------------------------


def _context_with_model_deployment(name: str = "gpt-4o-mini") -> dict:
    return {
        "terraform_outputs": {
            "primary_model_deployment_name": {"value": name},
        }
    }


def test_resolve_environment_variables_auto_injects_model_deployment_name() -> None:
    result = deploy_hosted_agent.resolve_environment_variables(
        {}, context=_context_with_model_deployment("gpt-4o-mini")
    )

    assert result == {"AZURE_AI_MODEL_DEPLOYMENT_NAME": "gpt-4o-mini"}


def test_resolve_environment_variables_keeps_other_explicit_env_vars() -> None:
    result = deploy_hosted_agent.resolve_environment_variables(
        {"SOME_OTHER_VAR": "value"}, context=_context_with_model_deployment("gpt-4o-mini")
    )

    assert result == {
        "SOME_OTHER_VAR": "value",
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": "gpt-4o-mini",
    }


def test_resolve_environment_variables_explicit_override_wins() -> None:
    result = deploy_hosted_agent.resolve_environment_variables(
        {"AZURE_AI_MODEL_DEPLOYMENT_NAME": "explicit-override"},
        context=_context_with_model_deployment("gpt-4o-mini"),
    )

    assert result == {"AZURE_AI_MODEL_DEPLOYMENT_NAME": "explicit-override"}
    # The Terraform output must not even need to be present when overridden.


def test_resolve_environment_variables_never_sets_foundry_project_endpoint() -> None:
    """FOUNDRY_PROJECT_ENDPOINT is platform-injected -- this script must never
    set it, even implicitly, so it can't shadow the platform's own value."""
    result = deploy_hosted_agent.resolve_environment_variables(
        {}, context=_context_with_model_deployment("gpt-4o-mini")
    )

    assert "FOUNDRY_PROJECT_ENDPOINT" not in result


def test_resolve_environment_variables_raises_when_terraform_output_missing_and_no_override() -> (
    None
):
    context = {"terraform_outputs": {}}

    with pytest.raises(deploy_hosted_agent.WorkshopContextError):
        deploy_hosted_agent.resolve_environment_variables({}, context=context)


# ---------------------------------------------------------------------------
# poll_version (bounded, injected clock/sleep -- mirrors run_evaluation.py's
# poll_run test pattern)
# ---------------------------------------------------------------------------


class _FakeVersion:
    """Mirrors ``AgentVersionDetails``'s dict-like ``Model`` base (see
    ``scripts/deploy_hosted_agent.py``'s ``_extract_version_error``
    docstring): ``.get(key, default)`` reads the raw underlying data,
    returning ``None`` for a key that was never populated -- there is no
    statically declared ``.error`` attribute, only this dict-style access.
    """

    def __init__(self, status: object, version: str = "1", *, error: object = None) -> None:
        self.status = status
        self.version = version
        self._data = {"error": error} if error is not None else {}

    def get(self, key: str, default: object = None) -> object:
        return self._data.get(key, default)


def test_poll_version_returns_once_active() -> None:
    statuses = iter([_FakeVersion("creating"), _FakeVersion("creating"), _FakeVersion("active")])
    sleeps: list[float] = []

    result = deploy_hosted_agent.poll_version(
        retrieve=lambda: next(statuses),
        interval_seconds=1.0,
        timeout_seconds=100.0,
        sleep=sleeps.append,
        now=lambda: 0.0,
    )

    assert result.status == "active"
    assert sleeps == [1.0, 1.0]


def test_poll_version_returns_once_failed() -> None:
    statuses = iter([_FakeVersion("creating"), _FakeVersion("failed")])

    result = deploy_hosted_agent.poll_version(
        retrieve=lambda: next(statuses),
        interval_seconds=1.0,
        timeout_seconds=100.0,
        sleep=lambda _s: None,
        now=lambda: 0.0,
    )

    assert result.status == "failed"


def test_poll_version_accepts_sdk_status_enum() -> None:
    result = deploy_hosted_agent.poll_version(
        retrieve=lambda: _FakeVersion(AgentVersionStatus.ACTIVE),
        interval_seconds=1.0,
        timeout_seconds=100.0,
        sleep=lambda _s: None,
        now=lambda: 0.0,
    )

    assert result.status is AgentVersionStatus.ACTIVE


def test_poll_version_raises_on_timeout() -> None:
    clock = iter([0.0, 0.0, 50.0, 200.0])
    always_creating = lambda: _FakeVersion("creating")  # noqa: E731

    with pytest.raises(deploy_hosted_agent.WorkshopContextError, match="did not reach a terminal"):
        deploy_hosted_agent.poll_version(
            retrieve=always_creating,
            interval_seconds=10.0,
            timeout_seconds=100.0,
            sleep=lambda _s: None,
            now=lambda: next(clock),
        )


# ---------------------------------------------------------------------------
# build_result
# ---------------------------------------------------------------------------


def test_build_result_succeeded_when_active() -> None:
    context = {
        "terraform_outputs": {
            "foundry_portal_url": {"value": "https://ai.azure.com"},
            "ai_services_account_name": {"value": "acct-1"},
            "foundry_project_name": {"value": "proj-1"},
        }
    }
    version = _FakeVersion("active", version="3")

    result = deploy_hosted_agent.build_result(
        agent_name="contoso-travel-hosted-planner",
        version=version,
        context=context,
        endpoint="https://acct-1.services.ai.azure.com/api/projects/proj-1",
    )

    assert result["succeeded"] is True
    assert result["status"] == "active"
    assert result["version"] == "3"
    assert result["portal_url"] == "https://ai.azure.com"
    assert "failure_hint" not in result
    # No fabricated deep link: only portal_url plus identifiers are present.
    assert "playground_url" not in result


def test_build_result_normalizes_sdk_status_enum() -> None:
    context = {
        "terraform_outputs": {
            "foundry_portal_url": {"value": "https://ai.azure.com"},
            "ai_services_account_name": {"value": "acct-1"},
            "foundry_project_name": {"value": "proj-1"},
        }
    }

    result = deploy_hosted_agent.build_result(
        agent_name="contoso-travel-hosted-planner",
        version=_FakeVersion(AgentVersionStatus.ACTIVE, version="1"),
        context=context,
        endpoint="https://acct-1.services.ai.azure.com/api/projects/proj-1",
    )

    assert result["status"] == "active"
    assert result["succeeded"] is True


def test_build_result_includes_failure_hint_when_failed_without_structured_error() -> None:
    context = {
        "terraform_outputs": {
            "foundry_portal_url": {"value": "https://ai.azure.com"},
            "ai_services_account_name": {"value": "acct-1"},
            "foundry_project_name": {"value": "proj-1"},
        }
    }
    version = _FakeVersion("failed", version="4")

    result = deploy_hosted_agent.build_result(
        agent_name="contoso-travel-hosted-planner",
        version=version,
        context=context,
        endpoint="https://acct-1.services.ai.azure.com/api/projects/proj-1",
    )

    assert result["succeeded"] is False
    assert "failure_hint" in result
    assert "error" not in result


def test_build_result_surfaces_version_error_when_the_service_populates_one() -> None:
    """When the SDK's ``AgentVersionDetails.get("error")`` does return a
    populated ``error`` field, ``build_result`` must surface its structured
    detail instead of the generic 'no structured details' hint."""
    context = {
        "terraform_outputs": {
            "foundry_portal_url": {"value": "https://ai.azure.com"},
            "ai_services_account_name": {"value": "acct-1"},
            "foundry_project_name": {"value": "proj-1"},
        }
    }
    version = _FakeVersion(
        "failed",
        version="5",
        error={"code": "BuildFailed", "message": "requirements.txt could not be resolved"},
    )

    result = deploy_hosted_agent.build_result(
        agent_name="contoso-travel-hosted-planner",
        version=version,
        context=context,
        endpoint="https://acct-1.services.ai.azure.com/api/projects/proj-1",
    )

    assert result["succeeded"] is False
    assert "failure_hint" not in result
    assert result["error"] == {
        "code": "BuildFailed",
        "message": "requirements.txt could not be resolved",
    }


# ---------------------------------------------------------------------------
# _parse_env_pairs
# ---------------------------------------------------------------------------


def test_parse_env_pairs_builds_dict() -> None:
    assert deploy_hosted_agent._parse_env_pairs(["A=1", "B=two"]) == {"A": "1", "B": "two"}


def test_parse_env_pairs_rejects_missing_equals() -> None:
    with pytest.raises(deploy_hosted_agent.WorkshopContextError, match="KEY=VALUE"):
        deploy_hosted_agent._parse_env_pairs(["NOTKEYVALUE"])


def test_parse_env_pairs_rejects_empty_key() -> None:
    with pytest.raises(deploy_hosted_agent.WorkshopContextError, match="empty key"):
        deploy_hosted_agent._parse_env_pairs(["=value"])


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------


def test_parse_args_defaults() -> None:
    args = deploy_hosted_agent.parse_args([])

    assert args.agent_name == deploy_hosted_agent.DEFAULT_HOSTED_AGENT_NAME
    assert args.cpu == deploy_hosted_agent.DEFAULT_CPU
    assert args.memory == deploy_hosted_agent.DEFAULT_MEMORY
    assert args.output == "human"
    assert args.env == []


def test_parse_args_overrides() -> None:
    args = deploy_hosted_agent.parse_args(
        ["--agent-name", "custom-agent", "--cpu", "2", "--memory", "4Gi", "--output", "json"]
    )

    assert args.agent_name == "custom-agent"
    assert args.cpu == "2"
    assert args.memory == "4Gi"
    assert args.output == "json"

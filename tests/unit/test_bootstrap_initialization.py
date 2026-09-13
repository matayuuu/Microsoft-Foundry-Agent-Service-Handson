"""Initialization contracts: data writes are faked, never represented as live E2E."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from scripts import bootstrap_custom_template as bootstrap

CONTEXT_FILE = Path(__file__).resolve().parents[1] / "fixtures" / "workshop-context.json"


@pytest.fixture
def context() -> dict:
    value = json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
    value["setup_status"] = "infrastructure-ready"
    return value


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    shutil.copytree(bootstrap.REPO_ROOT / "data", root / "data")
    (root / "scripts").mkdir()
    for name in ("bootstrap_data.py", "run_evaluation.py", "validate_environment.py"):
        shutil.copyfile(bootstrap.REPO_ROOT / "scripts" / name, root / "scripts" / name)
    return root


class FakeAdapters:
    def __init__(self, root: Path, fail_at: str | None = None) -> None:
        self.root = root
        self.fail_at = fail_at
        self.commands: list[tuple[str, ...]] = []
        self.stages: list[str] = []
        self.context_states: list[str] = []

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        self.commands.append(tuple(command))
        name = Path(command[1]).name
        if name == "bootstrap_data.py":
            name += ":" + command[command.index("--index-name") + 1]
        self.stages.append(name)
        current = json.loads((self.root / ".workshop" / "context.json").read_text(encoding="utf-8"))
        self.context_states.append(current["setup_status"])
        if name == self.fail_at:
            return subprocess.CompletedProcess(command, 2, "", "HTTP 400 InvalidParameter")
        result = {}
        if name == "validate_environment.py":
            result = {"overall_status": "pass", "checks": [{"name": "fixture", "status": "pass"}]}
        elif name == "run_evaluation.py":
            result = {
                "status": "ready",
                "dataset": {"name": "fixture-dataset", "version": "1"},
                "rubric_evaluator": {"name": "fixture-rubric", "version": "1"},
            }
        return subprocess.CompletedProcess(command, 0, json.dumps(result), "")


def test_data_preparation_and_validation_gate_the_only_success_output(
    repository: Path, context: dict
) -> None:
    output_path = repository / "deployment-output.json"
    runner = FakeAdapters(repository)
    result = bootstrap.run_bootstrap(
        bootstrap.BootstrapInputs(context, output_path), root=repository, runner=runner
    )
    assert runner.stages == [
        "bootstrap_data.py:contoso-travel-policy",
        "bootstrap_data.py:contoso-travel-approval",
        "run_evaluation.py",
        "validate_environment.py",
    ]
    assert runner.context_states == ["infrastructure-ready"] * 4
    assert result == {"status": "complete", "source_revision": context["source_revision"]}
    assert json.loads(output_path.read_text(encoding="utf-8")) == result
    assert not list(repository.rglob("*.zip"))
    assert not (repository / ".workshop" / "toolbox").exists()
    assert "--prepare-only" in runner.commands[2]
    assert "--participant-object-id" in runner.commands[3]
    assert "storage" not in [argument for command in runner.commands for argument in command]


def test_plan_uses_each_manifest_partition_and_explicit_endpoints(
    repository: Path, context: dict
) -> None:
    manifest = bootstrap.verify_local_assets(repository)
    stages = bootstrap.plan_initialization(context, manifest, repository, "isolated-python")
    for stage, index in zip(stages[:2], manifest["search_indexes"], strict=True):
        assert stage.command[0] == "isolated-python"
        assert stage.command[stage.command.index("--index-name") + 1] == index["name"]
        assert stage.command[stage.command.index("--embedding-deployment") + 1] == "embedding"
        assert context["source_base"] in stage.command
    assert stages[2].name == "prepare-evaluation"
    assert "--prepare-only" in stages[2].command
    assert stages[-1].name == "validate-environment"
    assert not any(stage.name == "prepare-portal-assets" for stage in stages)


@pytest.mark.parametrize(
    "missing", ["WORKSHOP_SOURCE_REVISION", "WORKSHOP_CONTEXT_JSON", "AZ_SCRIPTS_OUTPUT_PATH"]
)
def test_all_runtime_inputs_are_required(tmp_path: Path, context: dict, missing: str) -> None:
    environment = {
        "WORKSHOP_SOURCE_REVISION": context["source_revision"],
        "WORKSHOP_CONTEXT_JSON": json.dumps(context),
        "AZ_SCRIPTS_OUTPUT_PATH": str(tmp_path / "out.json"),
    }
    environment.pop(missing)
    with pytest.raises(bootstrap.BootstrapError, match=missing):
        bootstrap.inputs_from_environment(environment)


def test_current_context_boundary_does_not_require_storage(tmp_path: Path, context: dict) -> None:
    inputs = bootstrap.inputs_from_environment(
        {
            "WORKSHOP_SOURCE_REVISION": context["source_revision"],
            "WORKSHOP_CONTEXT_JSON": json.dumps(context),
            "AZ_SCRIPTS_OUTPUT_PATH": str(tmp_path / "out.json"),
        }
    )
    assert inputs.context["schema_version"] == "2.0"
    assert len(inputs.context["resource_outputs"]) == 24


@pytest.mark.parametrize(
    "missing",
    [
        "scripts/bootstrap_data.py",
        "scripts/run_evaluation.py",
        "scripts/validate_environment.py",
        "data/manifest.json",
    ],
)
def test_missing_sources_fail_before_side_effects(
    repository: Path, context: dict, missing: str
) -> None:
    (repository / missing).unlink()
    runner = FakeAdapters(repository)
    with pytest.raises(bootstrap.BootstrapError, match="missing"):
        bootstrap.run_bootstrap(
            bootstrap.BootstrapInputs(context, repository / "out.json"),
            root=repository,
            runner=runner,
        )
    assert runner.commands == []


def test_tampered_data_fails_before_side_effects(repository: Path, context: dict) -> None:
    manifest = bootstrap.verify_local_assets(repository)
    document = bootstrap.bootstrap_data.iter_documents(manifest)[0]
    bootstrap.data_path(repository, document.path).write_text("tampered", encoding="utf-8")
    runner = FakeAdapters(repository)
    with pytest.raises(bootstrap.BootstrapError):
        bootstrap.run_bootstrap(
            bootstrap.BootstrapInputs(context, repository / "out.json"),
            root=repository,
            runner=runner,
        )
    assert runner.commands == []


@pytest.mark.parametrize(
    "stage",
    [
        "bootstrap_data.py:contoso-travel-policy",
        "bootstrap_data.py:contoso-travel-approval",
        "run_evaluation.py",
        "validate_environment.py",
    ],
)
def test_failed_stage_never_leaves_a_success_marker(
    repository: Path, context: dict, stage: str
) -> None:
    output = repository / "out.json"
    output.write_text('{"status":"complete"}', encoding="utf-8")
    runner = FakeAdapters(repository, fail_at=stage)
    with pytest.raises(bootstrap.BootstrapError):
        bootstrap.run_bootstrap(
            bootstrap.BootstrapInputs(context, output), root=repository, runner=runner
        )
    assert not output.exists()
    assert runner.stages.count(stage) == 1
    assert runner.context_states == ["infrastructure-ready"] * len(runner.stages)


def test_redeployment_reuses_the_same_data_adapter_contract(
    repository: Path, context: dict
) -> None:
    inputs = bootstrap.BootstrapInputs(context, repository / "out.json")
    first, second = FakeAdapters(repository), FakeAdapters(repository)
    assert bootstrap.run_bootstrap(
        inputs, root=repository, runner=first
    ) == bootstrap.run_bootstrap(inputs, root=repository, runner=second)
    assert first.commands == second.commands


def test_readiness_retries_are_bounded() -> None:
    attempts, sleeps = [], []

    def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        attempts.append(command)
        return subprocess.CompletedProcess(command, 1, "", "HTTP 403 Forbidden")

    with pytest.raises(bootstrap.BootstrapError, match="readiness retries exhausted"):
        bootstrap.execute_stage(
            bootstrap.Stage("seed-search", ("python", "seed")),
            runner,
            sleep=sleeps.append,
        )
    assert len(attempts) == 6
    assert sleeps == [10, 20, 40, 60, 60]


@pytest.mark.parametrize(
    "detail", ["HTTP 400 InvalidParameter", "missing manifest", "unknown error"]
)
def test_permanent_errors_are_not_retried(detail: str) -> None:
    calls, sleeps = [], []

    def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 2, "", detail)

    with pytest.raises(bootstrap.BootstrapError, match="permanent"):
        bootstrap.execute_stage(
            bootstrap.Stage("seed-search", ("python", "seed")), runner, sleep=sleeps.append
        )
    assert len(calls) == 1
    assert sleeps == []


@pytest.mark.parametrize("attempts", [0, 11, 999])
def test_unbounded_retry_policies_are_rejected(attempts: int) -> None:
    with pytest.raises(ValueError, match="attempts"):
        bootstrap.RetryPolicy(attempts=attempts)


@pytest.mark.parametrize(
    "report",
    [{}, {"overall_status": "warn", "checks": []}, {"overall_status": "pass", "checks": []}],
)
def test_zero_exit_does_not_replace_validation_evidence(report: dict) -> None:
    with pytest.raises(bootstrap.BootstrapError, match="validate-environment"):
        bootstrap.execute_stage(
            bootstrap.Stage("validate-environment", ("python", "validate")),
            lambda command: subprocess.CompletedProcess(command, 0, json.dumps(report), ""),
        )


def test_evaluation_prepare_response_must_confirm_assets() -> None:
    with pytest.raises(bootstrap.BootstrapError, match="prepare-evaluation"):
        bootstrap.execute_stage(
            bootstrap.Stage("prepare-evaluation", ("python", "evaluate")),
            lambda command: subprocess.CompletedProcess(command, 0, '{"status":"ready"}', ""),
        )


def test_validation_retry_requires_every_failure_to_be_retryable() -> None:
    transient = {"name": "role", "status": "fail", "retryable": True}
    permanent = {"name": "schema", "status": "fail", "retryable": False}
    assert bootstrap.validation_retryable(json.dumps({"checks": [transient]}))
    assert not bootstrap.validation_retryable(json.dumps({"checks": [transient, permanent]}))
    assert not bootstrap.validation_retryable("HTTP 503 without a report")


def test_process_timeouts_do_not_restart_prior_successful_stages() -> None:
    attempts, sleeps = [], []

    def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        attempts.append(command)
        if len(attempts) == 1:
            raise subprocess.TimeoutExpired(command, 10)
        return subprocess.CompletedProcess(
            command, 0, '{"overall_status":"pass","checks":[{"status":"pass"}]}', ""
        )

    bootstrap.execute_stage(
        bootstrap.Stage("validate-environment", ("python", "validate")),
        runner,
        sleep=sleeps.append,
    )
    assert len(attempts) == 2
    assert sleeps == [10]

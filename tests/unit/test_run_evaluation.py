"""Unit tests for scripts/run_evaluation.py.

scripts/ is intentionally not a Python package, so the module under test is
loaded directly from its file path via importlib, matching
tests/unit/test_validate_environment.py and tests/unit/test_create_toolbox.py.
No live Foundry project, Azure credential, or OpenAI Evals API network call
happens in this file: ``poll_run`` is exercised with an injected fake clock
and fake retrieve callback, and dataset/evaluator I/O adapters use simple
fakes instead of the real SDK client.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from azure.core.exceptions import ResourceNotFoundError

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "run_evaluation.py"
SCHEMA_PATH = REPO_ROOT / "data" / "schemas" / "eval_case.schema.json"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_evaluation", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


run_evaluation = _load_module()

REAL_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

VALID_CASE = {
    "id": "eval-001",
    "category": "direct_policy_fact",
    "query": "東京から大阪へ日帰り出張する場合、食事の日当はいくらですか?",
    "expected_behavior": "1,500円と回答する。",
    "ground_truth": "1,500円",
    "expected_citations": ["policy-per-diem-001"],
    "requires_citation": True,
    "v1_expected_outcome": "pass",
    "v2_expected_outcome": "pass",
    "v1_failure_mode": None,
    "notes": None,
}


# ---------------------------------------------------------------------------
# load_eval_cases
# ---------------------------------------------------------------------------


def test_load_eval_cases_raises_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(run_evaluation.WorkshopContextError, match="not found"):
        run_evaluation.load_eval_cases(tmp_path / "missing.jsonl", REAL_SCHEMA)


def test_load_eval_cases_parses_valid_rows(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(VALID_CASE, ensure_ascii=False) + "\n", encoding="utf-8")

    cases = run_evaluation.load_eval_cases(path, REAL_SCHEMA)

    assert len(cases) == 1
    assert cases[0]["id"] == "eval-001"


def test_load_eval_cases_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(
        json.dumps(VALID_CASE, ensure_ascii=False)
        + "\n\n"
        + json.dumps(VALID_CASE, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    cases = run_evaluation.load_eval_cases(path, REAL_SCHEMA)

    assert len(cases) == 2


def test_load_eval_cases_raises_on_invalid_json_with_line_number(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text("{not valid json\n", encoding="utf-8")

    with pytest.raises(run_evaluation.WorkshopContextError, match=r"cases\.jsonl:1"):
        run_evaluation.load_eval_cases(path, REAL_SCHEMA)


def test_load_eval_cases_raises_when_schema_violated(tmp_path: Path) -> None:
    invalid_case = dict(VALID_CASE)
    del invalid_case["expected_behavior"]
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(invalid_case, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(run_evaluation.WorkshopContextError, match="eval-001"):
        run_evaluation.load_eval_cases(path, REAL_SCHEMA)


def test_load_eval_cases_raises_when_file_has_no_rows(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text("\n\n", encoding="utf-8")

    with pytest.raises(run_evaluation.WorkshopContextError, match="no evaluation cases"):
        run_evaluation.load_eval_cases(path, REAL_SCHEMA)


def test_live_subset_fixture_is_itself_schema_valid() -> None:
    """The real data/eval/live_subset.jsonl shipped in the repo must load cleanly."""
    live_subset = REPO_ROOT / "data" / "eval" / "live_subset.jsonl"

    cases = run_evaluation.load_eval_cases(live_subset, REAL_SCHEMA)

    assert len(cases) > 0
    assert all("query" in case for case in cases)


# ---------------------------------------------------------------------------
# dataset_content_version
# ---------------------------------------------------------------------------


def test_dataset_content_version_is_stable_for_same_content(tmp_path: Path) -> None:
    path_a = tmp_path / "a.jsonl"
    path_b = tmp_path / "b.jsonl"
    path_a.write_text("same content\n", encoding="utf-8")
    path_b.write_text("same content\n", encoding="utf-8")

    assert run_evaluation.dataset_content_version(path_a) == run_evaluation.dataset_content_version(
        path_b
    )


def test_dataset_content_version_changes_with_content(tmp_path: Path) -> None:
    path_a = tmp_path / "a.jsonl"
    path_b = tmp_path / "b.jsonl"
    path_a.write_text("content one\n", encoding="utf-8")
    path_b.write_text("content two\n", encoding="utf-8")

    assert run_evaluation.dataset_content_version(path_a) != run_evaluation.dataset_content_version(
        path_b
    )


# ---------------------------------------------------------------------------
# build_rubric_definition / rubric_matches
# ---------------------------------------------------------------------------


def test_build_rubric_definition_has_pass_threshold_and_dimensions() -> None:
    definition = run_evaluation.build_rubric_definition(pass_threshold=0.7)

    assert definition.pass_threshold == 0.7
    assert len(definition.dimensions) >= 3
    assert all(1 <= d.weight <= 10 for d in definition.dimensions)


def test_rubric_matches_true_for_identical_definition() -> None:
    version_a = run_evaluation.build_rubric_evaluator_version(pass_threshold=0.6)
    version_b = run_evaluation.build_rubric_evaluator_version(pass_threshold=0.6)

    assert run_evaluation.rubric_matches(version_a, version_b)


def test_rubric_matches_false_when_pass_threshold_differs() -> None:
    version_a = run_evaluation.build_rubric_evaluator_version(pass_threshold=0.6)
    version_b = run_evaluation.build_rubric_evaluator_version(pass_threshold=0.9)

    assert not run_evaluation.rubric_matches(version_a, version_b)


def test_rubric_matches_false_when_dimension_weight_differs() -> None:
    version_a = run_evaluation.build_rubric_evaluator_version()
    version_b = run_evaluation.build_rubric_evaluator_version()
    version_b.definition.dimensions[0].weight = 1

    assert not run_evaluation.rubric_matches(version_a, version_b)


# ---------------------------------------------------------------------------
# build_data_source_config / build_testing_criteria / build_run_data_source
# ---------------------------------------------------------------------------


def test_build_data_source_config_is_custom_with_query_required() -> None:
    config = run_evaluation.build_data_source_config()

    assert config["type"] == "custom"
    assert "query" in config["item_schema"]["required"]


def test_build_testing_criteria_includes_rubric_first() -> None:
    # TestingCriterionAzureAIEvaluator is a TypedDict (from
    # azure.ai.projects.models._patch_evaluation_typeddicts): instances are
    # plain dicts, so criteria are asserted with subscript access, not
    # attribute access.
    criteria = run_evaluation.build_testing_criteria(
        rubric_evaluator_name="contoso-travel-rubric", judge_deployment="primary"
    )

    assert criteria[0]["evaluator_name"] == "contoso-travel-rubric"
    assert criteria[0]["initialization_parameters"] == {"deployment_name": "primary"}


def test_build_testing_criteria_includes_default_builtins() -> None:
    criteria = run_evaluation.build_testing_criteria(
        rubric_evaluator_name="contoso-travel-rubric", judge_deployment="primary"
    )

    evaluator_names = {c["evaluator_name"] for c in criteria}
    assert "builtin.task_adherence" in evaluator_names
    assert "builtin.coherence" in evaluator_names
    assert "builtin.violence" in evaluator_names


def test_build_testing_criteria_violence_has_no_judge_deployment() -> None:
    criteria = run_evaluation.build_testing_criteria(
        rubric_evaluator_name="contoso-travel-rubric", judge_deployment="primary"
    )

    violence = next(c for c in criteria if c["evaluator_name"] == "builtin.violence")
    assert violence["initialization_parameters"] is None


def test_build_testing_criteria_task_adherence_sees_full_response() -> None:
    criteria = run_evaluation.build_testing_criteria(
        rubric_evaluator_name="contoso-travel-rubric", judge_deployment="primary"
    )

    task_adherence = next(c for c in criteria if c["evaluator_name"] == "builtin.task_adherence")
    assert task_adherence["data_mapping"]["response"] == "{{sample.output_items}}"


def test_build_run_data_source_targets_agent_by_name() -> None:
    data_source = run_evaluation.build_run_data_source(
        dataset_id="dataset-123", agent_name="contoso-travel-assistant"
    )

    assert data_source["type"] == "azure_ai_target_completions"
    assert data_source["source"] == {"type": "file_id", "id": "dataset-123"}
    assert data_source["target"] == {"type": "azure_ai_agent", "name": "contoso-travel-assistant"}


def test_build_run_data_source_includes_version_when_given() -> None:
    data_source = run_evaluation.build_run_data_source(
        dataset_id="dataset-123", agent_name="contoso-travel-assistant", agent_version="3"
    )

    assert data_source["target"]["version"] == "3"


# ---------------------------------------------------------------------------
# poll_run (bounded, injected clock)
# ---------------------------------------------------------------------------


def test_poll_run_returns_immediately_if_already_terminal() -> None:
    run = SimpleNamespace(status="completed")

    result = run_evaluation.poll_run(
        retrieve=lambda: run,
        interval_seconds=1.0,
        timeout_seconds=10.0,
        sleep=lambda s: None,
        now=lambda: 0.0,
    )

    assert result.status == "completed"


def test_poll_run_polls_until_terminal_status() -> None:
    statuses = iter(["in_progress", "in_progress", "completed"])
    sleeps: list[float] = []

    result = run_evaluation.poll_run(
        retrieve=lambda: SimpleNamespace(status=next(statuses)),
        interval_seconds=2.0,
        timeout_seconds=100.0,
        sleep=sleeps.append,
        now=lambda: 0.0,
    )

    assert result.status == "completed"
    assert sleeps == [2.0, 2.0]


def test_poll_run_raises_after_timeout_without_looping_forever() -> None:
    clock = iter([0.0, 0.0, 5.0, 11.0])

    with pytest.raises(run_evaluation.WorkshopContextError, match="did not reach a terminal state"):
        run_evaluation.poll_run(
            retrieve=lambda: SimpleNamespace(status="in_progress"),
            interval_seconds=1.0,
            timeout_seconds=10.0,
            sleep=lambda s: None,
            now=lambda: next(clock),
        )


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


def test_format_report_reads_dict_style_run() -> None:
    run = {
        "status": "completed",
        "report_url": "https://ai.azure.com/eval/xyz",
        "result_counts": {"total": 3, "passed": 2, "failed": 1, "errored": 0},
    }

    report = run_evaluation.format_report(run, eval_id="eval-1", run_id="run-1")

    assert report["status"] == "completed"
    assert report["result_counts"]["passed"] == 2
    assert report["report_url"] == "https://ai.azure.com/eval/xyz"


def test_format_report_reads_object_style_run() -> None:
    run = SimpleNamespace(
        status="failed",
        report_url="https://ai.azure.com/eval/abc",
        result_counts=SimpleNamespace(total=1, passed=0, failed=1, errored=0),
        per_testing_criteria_results=None,
    )

    report = run_evaluation.format_report(run, eval_id="eval-2", run_id="run-2")

    assert report["status"] == "failed"
    assert report["result_counts"]["failed"] == 1


def test_format_report_serializes_sdk_model_criteria() -> None:
    class FakeCriterionResult:
        def model_dump(self, *, mode: str) -> dict:
            assert mode == "json"
            return {
                "testing_criteria": "policy_rubric",
                "passed": 7,
                "failed": 1,
            }

    run = SimpleNamespace(
        status="completed",
        report_url="https://ai.azure.com/eval/criteria",
        result_counts=SimpleNamespace(total=8, passed=7, failed=1, errored=0),
        per_testing_criteria_results=[FakeCriterionResult()],
    )

    report = run_evaluation.format_report(run, eval_id="eval-3", run_id="run-3")

    assert report["per_testing_criteria_results"] == [
        {
            "testing_criteria": "policy_rubric",
            "passed": 7,
            "failed": 1,
        }
    ]
    json.dumps(report)


def test_report_serialization_rejects_unknown_sdk_value_type() -> None:
    with pytest.raises(TypeError, match="unsupported evaluation report value type"):
        run_evaluation._to_json_compatible(object())


# ---------------------------------------------------------------------------
# ensure_dataset / ensure_rubric_evaluator (fake SDK adapters)
# ---------------------------------------------------------------------------


class _FakeDatasetsOperations:
    def __init__(self, existing: object | None) -> None:
        self._existing = existing
        self.upload_calls: list[dict] = []

    def get(self, name: str, version: str) -> object:
        if self._existing is None:
            raise ResourceNotFoundError("not found")
        return self._existing

    def upload_file(self, *, name: str, version: str, file_path: str) -> object:
        self.upload_calls.append({"name": name, "version": version, "file_path": file_path})
        return SimpleNamespace(name=name, version=version, id=f"dataset-{version}")


class _FakeProjectClientForDatasets:
    def __init__(self, existing: object | None) -> None:
        self.datasets = _FakeDatasetsOperations(existing)


def test_ensure_dataset_reuses_existing_version(tmp_path: Path) -> None:
    existing = SimpleNamespace(name="ds", version="abc123", id="dataset-abc123")
    client = _FakeProjectClientForDatasets(existing)
    dataset_path = tmp_path / "cases.jsonl"
    dataset_path.write_text("{}\n", encoding="utf-8")

    result = run_evaluation.ensure_dataset(
        client, name="ds", version="abc123", file_path=dataset_path
    )

    assert result is existing
    assert client.datasets.upload_calls == []


def test_ensure_dataset_uploads_when_absent(tmp_path: Path) -> None:
    client = _FakeProjectClientForDatasets(existing=None)
    dataset_path = tmp_path / "cases.jsonl"
    dataset_path.write_text("{}\n", encoding="utf-8")

    result = run_evaluation.ensure_dataset(
        client, name="ds", version="newver", file_path=dataset_path
    )

    assert result.id == "dataset-newver"
    assert len(client.datasets.upload_calls) == 1


class _FakeEvaluatorsOperations:
    def __init__(self, existing: object | None) -> None:
        self._existing = existing
        self.create_calls: list[object] = []

    def get_version(self, name: str, version: str) -> object:
        if self._existing is None:
            raise ResourceNotFoundError("not found")
        return self._existing

    def create_version(self, name: str, evaluator_version: object) -> object:
        self.create_calls.append(evaluator_version)
        return evaluator_version


class _FakeBeta:
    def __init__(self, existing: object | None) -> None:
        self.evaluators = _FakeEvaluatorsOperations(existing)


class _FakeProjectClientForEvaluators:
    def __init__(self, existing: object | None) -> None:
        self.beta = _FakeBeta(existing)


def test_ensure_rubric_evaluator_reuses_matching_existing_version() -> None:
    existing = run_evaluation.build_rubric_evaluator_version()
    desired = run_evaluation.build_rubric_evaluator_version()
    client = _FakeProjectClientForEvaluators(existing)

    result = run_evaluation.ensure_rubric_evaluator(
        client, name="contoso-travel-rubric", desired=desired
    )

    assert result is existing
    assert client.beta.evaluators.create_calls == []


def test_ensure_rubric_evaluator_creates_when_absent() -> None:
    desired = run_evaluation.build_rubric_evaluator_version()
    client = _FakeProjectClientForEvaluators(existing=None)

    result = run_evaluation.ensure_rubric_evaluator(
        client, name="contoso-travel-rubric", desired=desired
    )

    assert result is desired
    assert client.beta.evaluators.create_calls == [desired]


def test_ensure_rubric_evaluator_creates_new_version_when_definition_changed() -> None:
    existing = run_evaluation.build_rubric_evaluator_version(pass_threshold=0.4)
    desired = run_evaluation.build_rubric_evaluator_version(pass_threshold=0.8)
    client = _FakeProjectClientForEvaluators(existing)

    result = run_evaluation.ensure_rubric_evaluator(
        client, name="contoso-travel-rubric", desired=desired
    )

    assert result is desired
    assert client.beta.evaluators.create_calls == [desired]

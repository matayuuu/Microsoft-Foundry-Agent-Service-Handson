"""Contract tests for data/eval/master.jsonl and data/eval/live_subset.jsonl.

Validates the exact columns/shape that planned evaluators and the optimizer
rely on: schema conformance, category coverage, and the master/live_subset
containment relationship.
"""

import json

import jsonschema

REQUIRED_CATEGORIES = {
    "direct_policy_fact",
    "multi_hop",
    "ambiguity_missing_info",
    "out_of_scope",
    "citation_requirement",
    "tool_choice",
    "prompt_injection_resistance",
    "missing_receipts",
    "current_info_web_search",
    "safety",
}


def _load_schema(data_dir):
    schema_path = data_dir / "schemas" / "eval_case.schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _load_jsonl(path):
    cases = []
    with path.open(encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise AssertionError(f"{path}:{line_number} is not valid JSON: {exc}") from exc
    return cases


def test_master_jsonl_matches_schema(data_dir):
    schema = _load_schema(data_dir)
    cases = _load_jsonl(data_dir / "eval" / "master.jsonl")
    for case in cases:
        jsonschema.validate(instance=case, schema=schema)


def test_live_subset_jsonl_matches_schema(data_dir):
    schema = _load_schema(data_dir)
    cases = _load_jsonl(data_dir / "eval" / "live_subset.jsonl")
    for case in cases:
        jsonschema.validate(instance=case, schema=schema)


def test_master_has_approximately_twelve_cases(data_dir):
    cases = _load_jsonl(data_dir / "eval" / "master.jsonl")
    assert 12 <= len(cases) <= 14, f"expected ~12 master cases, found {len(cases)}"


def test_live_subset_has_six_to_eight_cases(data_dir):
    cases = _load_jsonl(data_dir / "eval" / "live_subset.jsonl")
    assert 6 <= len(cases) <= 8, f"expected 6-8 live subset cases, found {len(cases)}"


def test_master_covers_every_required_category(data_dir):
    cases = _load_jsonl(data_dir / "eval" / "master.jsonl")
    categories = {case["category"] for case in cases}
    missing = REQUIRED_CATEGORIES - categories
    assert not missing, f"master.jsonl is missing required categories: {missing}"


def test_master_case_ids_are_unique(data_dir):
    cases = _load_jsonl(data_dir / "eval" / "master.jsonl")
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))


def test_live_subset_ids_are_a_subset_of_master(data_dir):
    master_ids = {case["id"] for case in _load_jsonl(data_dir / "eval" / "master.jsonl")}
    live_ids = {case["id"] for case in _load_jsonl(data_dir / "eval" / "live_subset.jsonl")}
    missing = live_ids - master_ids
    assert not missing, f"live_subset.jsonl references ids not present in master.jsonl: {missing}"


def test_live_subset_entries_are_identical_to_master(data_dir):
    """The live subset must be a verbatim slice of master, not a fork, so the
    two never silently disagree on expected_behavior/ground_truth/etc."""
    master_by_id = {case["id"]: case for case in _load_jsonl(data_dir / "eval" / "master.jsonl")}
    live_cases = _load_jsonl(data_dir / "eval" / "live_subset.jsonl")
    for case in live_cases:
        assert case == master_by_id[case["id"]], f"{case['id']} differs between the two files"


def test_cases_designed_so_v1_and_v2_outcomes_differ_somewhere(data_dir):
    """At least one case must show a measurable v1-vs-v2 improvement,
    otherwise the evaluation set cannot demonstrate the workshop's core
    "measurable improvement" narrative."""
    cases = _load_jsonl(data_dir / "eval" / "master.jsonl")
    improving_cases = [
        case for case in cases if case["v1_expected_outcome"] != case["v2_expected_outcome"]
    ]
    assert len(improving_cases) >= 4, (
        "expected at least 4 cases where v1_expected_outcome != v2_expected_outcome"
    )


def test_v2_expected_outcome_never_worse_than_v1(data_dir):
    """v2 (Foundry IQ + tools + evaluation-informed prompt) should never
    regress relative to v1 on any individual case."""
    rank = {"fail": 0, "partial": 1, "pass": 2}
    cases = _load_jsonl(data_dir / "eval" / "master.jsonl")
    for case in cases:
        assert rank[case["v2_expected_outcome"]] >= rank[case["v1_expected_outcome"]], (
            f"{case['id']}: v2 outcome regresses relative to v1"
        )


def test_citation_required_cases_declare_expected_citations(data_dir):
    cases = _load_jsonl(data_dir / "eval" / "master.jsonl")
    for case in cases:
        if case["requires_citation"]:
            assert case.get("expected_citations"), (
                f"{case['id']} requires_citation=true but has no expected_citations"
            )


def test_expected_citations_reference_known_manifest_documents(data_dir):
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    known_ids = {doc["id"] for doc in manifest["documents"]}
    cases = _load_jsonl(data_dir / "eval" / "master.jsonl")
    for case in cases:
        for citation_id in case.get("expected_citations") or []:
            assert citation_id in known_ids, (
                f"{case['id']} references unknown document id {citation_id}"
            )


def test_tool_choice_cases_declare_expected_tool_calls(data_dir):
    cases = _load_jsonl(data_dir / "eval" / "master.jsonl")
    tool_choice_cases = [case for case in cases if case["category"] == "tool_choice"]
    assert tool_choice_cases, "no tool_choice cases found"
    for case in tool_choice_cases:
        assert case.get("expected_tool_calls"), (
            f"{case['id']} is a tool_choice case but declares no expected_tool_calls"
        )

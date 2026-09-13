#!/usr/bin/env python3
"""Initialize and validate a custom-template deployment for shared GitHub materials.

The Deployment Scripts identity is already authenticated. This adapter only sequences
the existing setup scripts; it neither provisions infrastructure nor changes login state.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap_data
from lib.workshop_context import (
    WorkshopContextError,
    validate_source_revision,
    validate_workshop_context,
)
from validate_environment import DEFAULT_INDEX_NAMES, is_transient_failure, redact_diagnostic

REPO_ROOT = Path(__file__).resolve().parents[1]
Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class BootstrapError(RuntimeError):
    """A named bootstrap stage failed; no successful deployment output may be emitted."""


@dataclass(frozen=True)
class BootstrapInputs:
    context: dict[str, Any]
    output_path: Path


@dataclass(frozen=True)
class Stage:
    name: str
    command: tuple[str, ...]
    readiness_retries: bool = True


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 6
    initial_delay: float = 10
    maximum_delay: float = 60

    def __post_init__(self) -> None:
        if not 1 <= self.attempts <= 10:
            raise ValueError("retry attempts must be between 1 and 10")
        if not 0 < self.initial_delay <= self.maximum_delay <= 120:
            raise ValueError("retry delays must be positive and bounded by 120 seconds")


DEFAULT_RETRY = RetryPolicy()


def canonical_context(raw: Any, revision: str) -> dict[str, Any]:
    """Validate the template boundary and construct only allowlisted non-secret fields."""
    try:
        context = validate_workshop_context(
            raw,
            allowed_statuses=("infrastructure-ready", "complete"),
            expected_revision=revision,
        )
    except WorkshopContextError as exc:
        raise BootstrapError(f"inputs: {exc}") from exc
    return {**context, "setup_status": "infrastructure-ready"}


def inputs_from_environment(environment: Mapping[str, str]) -> BootstrapInputs:
    required = (
        "WORKSHOP_SOURCE_REVISION",
        "WORKSHOP_CONTEXT_JSON",
        "AZ_SCRIPTS_OUTPUT_PATH",
    )
    missing = [key for key in required if not environment.get(key)]
    if missing:
        raise BootstrapError(f"inputs: missing environment variable(s): {', '.join(missing)}.")
    try:
        revision = validate_source_revision(environment["WORKSHOP_SOURCE_REVISION"])
        context = canonical_context(json.loads(environment["WORKSHOP_CONTEXT_JSON"]), revision)
    except (ValueError, WorkshopContextError) as exc:
        raise BootstrapError(f"inputs: {exc}") from exc
    path = Path(environment["AZ_SCRIPTS_OUTPUT_PATH"])
    if not path.is_absolute() or path.is_symlink() or path.is_dir():
        raise BootstrapError(
            "inputs: AZ_SCRIPTS_OUTPUT_PATH must be an absolute regular file path."
        )
    return BootstrapInputs(context=context, output_path=path)


def data_path(root: Path, relative: str) -> Path:
    name = PurePosixPath(relative)
    if not name.parts or name.is_absolute() or ".." in name.parts or "\\" in relative:
        raise BootstrapError("local-assets: manifest contains an unsafe data path.")
    return root / "data" / Path(*name.parts)


def require_file(path: Path, stage: str) -> None:
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise BootstrapError(f"{stage}: required regular, nonempty file is missing: {path.name}.")


def verify_local_assets(root: Path) -> dict[str, Any]:
    """Reuse the data adapter's schema/checksum rules before any cloud side effects."""
    for name in (
        "scripts/bootstrap_data.py",
        "scripts/run_evaluation.py",
        "scripts/validate_environment.py",
        "data/manifest.json",
        "data/schemas/manifest.schema.json",
        "data/schemas/eval_case.schema.json",
    ):
        require_file(root / name, "local-assets")
    try:
        manifest = bootstrap_data.load_manifest(root / "data" / "manifest.json")
        schema = bootstrap_data.load_schema(root / "data" / "schemas" / "manifest.schema.json")
        errors = bootstrap_data.validate_manifest_schema(manifest, schema)
        if errors:
            raise BootstrapError("local-assets: manifest schema: " + "; ".join(errors))
        documents = bootstrap_data.iter_documents(manifest)
        for document in documents:
            require_file(data_path(root, document.path), "local-assets")
        errors = bootstrap_data.verify_source_checksums(
            documents, lambda document: bootstrap_data.read_source_bytes(root / "data", document)
        )
        if errors:
            raise BootstrapError("local-assets: " + "; ".join(errors))
        for group in ("receipts", "fixtures", "evaluation"):
            for entry in manifest[group]["files"]:
                path = data_path(root, entry["path"])
                require_file(path, "local-assets")
                canonical = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
                if (
                    len(canonical) != entry["size_bytes"]
                    or hashlib.sha256(canonical).hexdigest() != entry["sha256"]
                ):
                    raise BootstrapError(
                        f"local-assets: manifest checksum mismatch for {entry['path']}."
                    )
        names = [index["name"] for index in manifest["search_indexes"]]
        if len(names) != 2 or set(names) != set(DEFAULT_INDEX_NAMES):
            raise BootstrapError("local-assets: manifest must define both workshop Search indexes.")
        for name in names:
            bootstrap_data.select_documents_for_index(manifest, documents, name)
        return manifest
    except (OSError, ValueError, KeyError) as exc:
        raise BootstrapError(f"local-assets: {exc}") from exc


def plan_initialization(
    context: dict[str, Any], manifest: dict[str, Any], root: Path, python: str
) -> tuple[Stage, ...]:
    """Plan adapter arguments without credentials, process execution, or file writes."""
    outputs = {key: entry["value"] for key, entry in context["resource_outputs"].items()}
    context_path = str(root / ".workshop" / "context.json")
    stages = []
    for index in manifest["search_indexes"]:
        stages.append(
            Stage(
                f"seed-search:{index['name']}",
                (
                    python,
                    str(root / "scripts" / "bootstrap_data.py"),
                    "--manifest",
                    str(root / "data" / "manifest.json"),
                    "--schema",
                    str(root / "data" / "schemas" / "manifest.schema.json"),
                    "--search-endpoint",
                    outputs["search_service_endpoint"],
                    "--openai-endpoint",
                    outputs["openai_endpoint"],
                    "--embedding-deployment",
                    outputs["embedding_model_deployment_name"],
                    "--embedding-dimensions",
                    str(manifest["embedding"]["default_dimensions"]),
                    "--source-base",
                    context["source_base"],
                    "--index-name",
                    index["name"],
                ),
            )
        )
    datasets = [
        entry
        for entry in manifest["evaluation"]["files"]
        if entry["name"] == "eval_live_subset_jsonl"
    ]
    if len(datasets) != 1:
        raise BootstrapError(
            "local-assets: manifest must identify exactly one live evaluation subset."
        )
    dataset = datasets[0]
    stages.extend(
        (
            Stage(
                "prepare-evaluation",
                (
                    python,
                    str(root / "scripts" / "run_evaluation.py"),
                    "--context",
                    context_path,
                    "--dataset",
                    str(data_path(root, dataset["path"])),
                    "--schema",
                    str(root / "data" / "schemas" / "eval_case.schema.json"),
                    "--credential",
                    "azure-cli",
                    "--prepare-only",
                    "--output",
                    "json",
                ),
            ),
            Stage(
                "validate-environment",
                (
                    python,
                    str(root / "scripts" / "validate_environment.py"),
                    "--context",
                    context_path,
                    "--participant-object-id",
                    context["participant_object_id"],
                    "--format",
                    "json",
                    *(
                        argument
                        for index in manifest["search_indexes"]
                        for argument in (
                            "--index-name",
                            index["name"],
                            "--index-min-documents",
                            f"{index['name']}={len(index['document_ids'])}",
                        )
                    ),
                ),
            ),
        )
    )
    return tuple(stages)


def validation_retryable(stdout: str) -> bool:
    try:
        report = json.loads(stdout)
        failures = [check for check in report["checks"] if check["status"] == "fail"]
        return bool(failures) and all(check.get("retryable") is True for check in failures)
    except (ValueError, KeyError, TypeError):
        return False


def execute_stage(
    stage: Stage,
    runner: Runner,
    *,
    retry: RetryPolicy = DEFAULT_RETRY,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> subprocess.CompletedProcess[str]:
    for attempt in range(1, retry.attempts + 1):
        log(f"bootstrap {stage.name}: attempt {attempt}/{retry.attempts}.")
        process_timed_out = False
        try:
            result = runner(stage.command)
        except subprocess.TimeoutExpired:
            process_timed_out = True
            result = subprocess.CompletedProcess(
                stage.command,
                1,
                "",
                "TimeoutError: adapter exceeded its bounded execution timeout.",
            )
        except OSError as exc:
            raise BootstrapError(
                f"{stage.name}: executable could not run ({type(exc).__name__})."
            ) from exc
        if result.returncode == 0:
            if stage.name == "prepare-evaluation":
                prepared = json_object(result.stdout, stage.name)
                if prepared.get("status") != "ready" or any(
                    not isinstance(prepared.get(key), dict)
                    or not prepared[key].get("name")
                    or not prepared[key].get("version")
                    for key in ("dataset", "rubric_evaluator")
                ):
                    raise BootstrapError(
                        "prepare-evaluation: adapter did not confirm the dataset and rubric ready."
                    )
            if stage.name == "validate-environment":
                report = json_object(result.stdout, stage.name)
                checks = report.get("checks")
                if (
                    report.get("overall_status") != "pass"
                    or not isinstance(checks, list)
                    or not checks
                    or any(
                        not isinstance(check, dict) or check.get("status") != "pass"
                        for check in checks
                    )
                ):
                    raise BootstrapError(
                        "validate-environment: adapter did not report all checks passing."
                    )
                log(redact_diagnostic(result.stdout))
            return result
        detail = f"{result.stderr or ''}\n{result.stdout or ''}".strip()
        transient = process_timed_out or (
            validation_retryable(result.stdout)
            if stage.name == "validate-environment"
            else is_transient_failure(detail)
        )
        if not stage.readiness_retries or not transient or attempt == retry.attempts:
            if not stage.readiness_retries:
                reason = "adapter failed"
            else:
                reason = (
                    "readiness retries exhausted"
                    if transient
                    else "permanent or unclassified failure"
                )
            raise BootstrapError(
                f"{stage.name}: {reason} (exit {result.returncode}).\n"
                f"{redact_diagnostic(detail)[-4000:]}"
            )
        delay = min(retry.initial_delay * 2 ** (attempt - 1), retry.maximum_delay)
        log(f"bootstrap {stage.name}: transient readiness/RBAC failure; retry in {delay:g}s.")
        sleep(delay)
    raise AssertionError("unreachable retry state")


def json_object(text: str, stage: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except ValueError as exc:
        raise BootstrapError(f"{stage}: expected a JSON verification response.") from exc
    if not isinstance(value, dict):
        raise BootstrapError(f"{stage}: expected a JSON object.")
    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    if path.is_symlink():
        raise BootstrapError("local-output: refusing to replace a symbolic link.")
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(f"{path.name}.{uuid4().hex}.pending")
    try:
        pending.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def run_bootstrap(
    inputs: BootstrapInputs,
    *,
    root: Path = REPO_ROOT,
    runner: Runner | None = None,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> dict[str, str]:
    if not inputs.output_path.is_absolute() or inputs.output_path.is_symlink():
        raise BootstrapError("inputs: deployment output must not be a symbolic link.")
    inputs.output_path.unlink(missing_ok=True)
    manifest = verify_local_assets(root)
    context = canonical_context(inputs.context, inputs.context["source_revision"])
    stages = plan_initialization(context, manifest, root, sys.executable)
    context_path = root / ".workshop" / "context.json"
    if runner is None:

        def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                command,
                cwd=root,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=900,
            )

    def execute(stage: Stage) -> subprocess.CompletedProcess[str]:
        return execute_stage(stage, runner, sleep=sleep, log=log)

    write_json(context_path, context)
    for stage in stages:
        execute(stage)
    output = {"status": "complete", "source_revision": context["source_revision"]}
    write_json(inputs.output_path, output)
    log("bootstrap complete: Search and evaluation data are ready; all checks passed.")
    return output


def main() -> int:
    try:
        run_bootstrap(inputs_from_environment(os.environ))
    except (BootstrapError, WorkshopContextError, OSError, ValueError) as exc:
        print(f"bootstrap_custom_template.py: {redact_diagnostic(str(exc))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

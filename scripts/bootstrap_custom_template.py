#!/usr/bin/env python3
"""Initialize a custom-template deployment and publish its private participant ZIP.

The Deployment Scripts identity is already authenticated. This adapter only sequences
the existing setup scripts; it neither provisions infrastructure nor changes login state.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID, uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap_data
from lib.workshop_context import (
    CUSTOM_TEMPLATE_RESOURCE_OUTPUTS,
    SOURCE_REPOSITORY,
    WorkshopContextError,
    participant_object_id,
    validate_source_revision,
)
from validate_environment import DEFAULT_INDEX_NAMES, is_transient_failure, redact_diagnostic

REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_CONTAINER = "workshop-files"
ARTIFACT_BLOB = "foundry-workshop-files.zip"
PORTAL_ASSETS = (
    "travel-ops.openapi.json",
    "portal-values.json",
    "travel-estimation.zip",
    "preapproval-simulation.zip",
)
CONTEXT_KEYS = frozenset(
    {
        "schema_version",
        "provisioning_method",
        "setup_status",
        "subscription_id",
        "resource_group_name",
        "location",
        "source_base",
        "source_revision",
        "participant_object_id",
        "resource_outputs",
    }
)
Runner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class BootstrapError(RuntimeError):
    """A named bootstrap stage failed; no successful deployment output may be emitted."""


@dataclass(frozen=True)
class BootstrapInputs:
    context: dict[str, Any]
    output_path: Path
    container: str = ARTIFACT_CONTAINER


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
    validate_source_revision(revision)
    if not isinstance(raw, dict) or set(raw) != CONTEXT_KEYS:
        raise BootstrapError(
            "inputs: context must contain exactly the documented canonical fields."
        )
    if (
        raw["schema_version"] != "1.0"
        or raw["provisioning_method"] != "azure-custom-template"
        or raw["setup_status"] not in ("infrastructure-ready", "complete")
    ):
        raise BootstrapError(
            "inputs: context must describe initialized custom-template infrastructure."
        )
    if raw["source_revision"] != revision or raw["source_base"] != (
        f"{SOURCE_REPOSITORY}/blob/{revision}"
    ):
        raise BootstrapError(
            "inputs: context source revision/base does not match the pinned source."
        )
    participant = participant_object_id(raw)
    subscription = raw["subscription_id"]
    if (
        not isinstance(subscription, str)
        or re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", subscription)
        is None
        or UUID(subscription).int == 0
    ):
        raise BootstrapError("inputs: subscription_id must be a valid nonzero UUID.")
    group, location = raw["resource_group_name"], raw["location"]
    if (
        not isinstance(group, str)
        or re.fullmatch(r"[\w.()-]{1,90}", group) is None
        or group.endswith(".")
        or not isinstance(location, str)
        or re.fullmatch(r"[a-z0-9]+", location) is None
    ):
        raise BootstrapError("inputs: resource_group_name or location is invalid.")
    outputs = raw["resource_outputs"]
    if not isinstance(outputs, dict) or set(outputs) != set(CUSTOM_TEMPLATE_RESOURCE_OUTPUTS):
        raise BootstrapError(
            "inputs: resource_outputs must contain exactly the template output keys."
        )
    values: dict[str, str] = {}
    for key, entry in outputs.items():
        value = entry.get("value") if isinstance(entry, dict) else None
        if (
            not isinstance(entry, dict)
            or set(entry) != {"value"}
            or not isinstance(value, str)
            or not value.strip()
            or value != value.strip()
            or any(ord(character) < 32 for character in value)
        ):
            raise BootstrapError(f"inputs: resource output {key} must contain one nonempty value.")
        values[key] = value
        if (
            key.endswith("_name")
            and key != "resource_group_name"
            and re.fullmatch(r"[A-Za-z0-9_.()-]{1,128}", value) is None
        ):
            raise BootstrapError(f"inputs: resource output {key} contains an invalid name.")
    if values["resource_group_name"] != group or values["location"] != location:
        raise BootstrapError("inputs: resource outputs disagree with the context's group/location.")
    if re.fullmatch(r"[a-z0-9]{3,24}", values["storage_account_name"]) is None:
        raise BootstrapError("inputs: storage_account_name is invalid.")
    rg_id = f"/subscriptions/{subscription}/resourceGroups/{group}"
    expected_ids = {
        "foundry_project_id": (
            f"{rg_id}/providers/Microsoft.CognitiveServices/accounts/"
            f"{values['ai_services_account_name']}/projects/{values['foundry_project_name']}"
        ),
        "application_insights_id": (
            f"{rg_id}/providers/Microsoft.Insights/components/{values['application_insights_name']}"
        ),
        "azureml_workspace_id": (
            f"{rg_id}/providers/Microsoft.MachineLearningServices/workspaces/"
            f"{values['azureml_workspace_name']}"
        ),
        "storage_account_id": (
            f"{rg_id}/providers/Microsoft.Storage/storageAccounts/{values['storage_account_name']}"
        ),
        "key_vault_id": f"{rg_id}/providers/Microsoft.KeyVault/vaults/{values['key_vault_name']}",
    }
    for key, expected in expected_ids.items():
        if values[key].casefold() != expected.casefold():
            raise BootstrapError(
                f"inputs: {key} does not identify the expected resource in this RG."
            )
    account = values["ai_services_account_name"]
    expected_urls = {
        "ai_services_endpoint": {
            f"https://{account}.cognitiveservices.azure.com",
            f"https://{account}.services.ai.azure.com",
        },
        "openai_endpoint": {f"https://{account}.openai.azure.com/openai/v1"},
        "foundry_project_endpoint": {
            f"https://{account}.services.ai.azure.com/api/projects/{values['foundry_project_name']}"
        },
        "search_service_endpoint": {f"https://{values['search_service_name']}.search.windows.net"},
        "foundry_portal_url": {"https://ai.azure.com"},
    }
    for key, allowed in expected_urls.items():
        if values[key].removesuffix("/") not in allowed:
            raise BootstrapError(
                f"inputs: {key} must be the expected unsigned Azure HTTPS endpoint."
            )
    fqdn = values["travel_api_fqdn"]
    if (
        re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", fqdn) is None
        or not fqdn.endswith(".azurecontainerapps.io")
        or urlsplit(f"https://{fqdn}").hostname != fqdn
    ):
        raise BootstrapError("inputs: travel_api_fqdn must be an Azure Container Apps hostname.")
    return {
        **{key: raw[key] for key in CONTEXT_KEYS - {"resource_outputs"}},
        "participant_object_id": participant,
        "setup_status": "infrastructure-ready",
        "resource_outputs": {
            key: {"value": values[key]} for key in CUSTOM_TEMPLATE_RESOURCE_OUTPUTS
        },
    }


def inputs_from_environment(environment: Mapping[str, str]) -> BootstrapInputs:
    required = (
        "WORKSHOP_SOURCE_REVISION",
        "WORKSHOP_CONTEXT_JSON",
        "WORKSHOP_ARTIFACT_CONTAINER",
        "AZ_SCRIPTS_OUTPUT_PATH",
    )
    missing = [key for key in required if not environment.get(key)]
    if missing:
        raise BootstrapError(f"inputs: missing environment variable(s): {', '.join(missing)}.")
    if environment["WORKSHOP_ARTIFACT_CONTAINER"] != ARTIFACT_CONTAINER:
        raise BootstrapError(f"inputs: WORKSHOP_ARTIFACT_CONTAINER must be {ARTIFACT_CONTAINER}.")
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
        "scripts/prepare_toolbox_assets.py",
        "scripts/prepare_participant_download.py",
        "data/manifest.json",
        "data/schemas/manifest.schema.json",
        "data/schemas/eval_case.schema.json",
        "data/skills/travel-estimation/SKILL.md",
        "data/skills/preapproval-simulation/SKILL.md",
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
            Stage(
                "prepare-portal-assets",
                (
                    python,
                    str(root / "scripts" / "prepare_toolbox_assets.py"),
                    "--context",
                    context_path,
                    "--output-dir",
                    str(root / ".workshop" / "toolbox"),
                ),
                readiness_retries=False,
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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    if inputs.container != ARTIFACT_CONTAINER:
        raise BootstrapError(f"inputs: artifact container must be {ARTIFACT_CONTAINER}.")
    if not inputs.output_path.is_absolute() or inputs.output_path.is_symlink():
        raise BootstrapError("inputs: deployment output must not be a symbolic link.")
    inputs.output_path.unlink(missing_ok=True)
    manifest = verify_local_assets(root)
    context = canonical_context(inputs.context, inputs.context["source_revision"])
    stages = plan_initialization(context, manifest, root, sys.executable)
    context_path = root / ".workshop" / "context.json"
    artifact = root / ".workshop" / "download" / ARTIFACT_BLOB
    verified = artifact.with_name(f"verified-{uuid4().hex}.zip")
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

    storage = context["resource_outputs"]["storage_account_name"]["value"]
    az = shutil.which("az") or "az"

    def storage_stage(name: str, arguments: Sequence[str]) -> Stage:
        return Stage(
            name,
            (
                az,
                "storage",
                *arguments,
                "--account-name",
                storage,
                "--auth-mode",
                "login",
                "--only-show-errors",
                "--output",
                "json",
            ),
        )

    def verify_private_container() -> None:
        result = execute(
            storage_stage(
                "verify-private-container",
                (
                    "container",
                    "show",
                    "--name",
                    inputs.container,
                    "--query",
                    "{public_access:properties.publicAccess}",
                ),
            )
        )
        info = json_object(result.stdout, "verify-private-container")
        if "public_access" not in info or info["public_access"] not in (
            None,
            "off",
            "None",
            "none",
        ):
            raise BootstrapError("verify-private-container: participant container must be private.")

    write_json(context_path, context)
    try:
        for stage in stages:
            execute(stage)
        for name in PORTAL_ASSETS:
            require_file(root / ".workshop" / "toolbox" / name, "prepare-portal-assets")
        write_json(context_path, {**context, "setup_status": "complete"})
        execute(
            Stage(
                "package-participant-download",
                (
                    sys.executable,
                    str(root / "scripts" / "prepare_participant_download.py"),
                    "--context",
                    str(context_path),
                    "--output",
                    str(artifact),
                ),
                readiness_retries=False,
            )
        )
        require_file(artifact, "package-participant-download")
        digest = file_sha256(artifact)
        revision = context["source_revision"]
        verify_private_container()
        execute(
            storage_stage(
                "upload-participant-download",
                (
                    "blob",
                    "upload",
                    "--container-name",
                    inputs.container,
                    "--name",
                    ARTIFACT_BLOB,
                    "--file",
                    str(artifact),
                    "--overwrite",
                    "true",
                    "--no-progress",
                    "--content-type",
                    "application/zip",
                    "--metadata",
                    f"sha256={digest}",
                    f"source_revision={revision}",
                ),
            )
        )
        result = execute(
            storage_stage(
                "verify-blob-metadata",
                (
                    "blob",
                    "show",
                    "--container-name",
                    inputs.container,
                    "--name",
                    ARTIFACT_BLOB,
                    "--query",
                    "{etag:properties.etag,size:properties.contentLength,metadata:metadata}",
                ),
            )
        )
        remote = json_object(result.stdout, "verify-blob-metadata")
        if (
            remote.get("size") != artifact.stat().st_size
            or not isinstance(remote.get("metadata"), dict)
            or remote["metadata"].get("sha256") != digest
            or remote["metadata"].get("source_revision") != revision
            or not isinstance(remote.get("etag"), str)
            or re.fullmatch(r'"?0x[0-9a-fA-F]+"?', remote["etag"]) is None
        ):
            raise BootstrapError(
                "verify-blob-metadata: published artifact metadata does not match."
            )
        execute(
            storage_stage(
                "verify-blob-content",
                (
                    "blob",
                    "download",
                    "--container-name",
                    inputs.container,
                    "--name",
                    ARTIFACT_BLOB,
                    "--file",
                    str(verified),
                    "--if-match",
                    remote["etag"],
                    "--overwrite",
                    "true",
                    "--no-progress",
                ),
            )
        )
        require_file(verified, "verify-blob-content")
        if file_sha256(verified) != digest:
            raise BootstrapError("verify-blob-content: published artifact SHA-256 does not match.")
        verify_private_container()
        output = {
            "status": "complete",
            "storage_account_name": storage,
            "container_name": inputs.container,
            "blob_name": ARTIFACT_BLOB,
            "sha256": digest,
            "source_revision": revision,
        }
        write_json(inputs.output_path, output)
        log("bootstrap complete: private participant artifact published and verified.")
        return output
    except Exception:
        write_json(context_path, context)
        inputs.output_path.unlink(missing_ok=True)
        raise
    finally:
        verified.unlink(missing_ok=True)


def main() -> int:
    try:
        run_bootstrap(inputs_from_environment(os.environ))
    except (BootstrapError, WorkshopContextError, OSError, ValueError) as exc:
        print(f"bootstrap_custom_template.py: {redact_diagnostic(str(exc))}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

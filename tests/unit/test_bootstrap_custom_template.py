"""Network-free bootstrap boundary tests; fake processes are not Portal E2E evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import zipfile
from collections.abc import Sequence
from pathlib import Path

import pytest

from scripts import bootstrap_custom_template as bootstrap

REVISION = "1234abcd" * 5
PARTICIPANT = "11111111-2222-4333-8444-555555555555"
SUBSCRIPTION = "99999999-8888-4777-8666-555555555555"


def context_fixture() -> dict[str, object]:
    group = "rg-workshop"
    rg_id = f"/subscriptions/{SUBSCRIPTION}/resourceGroups/{group}"
    values = {key: "fixture" for key in bootstrap.CUSTOM_TEMPLATE_RESOURCE_OUTPUTS}
    values.update(
        {
            "resource_group_name": group,
            "location": "japaneast",
            "ai_services_account_name": "aif-workshop",
            "ai_services_endpoint": "https://aif-workshop.cognitiveservices.azure.com/",
            "openai_endpoint": "https://aif-workshop.openai.azure.com/openai/v1/",
            "foundry_project_name": "contoso-travel",
            "foundry_project_id": (
                f"{rg_id}/providers/Microsoft.CognitiveServices/accounts/aif-workshop/projects/"
                "contoso-travel"
            ),
            "foundry_project_endpoint": (
                "https://aif-workshop.services.ai.azure.com/api/projects/contoso-travel"
            ),
            "primary_model_deployment_name": "gpt-5.6-luna",
            "evaluation_model_deployment_name": "gpt-5.5",
            "optimizer_model_deployment_name": "gpt-5.5",
            "embedding_model_deployment_name": "embedding",
            "search_service_name": "srch-workshop",
            "search_service_endpoint": "https://srch-workshop.search.windows.net",
            "search_pricing_model": "dedicated",
            "storage_account_name": "stworkshop",
            "storage_account_id": f"{rg_id}/providers/Microsoft.Storage/storageAccounts/stworkshop",
            "azureml_workspace_name": "mlw-workshop",
            "azureml_workspace_id": (
                f"{rg_id}/providers/Microsoft.MachineLearningServices/workspaces/mlw-workshop"
            ),
            "key_vault_name": "kv-workshop",
            "key_vault_id": f"{rg_id}/providers/Microsoft.KeyVault/vaults/kv-workshop",
            "application_insights_name": "appi-workshop",
            "application_insights_id": (
                f"{rg_id}/providers/Microsoft.Insights/components/appi-workshop"
            ),
            "travel_api_container_app_name": "ca-workshop",
            "travel_api_fqdn": "ca-workshop.fixture.japaneast.azurecontainerapps.io",
            "foundry_portal_url": "https://ai.azure.com",
        }
    )
    return {
        "schema_version": "1.0",
        "provisioning_method": "azure-custom-template",
        "setup_status": "infrastructure-ready",
        "subscription_id": SUBSCRIPTION,
        "resource_group_name": group,
        "location": "japaneast",
        "participant_object_id": PARTICIPANT,
        "source_revision": REVISION,
        "source_base": f"{bootstrap.SOURCE_REPOSITORY}/blob/{REVISION}",
        "resource_outputs": {key: {"value": value} for key, value in values.items()},
    }


def environment_fixture(root: Path) -> dict[str, str]:
    return {
        "WORKSHOP_SOURCE_REVISION": REVISION,
        "WORKSHOP_CONTEXT_JSON": json.dumps(context_fixture()),
        "WORKSHOP_ARTIFACT_CONTAINER": "workshop-files",
        "AZ_SCRIPTS_OUTPUT_PATH": str(root / "deployment-output.json"),
    }


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    shutil.copytree(bootstrap.REPO_ROOT / "data", root / "data")
    (root / "scripts").mkdir()
    for name in (
        "bootstrap_data.py",
        "run_evaluation.py",
        "validate_environment.py",
        "prepare_toolbox_assets.py",
        "prepare_participant_download.py",
    ):
        shutil.copyfile(bootstrap.REPO_ROOT / "scripts" / name, root / "scripts" / name)
    return root


class FakeAdapters:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.commands: list[tuple[str, ...]] = []
        self.stages: list[str] = []
        self.fail_at: str | None = None
        self.omit_asset = False
        self.corrupt_download = False
        self.public_access: str | None = None
        self.uploaded = b""
        self.context_states: list[str] = []

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        arguments = tuple(command)
        self.commands.append(arguments)
        if arguments[1] == "storage":
            name = "-".join(arguments[2:4])
        else:
            name = Path(arguments[1]).name
            self.context_states.append(
                json.loads((self.root / ".workshop" / "context.json").read_text(encoding="utf-8"))[
                    "setup_status"
                ]
            )
        if name == "bootstrap_data.py":
            name += ":" + arguments[arguments.index("--index-name") + 1]
        self.stages.append(name)
        if name == self.fail_at:
            return subprocess.CompletedProcess(command, 2, "", "HTTP 400 InvalidParameter")
        response: object = {}
        if name == "validate_environment.py":
            response = {"overall_status": "pass", "checks": [{"name": "fake", "status": "pass"}]}
        elif name == "run_evaluation.py":
            response = {
                "status": "ready",
                "dataset": {"name": "fixture-dataset", "version": "123"},
                "rubric_evaluator": {"name": "fixture-rubric", "version": "1"},
            }
        elif name == "prepare_toolbox_assets.py":
            directory = self.root / ".workshop" / "toolbox"
            directory.mkdir(parents=True, exist_ok=True)
            for filename in (
                bootstrap.PORTAL_ASSETS[:-1] if self.omit_asset else bootstrap.PORTAL_ASSETS
            ):
                (directory / filename).write_bytes(b"unit-test asset")
        elif name == "prepare_participant_download.py":
            assert self.context_states[-1] == "complete"
            output = Path(arguments[arguments.index("--output") + 1])
            output.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(output, "w") as archive:
                archive.writestr(
                    "synthetic.txt", "unit-test artifact; not a real participant bundle"
                )
                archive.write(self.root / ".workshop" / "context.json", ".workshop/context.json")
        elif name == "container-show":
            response = {"public_access": self.public_access}
        elif name == "blob-upload":
            self.uploaded = Path(arguments[arguments.index("--file") + 1]).read_bytes()
        elif name == "blob-show":
            response = {
                "size": len(self.uploaded),
                "metadata": {
                    "sha256": hashlib.sha256(self.uploaded).hexdigest(),
                    "source_revision": REVISION,
                },
                "etag": '"0x8DA0123ABC"',
            }
        elif name == "blob-download":
            assert arguments[arguments.index("--if-match") + 1] == '"0x8DA0123ABC"'
            path = Path(arguments[arguments.index("--file") + 1])
            path.write_bytes(b"corrupt content" if self.corrupt_download else self.uploaded)
        return subprocess.CompletedProcess(command, 0, json.dumps(response), "")


def test_complete_initialization_precedes_keyless_private_publication(repository: Path) -> None:
    runner = FakeAdapters(repository)
    inputs = bootstrap.inputs_from_environment(environment_fixture(repository))
    logs: list[str] = []
    output = bootstrap.run_bootstrap(inputs, root=repository, runner=runner, log=logs.append)
    assert runner.stages == [
        "bootstrap_data.py:contoso-travel-policy",
        "bootstrap_data.py:contoso-travel-approval",
        "run_evaluation.py",
        "validate_environment.py",
        "prepare_toolbox_assets.py",
        "prepare_participant_download.py",
        "container-show",
        "blob-upload",
        "blob-show",
        "blob-download",
        "container-show",
    ]
    assert runner.context_states == ["infrastructure-ready"] * 5 + ["complete"]
    assert output == {
        "status": "complete",
        "storage_account_name": "stworkshop",
        "container_name": "workshop-files",
        "blob_name": "foundry-workshop-files.zip",
        "sha256": hashlib.sha256(runner.uploaded).hexdigest(),
        "source_revision": REVISION,
    }
    assert json.loads(inputs.output_path.read_text(encoding="utf-8")) == output
    for command in runner.commands:
        if command[1] == "storage":
            assert command[command.index("--auth-mode") + 1] == "login"
            assert command[command.index("--account-name") + 1] == "stworkshop"
            assert not {"--account-key", "--sas-token", "generate-sas", "create", "delete"} & set(
                command
            )
    upload = next(command for command in runner.commands if command[2:4] == ("blob", "upload"))
    assert f"sha256={output['sha256']}" in upload
    assert f"source_revision={REVISION}" in upload
    assert not list((repository / ".workshop" / "download").glob("verified-*"))
    assert "published and verified" in logs[-1]


def test_bootstrap_handoff_uses_the_real_packager_cli_contract(repository: Path) -> None:
    from scripts.prepare_toolbox_assets import export_assets

    adapters = FakeAdapters(repository)
    inputs = bootstrap.inputs_from_environment(environment_fixture(repository))
    portal_assets = repository / ".workshop" / "toolbox"
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "Network-free unit-test API", "version": "1"},
        "servers": [{"url": "https://ca-workshop.fixture.japaneast.azurecontainerapps.io"}],
        "paths": {
            "/health": {
                "get": {
                    "operationId": "getHealth",
                    "responses": {"200": {"description": "healthy"}},
                }
            }
        },
    }

    def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        result = adapters(command)
        script = Path(command[1]).name
        if script == "prepare_toolbox_assets.py":
            export_assets(
                spec=spec,
                endpoint=inputs.context["resource_outputs"]["foundry_project_endpoint"]["value"],
                output_dir=portal_assets,
                skills_dir=repository / "data" / "skills",
            )
        elif script == "prepare_participant_download.py":
            return subprocess.run(
                [
                    command[0],
                    str(bootstrap.REPO_ROOT / "scripts" / "prepare_participant_download.py"),
                    *command[2:],
                ],
                cwd=bootstrap.REPO_ROOT,
                check=False,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
        return result

    output = bootstrap.run_bootstrap(inputs, root=repository, runner=runner)
    artifact = repository / ".workshop" / "download" / bootstrap.ARTIFACT_BLOB
    assert output["sha256"] == hashlib.sha256(adapters.uploaded).hexdigest()
    prefix = "Microsoft-Foundry-Agent-Service-Handson/"
    with zipfile.ZipFile(artifact) as archive:
        manifest = json.loads(archive.read(prefix + "bundle-manifest.json"))
        context = json.loads(archive.read(prefix + ".workshop/context.json"))
        assert manifest["source_revision"] == context["source_revision"] == REVISION
        assert "source_branch" not in manifest
        assert context["schema_version"] == "1.0"
        assert context["provisioning_method"] == "azure-custom-template"
        assert context["setup_status"] == "complete"
        assert context["participant_object_id"] == PARTICIPANT
        for name in bootstrap.PORTAL_ASSETS:
            entry = f"portal-assets/{name}"
            content = (portal_assets / name).read_bytes()
            assert archive.read(prefix + entry) == content
            assert manifest["files"][entry]["sha256"] == hashlib.sha256(content).hexdigest()
        assert prefix + "scripts/lib/workshop_context.py" in archive.namelist()
        assert any(
            name.startswith(prefix + "tests/unit/hosted_agent/") for name in archive.namelist()
        )
        for name in (
            "bootstrap_custom_template.py",
            "bootstrap-custom-template.sh",
            "admin-preflight.sh",
            "prepare_participant_download.py",
            "build_participant_bundle.py",
        ):
            assert prefix + "scripts/" + name not in archive.namelist()


def test_command_plan_uses_both_manifest_partitions_and_explicit_endpoints(
    repository: Path,
) -> None:
    manifest = bootstrap.verify_local_assets(repository)
    context = bootstrap.canonical_context(context_fixture(), REVISION)
    plan = bootstrap.plan_initialization(context, manifest, repository, "isolated-python")
    assert [stage.name for stage in plan] == [
        "seed-search:contoso-travel-policy",
        "seed-search:contoso-travel-approval",
        "prepare-evaluation",
        "validate-environment",
        "prepare-portal-assets",
    ]
    for stage, index in zip(plan[:2], manifest["search_indexes"], strict=True):
        command = stage.command
        assert command[0] == "isolated-python"
        assert command[command.index("--index-name") + 1] == index["name"]
        assert command[command.index("--openai-endpoint") + 1] == (
            "https://aif-workshop.openai.azure.com/openai/v1/"
        )
        assert command[command.index("--search-endpoint") + 1] == (
            "https://srch-workshop.search.windows.net"
        )
        assert command[command.index("--embedding-deployment") + 1] == "embedding"
        assert command[command.index("--embedding-dimensions") + 1] == "1536"
        assert command[command.index("--source-base") + 1].endswith(REVISION)
        assert not {"--dry-run", "--delete", "--reset"} & set(command)
    assert "--prepare-only" in plan[2].command
    assert plan[2].command[plan[2].command.index("--credential") + 1] == "azure-cli"
    assert plan[3].command[plan[3].command.index("--participant-object-id") + 1] == PARTICIPANT
    assert "--skip-search-checks" not in plan[3].command
    assert "contoso-travel-policy=9" in plan[3].command
    assert "contoso-travel-approval=1" in plan[3].command


@pytest.mark.parametrize(
    "variable",
    [
        "WORKSHOP_SOURCE_REVISION",
        "WORKSHOP_CONTEXT_JSON",
        "WORKSHOP_ARTIFACT_CONTAINER",
        "AZ_SCRIPTS_OUTPUT_PATH",
    ],
)
def test_environment_contract_requires_every_input(tmp_path: Path, variable: str) -> None:
    environment = environment_fixture(tmp_path)
    del environment[variable]
    with pytest.raises(bootstrap.BootstrapError, match=variable):
        bootstrap.inputs_from_environment(environment)


@pytest.mark.parametrize(
    "revision", ["main", "release-v1", "a" * 39, "a" * 41, "A" * 40, "../" * 14]
)
def test_environment_rejects_mutable_or_untrusted_source(tmp_path: Path, revision: str) -> None:
    environment = environment_fixture(tmp_path)
    environment["WORKSHOP_SOURCE_REVISION"] = revision
    with pytest.raises(bootstrap.BootstrapError, match="40-character"):
        bootstrap.inputs_from_environment(environment)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_revision", "a" * 40),
        ("source_base", "https://example.invalid/code"),
        ("setup_status", "unknown"),
        ("setup_status", []),
        ("provisioning_method", "legacy"),
        ("participant_object_id", "managed-identity-name"),
        ("subscription_id", "not-a-subscription"),
        ("resource_group_name", "other-resource-group"),
        ("access_token", "do-not-copy"),
    ],
)
def test_context_rejects_mismatch_unknown_state_and_secret_fields(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    context = context_fixture()
    context[field] = value
    environment = environment_fixture(tmp_path)
    environment["WORKSHOP_CONTEXT_JSON"] = json.dumps(context)
    with pytest.raises(bootstrap.BootstrapError):
        bootstrap.inputs_from_environment(environment)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("storage_account_name", "../other-account"),
        ("search_service_endpoint", "https://attacker.invalid"),
        ("openai_endpoint", "https://aif-workshop.openai.azure.com/openai/v1/?sig=unsafe"),
        ("travel_api_fqdn", "localhost"),
        ("storage_account_id", "/subscriptions/other/resourceGroups/shared"),
        ("key_vault_name", ""),
    ],
)
def test_context_validates_resource_boundaries_without_live_probing(
    tmp_path: Path,
    key: str,
    value: str,
) -> None:
    context = context_fixture()
    context["resource_outputs"][key]["value"] = value
    environment = environment_fixture(tmp_path)
    environment["WORKSHOP_CONTEXT_JSON"] = json.dumps(context)
    with pytest.raises(bootstrap.BootstrapError):
        bootstrap.inputs_from_environment(environment)


def test_canonical_context_is_a_clean_copy_and_resets_redeployment_state() -> None:
    raw = context_fixture()
    raw["setup_status"] = "complete"
    original = copy.deepcopy(raw)
    context = bootstrap.canonical_context(raw, REVISION)
    assert raw == original
    assert context["setup_status"] == "infrastructure-ready"
    context["resource_outputs"]["storage_account_name"]["value"] = "changed-only-in-copy"
    assert raw == original


@pytest.mark.parametrize(
    "missing",
    [
        "data/manifest.json",
        "data/eval/live_subset.jsonl",
        "data/skills/travel-estimation/SKILL.md",
        "data/policies/01-general-policy.md",
    ],
)
def test_missing_source_assets_fail_before_any_adapter(repository: Path, missing: str) -> None:
    (repository / missing).unlink()
    runner = FakeAdapters(repository)
    inputs = bootstrap.inputs_from_environment(environment_fixture(repository))
    with pytest.raises(bootstrap.BootstrapError, match="local-assets"):
        bootstrap.run_bootstrap(inputs, root=repository, runner=runner)
    assert runner.commands == []
    assert not inputs.output_path.exists()


def test_tampered_manifest_document_fails_before_any_adapter(repository: Path) -> None:
    (repository / "data" / "policies" / "01-general-policy.md").write_text(
        "changed", encoding="utf-8"
    )
    runner = FakeAdapters(repository)
    inputs = bootstrap.inputs_from_environment(environment_fixture(repository))
    with pytest.raises(bootstrap.BootstrapError, match="local-assets"):
        bootstrap.run_bootstrap(inputs, root=repository, runner=runner)
    assert runner.commands == []
    assert not inputs.output_path.exists()


@pytest.mark.parametrize(
    ("failure", "stage"),
    [
        ("bootstrap_data.py:contoso-travel-policy", "seed-search:contoso-travel-policy"),
        ("bootstrap_data.py:contoso-travel-approval", "seed-search:contoso-travel-approval"),
        ("run_evaluation.py", "prepare-evaluation"),
        ("validate_environment.py", "validate-environment"),
        ("prepare_toolbox_assets.py", "prepare-portal-assets"),
        ("prepare_participant_download.py", "package-participant-download"),
        ("blob-upload", "upload-participant-download"),
        ("blob-show", "verify-blob-metadata"),
        ("blob-download", "verify-blob-content"),
    ],
)
def test_failed_stage_never_emits_success_or_leaves_complete_context(
    repository: Path,
    failure: str,
    stage: str,
) -> None:
    runner = FakeAdapters(repository)
    runner.fail_at = failure
    inputs = bootstrap.inputs_from_environment(environment_fixture(repository))
    inputs.output_path.write_text('{"status":"complete","stale":true}', encoding="utf-8")
    with pytest.raises(bootstrap.BootstrapError, match=stage):
        bootstrap.run_bootstrap(inputs, root=repository, runner=runner)
    assert not inputs.output_path.exists()
    assert runner.stages[-1] == failure
    assert (
        json.loads((repository / ".workshop" / "context.json").read_text(encoding="utf-8"))[
            "setup_status"
        ]
        == "infrastructure-ready"
    )


@pytest.mark.parametrize("fault", ["missing-portal-asset", "public-container", "corrupt-download"])
def test_artifact_gates_fail_closed(repository: Path, fault: str) -> None:
    runner = FakeAdapters(repository)
    runner.omit_asset = fault == "missing-portal-asset"
    runner.public_access = "blob" if fault == "public-container" else None
    runner.corrupt_download = fault == "corrupt-download"
    inputs = bootstrap.inputs_from_environment(environment_fixture(repository))
    with pytest.raises(bootstrap.BootstrapError):
        bootstrap.run_bootstrap(inputs, root=repository, runner=runner)
    assert not inputs.output_path.exists()
    if fault != "corrupt-download":
        assert "blob-upload" not in runner.stages


def test_redeployment_reuses_the_same_adapter_and_artifact_contract(repository: Path) -> None:
    runner = FakeAdapters(repository)
    inputs = bootstrap.inputs_from_environment(environment_fixture(repository))
    for _ in range(2):
        bootstrap.run_bootstrap(inputs, root=repository, runner=runner)
    assert runner.stages.count("bootstrap_data.py:contoso-travel-policy") == 2
    assert runner.stages.count("run_evaluation.py") == 2
    assert runner.stages.count("blob-upload") == 2
    assert json.loads(inputs.output_path.read_text(encoding="utf-8"))["status"] == "complete"


@pytest.mark.parametrize("status", [403, 503])
def test_public_portal_assets_do_not_enter_the_outer_rbac_retry_loop(
    repository: Path, status: int
) -> None:
    manifest = bootstrap.verify_local_assets(repository)
    context = bootstrap.canonical_context(context_fixture(), REVISION)
    stage = next(
        stage
        for stage in bootstrap.plan_initialization(context, manifest, repository, "python")
        if stage.name == "prepare-portal-assets"
    )
    attempts: list[Sequence[str]] = []
    delays: list[float] = []

    def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        attempts.append(command)
        return subprocess.CompletedProcess(command, 2, "", f"OpenAPI HTTP {status}")

    assert stage.readiness_retries is False
    with pytest.raises(bootstrap.BootstrapError, match="prepare-portal-assets: adapter failed"):
        bootstrap.execute_stage(stage, runner, sleep=delays.append)
    assert len(attempts) == 1
    assert delays == []


def test_readiness_retries_have_an_exact_bound_and_report_stage() -> None:
    attempts: list[Sequence[str]] = []
    sleeps: list[float] = []
    logs: list[str] = []

    def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        attempts.append(command)
        return subprocess.CompletedProcess(
            command, 1, "", "HTTP 403 AuthorizationPermissionMismatch"
        )

    stage = bootstrap.Stage("seed-search:contoso-travel-policy", ("python", "bootstrap_data.py"))
    with pytest.raises(
        bootstrap.BootstrapError, match=r"seed-search:.*readiness retries exhausted"
    ):
        bootstrap.execute_stage(stage, runner, sleep=sleeps.append, log=logs.append)
    assert len(attempts) == 6
    assert sleeps == [10, 20, 40, 60, 60]
    assert sum("retry in" in line for line in logs) == 5


def test_transient_failure_can_recover_without_restarting_successful_stages() -> None:
    calls = 0
    sleeps: list[float] = []

    def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(command, int(calls < 3), "", "HTTP 503")

    stage = bootstrap.Stage("seed-search:contoso-travel-policy", ("python", "bootstrap_data.py"))
    assert bootstrap.execute_stage(stage, runner, sleep=sleeps.append).returncode == 0
    assert calls == 3
    assert sleeps == [10, 20]


@pytest.mark.parametrize(
    "detail",
    [
        "HTTP 400 InvalidParameter",
        "HTTP 429 InsufficientQuota",
        "HTTP 403 PublicNetworkAccessDisabled",
        "missing manifest",
        "unknown hard service failure",
    ],
)
def test_permanent_failures_do_not_retry(detail: str) -> None:
    calls: list[Sequence[str]] = []
    sleeps: list[float] = []

    def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 2, "", detail)

    with pytest.raises(bootstrap.BootstrapError, match="permanent"):
        bootstrap.execute_stage(
            bootstrap.Stage("seed-search", ("python", "seed")), runner, sleep=sleeps.append
        )
    assert len(calls) == 1
    assert sleeps == []


def test_validation_retry_requires_every_failure_to_be_transient() -> None:
    transient = {"name": "role", "status": "fail", "retryable": True}
    permanent = {"name": "schema", "status": "fail", "retryable": False}
    assert bootstrap.validation_retryable(json.dumps({"checks": [transient]}))
    assert not bootstrap.validation_retryable(json.dumps({"checks": [transient, permanent]}))
    assert not bootstrap.validation_retryable("HTTP 503 but no report")


@pytest.mark.parametrize(
    "report",
    [
        {},
        {"overall_status": "pass", "checks": []},
        {"overall_status": "fail", "checks": [{"status": "fail"}]},
    ],
)
def test_zero_exit_without_successful_validation_is_not_complete(report: object) -> None:
    with pytest.raises(bootstrap.BootstrapError, match="validate-environment"):
        bootstrap.execute_stage(
            bootstrap.Stage("validate-environment", ("python", "validate")),
            lambda command: subprocess.CompletedProcess(command, 0, json.dumps(report), ""),
        )


@pytest.mark.parametrize("attempts", [0, -1, 11])
def test_unbounded_retry_policy_is_rejected(attempts: int) -> None:
    with pytest.raises(ValueError, match="between 1 and 10"):
        bootstrap.RetryPolicy(attempts=attempts)


@pytest.mark.parametrize("checks", [None, {}, [None], ["pass"], [{"status": "warn"}]])
def test_malformed_validation_checks_fail_with_the_validation_stage(checks: object) -> None:
    with pytest.raises(bootstrap.BootstrapError, match="validate-environment"):
        bootstrap.execute_stage(
            bootstrap.Stage("validate-environment", ("python", "validate")),
            lambda command: subprocess.CompletedProcess(
                command, 0, json.dumps({"overall_status": "pass", "checks": checks}), ""
            ),
        )


@pytest.mark.parametrize(
    "prepared",
    [{}, {"status": "ready"}, {"status": "failed", "dataset": {}, "rubric_evaluator": {}}],
)
def test_zero_exit_without_prepared_evaluation_assets_fails(prepared: object) -> None:
    with pytest.raises(bootstrap.BootstrapError, match="prepare-evaluation"):
        bootstrap.execute_stage(
            bootstrap.Stage("prepare-evaluation", ("python", "evaluate")),
            lambda command: subprocess.CompletedProcess(command, 0, json.dumps(prepared), ""),
        )


def test_deployment_output_write_failure_rolls_back_completion(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = FakeAdapters(repository)
    inputs = bootstrap.inputs_from_environment(environment_fixture(repository))
    write_json = bootstrap.write_json

    def fail_output(path: Path, value: dict[str, object]) -> None:
        if path == inputs.output_path:
            raise OSError("test output path unavailable")
        write_json(path, value)

    monkeypatch.setattr(bootstrap, "write_json", fail_output)
    with pytest.raises(OSError, match="output path unavailable"):
        bootstrap.run_bootstrap(inputs, root=repository, runner=runner)
    assert not inputs.output_path.exists()
    assert (
        json.loads((repository / ".workshop" / "context.json").read_text(encoding="utf-8"))[
            "setup_status"
        ]
        == "infrastructure-ready"
    )
    assert not list((repository / ".workshop" / "download").glob("verified-*"))


def test_validation_process_timeout_has_bounded_readiness_retry() -> None:
    calls = 0
    sleeps: list[float] = []

    def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise subprocess.TimeoutExpired(command, 900)
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps({"overall_status": "pass", "checks": [{"name": "fake", "status": "pass"}]}),
            "",
        )

    bootstrap.execute_stage(
        bootstrap.Stage("validate-environment", ("python", "validate")),
        runner,
        sleep=sleeps.append,
    )
    assert calls == 2
    assert sleeps == [10]

#!/usr/bin/env python3
"""scripts/deploy_hosted_agent.py

Deploys the Microsoft Agent Framework Hosted Agent in ``src/hosted-agent/`` to
the workshop's Microsoft Foundry project, used in labs/07-hosted-multi-agent.md.

What this does, per docs/architecture.md ("Terraform owns Azure
infrastructure; Python SDK wrappers own Foundry data-plane objects") and the
current ``azure-ai-projects`` source-code remote-build contract
(``AIProjectClient.agents.create_version_from_code``, inspected directly from
the installed 2.5.x SDK -- retrieved 2026-08-21):

1. Reads ``.workshop/context.json`` (written by ``scripts/setup.sh``) for the
   Foundry project endpoint. No endpoint or resource name is ever hardcoded
   here.
2. Zips ``src/hosted-agent/`` in-memory, excluding everything matched by its
   ``.agentignore`` (a small, gitignore-style subset -- comments, blank
   lines, ``dir/`` suffixes, and ``fnmatch`` globs; no negation or ``**``,
   since the bundled ``.agentignore`` never needs them).
3. Validates that the required entry point/dependency/domain files are
   present in the zip and that ``--cpu``/``--memory`` form one of the three
   documented Hosted Agent tiers, before making any network call.
4. Auto-injects ``AZURE_AI_MODEL_DEPLOYMENT_NAME`` into the container's
   environment variables from the ``primary_model_deployment_name``
   Terraform output, unless a participant already supplied it via
   ``--env AZURE_AI_MODEL_DEPLOYMENT_NAME=...``. ``FOUNDRY_PROJECT_ENDPOINT``
   is never set here -- the Hosted Agent platform injects it automatically
   (see ``src/hosted-agent/workflow.py``'s ``_default_chat_client``).
5. Calls ``create_version_from_code`` with a ``HostedAgentDefinition`` using
   ``CodeConfiguration(runtime="python_3_13", entry_point=["python",
   "main.py"], dependency_resolution=REMOTE_BUILD)`` and
   ``protocol_versions=[responses@1.0.0]`` (port 8088, per
   ``src/hosted-agent/main.py``). Every call creates a new, immutable agent
   version -- this script never mutates an existing version.
6. Polls ``get_version`` with a bounded timeout (never an unbounded loop)
   until the version reaches ``active`` or ``failed``, then prints both a
   human-readable summary and (with ``--output json``) a machine-readable
   result -- including the SDK's ``version.error`` details when the service
   populates them on a failed version (not just ``status``).

This script never fabricates a deep link into the Foundry portal: the
``azure-ai-projects`` SDK does not return an agent/version playground URL
(confirmed by inspecting ``AgentEndpointConfig``/``AgentVersionDetails`` in
the installed SDK -- neither carries a URL field), and this repo's own
``infra/outputs.tf`` (``foundry_portal_url``) already documents that no
officially confirmed deep-link format was found. Deploy output instead
prints the generic portal URL plus the account/project/agent/version
identifiers a participant needs to navigate there by hand.

Design, mirroring scripts/create_toolbox.py and scripts/run_evaluation.py:
zip assembly, ignore-pattern matching, tier validation, and the bounded poll
loop are pure functions, fully unit/contract-testable without Azure access or
a real zip file on disk. Only ``main`` performs I/O (reading files under
src/hosted-agent/, calling the azure-ai-projects SDK).

Authentication: az login only, via AzureCliCredential (default) or
DefaultAzureCredential (--credential default). No API keys, connection
strings, or client secrets are read anywhere in this script.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import io
import json
import sys
import time
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Make the sibling `lib` package importable regardless of current working
# directory (scripts/ is intentionally not an installed Python package).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    CodeConfiguration,
    CodeDependencyResolution,
    HostedAgentDefinition,
    ProtocolVersionRecord,
)
from azure.core.exceptions import HttpResponseError
from lib.workshop_context import (
    DEFAULT_CONTEXT_PATH,
    WorkshopContextError,
    build_credential,
    load_context,
    project_endpoint,
    terraform_output,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = REPO_ROOT / "src" / "hosted-agent"
DEFAULT_AGENTIGNORE_NAME = ".agentignore"

# Shared with delete_hosted_agent.py (imported from there) so both scripts
# target the same agent by default without duplicating the literal.
DEFAULT_HOSTED_AGENT_NAME = "contoso-travel-hosted-planner"

DEFAULT_RUNTIME = "python_3_13"
DEFAULT_ENTRY_POINT = ["python", "main.py"]
DEFAULT_PROTOCOL = "responses"
DEFAULT_PROTOCOL_VERSION = "1.0.0"

# The only cpu/memory pairs documented for Hosted Agents at authoring time
# (Microsoft Foundry azd-ai-cli reference, retrieved 2026-08-21). Rejecting
# anything else here surfaces a clear error before any network call, instead
# of a confusing 4xx from the service.
VALID_CPU_MEMORY_TIERS: tuple[tuple[str, str], ...] = (
    ("0.5", "1Gi"),
    ("1", "2Gi"),
    ("2", "4Gi"),
)
DEFAULT_CPU, DEFAULT_MEMORY = "1", "2Gi"

# Files that must be present in the zip for the Responses-protocol workflow
# to have any chance of building/running remotely. Not exhaustive -- just
# the ones whose absence means "wrong directory" or "broken scaffold" rather
# than a REMOTE_BUILD-time dependency problem.
REQUIRED_SOURCE_FILES: tuple[str, ...] = (
    "main.py",
    "requirements.txt",
    "domain.py",
    "workflow.py",
)

DEFAULT_VERSION_DESCRIPTION = (
    "Contoso travel trip-planning workflow (Microsoft Agent Framework, Responses protocol)."
)
DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_TIMEOUT_SECONDS = 600.0

TERMINAL_STATUSES = frozenset({"active", "failed"})


# ---------------------------------------------------------------------------
# Pure logic (unit-testable, no Azure/network/filesystem access beyond the
# explicit source_dir walk performed by iter_source_files)
# ---------------------------------------------------------------------------


def parse_ignore_patterns(text: str) -> list[str]:
    """Parse ``.agentignore`` content into a list of patterns.

    Supports the small gitignore subset this repo's bundled ``.agentignore``
    actually uses: blank lines and ``#`` comments are skipped, a trailing
    ``/`` marks a directory-only pattern, everything else is an
    ``fnmatch``-style glob matched against either the path's basename or its
    full repo-relative-to-``source_dir`` posix path. Negation (``!``) and
    ``**`` are intentionally unsupported since nothing in this repo's
    ``.agentignore`` needs them -- adding silent partial support for them
    would be more misleading than refusing them outright.
    """
    patterns: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("!"):
            raise WorkshopContextError(
                f"'{DEFAULT_AGENTIGNORE_NAME}' negation ('!') is not supported: {raw_line!r}"
            )
        if "**" in line:
            raise WorkshopContextError(
                f"'{DEFAULT_AGENTIGNORE_NAME}' '**' patterns are not supported: {raw_line!r}"
            )
        patterns.append(line)
    return patterns


def is_ignored(relative_posix_path: str, patterns: list[str]) -> bool:
    """True if ``relative_posix_path`` (posix-separated, relative to the
    source directory) matches any pattern from :func:`parse_ignore_patterns`.

    A directory pattern (``dir/``) matches if any ancestor path segment
    equals it (which hides everything under that directory, since we only
    ever walk files, never bare directory entries). A pattern with no ``/``
    matches the basename at any depth (gitignore's default). A pattern
    containing ``/`` is matched against the full relative path.
    """
    parts = relative_posix_path.split("/")
    basename = parts[-1]
    ancestors = parts[:-1]
    for pattern in patterns:
        if pattern.endswith("/"):
            directory = pattern.rstrip("/")
            if any(fnmatch.fnmatch(segment, directory) for segment in ancestors):
                return True
            continue
        if "/" in pattern:
            if fnmatch.fnmatch(relative_posix_path, pattern):
                return True
        elif fnmatch.fnmatch(basename, pattern):
            return True
    return False


def iter_source_files(source_dir: Path, patterns: list[str]) -> list[Path]:
    """List every non-ignored file under ``source_dir``, sorted for a
    deterministic zip layout (and thus a deterministic content hash for
    otherwise-unchanged source)."""
    files: list[Path] = []
    for path in source_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(source_dir).as_posix()
        if is_ignored(relative, patterns):
            continue
        files.append(path)
    return sorted(files, key=lambda p: p.relative_to(source_dir).as_posix())


def validate_required_files(source_dir: Path, files: list[Path]) -> None:
    """Raise ``WorkshopContextError`` if any :data:`REQUIRED_SOURCE_FILES` is
    missing from the (non-ignored) file list -- catches "wrong directory" or
    a broken scaffold before any network call."""
    present = {f.relative_to(source_dir).as_posix() for f in files}
    missing = [name for name in REQUIRED_SOURCE_FILES if name not in present]
    if missing:
        raise WorkshopContextError(
            f"{source_dir} is missing required file(s): {', '.join(missing)}. "
            "Check that --source-dir points at src/hosted-agent/ and that "
            ".agentignore is not over-excluding."
        )


AZURE_AI_MODEL_DEPLOYMENT_NAME_VAR = "AZURE_AI_MODEL_DEPLOYMENT_NAME"
PRIMARY_MODEL_DEPLOYMENT_OUTPUT = "primary_model_deployment_name"


def resolve_environment_variables(
    explicit_env: dict[str, str], *, context: dict[str, Any]
) -> dict[str, str]:
    """Merge ``--env`` overrides with the model deployment name auto-injected
    from Terraform.

    ``AZURE_AI_MODEL_DEPLOYMENT_NAME`` is required at runtime by every real
    agent in ``src/hosted-agent/workflow.py`` (see
    ``workflow._default_chat_client``), so it is auto-set here from the
    ``primary_model_deployment_name`` Terraform output rather than requiring
    every participant to look it up and pass ``--env`` by hand. An explicit
    ``--env AZURE_AI_MODEL_DEPLOYMENT_NAME=...`` always wins.

    ``FOUNDRY_PROJECT_ENDPOINT`` is intentionally never set here: the Hosted
    Agent platform injects it into the container automatically once
    deployed (see the microsoft-foundry skill's "Expected env-var
    fingerprint" reference), so setting it explicitly would be redundant at
    best and could shadow the platform's own value at worst.
    """
    if AZURE_AI_MODEL_DEPLOYMENT_NAME_VAR in explicit_env:
        return dict(explicit_env)
    model_deployment_name = terraform_output(context, PRIMARY_MODEL_DEPLOYMENT_OUTPUT)
    return {**explicit_env, AZURE_AI_MODEL_DEPLOYMENT_NAME_VAR: model_deployment_name}


def validate_cpu_memory(cpu: str, memory: str) -> None:
    """Raise ``WorkshopContextError`` if ``(cpu, memory)`` is not one of the
    documented Hosted Agent tiers."""
    if (cpu, memory) not in VALID_CPU_MEMORY_TIERS:
        valid = ", ".join(f"{c}/{m}" for c, m in VALID_CPU_MEMORY_TIERS)
        raise WorkshopContextError(
            f"unsupported --cpu/--memory combination '{cpu}'/'{memory}'. Valid tiers: {valid}."
        )


def build_zip_bytes(source_dir: Path, files: list[Path]) -> bytes:
    """Zip ``files`` (already filtered by :func:`iter_source_files`) into an
    in-memory archive with paths relative to ``source_dir``, for
    ``create_version_from_code``'s ``code`` parameter."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            arcname = file_path.relative_to(source_dir).as_posix()
            archive.write(file_path, arcname=arcname)
    return buffer.getvalue()


def sha256_hex(data: bytes) -> str:
    """SHA-256 hex digest, passed as ``code_zip_sha256`` so the service can
    verify upload integrity."""
    return hashlib.sha256(data).hexdigest()


def build_definition(
    *,
    cpu: str,
    memory: str,
    runtime: str = DEFAULT_RUNTIME,
    entry_point: list[str] | None = None,
    protocol: str = DEFAULT_PROTOCOL,
    protocol_version: str = DEFAULT_PROTOCOL_VERSION,
    environment_variables: dict[str, str] | None = None,
) -> HostedAgentDefinition:
    """Build the ``HostedAgentDefinition`` for a REMOTE_BUILD code deployment.

    Kept separate from any Azure call so its shape (in particular
    ``kind == AgentKind.HOSTED`` and ``dependency_resolution ==
    CodeDependencyResolution.REMOTE_BUILD``) can be asserted in tests without
    a live project or network access.
    """
    # HostedAgentDefinition.__init__ sets kind=AgentKind.HOSTED unconditionally
    # (see azure.ai.projects.models), so it is never passed explicitly here.
    return HostedAgentDefinition(
        cpu=cpu,
        memory=memory,
        environment_variables=environment_variables or None,
        protocol_versions=[ProtocolVersionRecord(protocol=protocol, version=protocol_version)],
        code_configuration=CodeConfiguration(
            runtime=runtime,
            entry_point=entry_point or list(DEFAULT_ENTRY_POINT),
            dependency_resolution=CodeDependencyResolution.REMOTE_BUILD,
        ),
    )


def poll_version(
    *,
    retrieve: Callable[[], Any],
    interval_seconds: float,
    timeout_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], float] = time.monotonic,
) -> Any:
    """Poll ``get_version`` until the version reaches a terminal status, with
    a bound. Never loops unboundedly: raises ``WorkshopContextError`` once
    ``timeout_seconds`` has elapsed. ``retrieve``/``sleep``/``now`` are
    injected so this is fully unit-testable without real waiting or a live
    SDK client (mirrors scripts/run_evaluation.py's ``poll_run``).
    """
    deadline = now() + timeout_seconds
    version = retrieve()
    while str(version.status) not in TERMINAL_STATUSES:
        if now() >= deadline:
            raise WorkshopContextError(
                f"agent version did not reach a terminal state within {timeout_seconds:.0f}s "
                f"(last status: {version.status}). Check the Foundry portal, or re-run with "
                "a larger --timeout."
            )
        sleep(interval_seconds)
        version = retrieve()
    return version


def _extract_version_error(version: Any) -> dict[str, Any] | None:
    """Return the SDK's raw ``error`` field for a failed version, if the
    service populated one.

    ``AgentVersionDetails`` does not statically declare an ``error``
    attribute in the installed ``azure-ai-projects`` SDK (only ``status``),
    but like every generated model in this SDK it wraps the raw
    deserialized JSON response as a dict-like object (``Model`` extends
    ``MutableMapping``), so ``version.get("error")`` still returns a
    service-populated ``error`` field when one is present -- this is a
    genuine SDK access pattern (verified via ``inspect.getsource`` on the
    installed SDK), not a fabricated field. Returns ``None`` when the
    service did not include one, so callers can fall back to a generic hint.
    """
    getter = getattr(version, "get", None)
    if not callable(getter):
        return None
    error = getter("error")
    if error is None:
        return None
    if isinstance(error, dict):
        return error
    # A typed ApiError-like object rather than a plain dict: pull out the
    # documented fields (code/message/param/type) via getattr.
    detail = {
        key: value
        for key, value in (
            ("code", getattr(error, "code", None)),
            ("message", getattr(error, "message", None)),
            ("param", getattr(error, "param", None)),
            ("type", getattr(error, "type", None)),
        )
        if value is not None
    }
    return detail or None


def build_result(
    *,
    agent_name: str,
    version: Any,
    context: dict[str, Any],
    endpoint: str,
) -> dict[str, Any]:
    """Assemble the machine-readable result dict shared by ``--output
    json`` and the human-readable summary. No deep link is fabricated here
    (see module docstring); only identifiers a participant can use to
    navigate the portal by hand are included.
    """
    status = str(version.status)
    result: dict[str, Any] = {
        "agent_name": agent_name,
        "version": version.version,
        "status": status,
        "succeeded": status == "active",
        "project_endpoint": endpoint,
        "portal_url": terraform_output(context, "foundry_portal_url"),
        "ai_services_account_name": terraform_output(context, "ai_services_account_name"),
        "foundry_project_name": terraform_output(context, "foundry_project_name"),
    }
    if status == "failed":
        error_detail = _extract_version_error(version)
        if error_detail:
            result["error"] = error_detail
        else:
            result["failure_hint"] = (
                "The Foundry API did not return a structured 'error' field for this "
                "version; check the Foundry portal's Agents > "
                f"{agent_name} > version {version.version} page, or App Insights traces, for "
                "the remote build/runtime error."
            )
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--context", type=Path, default=DEFAULT_CONTEXT_PATH, help="Path to .workshop/context.json"
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="Directory to zip and deploy (default: src/hosted-agent/)",
    )
    parser.add_argument(
        "--agent-name",
        default=DEFAULT_HOSTED_AGENT_NAME,
        help="Hosted Agent name to create a version for",
    )
    parser.add_argument("--cpu", default=DEFAULT_CPU, help=f"CPU tier (default: {DEFAULT_CPU})")
    parser.add_argument(
        "--memory", default=DEFAULT_MEMORY, help=f"Memory tier (default: {DEFAULT_MEMORY})"
    )
    parser.add_argument(
        "--description", default=None, help="Description recorded on the new agent version"
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Environment variable to set in the hosted container (repeatable)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Seconds between version status polls",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Maximum seconds to wait for the version to become active/failed",
    )
    parser.add_argument(
        "--credential",
        choices=["azure-cli", "default"],
        default="azure-cli",
        help="Credential source (both are az login-only; default: azure-cli)",
    )
    parser.add_argument(
        "--output", choices=["human", "json"], default="human", help="Output format"
    )
    return parser.parse_args(argv)


def _parse_env_pairs(pairs: list[str]) -> dict[str, str]:
    env: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise WorkshopContextError(f"--env value '{pair}' is not in KEY=VALUE form")
        key, _, value = pair.partition("=")
        if not key:
            raise WorkshopContextError(f"--env value '{pair}' has an empty key")
        env[key] = value
    return env


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        context = load_context(args.context)
        endpoint = project_endpoint(context)
        validate_cpu_memory(args.cpu, args.memory)
        explicit_env = _parse_env_pairs(args.env)
        environment_variables = resolve_environment_variables(explicit_env, context=context)

        agentignore_path = args.source_dir / DEFAULT_AGENTIGNORE_NAME
        patterns = (
            parse_ignore_patterns(agentignore_path.read_text(encoding="utf-8"))
            if agentignore_path.exists()
            else []
        )
        files = iter_source_files(args.source_dir, patterns)
        validate_required_files(args.source_dir, files)
        zip_bytes = build_zip_bytes(args.source_dir, files)
        definition = build_definition(
            cpu=args.cpu, memory=args.memory, environment_variables=environment_variables
        )
    except WorkshopContextError as exc:
        print(f"deploy_hosted_agent.py: {exc}", file=sys.stderr)
        return 2

    credential = build_credential(args.credential)
    try:
        with AIProjectClient(endpoint=endpoint, credential=credential) as client:
            created = client.agents.create_version_from_code(
                args.agent_name,
                definition=definition,
                code=io.BytesIO(zip_bytes),
                code_zip_sha256=sha256_hex(zip_bytes),
                description=args.description or DEFAULT_VERSION_DESCRIPTION,
            )
            version = poll_version(
                retrieve=lambda: client.agents.get_version(args.agent_name, created.version),
                interval_seconds=args.poll_interval,
                timeout_seconds=args.timeout,
            )
    except HttpResponseError as exc:
        print(
            f"deploy_hosted_agent.py: Foundry API error creating agent version: {exc}",
            file=sys.stderr,
        )
        return 1
    except WorkshopContextError as exc:
        print(f"deploy_hosted_agent.py: {exc}", file=sys.stderr)
        return 1

    result = build_result(
        agent_name=args.agent_name, version=version, context=context, endpoint=endpoint
    )

    if args.output == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"agent:   {result['agent_name']}")
        print(f"version: {result['version']}")
        print(f"status:  {result['status']}")
        if "error" in result:
            error = result["error"]
            print(
                f"error:   {error.get('code', '(no code)')}: {error.get('message', '(no message)')}"
            )
        elif "failure_hint" in result:
            print(f"note:    {result['failure_hint']}")
        print(f"project endpoint: {result['project_endpoint']}")
        print(
            f"portal:  {result['portal_url']} (open, then find "
            f"account '{result['ai_services_account_name']}' > project "
            f"'{result['foundry_project_name']}' > Agents > {result['agent_name']} > "
            f"version {result['version']} > Playground)"
        )

    return 0 if result["succeeded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

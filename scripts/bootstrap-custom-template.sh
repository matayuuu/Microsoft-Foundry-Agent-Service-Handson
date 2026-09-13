#!/usr/bin/env bash
set -euo pipefail

for prerequisite in az python3; do
    if ! command -v "$prerequisite" >/dev/null 2>&1; then
        printf 'bootstrap runtime: required executable %s is missing from the Deployment Scripts image.\n' "$prerequisite" >&2
        exit 1
    fi
done

# Keep Azure CLI's interpreter and automatically signed-in identity untouched.
python3 -I - <<'PY'
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import ssl
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

REPOSITORY = "matayuuu/Microsoft-Foundry-Agent-Service-Handson"
MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_EXTRACTED_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 20000
TRANSIENT_HTTP = {408, 425, 429, 500, 502, 503, 504}


def fail(stage, message):
    raise RuntimeError(f"bootstrap {stage}: {message}")


def validate_environment(environment):
    revision = environment.get("WORKSHOP_SOURCE_REVISION", "")
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        fail("inputs", "WORKSHOP_SOURCE_REVISION must be a published lowercase 40-character SHA.")
    try:
        context = json.loads(environment.get("WORKSHOP_CONTEXT_JSON", ""))
    except (TypeError, ValueError):
        fail("inputs", "WORKSHOP_CONTEXT_JSON must contain the non-secret template context.")
    if not isinstance(context, dict) or context.get("source_revision") != revision:
        fail("inputs", "context.source_revision must equal WORKSHOP_SOURCE_REVISION.")
    expected_source = f"https://github.com/{REPOSITORY}/blob/{revision}"
    if context.get("source_base") != expected_source:
        fail("inputs", "context.source_base must reference the fixed workshop repository and SHA.")
    if context.get("schema_version") != "2.0":
        fail("inputs", "WORKSHOP_CONTEXT_JSON must use the current schema version 2.0.")
    output = environment.get("AZ_SCRIPTS_OUTPUT_PATH", "")
    if not output or not Path(output).is_absolute():
        fail("inputs", "AZ_SCRIPTS_OUTPUT_PATH must be supplied by Azure Deployment Scripts.")
    if Path(output).is_symlink() or Path(output).is_dir():
        fail("inputs", "AZ_SCRIPTS_OUTPUT_PATH must name a regular output file, not a link/directory.")
    return revision


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        fail("source download", "unexpected archive redirect; only the fixed source URL is allowed.")


def download_source(revision, destination, *, sleep=time.sleep):
    url = f"https://codeload.github.com/{REPOSITORY}/tar.gz/{revision}"
    opener = urllib.request.build_opener(NoRedirect())
    for attempt in range(1, 6):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "foundry-workshop-bootstrap"})
            with opener.open(request, timeout=120) as response, destination.open("wb") as output:
                total = 0
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > MAX_ARCHIVE_BYTES:
                        fail("source download", "archive exceeds the supported size limit.")
                    output.write(chunk)
            return
        except urllib.error.HTTPError as exc:
            if exc.code not in TRANSIENT_HTTP or attempt == 5:
                fail("source download", f"HTTP {exc.code}; confirm that the exact SHA is published.")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if isinstance(getattr(exc, "reason", None), ssl.SSLCertVerificationError):
                fail("source download", "TLS certificate verification failed.")
            if attempt == 5:
                fail("source download", "network readiness retries exhausted.")
        delay = min(2 ** attempt, 30)
        print(f"bootstrap source download: transient failure; retry {attempt}/4 in {delay}s.", flush=True)
        sleep(delay)


def extract_source(archive_path, destination, revision):
    expected_root = f"Microsoft-Foundry-Agent-Service-Handson-{revision}"
    with tarfile.open(archive_path, "r:gz") as archive:
        members = []
        seen = set()
        total = 0
        for member in archive:
            name = PurePosixPath(member.name)
            if (
                name.is_absolute()
                or ".." in name.parts
                or "\\" in member.name
                or ":" in member.name
                or not name.parts
                or name.parts[0] != expected_root
                or not (member.isdir() or member.isfile())
                or name in seen
                or member.size < 0
            ):
                fail("source extraction", "archive contains an unsafe, duplicate, or unexpected entry.")
            seen.add(name)
            total += member.size
            if len(seen) > MAX_MEMBERS or total > MAX_EXTRACTED_BYTES:
                fail("source extraction", "archive exceeds the supported extraction limits.")
            members.append(member)
        for member in members:
            path = destination.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, path.open("xb") as output:
                    shutil.copyfileobj(source, output)
                path.chmod(0o755 if member.mode & 0o111 else 0o644)
    root = destination / expected_root
    for relative in ("pyproject.toml", "scripts/bootstrap_custom_template.py"):
        if not (root / relative).is_file():
            fail("source extraction", f"pinned archive is missing {relative}.")
    return root


def main():
    revision = validate_environment(os.environ)
    Path(os.environ["AZ_SCRIPTS_OUTPUT_PATH"]).unlink(missing_ok=True)
    if not (3, 10) <= sys.version_info[:2] < (3, 14):
        fail("runtime", "select a supported AzureCLI image with Python 3.10 through 3.13.")
    for module in ("venv", "ensurepip", "ssl"):
        if importlib.util.find_spec(module) is None:
            fail(
                "runtime",
                f"Python {module} is unavailable. Select a supported Deployment Scripts AzureCLI "
                "image with venv and ensurepip; never install into Azure CLI's interpreter.",
            )
    # The service working directory can be an Azure Files mount. Keep Python,
    # executable files, and package build operations on the container filesystem.
    work = Path(tempfile.mkdtemp(prefix="foundry-workshop-", dir="/tmp"))
    archive = work / "source.tar.gz"
    print(f"bootstrap source download: fetching pinned revision {revision}.", flush=True)
    download_source(revision, archive)
    try:
        root = extract_source(archive, work, revision)
    except (OSError, tarfile.TarError) as exc:
        fail("source extraction", f"archive could not be safely extracted ({type(exc).__name__}).")
    archive.unlink()
    virtual_environment = work / "python"
    environment = os.environ.copy()
    for key in ("PYTHONHOME", "PYTHONPATH"):
        environment.pop(key, None)
    environment["PYTHONNOUSERSITE"] = "1"
    build_work = work / "pip-work"
    build_work.mkdir(mode=0o700)
    for key in ("TMPDIR", "TEMP", "TMP"):
        environment[key] = str(build_work)
    try:
        subprocess.run(
            [sys.executable, "-I", "-m", "venv", str(virtual_environment)],
            check=True, env=environment,
        )
    except subprocess.CalledProcessError:
        fail("runtime", "venv creation failed; use an AzureCLI image with working venv/ensurepip.")
    python = virtual_environment / "bin" / "python"
    print("bootstrap dependencies: installing only the project's provisioning dependencies.", flush=True)
    try:
        subprocess.run(
            [str(python), "-I", "-m", "pip", "--isolated", "--disable-pip-version-check",
             "install", "--no-input", "--no-cache-dir", "."],
            cwd=root, check=True, env=environment,
        )
    except subprocess.CalledProcessError:
        fail("dependencies", "provisioning dependency installation failed in the isolated venv.")
    result = subprocess.run(
        [str(python), "-s", "scripts/bootstrap_custom_template.py"],
        cwd=root, env=environment, check=False,
    )
    return result.returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, tarfile.TarError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
PY

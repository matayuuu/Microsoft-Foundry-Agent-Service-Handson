"""Launch repository-scoped JupyterLab behind an explicitly selected Web preview."""

from __future__ import annotations

import argparse
import getpass
import hmac
import ipaddress
import json
import os
import re
import secrets
import socket
import stat
import sys
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from scripts.cloud_shell_environment import (
    EnvironmentError,
    state_directory,
    validate_ready,
)


@dataclass(frozen=True)
class Preview:
    origin: str
    hostname: str
    base_url: str

    @property
    def url(self) -> str:
        return self.origin + self.base_url


@dataclass
class PreviewCapture:
    nonce: str
    port: int
    preview: Preview | None = None


class LauncherParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(
            2,
            "Invalid launcher arguments (values are not echoed). Use --help. "
            "Use a supported Cloud Shell port and an actual HTTPS preview URL without secrets.\n",
        )


def port_number(value: str) -> int:
    if not re.fullmatch(r"[1-9][0-9]{0,4}", value) or not (
        1025 <= int(value) <= 8079 or 8091 <= int(value) <= 49151
    ):
        raise argparse.ArgumentTypeError("Cloud Shell ports are 1025-8079 or 8091-49151")
    return int(value)


def base_path(value: str) -> str:
    if (
        not value.startswith("/")
        or not re.fullmatch(r"/[A-Za-z0-9._~/-]*", value)
        or "//" in value
        or any(part in {".", ".."} for part in value.split("/"))
    ):
        raise ValueError("base URL must be an absolute URL path without query, escapes, or '..'")
    return value.rstrip("/") + "/"


def preview_url(value: str, base_url: str | None = None) -> Preview:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        port = parsed.port
        labels = host.split(".")
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or "?" in value
            or "#" in value
            or any(character.isspace() for character in value)
            or "\\" in value
            or len(labels) < 2
            or any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels
            )
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise ValueError("Not a preview origin")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError("An actual preview hostname is required")
        path = base_path(parsed.path or "/")
        if base_url is not None:
            path = base_path(base_url)
        origin = f"https://{host}" + (f":{port}" if port and port != 443 else "")
        return Preview(origin, host, path)
    except ValueError as exc:
        raise ValueError(
            "--preview-url must be the actual HTTPS Web preview URL, with a DNS hostname "
            "and no credentials, query, or fragment. Use --base-url only for a verified proxy path."
        ) from exc


def ensure_port_available(host: str, port: int) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if os.name == "posix":
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((host, port))
            probe.listen(1)
    except OSError as exc:
        raise EnvironmentError(
            f"Port {port} is unavailable. Stop your previous preview/Jupyter server with "
            "Ctrl-C, or explicitly choose another --port and open that port in Web preview. "
            "The launcher never chooses another port automatically."
        ) from exc


def private_directory(path: Path, repo: Path) -> Path:
    """Do not follow a link or silently change permissions on an existing directory."""
    if path.is_symlink() or path.resolve().is_relative_to(repo):
        raise EnvironmentError(
            "Jupyter runtime/config must be outside the repository, not symlinked."
        )
    if not path.exists():
        private_directory(path.parent, repo)
        path.mkdir(mode=0o700)
    metadata = path.stat()
    if (
        not path.is_dir()
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) not in {0o700, 0o1700}
    ):
        raise EnvironmentError(
            f"{path} must be user-owned with permissions 0700 (sticky bit permitted). "
            "Do not enable JUPYTER_ALLOW_INSECURE_WRITES."
        )
    return path


def read_token_file(path: Path, repo: Path) -> str:
    if (
        not path.is_absolute()
        or path.is_symlink()
        or not path.is_file()
        or path.resolve().is_relative_to(repo)
    ):
        raise EnvironmentError(
            "JUPYTER_TOKEN_FILE must be a regular absolute file outside the repo."
        )
    metadata = path.stat()
    if (
        metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o600
        or metadata.st_size > 256
    ):
        raise EnvironmentError(
            "JUPYTER_TOKEN_FILE must be user-owned, mode 0600, and at most 256 bytes."
        )
    token = path.read_text(encoding="ascii")
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token):
        raise EnvironmentError(
            "JUPYTER_TOKEN_FILE must contain 32-256 random URL-safe characters with no newline."
        )
    return token


def write_token(path: Path) -> str:
    token = secrets.token_urlsafe(32)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        handle.write(token)
    return token


def password_hash() -> str:
    if not sys.stdin.isatty():
        raise EnvironmentError(
            "Start Jupyter in an interactive Cloud Shell terminal to choose a private password, "
            "or supply your existing 0600 JUPYTER_TOKEN_FILE outside the repository. "
            "Never put a password/token in command-line arguments or a URL."
        )
    first = getpass.getpass("Choose a Jupyter password (at least 12 characters; not echoed): ")
    second = getpass.getpass("Repeat the Jupyter password: ")
    if len(first) < 12 or not hmac.compare_digest(first.encode(), second.encode()):
        raise EnvironmentError(
            "Passwords must match and contain at least 12 characters; try again."
        )
    from jupyter_server.auth.security import passwd

    return passwd(first)


def server_arguments(
    repo: Path, runtime: Path, preview: Preview, host: str, port: int
) -> list[str]:
    # Explicit CLI values take precedence over any installed Jupyter config.
    values: dict[str, object] = {
        "ServerApp.root_dir": str(repo),
        "ServerApp.ip": host,
        "ServerApp.port": port,
        "ServerApp.port_retries": 0,
        "ServerApp.open_browser": False,
        "ServerApp.use_redirect_file": False,
        "ServerApp.allow_remote_access": False,
        "ServerApp.local_hostnames": ["localhost", preview.hostname],
        "ServerApp.allow_origin": preview.origin,
        "ServerApp.allow_origin_pat": "",
        "ServerApp.allow_credentials": False,
        "ServerApp.disable_check_xsrf": False,
        "ServerApp.trust_xheaders": False,
        "ServerApp.allow_unauthenticated_access": False,
        "ServerApp.authenticate_prometheus": True,
        "ServerApp.base_url": preview.base_url,
        "ServerApp.default_url": "/lab",
        "ServerApp.custom_display_url": preview.url,
        "ServerApp.cookie_secret_file": str(runtime / "jupyter-cookie-secret"),
        "LabApp.user_settings_dir": str(runtime / "lab-settings"),
        "LabApp.workspaces_dir": str(runtime / "lab-workspaces"),
        "KernelSpecManager.ensure_native_kernel": False,
        "KernelSpecManager.allowed_kernelspecs": ["foundry-workshop", "foundry-hosted-agent"],
        "MappingKernelManager.default_kernel_name": "foundry-workshop",
        "ServerApp.identity_provider_class": (
            "scripts.cloud_shell_identity.CloudShellIdentityProvider"
        ),
        "IdentityProvider.secure_cookie": True,
        "IdentityProvider.cookie_options": {"secure": True, "httponly": True, "samesite": "Lax"},
        "PasswordIdentityProvider.allow_password_change": False,
        "ServerApp.tornado_settings": {
            "xsrf_cookie_kwargs": {"secure": True, "samesite": "Lax"},
            "compress_response": False,
        },
        "FileContentsManager.allow_hidden": False,
        "Application.log_level": "INFO",
    }
    return [
        f"--{key}={value!r}" if isinstance(value, (dict, list)) else f"--{key}={value}"
        for key, value in values.items()
    ]


class DiscoveryHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = (
            b"Cloud Shell preview discovery only; no repository files are served.\n"
            b"Copy this tab's HTTPS URL. Stop discovery with Ctrl-C, then run:\n"
            b"bash scripts/start-cloud-shell-jupyter.sh --preview-url 'COPIED_HTTPS_URL'\n"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        # Never reflect an untrusted Host, URL query, or proxy header into logs.
        pass


def capture_preview(payload: object, capture: PreviewCapture) -> Preview:
    if not isinstance(payload, dict) or not hmac.compare_digest(
        str(payload.get("nonce", "")), capture.nonce
    ):
        raise ValueError("Preview discovery authorization failed.")
    value = payload.get("url")
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("Preview discovery did not receive a valid URL.")
    preview = preview_url(value)
    if not preview.hostname.endswith(
        (".servicebus.windows.net", ".servicebus.usgovcloudapi.net")
    ) or not preview.base_url.endswith(f"/proxy/{capture.port}/"):
        raise ValueError("Preview discovery did not originate from this Cloud Shell port.")
    return preview


def automatic_discovery_page(capture: PreviewCapture) -> bytes:
    nonce = json.dumps(capture.nonce)
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>Starting JupyterLab</title></head>"
        '<body id="cloud-shell-preview-discovery">'
        "<h1>Cloud Shell preview detected</h1>"
        '<p id="status">Starting the secured JupyterLab server. Keep this tab open.</p>'
        f'<script nonce="{capture.nonce}">'
        "(()=>{const status=document.getElementById('status');"
        "const captureUrl=new URL('capture',location.href);"
        "const previewUrl=location.origin+location.pathname;"
        "fetch(captureUrl,{method:'POST',credentials:'same-origin',cache:'no-store',"
        "headers:{'Content-Type':'application/json'},"
        f"body:JSON.stringify({{nonce:{nonce},url:previewUrl}})}})"
        ".then(response=>{if(!response.ok)throw Error('capture failed');"
        "status.textContent='JupyterLab is starting. This page reloads automatically.';"
        "const retry=async()=>{try{const response=await fetch(location.href,"
        "{credentials:'same-origin',cache:'no-store'});const text=await response.text();"
        "if(!text.includes('cloud-shell-preview-discovery')){location.reload();return;}}"
        "catch{}setTimeout(retry,1500);};setTimeout(retry,1500);})"
        ".catch(()=>{status.textContent='Preview detection failed. Return to the terminal.';});"
        "})();</script></body></html>"
    ).encode()


def automatic_discovery_handler(capture: PreviewCapture) -> type[BaseHTTPRequestHandler]:
    class AutomaticDiscoveryHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = automatic_discovery_page(capture)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Content-Security-Policy",
                f"default-src 'none'; script-src 'nonce-{capture.nonce}'; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
                "form-action 'none'",
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path != "/capture":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
                if self.headers.get_content_type() != "application/json" or not 1 <= length <= 4096:
                    raise ValueError("Invalid preview capture request.")
                payload = json.loads(self.rfile.read(length))
                preview = capture_preview(payload, capture)
            except (ValueError, json.JSONDecodeError):
                self.send_error(400)
                return
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)
            capture.preview = preview

        def log_message(self, format: str, *args: object) -> None:
            # Never reflect an untrusted Host, URL, or request body into logs.
            pass

    return AutomaticDiscoveryHandler


def automatic_discover_preview(host: str, port: int, timeout: int = 300) -> Preview:
    capture = PreviewCapture(secrets.token_urlsafe(24), port)
    deadline = time.monotonic() + timeout
    with HTTPServer((host, port), automatic_discovery_handler(capture)) as server:
        server.timeout = 1
        print(f"Open Cloud Shell Web preview for port {port}, then choose Open and browse.")
        print("The preview tab will detect its URL and reload into JupyterLab automatically.")
        while capture.preview is None:
            if time.monotonic() >= deadline:
                raise EnvironmentError(
                    "Timed out waiting for Web preview. Run this command again, open the same "
                    "port, and choose Open and browse."
                )
            server.handle_request()
    return capture.preview


def discover_preview(host: str, port: int) -> None:
    with HTTPServer((host, port), DiscoveryHandler) as server:
        print(
            f"Discovery only on port {port}. "
            f"In Cloud Shell choose Web preview, enter {port}, then Open and browse."
        )
        print(
            "Open the preview tab and copy its actual HTTPS URL. No URL is inferred from env vars."
        )
        print("Press Ctrl-C here, then restart with --preview-url 'COPIED_HTTPS_URL'.")
        print(
            "If loopback is unreachable, retry explicitly with --listen 0.0.0.0 and the same port."
        )
        server.serve_forever()


def validate_launch_environment() -> None:
    if os.environ.get("JUPYTER_ALLOW_INSECURE_WRITES") or os.environ.get("JUPYTER_TOKEN"):
        raise EnvironmentError(
            "Unset JUPYTER_ALLOW_INSECURE_WRITES and JUPYTER_TOKEN for this workshop process. "
            "Use the password prompt or a private JUPYTER_TOKEN_FILE, never command-line secrets."
        )


def launch(
    repo: Path,
    preview: Preview,
    host: str,
    port: int,
    *,
    prepared_password_hash: str | None = None,
) -> None:
    validate_launch_environment()
    from jupyterlab.labapp import LabApp
    from traitlets.config import Config

    class WorkshopLabApp(LabApp):
        load_other_extensions = False

        @classmethod
        def get_extension_package(cls) -> str:
            return "jupyterlab"

    ensure_port_available(host, port)
    runtime = private_directory(state_directory(repo) / "jupyter" / str(port), repo)
    import fcntl

    with (runtime / "launcher.lock").open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise EnvironmentError(
                "A Jupyter launcher already owns this port; stop it first."
            ) from exc
        token_path: Path
        generated = False
        hashed_password = ""
        external = os.environ.get("JUPYTER_TOKEN_FILE")
        if external:
            token_path = Path(external)
            token = read_token_file(token_path, repo)
        else:
            hashed_password = prepared_password_hash or password_hash()
            token_path = runtime / f"token-{secrets.token_hex(12)}"
            token = write_token(token_path)
            generated = True
        try:
            config_dir = private_directory(runtime / "config", repo)
            os.environ.update(
                JUPYTER_RUNTIME_DIR=str(runtime),
                JUPYTER_CONFIG_DIR=str(config_dir),
                JUPYTER_CONFIG_PATH=str(config_dir),
                JUPYTER_TOKEN_FILE=str(token_path),
                AZURE_TOKEN_CREDENTIALS="AzureCliCredential",
            )
            config = Config()
            config.PasswordIdentityProvider.hashed_password = hashed_password
            app = WorkshopLabApp.initialize_server(
                argv=server_arguments(repo, runtime, preview, host, port),
                config=config,
                runtime_dir=str(runtime),
            )
            app.kernel_spec_manager.kernel_dirs = [str(repo / ".venv/share/jupyter/kernels")]
            from scripts.cloud_shell_proxy import configure_relay

            configure_relay(app, preview.origin, preview.base_url)
            from scripts.cloud_shell_channels import install_channels

            channels = install_channels(app, preview.origin, preview.base_url)
            identity = app.identity_provider
            if (
                not identity.auth_enabled
                or not hmac.compare_digest(identity.token, token)
                or identity.token_generated
                or identity.hashed_password != hashed_password
            ):
                raise EnvironmentError("Jupyter authentication was overridden; refusing to serve.")
            print(f"Open {preview.url} in the actual Web preview tab.")
            print(
                "Sign in with your chosen password (or the existing token you supplied privately)."
            )
            print("Keep this terminal dedicated to Jupyter. Use New session for workshop commands.")
            print("Stop: save notebooks, press Ctrl-C and confirm, then close Web preview's port.")
            print("Restart: run this launcher again with the current actual preview URL.")
            try:
                app.start()
            finally:
                channels.close()
        finally:
            if generated:
                token_path.unlink(missing_ok=True)


def main() -> int:
    parser = LauncherParser(description=__doc__)
    parser.add_argument("--port", type=port_number, default=5000)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--auto-discover", action="store_true", help=argparse.SUPPRESS)
    modes.add_argument("--discover-preview", action="store_true")
    modes.add_argument(
        "--preview-url", help="Actual HTTPS URL from the Cloud Shell Web preview tab"
    )
    parser.add_argument("--base-url", help="Verified proxy base path (default: preview URL path)")
    parser.add_argument("--listen", choices=["127.0.0.1", "0.0.0.0"], default="127.0.0.1")
    arguments = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    try:
        if arguments.discover_preview and arguments.base_url:
            raise ValueError("--base-url requires --preview-url")
        validate_ready(repo)
        ensure_port_available(arguments.listen, arguments.port)
        if arguments.discover_preview:
            discover_preview(arguments.listen, arguments.port)
        else:
            if arguments.preview_url:
                preview = preview_url(arguments.preview_url, arguments.base_url)
                launch(repo, preview, arguments.listen, arguments.port)
            else:
                if arguments.base_url:
                    raise ValueError("--base-url requires --preview-url")
                validate_launch_environment()
                prepared_password_hash = (
                    None if os.environ.get("JUPYTER_TOKEN_FILE") else password_hash()
                )
                preview = automatic_discover_preview(arguments.listen, arguments.port)
                launch(
                    repo,
                    preview,
                    arguments.listen,
                    arguments.port,
                    prepared_password_hash=prepared_password_hash,
                )
        return 0
    except KeyboardInterrupt:
        print(
            "\nServer stopped. Close the Web preview port. Saved notebooks and state are unchanged."
        )
        return 0
    except (EnvironmentError, ValueError, OSError, ImportError) as exc:
        print(f"Cloud Shell Jupyter: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

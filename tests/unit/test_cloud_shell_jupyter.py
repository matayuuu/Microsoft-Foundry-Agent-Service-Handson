from __future__ import annotations

import argparse
import ast
import json
import os
import re
import socket
import stat
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import UTC
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import cloud_shell_jupyter as jupyter


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "1",
        "1024",
        "8080",
        "8090",
        "49152",
        "65535",
        "-1",
        "65536",
        "1.5",
        "auto",
        "05000",
        "5000\n",
        "1" * 1000,
    ],
)
def test_invalid_ports_fail(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        jupyter.port_number(value)


@pytest.mark.parametrize("value", ["1025", "5000", "8079", "8091", "49151"])
def test_explicit_port_is_used_exactly(value: str) -> None:
    assert jupyter.port_number(value) == int(value)


@pytest.mark.parametrize(
    "url",
    [
        "http://preview.example.test/",
        "https://name:secret@preview.example.test/",
        "https://preview.example.test/?token=private",
        "https://preview.example.test/#private",
        "https://*.example.test/",
        "https://127.0.0.1/",
        "https://localhost/",
        "https://preview.example.test:65536/",
        "https://preview.example.test/../",
        "https://preview.example.test/%2f",
        "https://preview.example.test//",
        "https://preview.example.test/\n",
        "https://preview.example.test\\@elsewhere.test/",
    ],
)
def test_unsafe_preview_urls_are_rejected_without_echoing_secrets(url: str) -> None:
    with pytest.raises(ValueError) as error:
        jupyter.preview_url(url)
    assert "private" not in str(error.value)
    assert "name:secret" not in str(error.value)


def test_preview_uses_actual_origin_and_validated_optional_base_path() -> None:
    preview = jupyter.preview_url("https://actual.example.test/observed/proxy/")
    assert preview.hostname == "actual.example.test"
    assert preview.origin == "https://actual.example.test"
    assert preview.base_url == "/observed/proxy/"
    assert preview.url == "https://actual.example.test/observed/proxy/"
    assert jupyter.preview_url(preview.url, "/").base_url == "/"
    with pytest.raises(ValueError):
        jupyter.preview_url(preview.url, "/../")


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"nonce": "wrong", "url": "https://relay.servicebus.windows.net/id/proxy/5000/"},
        {"nonce": "expected", "url": "https://elsewhere.example/id/proxy/5000/"},
        {
            "nonce": "expected",
            "url": "https://relay.servicebus.windows.net/id/proxy/6000/",
        },
        {
            "nonce": "expected",
            "url": "https://relay.servicebus.windows.net/id/proxy/5000/?token=private",
        },
    ],
)
def test_automatic_capture_rejects_wrong_nonce_host_port_and_secrets(payload: object) -> None:
    with pytest.raises(ValueError) as error:
        jupyter.capture_preview(payload, jupyter.PreviewCapture("expected", 5000))
    assert "private" not in str(error.value)


def test_automatic_capture_accepts_the_actual_cloud_shell_preview() -> None:
    captured = jupyter.capture_preview(
        {
            "nonce": "expected",
            "url": (
                "https://relay.servicebus.windows.net/"
                "11111111-1111-4111-8111-111111111111/proxy/5000/"
            ),
        },
        jupyter.PreviewCapture("expected", 5000),
    )
    assert captured.origin == "https://relay.servicebus.windows.net"
    assert captured.base_url.endswith("/proxy/5000/")


def test_one_command_discovery_round_trip_uses_nonce_and_browser_url() -> None:
    port = None
    for candidate in range(5600, 5700):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", candidate))
            except OSError:
                continue
        port = candidate
        break
    if port is None:
        pytest.skip("No test port is available")

    result: dict[str, object] = {}

    def discover() -> None:
        result["preview"] = jupyter.automatic_discover_preview("127.0.0.1", port, timeout=5)

    worker = threading.Thread(target=discover)
    worker.start()
    page = None
    for _ in range(50):
        try:
            page = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1).read()
            break
        except (OSError, urllib.error.URLError):
            time.sleep(0.05)
    assert page is not None
    html = page.decode()
    nonce = re.search(r'<script nonce="([A-Za-z0-9_-]+)">', html)
    assert nonce is not None
    assert "location.origin+location.pathname" in html
    assert "location.reload()" in html
    body = json.dumps(
        {
            "nonce": nonce.group(1),
            "url": (
                "https://relay.servicebus.windows.net/"
                f"11111111-1111-4111-8111-111111111111/proxy/{port}/"
            ),
        }
    ).encode()
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/capture",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    assert json.loads(urllib.request.urlopen(request, timeout=2).read()) == {"ok": True}
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert result["preview"].base_url.endswith(f"/proxy/{port}/")


def test_insecure_environment_is_rejected_before_discovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JUPYTER_TOKEN", "do-not-put-secrets-in-the-environment")
    with pytest.raises(jupyter.EnvironmentError, match="Unset JUPYTER"):
        jupyter.validate_launch_environment()


def test_busy_port_does_not_auto_increment() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        with pytest.raises(jupyter.EnvironmentError, match="never chooses another port"):
            jupyter.ensure_port_available("127.0.0.1", port)


@pytest.mark.skipif(os.name != "posix", reason="Cloud Shell uses POSIX socket reuse semantics")
def test_recently_closed_discovery_connection_does_not_look_like_a_running_server() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port)) as client:
            connection, _ = listener.accept()
            connection.close()
            assert client.recv(1) == b""
    jupyter.ensure_port_available("127.0.0.1", port)


def test_security_arguments_cannot_be_overridden_by_user_config(tmp_path: Path) -> None:
    preview = jupyter.preview_url("https://actual.example.test/observed/")
    args = jupyter.server_arguments(
        tmp_path / "repo", tmp_path / "runtime", preview, "127.0.0.1", 5000
    )
    options = dict(arg.removeprefix("--").split("=", 1) for arg in args)
    assert options["ServerApp.port"] == "5000"
    assert options["ServerApp.port_retries"] == "0"
    assert options["ServerApp.ip"] == "127.0.0.1"
    for name in (
        "allow_remote_access",
        "disable_check_xsrf",
        "trust_xheaders",
        "allow_unauthenticated_access",
        "open_browser",
        "use_redirect_file",
    ):
        assert options[f"ServerApp.{name}"] == "False"
    assert options["ServerApp.allow_origin"] == preview.origin
    assert options["ServerApp.allow_origin_pat"] == ""
    assert ast.literal_eval(options["ServerApp.local_hostnames"]) == ["localhost", preview.hostname]
    assert options["ServerApp.base_url"] == preview.base_url
    assert options["ServerApp.root_dir"] == str(tmp_path / "repo")
    assert options["IdentityProvider.secure_cookie"] == "True"
    assert ast.literal_eval(options["IdentityProvider.cookie_options"]) == {
        "secure": True,
        "httponly": True,
        "samesite": "Lax",
    }
    assert ast.literal_eval(options["ServerApp.tornado_settings"])["xsrf_cookie_kwargs"]["secure"]
    assert not any("token=" in arg or "password=" in arg for arg in args)


def test_runtime_must_be_outside_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(jupyter.EnvironmentError, match="outside"):
        jupyter.private_directory(repo / ".jupyter", repo)
    assert not (repo / ".jupyter").exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX ownership/mode enforcement runs in Linux CI")
def test_runtime_permission_enforcement(tmp_path: Path) -> None:
    tmp_path.chmod(0o700)
    private = jupyter.private_directory(tmp_path / "runtime", tmp_path / "repo")
    assert stat.S_IMODE(private.stat().st_mode) == 0o700
    private.chmod(0o1700)
    assert jupyter.private_directory(private, tmp_path / "repo") == private
    private.chmod(0o755)
    with pytest.raises(jupyter.EnvironmentError, match="0700"):
        jupyter.private_directory(private, tmp_path / "repo")
    assert stat.S_IMODE(private.stat().st_mode) == 0o755


def test_token_generation_never_prints_secret_and_will_not_overwrite(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    token_file = tmp_path / "token"
    token = jupyter.write_token(token_file)
    assert len(token) >= 32
    assert token_file.read_text() == token
    assert capsys.readouterr().out == ""
    with pytest.raises(FileExistsError):
        jupyter.write_token(token_file)


def test_external_token_cannot_be_in_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    token_file = repo / "token"
    token_file.write_text("not-printed")
    with pytest.raises(jupyter.EnvironmentError, match="outside"):
        jupyter.read_token_file(token_file, repo)


@pytest.mark.parametrize(
    ("uid", "mode", "size"),
    [(1, 0o600, 43), (0, 0o644, 43), (0, 0o666, 43), (0, 0o600, 257)],
)
def test_external_token_rejects_insecure_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, uid: int, mode: int, size: int
) -> None:
    token_file = tmp_path / "external-token"
    token_file.write_text("a" * 43)
    original_stat = Path.stat

    def fake_stat(path: Path, *args: object, **kwargs: object) -> object:
        if path == token_file:
            return SimpleNamespace(st_uid=uid, st_mode=stat.S_IFREG | mode, st_size=size)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(jupyter.os, "getuid", lambda: 0, raising=False)
    monkeypatch.setattr(Path, "stat", fake_stat)
    with pytest.raises(jupyter.EnvironmentError, match="0600"):
        jupyter.read_token_file(token_file, tmp_path / "repo")


def test_password_prompt_requires_interactive_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(jupyter.sys.stdin, "isatty", lambda: False)
    with pytest.raises(jupyter.EnvironmentError, match="interactive Cloud Shell"):
        jupyter.password_hash()


def test_real_jupyter_traits_and_masked_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server_module = pytest.importorskip("jupyter_server.serverapp")
    identity_module = pytest.importorskip("jupyter_server.auth.identity")
    token_file = tmp_path / "token"
    token = jupyter.write_token(token_file)
    monkeypatch.delenv("JUPYTER_TOKEN", raising=False)
    monkeypatch.setenv("JUPYTER_TOKEN_FILE", str(token_file))
    repo = tmp_path / "repo"
    repo.mkdir()
    server = server_module.ServerApp()
    preview = jupyter.preview_url("https://preview.example.test/")
    server.parse_command_line(
        jupyter.server_arguments(repo, tmp_path / "runtime", preview, "127.0.0.1", 5000)
    )
    provider = identity_module.PasswordIdentityProvider(parent=server, config=server.config)
    server.identity_provider = provider
    assert provider.token == token
    assert provider.auth_enabled and not provider.token_generated
    assert provider.secure_cookie
    assert server.allow_remote_access is False
    assert server.disable_check_xsrf is False
    assert server.trust_xheaders is False
    assert server.port_retries == 0
    assert token not in server.display_url
    assert "preview.example.test" in server.display_url


def test_launcher_initializes_real_jupyterlab_with_authentication(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    server_module = pytest.importorskip("jupyter_server.serverapp")
    pytest.importorskip("jupyterlab.labapp")
    security = pytest.importorskip("jupyter_server.auth.security")
    repo = tmp_path / "repo"
    repo.mkdir()
    private = tmp_path / "private"
    monkeypatch.setattr(jupyter, "state_directory", lambda path: private)

    def local_private(path: Path, repo: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    monkeypatch.setattr(jupyter, "private_directory", local_private)
    if os.name == "nt":
        monkeypatch.setitem(
            sys.modules,
            "fcntl",
            SimpleNamespace(flock=lambda *args: None, LOCK_EX=1, LOCK_NB=2),
        )
    for name in ("JUPYTER_TOKEN_FILE", "JUPYTER_TOKEN", "JUPYTER_ALLOW_INSECURE_WRITES"):
        monkeypatch.delenv(name, raising=False)
    for name in (
        "JUPYTER_RUNTIME_DIR",
        "JUPYTER_CONFIG_DIR",
        "JUPYTER_CONFIG_PATH",
        "AZURE_TOKEN_CREDENTIALS",
    ):
        monkeypatch.setenv(name, os.environ.get(name, ""))
    chosen_hash = security.passwd("synthetic-workshop-test-password")
    monkeypatch.setattr(jupyter, "password_hash", lambda: chosen_hash)
    tokens: list[str] = []
    servers = []

    def inspect_instead_of_starting(server: object) -> None:
        servers.append(server)
        tokens.append(server.identity_provider.token)
        assert server.identity_provider.hashed_password == chosen_hash
        assert server.identity_provider.auth_enabled
        assert server.root_dir == str(repo)
        assert server.runtime_dir == str(private / "jupyter" / str(port))
        assert server.port_retries == 0
        assert server.allow_remote_access is False
        assert server.disable_check_xsrf is False
        assert server.allow_origin == "https://preview.example.test"
        assert server.web_app.settings["xsrf_cookies"] is True
        assert server.identity_provider.secure_cookie
        assert server.kernel_spec_manager.kernel_dirs == [str(repo / ".venv/share/jupyter/kernels")]

        async def check_http_boundaries() -> None:
            import json
            import uuid
            from datetime import datetime
            from http.cookies import SimpleCookie
            from urllib.parse import urlencode

            from tornado.httpclient import AsyncHTTPClient, HTTPRequest

            client = AsyncHTTPClient(force_instance=True)
            url = f"http://127.0.0.1:{port}"
            valid_host = {"Host": "preview.example.test"}
            authenticated = {
                **valid_host,
                "Authorization": f"token {server.identity_provider.token}",
            }
            try:
                unauthenticated = await client.fetch(
                    HTTPRequest(url + "/api/status", headers=valid_host),
                    raise_error=False,
                )
                assert unauthenticated.code == 403
                accepted = await client.fetch(
                    HTTPRequest(url + "/api/status", headers=authenticated),
                    raise_error=False,
                )
                assert accepted.code == 200
                cookies = accepted.headers.get_list("Set-Cookie")
                login_cookie = next(cookie for cookie in cookies if cookie.startswith("username-"))
                assert "Secure" in login_cookie and "HttpOnly" in login_cookie
                rejected_host = await client.fetch(
                    HTTPRequest(
                        url + "/api/status",
                        headers={**authenticated, "Host": "untrusted.example.test"},
                    ),
                    raise_error=False,
                )
                assert rejected_host.code == 403
                missing_xsrf = await client.fetch(
                    HTTPRequest(
                        url + "/api/kernels",
                        method="POST",
                        body="{}",
                        headers={**valid_host, "Cookie": login_cookie.split(";", 1)[0]},
                    ),
                    raise_error=False,
                )
                assert missing_xsrf.code == 403
                assert server.kernel_manager.list_kernels() == []

                relay_cookie = "auth-token=" + "synthetic-relay-cookie-" * 3
                relay_headers = {**valid_host, "Cookie": relay_cookie}
                unknown_relay = await client.fetch(
                    HTTPRequest(url + "/api/status", headers=relay_headers), raise_error=False
                )
                assert unknown_relay.code == 403
                login = await client.fetch(
                    HTTPRequest(url + "/login", headers=relay_headers), raise_error=False
                )
                assert login.code == 200
                assert b"cloud-shell-xsrf" in login.body
                xsrf = SimpleCookie()
                for cookie in login.headers.get_list("Set-Cookie"):
                    xsrf.load(cookie)
                xsrf_value = xsrf["_xsrf"].value
                form_headers = {
                    **valid_host,
                    "Cookie": relay_cookie + "; _xsrf=" + xsrf_value,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://preview.example.test",
                }
                relay_headers["Cookie"] += "; _xsrf=" + xsrf_value
                wrong_password = await client.fetch(
                    HTTPRequest(
                        url + "/login",
                        method="POST",
                        headers=form_headers,
                        body=urlencode({"_xsrf": xsrf_value, "password": "wrong-password"}),
                    ),
                    raise_error=False,
                )
                assert wrong_password.code == 401
                still_unknown = await client.fetch(
                    HTTPRequest(url + "/api/status", headers=relay_headers), raise_error=False
                )
                assert still_unknown.code == 403
                valid_login = await client.fetch(
                    HTTPRequest(
                        url + "/login",
                        method="POST",
                        headers=form_headers,
                        body=urlencode(
                            {
                                "_xsrf": xsrf_value,
                                "password": "synthetic-workshop-test-password",
                            }
                        ),
                    ),
                    raise_error=False,
                )
                assert valid_login.code == 200
                relay_accepted = await client.fetch(
                    HTTPRequest(url + "/api/status", headers=relay_headers), raise_error=False
                )
                assert relay_accepted.code == 200
                other_relay = await client.fetch(
                    HTTPRequest(
                        url + "/api/status",
                        headers={**valid_host, "Cookie": "auth-token=" + "different-cookie-" * 3},
                    ),
                    raise_error=False,
                )
                assert other_relay.code == 403
                missing_relay_xsrf = await client.fetch(
                    HTTPRequest(
                        url + "/api/kernels",
                        method="POST",
                        headers=relay_headers,
                        body="{}",
                    ),
                    raise_error=False,
                )
                assert missing_relay_xsrf.code == 403
                spec_dir = repo / ".venv/share/jupyter/kernels/foundry-workshop"
                spec_dir.mkdir(parents=True)
                (spec_dir / "kernel.json").write_text(
                    json.dumps(
                        {
                            "argv": [
                                sys.executable,
                                "-m",
                                "ipykernel_launcher",
                                "-f",
                                "{connection_file}",
                            ],
                            "display_name": "Synthetic test kernel",
                            "language": "python",
                        }
                    )
                )
                json_headers = {
                    **relay_headers,
                    "Content-Type": "application/json",
                    "X-XSRFToken": xsrf_value,
                    "Origin": "https://preview.example.test",
                }
                kernel = await client.fetch(
                    HTTPRequest(
                        url + "/api/kernels",
                        method="POST",
                        headers=json_headers,
                        body=json.dumps({"name": "foundry-workshop"}),
                    ),
                    raise_error=False,
                )
                assert kernel.code == 201
                kernel_id = json.loads(kernel.body)["id"]
                channel_id = None
                try:
                    session_id = str(uuid.uuid4())
                    opened = await client.fetch(
                        HTTPRequest(
                            url + "/cloud-shell/channels",
                            method="POST",
                            headers=json_headers,
                            body=json.dumps({"kernel_id": kernel_id, "session_id": session_id}),
                        ),
                        raise_error=False,
                    )
                    assert opened.code == 200, opened.body
                    channel_id = json.loads(opened.body)["id"]
                    message = {
                        "header": {
                            "msg_id": str(uuid.uuid4()),
                            "username": "synthetic",
                            "session": session_id,
                            "msg_type": "execute_request",
                            "version": "5.3",
                            "date": datetime.now(UTC).isoformat(),
                        },
                        "parent_header": {},
                        "metadata": {},
                        "content": {
                            "code": "print('relay-channel-roundtrip')",
                            "silent": False,
                            "store_history": False,
                            "user_expressions": {},
                            "allow_stdin": False,
                            "stop_on_error": True,
                        },
                        "channel": "shell",
                        "buffers": [],
                    }
                    await client.fetch(
                        HTTPRequest(
                            url + "/cloud-shell/channels/" + channel_id,
                            method="POST",
                            headers=json_headers,
                            body=json.dumps({"type": "text", "data": json.dumps(message)}),
                        )
                    )
                    received = ""
                    for _ in range(6):
                        poll = await client.fetch(
                            HTTPRequest(
                                url + "/cloud-shell/channels/" + channel_id,
                                headers=relay_headers,
                                request_timeout=15,
                            )
                        )
                        received += json.dumps(json.loads(poll.body)["messages"])
                        if "relay-channel-roundtrip" in received:
                            break
                    assert "relay-channel-roundtrip" in received
                finally:
                    if channel_id is not None:
                        await client.fetch(
                            HTTPRequest(
                                url + "/cloud-shell/channels/" + channel_id,
                                method="DELETE",
                                headers=json_headers,
                            ),
                            raise_error=False,
                        )
                    await client.fetch(
                        HTTPRequest(
                            url + "/api/kernels/" + kernel_id,
                            method="DELETE",
                            headers=json_headers,
                        ),
                        raise_error=False,
                    )
                await client.fetch(
                    HTTPRequest(url + "/logout", headers=relay_headers), raise_error=False
                )
                logged_out = await client.fetch(
                    HTTPRequest(url + "/api/status", headers=relay_headers), raise_error=False
                )
                assert logged_out.code == 403
                assert server.kernel_manager.list_kernels() == []
            finally:
                client.close()

        server.io_loop.run_sync(check_http_boundaries)

    monkeypatch.setattr(server_module.ServerApp, "start", inspect_instead_of_starting)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server_module.ServerApp.clear_instance()
    try:
        jupyter.launch(repo, jupyter.preview_url("https://preview.example.test"), "127.0.0.1", port)
    finally:
        if not servers and server_module.ServerApp.initialized():
            servers.append(server_module.ServerApp.instance())
        for server in servers:
            if getattr(server, "http_server", None):
                server.http_server.stop()
                server.io_loop.run_sync(server._cleanup)
        server_module.ServerApp.clear_instance()
    output = capsys.readouterr()
    assert len(tokens) == 1
    assert tokens[0] not in output.out + output.err
    assert not list(private.rglob("token-*"))


def test_unknown_arguments_cannot_echo_a_secret(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    monkeypatch.setattr(sys, "argv", ["launcher", "--token", "synthetic-private-value"])
    with pytest.raises(SystemExit) as error:
        jupyter.main()
    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "synthetic-private-value" not in captured.err + captured.out

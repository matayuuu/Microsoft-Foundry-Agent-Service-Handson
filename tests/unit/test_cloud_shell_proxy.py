from __future__ import annotations

import json

import pytest
from tornado import httputil

from scripts.cloud_shell_proxy import PrefixMessageDelegate, redirect_transform, safe_redirect


class RecordingDelegate(httputil.HTTPMessageDelegate):
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.chunks: list[bytes] = []
        self.finished = False
        self.closed = False

    def headers_received(self, start_line, headers) -> None:
        self.paths.append(start_line.path)

    def data_received(self, chunk: bytes) -> None:
        self.chunks.append(chunk)

    def finish(self) -> None:
        self.finished = True

    def on_connection_close(self) -> None:
        self.closed = True


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/", "/session/proxy/5000/"),
        ("/login?next=%2Flab", "/session/proxy/5000/login?next=%2Flab"),
        ("/session/proxy/5000/lab", "/session/proxy/5000/lab"),
        ("/session/proxy/5000", "/session/proxy/5000"),
    ],
)
def test_restore_prefix_without_double_prefixing_or_losing_query(path, expected) -> None:
    recording = RecordingDelegate()
    delegate = PrefixMessageDelegate(recording, "/session/proxy/5000/")
    delegate.headers_received(
        httputil.RequestStartLine("GET", path, "HTTP/1.1"), httputil.HTTPHeaders()
    )
    delegate.data_received(b"streamed body")
    delegate.finish()
    delegate.on_connection_close()
    assert recording.paths == [expected]
    assert recording.chunks == [b"streamed body"]
    assert recording.finished and recording.closed


@pytest.mark.parametrize(
    "location",
    [
        "https://elsewhere.invalid/session/proxy/5000/lab",
        "//elsewhere.invalid/session/proxy/5000/lab",
        "/session/proxy/5000/../outside",
        "/session/proxy/5000/%2e%2e/outside",
        "/outside",
        "javascript:alert(1)",
    ],
)
def test_redirects_cannot_escape_the_preview(location: str) -> None:
    assert not safe_redirect(location, "https://preview.example.test", "/session/proxy/5000/")


def test_relay_navigation_preserves_authentication_cookie_headers() -> None:
    transform = redirect_transform("https://preview.example.test", "/session/proxy/5000/")(
        httputil.HTTPServerRequest(uri="/")
    )
    headers = httputil.HTTPHeaders(
        {
            "Location": "/session/proxy/5000/login?next=%2Flab",
            "Set-Cookie": "test=synthetic; Secure; HttpOnly; Path=/session/proxy/5000/",
        }
    )
    status, result, body = transform.transform_first_chunk(302, headers, b"", True)
    assert status == 200
    assert "Location" not in result
    assert result["Set-Cookie"] == headers["Set-Cookie"]
    assert result["Cache-Control"] == "no-store"
    assert b'http-equiv="refresh"' in body
    assert b"Continue to Jupyter" in body
    assert b"<script" not in body


def test_relay_does_not_turn_authentication_failure_into_success() -> None:
    transform = redirect_transform("https://preview.example.test", "/session/proxy/5000/")(
        httputil.HTTPServerRequest(uri="/")
    )
    headers = httputil.HTTPHeaders()
    assert transform.transform_first_chunk(403, headers, b"Forbidden", True) == (
        403,
        headers,
        b"Forbidden",
    )


def test_cookie_bridge_exposes_only_the_intentionally_readable_xsrf_cookie() -> None:
    transform = redirect_transform("https://preview.example.test", "/session/proxy/5000/")(
        httputil.HTTPServerRequest(uri="/session/proxy/5000/login")
    )
    headers = httputil.HTTPHeaders({"Content-Type": "text/html"})
    headers.add("Set-Cookie", "username=private-authentication-cookie; Secure; HttpOnly")
    headers.add("Set-Cookie", "_xsrf=synthetic-xsrf; Secure; SameSite=Lax")
    status, _, body = transform.transform_first_chunk(
        200, headers, b'<html><input name="_xsrf" value="synthetic-xsrf"></html>', True
    )
    assert status == 200
    assert b"document.cookie=" in body
    assert b"_xsrf=synthetic-xsrf" in body
    assert b"private-authentication-cookie" not in body
    assert b"Path=/session/proxy/5000/" in body


@pytest.mark.parametrize("status", [201, 204, 400, 403, 404, 500])
@pytest.mark.parametrize(
    "route",
    [
        "api",
        "api/sessions",
        "lab/api/settings/@jupyterlab/apputils-extension:themes",
        "lab/api/workspaces/default",
    ],
)
def test_explicit_api_transport_retains_actual_status_and_never_exports_cookies(
    status: int,
    route: str,
) -> None:
    request = httputil.HTTPServerRequest(
        uri="/session/proxy/5000/" + route,
        headers=httputil.HTTPHeaders({"X-Foundry-Cloud-Shell": "1"}),
    )
    transform = redirect_transform("https://preview.example.test", "/session/proxy/5000/")(request)
    headers = httputil.HTTPHeaders(
        {
            "Content-Type": "application/json",
            "Set-Cookie": "username=private-cookie; HttpOnly; Secure",
        }
    )
    response_status, _, body = transform.transform_first_chunk(
        status, headers, b'{"result":"synthetic"}', True
    )
    envelope = json.loads(body)
    assert response_status == 200
    assert envelope["status"] == status
    assert json.loads(envelope["body"]) == {"result": "synthetic"}
    assert "Set-Cookie" not in envelope["headers"]
    assert b"private-cookie" not in body


@pytest.mark.parametrize(
    "route",
    ["lab", "lab/api/settings-other", "lab/api/workspaces-other", "files/example.txt"],
)
def test_api_transport_does_not_capture_other_routes(route: str) -> None:
    request = httputil.HTTPServerRequest(
        uri="/session/proxy/5000/" + route,
        headers=httputil.HTTPHeaders({"X-Foundry-Cloud-Shell": "1"}),
    )
    transform = redirect_transform("https://preview.example.test", "/session/proxy/5000/")(request)
    headers = httputil.HTTPHeaders({"Content-Type": "text/plain"})
    assert transform.transform_first_chunk(404, headers, b"Not found", True) == (
        404,
        headers,
        b"Not found",
    )

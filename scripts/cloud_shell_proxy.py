"""Adapt Cloud Shell's path-stripping relay without weakening Jupyter authentication."""

from __future__ import annotations

import html
import json
import posixpath
from collections.abc import Awaitable
from html.parser import HTMLParser
from http.cookies import SimpleCookie
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlsplit

from tornado import httputil
from tornado.web import OutputTransform

from scripts.cloud_shell_channels import browser_channels_script
from scripts.cloud_shell_environment import EnvironmentError

if TYPE_CHECKING:
    from jupyter_server.serverapp import ServerApp


class PrefixMessageDelegate(httputil.HTTPMessageDelegate):
    def __init__(self, delegate: httputil.HTTPMessageDelegate, prefix: str) -> None:
        self.delegate = delegate
        self.prefix = prefix

    def headers_received(
        self,
        start_line: httputil.RequestStartLine | httputil.ResponseStartLine,
        headers: httputil.HTTPHeaders,
    ) -> Awaitable[None] | None:
        if not isinstance(start_line, httputil.RequestStartLine):
            raise EnvironmentError("The preview adapter requires an HTTP request.")
        path = start_line.path.partition("?")[0]
        if path != self.prefix.rstrip("/") and not path.startswith(self.prefix):
            start_line = start_line._replace(path=self.prefix.rstrip("/") + start_line.path)
        return self.delegate.headers_received(start_line, headers)

    def data_received(self, chunk: bytes) -> Awaitable[None] | None:
        return self.delegate.data_received(chunk)

    def finish(self) -> None:
        self.delegate.finish()

    def on_connection_close(self) -> None:
        self.delegate.on_connection_close()


class PrefixConnectionDelegate(httputil.HTTPServerConnectionDelegate):
    def __init__(self, delegate: httputil.HTTPServerConnectionDelegate, prefix: str) -> None:
        self.delegate = delegate
        self.prefix = prefix

    def start_request(
        self, server_conn: object, request_conn: httputil.HTTPConnection
    ) -> httputil.HTTPMessageDelegate:
        return PrefixMessageDelegate(
            self.delegate.start_request(server_conn, request_conn), self.prefix
        )


def safe_redirect(location: str, origin: str, prefix: str) -> bool:
    parsed = urlsplit(location)
    if (parsed.scheme or parsed.netloc) and f"{parsed.scheme}://{parsed.netloc}" != origin:
        return False
    if not parsed.path.startswith("/") or "\\" in location:
        return False
    path = posixpath.normpath(unquote(parsed.path))
    return path == prefix.rstrip("/") or path.startswith(prefix)


class LoginXsrfParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "input" and attributes.get("name") == "_xsrf":
            self.token = attributes.get("value")


def transport_api_roots(prefix: str) -> tuple[str, ...]:
    return tuple(prefix + route for route in ("api", "lab/api/settings", "lab/api/workspaces"))


def browser_transport_script(prefix: str) -> bytes:
    paths = json.dumps(transport_api_roots(prefix))
    return (
        '<script id="cloud-shell-transport">'
        "(()=>{if(window.__foundryRelayFetch)return;window.__foundryRelayFetch=true;"
        "const original=window.fetch.bind(window);"
        "window.fetch=async(input,options)=>{"
        "const url=new URL(input instanceof Request?input.url:String(input),location.href);"
        f"if(url.origin!==location.origin||!{paths}.some(path=>"
        "url.pathname===path||url.pathname.startsWith(path+'/')))"
        "return original(input,options);"
        "const headers=new Headers(input instanceof Request?input.headers:undefined);"
        "if(options&&options.headers)new Headers(options.headers).forEach((v,k)=>headers.set(k,v));"
        "headers.set('X-Foundry-Cloud-Shell','1');"
        "const response=await original(input,{...options,headers});"
        "const text=await response.clone().text();let envelope;"
        "try{envelope=JSON.parse(text);}catch{return response;}"
        "if(envelope.__foundry_relay!==1||!Number.isInteger(envelope.status)"
        "||typeof envelope.body!=='string')return response;"
        "const body=[204,205,304].includes(envelope.status)?null:envelope.body;"
        "const restored=new Response(body,{status:envelope.status,headers:envelope.headers});"
        "Object.defineProperty(restored,'url',{value:response.url});return restored;"
        "};})();</script>"
    ).encode()


def redirect_transform(origin: str, prefix: str) -> type[OutputTransform]:
    class RelayRedirectTransform(OutputTransform):
        def __init__(self, request: httputil.HTTPServerRequest) -> None:
            self.request = request

        def transform_first_chunk(
            self,
            status_code: int,
            headers: httputil.HTTPHeaders,
            chunk: bytes,
            finishing: bool,
        ) -> tuple[int, httputil.HTTPHeaders, bytes]:
            location = headers.get("Location", "")
            if not finishing or headers.get("Content-Encoding"):
                return status_code, headers, chunk
            if (
                any(
                    self.request.path == path or self.request.path.startswith(path + "/")
                    for path in transport_api_roots(prefix)
                )
                and self.request.headers.get("X-Foundry-Cloud-Shell") == "1"
            ):
                envelope = {
                    "__foundry_relay": 1,
                    "status": status_code,
                    "headers": {
                        key: headers[key] for key in ("Content-Type", "Location") if key in headers
                    },
                    "body": chunk.decode("utf-8"),
                }
                body = json.dumps(envelope).encode()
                headers.pop("Location", None)
                headers["Content-Type"] = "application/json"
                headers["Content-Length"] = str(len(body))
                headers["Cache-Control"] = "no-store"
                return 200, headers, body
            changed = False
            if status_code in {301, 302, 303, 307, 308} and safe_redirect(location, origin, prefix):
                target = html.escape(location, quote=True)
                chunk = (
                    '<!doctype html><html><head><meta charset="utf-8">'
                    f'<meta http-equiv="refresh" content="0;url={target}">'
                    "<title>Continue to Jupyter</title></head><body>"
                    f'<a href="{target}">Continue to Jupyter</a></body></html>'
                ).encode()
                del headers["Location"]
                headers["Content-Type"] = "text/html; charset=utf-8"
                status_code = 200
                changed = True
            if (
                status_code == 200
                and headers.get("Content-Type", "").startswith("text/html")
                and (
                    self.request.path == prefix + "login"
                    or self.request.path == prefix + "lab"
                    or self.request.path.startswith(prefix + "lab/")
                )
                and b"<head>" in chunk
            ):
                scripts = browser_transport_script(prefix) + browser_channels_script(prefix)
                chunk = chunk.replace(b"<head>", b"<head>" + scripts, 1)
                changed = True
            if (
                status_code == 200
                and headers.get("Content-Type", "").startswith("text/html")
                and self.request.path == prefix + "login"
            ):
                parser = LoginXsrfParser()
                parser.feed(chunk.decode("utf-8"))
                if parser.token:
                    # XSRF is intentionally readable by Jupyter's browser code.
                    # Never expose an authentication cookie through this bridge.
                    cookies = SimpleCookie()
                    cookies["_xsrf"] = parser.token
                    xsrf = cookies["_xsrf"]
                    xsrf["path"] = prefix
                    xsrf["secure"] = True
                    xsrf["samesite"] = "Lax"
                    literal = json.dumps(xsrf.OutputString()).replace("<", "\\u003c")
                    script = (
                        f'<script id="cloud-shell-xsrf">document.cookie={literal};</script>'
                    ).encode()
                    chunk += script
                    changed = True
            if changed:
                headers["Content-Length"] = str(len(chunk))
                headers["Cache-Control"] = "no-store"
                headers["X-Content-Type-Options"] = "nosniff"
            return status_code, headers, chunk

    return RelayRedirectTransform


def configure_relay(server: ServerApp, origin: str, prefix: str) -> None:
    callback = server.http_server.request_callback
    if not isinstance(callback, httputil.HTTPServerConnectionDelegate):
        raise EnvironmentError("Unsupported Jupyter HTTP server; the preview adapter was not set.")
    # Restore only the configured prefix, retaining Tornado's streaming/WS delegate.
    server.http_server.request_callback = PrefixConnectionDelegate(callback, prefix)
    # Cloud Shell's relay drops 3xx responses; retain cookies and navigate in HTML.
    server.web_app.add_transform(redirect_transform(origin, prefix))

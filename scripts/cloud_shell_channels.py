"""Authenticated HTTP polling for kernel channels on Cloud Shell's HTTP-only relay."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from jupyter_server.base.handlers import APIHandler
from tornado import web, websocket
from tornado.httpclient import HTTPClientError, HTTPRequest
from tornado.ioloop import PeriodicCallback

if TYPE_CHECKING:
    from jupyter_server.serverapp import ServerApp

LOGGER = logging.getLogger(__name__)


@dataclass
class Channel:
    owner: str
    socket: websocket.WebSocketClientConnection
    messages: asyncio.Queue[dict[str, str]] = field(
        default_factory=lambda: asyncio.Queue(maxsize=128)
    )
    last_used: float = field(default_factory=time.monotonic)
    closed: bool = False
    reader: asyncio.Task[None] | None = None

    async def read(self) -> None:
        try:
            while True:
                message = await self.socket.read_message()
                if message is None:
                    break
                if isinstance(message, bytes):
                    payload = {"type": "binary", "data": base64.b64encode(message).decode()}
                else:
                    payload = {"type": "text", "data": message}
                await self.messages.put(payload)
        finally:
            self.closed = True

    def close(self) -> None:
        self.closed = True
        self.socket.close()
        if self.reader is not None:
            self.reader.cancel()

    def reader_finished(self, reader: asyncio.Task[None]) -> None:
        if not reader.cancelled() and (error := reader.exception()) is not None:
            LOGGER.warning("Kernel channel reader failed (%s).", type(error).__name__)

    def reader_failed(self) -> bool:
        return (
            self.reader is not None
            and self.reader.done()
            and not self.reader.cancelled()
            and self.reader.exception() is not None
        )


class ChannelManager:
    def __init__(self, port: int, origin: str, prefix: str) -> None:
        self.port = port
        self.origin = origin
        self.prefix = prefix
        self.channels: dict[str, Channel] = {}
        self.pending_opens = 0
        self.closed = False
        self.reaper = PeriodicCallback(self.reap, 30000)
        self.reaper.start()

    def reap(self) -> None:
        now = time.monotonic()
        for key, channel in list(self.channels.items()):
            if now - channel.last_used > 90:
                channel.close()
                del self.channels[key]

    def close(self) -> None:
        self.closed = True
        self.reaper.stop()
        for channel in self.channels.values():
            channel.close()
        self.channels.clear()

    @contextmanager
    def reserve_slot(self) -> Iterator[None]:
        if self.closed:
            raise web.HTTPError(503, "Kernel channel server is stopping")
        self.reap()
        if len(self.channels) + self.pending_opens >= 16:
            raise web.HTTPError(429, "Too many active kernel channels")
        self.pending_opens += 1
        try:
            yield
        finally:
            self.pending_opens -= 1

    def owned(self, key: str, owner: str) -> Channel:
        channel = self.channels.get(key)
        if channel is None or channel.owner != owner:
            raise web.HTTPError(404)
        channel.last_used = time.monotonic()
        return channel


class ChannelHandler(APIHandler):
    def initialize(self, manager: ChannelManager) -> None:
        self.manager = manager

    def set_default_headers(self) -> None:
        super().set_default_headers()
        self.set_header("Cache-Control", "no-store")

    @web.authenticated
    async def post(self, channel_id: str = "") -> None:
        body = self.get_json_body()
        if not isinstance(body, dict):
            raise web.HTTPError(400, "Expected a JSON object")
        owner = self.current_user.username
        if channel_id:
            channel = self.manager.owned(channel_id, owner)
            if channel.closed:
                raise web.HTTPError(410, "Kernel channel closed")
            data = body.get("data")
            if not isinstance(data, str) or len(data) > 16 * 1024 * 1024:
                raise web.HTTPError(400, "Invalid channel message")
            kind = body.get("type")
            if kind == "binary":
                try:
                    payload = base64.b64decode(data, validate=True)
                except ValueError as exc:
                    raise web.HTTPError(400, "Invalid binary message") from exc
                await channel.socket.write_message(payload, binary=True)
            elif kind == "text":
                await channel.socket.write_message(data)
            else:
                raise web.HTTPError(400, "Unknown channel message type")
            self.finish({"ok": True})
            return
        if body.get("events") is True:
            path = "api/events/subscribe"
        else:
            try:
                kernel_id = str(uuid.UUID(body["kernel_id"]))
                session_id = str(uuid.UUID(body["session_id"]))
            except (KeyError, TypeError, ValueError, AttributeError) as exc:
                raise web.HTTPError(400, "Invalid kernel/session identifier") from exc
            path = f"api/kernels/{kernel_id}/channels?session_id={session_id}"
        # The destination is fixed loopback, never a client-supplied host or URL.
        request = HTTPRequest(
            f"ws://127.0.0.1:{self.manager.port}{self.manager.prefix}{path}",
            headers={
                "Host": urlsplit(self.manager.origin).netloc,
                "Origin": self.manager.origin,
                "Cookie": self.request.headers.get("Cookie", ""),
                "Authorization": self.request.headers.get("Authorization", ""),
            },
            connect_timeout=15,
        )
        with self.manager.reserve_slot():
            try:
                connection = await websocket.websocket_connect(
                    request, max_message_size=16 * 1024 * 1024
                )
            except (HTTPClientError, OSError) as exc:
                raise web.HTTPError(
                    502, "Could not connect the authenticated kernel channel"
                ) from exc
            if self.manager.closed:
                connection.close()
                raise web.HTTPError(503, "Kernel channel server is stopping")
            key = uuid.uuid4().hex
            channel = Channel(owner, connection)
            self.manager.channels[key] = channel
            channel.reader = asyncio.create_task(channel.read())
            channel.reader.add_done_callback(channel.reader_finished)
            self.finish({"ok": True, "id": key})

    @web.authenticated
    async def get(self, channel_id: str) -> None:
        channel = self.manager.owned(channel_id, self.current_user.username)
        messages = []
        if not channel.closed or not channel.messages.empty():
            with suppress(TimeoutError):
                messages.append(await asyncio.wait_for(channel.messages.get(), timeout=10))
        while not channel.messages.empty() and len(messages) < 64:
            messages.append(channel.messages.get_nowait())
        self.finish(
            {
                "ok": True,
                "messages": messages,
                "closed": channel.closed and channel.messages.empty(),
                "close_code": 1006 if channel.reader_failed() else 1000,
            }
        )

    @web.authenticated
    async def delete(self, channel_id: str) -> None:
        channel = self.manager.owned(channel_id, self.current_user.username)
        channel.close()
        del self.manager.channels[channel_id]
        self.finish({"ok": True})


def install_channels(server: ServerApp, origin: str, prefix: str) -> ChannelManager:
    manager = ChannelManager(server.port, origin, prefix)
    server.web_app.add_handlers(
        ".*",
        [
            (
                prefix + r"cloud-shell/channels(?:/([a-f0-9]{32}))?",
                ChannelHandler,
                {"manager": manager},
            )
        ],
    )
    server.web_app.settings["page_config_hook"] = lambda handler, config: {
        **config,
        "token": "",
    }
    return manager


def browser_channels_script(prefix: str) -> bytes:
    path = json.dumps(prefix)
    return (
        '<script id="cloud-shell-channels">'
        "(()=>{if(window.__foundryRelaySockets)return;window.__foundryRelaySockets=true;"
        f"const base={path};const Native=window.WebSocket;"
        "const request=async(method,path,body)=>{"
        "const match=document.cookie.split(';').map(x=>x.trim()).find(x=>x.startsWith('_xsrf='));"
        "const xsrf=match?decodeURIComponent(match.slice(6)):'';"
        "const r=await fetch(base+'cloud-shell/channels'+path,{method,"
        "credentials:'same-origin',cache:'no-store',"
        "headers:{'Content-Type':'application/json','X-XSRFToken':xsrf},"
        "body:body===undefined?undefined:JSON.stringify(body)});"
        "const data=await r.json();if(data.ok!==true)"
        "throw Error('Authenticated channel request failed');"
        "return data;};"
        "class Relay extends EventTarget{"
        "constructor(url,protocols){super();this.url=String(url);this.readyState=0;"
        "this.protocol='';this.extensions='';this.binaryType='arraybuffer';this.bufferedAmount=0;"
        "this.onopen=this.onmessage=this.onerror=this.onclose=null;"
        "this._sendQueue=Promise.resolve();this._open();}"
        "_emit(type,event){this.dispatchEvent(event);const f=this['on'+type];"
        "if(typeof f==='function')f.call(this,event);}"
        "async _open(){try{const u=new URL(this.url,location.href);"
        "const match=u.pathname.slice(base.length).match(/^api\\/kernels\\/([^/]+)\\/channels$/);"
        "const data=await request('POST','',match?{kernel_id:match[1],"
        "session_id:u.searchParams.get('session_id')||crypto.randomUUID()}:{events:true});"
        "this._id=data.id;if(this.readyState===3){await request('DELETE','/'+this._id);return;}"
        "this.readyState=1;this._emit('open',new Event('open'));this._poll();"
        "}catch{this._emit('error',new Event('error'));this._closed(1006);}}"
        "async _poll(){try{while(this.readyState===1){const data=await request('GET','/'+this._id);"
        "for(const m of data.messages){let value=m.data;"
        "if(m.type==='binary'){const b=Uint8Array.from(atob(value),c=>c.charCodeAt(0));"
        "value=this.binaryType==='blob'?new Blob([b]):b.buffer;}"
        "this._emit('message',new MessageEvent('message',{data:value}));}"
        "if(data.closed){const code=data.close_code===1000?1000:1006;"
        "if(code!==1000)this._emit('error',new Event('error'));this._closed(code);break;}}"
        "}catch{if(this.readyState!==3){this._emit('error',new Event('error'));"
        "this._closed(1006);}}}"
        "send(data){if(this.readyState!==1)"
        "throw new DOMException('Socket not open','InvalidStateError');"
        "this._sendQueue=this._sendQueue.then(async()=>{let payload;"
        "if(typeof data==='string')payload={type:'text',data};else{"
        "const bytes=new Uint8Array(data instanceof Blob?await data.arrayBuffer():"
        "ArrayBuffer.isView(data)?data.buffer.slice(data.byteOffset,data.byteOffset+data.byteLength):data);"
        "let binary='';for(let i=0;i<bytes.length;i+=8192)"
        "binary+=String.fromCharCode(...bytes.subarray(i,i+8192));"
        "payload={type:'binary',data:btoa(binary)};}"
        "await request('POST','/'+this._id,payload);}).catch(()=>{"
        "this._emit('error',new Event('error'));this._closed(1006);});}"
        "close(){if(this.readyState>=2)return;this.readyState=2;"
        "if(!this._id){this._closed(1000);return;}"
        "request('DELETE','/'+this._id).then(()=>this._closed(1000)).catch(()=>{"
        "console.warn('Cloud Shell channel cleanup failed; the server will expire it.');"
        "this._emit('error',new Event('error'));this._closed(1006);});}"
        "_closed(code){if(this.readyState===3)return;this.readyState=3;"
        "this._emit('close',new CloseEvent('close',{code,wasClean:code===1000}));}}"
        "for(const [key,value] of Object.entries({CONNECTING:0,OPEN:1,CLOSING:2,CLOSED:3})){"
        "Relay[key]=value;Relay.prototype[key]=value;}"
        "function Socket(url,protocols){const u=new URL(String(url),location.href);"
        "const local=u.host===location.host&&u.pathname.startsWith(base);"
        "const route=local?u.pathname.slice(base.length):'';"
        "return local&&(/^api\\/kernels\\/[^/]+\\/channels$/.test(route)"
        "||route==='api/events/subscribe')"
        "?new Relay(url,protocols):new Native(url,protocols);}"
        "Object.assign(Socket,{CONNECTING:0,OPEN:1,CLOSING:2,CLOSED:3});"
        "Socket.prototype=Native.prototype;window.WebSocket=Socket;})();</script>"
    ).encode()

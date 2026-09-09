from __future__ import annotations

import asyncio
import base64
import json
import uuid
from contextlib import suppress

import pytest
from jupyter_server.auth import User
from tornado import httputil, web
from tornado.httpclient import HTTPClientError

from scripts import cloud_shell_channels as channels


class FakeSocket:
    def __init__(self) -> None:
        self.incoming: asyncio.Queue[str | bytes | None] = asyncio.Queue()
        self.sent: list[tuple[str | bytes, bool]] = []
        self.closed = False

    async def read_message(self) -> str | bytes | None:
        return await self.incoming.get()

    async def write_message(self, message: str | bytes, binary: bool = False) -> None:
        self.sent.append((message, binary))

    def close(self) -> None:
        self.closed = True


class StubHandler(channels.ChannelHandler):
    """Exercise handler logic; the real-server test covers authentication and XSRF."""

    def __init__(self, manager: channels.ChannelManager, body=None, owner="owner") -> None:
        self.manager = manager
        self.current_user = User(owner)
        self.request = httputil.HTTPServerRequest()
        self.body = body
        self.result = None

    def get_json_body(self):
        return self.body

    def finish(self, chunk=None) -> None:
        self.result = chunk


def kernel_request() -> dict[str, str]:
    return {"kernel_id": str(uuid.uuid4()), "session_id": str(uuid.uuid4())}


def manager() -> channels.ChannelManager:
    return channels.ChannelManager(5000, "https://preview.example.test", "/session/proxy/5000/")


async def close_manager(value: channels.ChannelManager) -> None:
    readers = [
        channel.reader
        for channel in value.channels.values()
        if channel.reader is not None and not channel.reader.done()
    ]
    value.close()
    for reader in readers:
        with suppress(asyncio.CancelledError):
            await reader


def test_concurrent_handshakes_reserve_the_channel_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        value = manager()
        gate = asyncio.Event()
        started = []

        async def connect(request, **kwargs):
            started.append(request.url)
            await gate.wait()
            return FakeSocket()

        monkeypatch.setattr(channels.websocket, "websocket_connect", connect)
        handlers = [StubHandler(value, kernel_request()) for _ in range(24)]
        tasks = [asyncio.create_task(handler.post()) for handler in handlers]
        try:
            await asyncio.sleep(0)
            assert len(started) == 16
            assert value.pending_opens == 16
            assert not value.channels
            gate.set()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            assert sum(result is None for result in results) == 16
            errors = [result for result in results if result is not None]
            assert len(errors) == 8
            assert all(
                isinstance(error, web.HTTPError) and error.status_code == 429 for error in errors
            )
            assert value.pending_opens == 0
            assert len(value.channels) == 16
            assert all(
                url.startswith("ws://127.0.0.1:5000/session/proxy/5000/api/kernels/")
                for url in started
            )
        finally:
            gate.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            await close_manager(value)

    asyncio.run(run())


def test_failed_handshake_releases_capacity(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        value = manager()

        async def rejected(request, **kwargs):
            raise HTTPClientError(403, "Synthetic rejection")

        monkeypatch.setattr(channels.websocket, "websocket_connect", rejected)
        try:
            with pytest.raises(web.HTTPError) as failure:
                await StubHandler(value, kernel_request()).post()
            assert failure.value.status_code == 502
            assert value.pending_opens == 0
            assert not value.channels

            async def accepted(request, **kwargs):
                return FakeSocket()

            monkeypatch.setattr(channels.websocket, "websocket_connect", accepted)
            await StubHandler(value, kernel_request()).post()
            assert value.pending_opens == 0
            assert len(value.channels) == 1
        finally:
            await close_manager(value)

    asyncio.run(run())


@pytest.mark.parametrize("shutdown", [False, True])
def test_cancel_or_shutdown_during_handshake_releases_capacity(
    monkeypatch: pytest.MonkeyPatch, shutdown: bool
) -> None:
    async def run() -> None:
        value = manager()
        gate = asyncio.Event()
        socket = FakeSocket()

        async def connect(request, **kwargs):
            await gate.wait()
            return socket

        monkeypatch.setattr(channels.websocket, "websocket_connect", connect)
        task = asyncio.create_task(StubHandler(value, kernel_request()).post())
        await asyncio.sleep(0)
        assert value.pending_opens == 1
        try:
            if shutdown:
                value.close()
                gate.set()
                with pytest.raises(web.HTTPError) as failure:
                    await task
                assert failure.value.status_code == 503
                assert socket.closed
            else:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            assert value.pending_opens == 0
            assert not value.channels
        finally:
            await close_manager(value)

    asyncio.run(run())


@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_wrong_owner_cannot_read_write_or_delete(method: str) -> None:
    async def run() -> None:
        value = manager()
        socket = FakeSocket()
        key = uuid.uuid4().hex
        channel = channels.Channel("owner", socket)
        value.channels[key] = channel
        handler = StubHandler(value, {"type": "text", "data": "not authorized"}, owner="other")
        try:
            with pytest.raises(web.HTTPError) as failure:
                await getattr(handler, method)(key)
            assert failure.value.status_code == 404
            assert value.channels[key] is channel
            assert not socket.sent and not socket.closed
            assert handler.result is None
        finally:
            await close_manager(value)

    asyncio.run(run())


def test_closed_channel_drains_all_final_frames(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        value = manager()
        socket = FakeSocket()
        binary = b"\x00\xff\x04"
        reply = json.dumps({"header": {"msg_type": "execute_reply"}, "content": {"status": "ok"}})
        for message in [*(str(index) for index in range(65)), binary, reply, None]:
            socket.incoming.put_nowait(message)

        async def connect(request, **kwargs):
            return socket

        monkeypatch.setattr(channels.websocket, "websocket_connect", connect)
        opened = StubHandler(value, kernel_request())
        try:
            await opened.post()
            key = opened.result["id"]
            channel = value.channels[key]
            await channel.reader
            first = StubHandler(value)
            await first.get(key)
            assert len(first.result["messages"]) == 64
            assert first.result["closed"] is False
            last = StubHandler(value)
            await last.get(key)
            assert last.result["closed"] is True
            assert last.result["close_code"] == 1000
            messages = first.result["messages"] + last.result["messages"]
            assert len(messages) == 67
            assert messages[-2]["type"] == "binary"
            assert base64.b64decode(messages[-2]["data"]) == binary
            assert messages[-1] == {"type": "text", "data": reply}
        finally:
            await close_manager(value)

    asyncio.run(run())


def test_binary_message_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        value = manager()
        socket = FakeSocket()

        async def connect(request, **kwargs):
            return socket

        monkeypatch.setattr(channels.websocket, "websocket_connect", connect)
        opened = StubHandler(value, kernel_request())
        try:
            await opened.post()
            key = opened.result["id"]
            binary = b"\x00\xff\x04"
            await StubHandler(
                value, {"type": "binary", "data": base64.b64encode(binary).decode()}
            ).post(key)
            assert socket.sent == [(binary, True)]
            socket.incoming.put_nowait(binary)
            poll = StubHandler(value)
            await poll.get(key)
            assert poll.result["messages"] == [
                {"type": "binary", "data": base64.b64encode(binary).decode()}
            ]
            assert poll.result["closed"] is False
            with pytest.raises(web.HTTPError) as failure:
                await StubHandler(value, {"type": "binary", "data": "not base64!"}).post(key)
            assert failure.value.status_code == 400
        finally:
            await close_manager(value)

    asyncio.run(run())


def test_idle_reaper_closes_only_expired_channels(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        value = manager()
        expired = channels.Channel("owner", FakeSocket(), last_used=1)
        active = channels.Channel("owner", FakeSocket(), last_used=95)
        expired.reader = asyncio.create_task(expired.read())
        value.channels.update(expired=expired, active=active)
        monkeypatch.setattr(channels.time, "monotonic", lambda: 100)
        try:
            value.reap()
            assert "expired" not in value.channels
            assert expired.closed and expired.socket.closed
            with suppress(asyncio.CancelledError):
                await expired.reader
            assert value.owned("active", "owner") is active
            assert active.last_used == 100
            assert not active.closed
        finally:
            await close_manager(value)

    asyncio.run(run())


@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        {},
        {"kernel_id": "https://other.invalid", "session_id": str(uuid.uuid4())},
        {"kernel_id": str(uuid.uuid4()), "session_id": "../outside"},
    ],
)
def test_invalid_destination_never_opens_a_socket(monkeypatch: pytest.MonkeyPatch, body) -> None:
    async def run() -> None:
        value = manager()

        async def forbidden(*args, **kwargs):
            pytest.fail("Invalid identifiers must not reach the WebSocket client")

        monkeypatch.setattr(channels.websocket, "websocket_connect", forbidden)
        try:
            with pytest.raises(web.HTTPError) as failure:
                await StubHandler(value, body).post()
            assert failure.value.status_code == 400
            assert value.pending_opens == 0
        finally:
            await close_manager(value)

    asyncio.run(run())


def test_reader_failure_is_reported_after_buffered_output(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    class BrokenSocket(FakeSocket):
        async def read_message(self):
            if not self.incoming.empty():
                return self.incoming.get_nowait()
            raise OSError("synthetic-private-error-detail")

    async def run() -> None:
        value = manager()
        socket = BrokenSocket()
        socket.incoming.put_nowait("before failure")

        async def connect(request, **kwargs):
            return socket

        monkeypatch.setattr(channels.websocket, "websocket_connect", connect)
        opened = StubHandler(value, kernel_request())
        try:
            await opened.post()
            key = opened.result["id"]
            with pytest.raises(OSError):
                await value.channels[key].reader
            poll = StubHandler(value)
            await poll.get(key)
            assert poll.result["messages"] == [{"type": "text", "data": "before failure"}]
            assert poll.result["closed"] is True
            assert poll.result["close_code"] == 1006
            assert "Kernel channel reader failed (OSError)" in caplog.text
            assert "synthetic-private-error-detail" not in caplog.text
        finally:
            await close_manager(value)

    asyncio.run(run())

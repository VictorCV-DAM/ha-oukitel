"""Async TCP session with a station on the local network.

Connects to TCP port 6607, completes the AES handshake, subscribes to
high-frequency telemetry and keeps the stream alive with periodic keepalives.
Decoded telemetry is delivered via a callback as {tag_id: value}.
"""

from __future__ import annotations

import asyncio
import logging
import struct
from collections.abc import Callable
from typing import Any

from .local_frame import (
    FrameAssembler,
    auth_key_bytes,
    build_encrypted_frame,
    build_frame,
    decrypt_payload,
    fresh_iv,
    session_token,
    ttlv_decode,
    ttlv_encode,
)
from .local_scan import (
    _CMD_HELLO,
    _CMD_KEEPALIVE,
    _CMD_LOGIN,
    _CMD_LOGIN_OK,
    _CMD_NONCE,
    _CMD_PING,
    _CMD_PONG,
    _CMD_READ,
    _CMD_TELEMETRY,
    _CMD_WRITE,
    _DEFAULT_READ_TAGS,
    _REPORT_MODE_LAN,
    _TAG_REPORT_MODE,
    _TCP_PORT,
)

_LOGGER = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 15.0
_READ_TIMEOUT = 90.0
_KEEPALIVE_INTERVAL = 12.0
_CLOSE_TIMEOUT = 5.0


class LocalSessionError(Exception):
    pass


class LocalAuthError(LocalSessionError):
    pass


class LocalSession:
    """Manages one TCP session with a station: handshake → stream → keepalive loop."""

    def __init__(
        self,
        host: str,
        auth_key_b64: str,
        on_telemetry: Callable[[dict[int, Any]], None],
        read_tags: tuple[int, ...] = _DEFAULT_READ_TAGS,
    ) -> None:
        self._host = host
        self._key = auth_key_bytes(auth_key_b64)
        self._on_telemetry = on_telemetry
        self._read_tags = read_tags
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._assembler = FrameAssembler()
        self._keepalive_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, _TCP_PORT),
                timeout=_CONNECT_TIMEOUT,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            raise LocalSessionError(f"Cannot reach {self._host}:{_TCP_PORT}") from exc

        await self._handshake()
        await self._subscribe()
        self._keepalive_task = asyncio.ensure_future(self._keepalive_loop())

    async def close(self) -> None:
        if self._keepalive_task and not self._keepalive_task.done():
            self._keepalive_task.cancel()
            try:
                await asyncio.wait_for(self._keepalive_task, timeout=_CLOSE_TIMEOUT)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
        if self._writer:
            try:
                self._writer.close()
                await asyncio.wait_for(self._writer.wait_closed(), timeout=_CLOSE_TIMEOUT)
            except Exception:
                pass

    async def read_loop(self) -> None:
        """Drive the receive loop; exits when the connection drops or times out."""
        while True:
            try:
                chunk = await asyncio.wait_for(
                    self._reader.read(4096), timeout=_READ_TIMEOUT
                )
            except asyncio.TimeoutError:
                _LOGGER.debug("LAN read timeout for %s", self._host)
                return
            if not chunk:
                return
            for _pid, cmd, payload in self._assembler.feed(chunk):
                await self._handle(cmd, payload)

    async def send_write(self, tag: int, kind: str, value: Any) -> None:
        body = ttlv_encode([(tag, kind, value)])
        iv = fresh_iv()
        frame = build_encrypted_frame(_CMD_WRITE, body, self._key, iv)
        self._writer.write(frame)
        await self._writer.drain()

    async def request_read(self) -> None:
        body = b"".join(struct.pack(">H", t) for t in self._read_tags)
        iv = fresh_iv()
        frame = build_encrypted_frame(_CMD_READ, body, self._key, iv)
        self._writer.write(frame)
        await self._writer.drain()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _send_raw(self, cmd: int, payload: bytes = b"") -> None:
        self._writer.write(build_frame(cmd, payload))
        await self._writer.drain()

    async def _recv_cmd(self, expected_cmd: int, timeout: float = 10.0) -> bytes:
        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise LocalSessionError(f"Timeout waiting for cmd {expected_cmd:#06x}")
            try:
                chunk = await asyncio.wait_for(self._reader.read(4096), timeout=remaining)
            except asyncio.TimeoutError:
                raise LocalSessionError(f"Timeout waiting for cmd {expected_cmd:#06x}")
            if not chunk:
                raise LocalSessionError("Connection closed during handshake")
            for _pid, cmd, payload in self._assembler.feed(chunk):
                if cmd == expected_cmd:
                    return payload

    async def _handshake(self) -> None:
        await self._send_raw(_CMD_HELLO)

        nonce_payload = await self._recv_cmd(_CMD_NONCE)
        nonce_fields = ttlv_decode(nonce_payload)
        nonce_str = next(
            (v for v in nonce_fields.values() if isinstance(v, str)), None
        )
        if not nonce_str:
            raise LocalAuthError("Device did not send a nonce")

        token = session_token(self._key, nonce_str)
        login_body = ttlv_encode([(1, "num", len(token))])
        login_body += token.encode()
        await self._send_raw(_CMD_LOGIN, login_body)

        result_payload = await self._recv_cmd(_CMD_LOGIN_OK)
        result_fields = ttlv_decode(result_payload)
        status = result_fields.get(1, -1)
        if status != 0:
            raise LocalAuthError(f"Station rejected login (status={status})")

        _LOGGER.debug("LAN handshake succeeded with %s", self._host)

    async def _subscribe(self) -> None:
        body = ttlv_encode([(_TAG_REPORT_MODE, "num", _REPORT_MODE_LAN)])
        iv = fresh_iv()
        frame = build_encrypted_frame(_CMD_WRITE, body, self._key, iv)
        self._writer.write(frame)
        await self._writer.drain()
        await self.request_read()

    async def _keepalive_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(_KEEPALIVE_INTERVAL)
                body = ttlv_encode([(_TAG_REPORT_MODE, "num", _REPORT_MODE_LAN)])
                iv = fresh_iv()
                frame = build_encrypted_frame(_CMD_WRITE, body, self._key, iv)
                self._writer.write(frame)
                await self._writer.drain()
                await self.request_read()
        except (asyncio.CancelledError, Exception):
            pass

    async def _handle(self, cmd: int, payload: bytes) -> None:
        if cmd == _CMD_PING:
            await self._send_raw(_CMD_PONG)
            return
        if cmd == _CMD_KEEPALIVE:
            await self._send_raw(_CMD_KEEPALIVE)
            return
        if cmd == _CMD_TELEMETRY:
            try:
                if len(payload) > 16:
                    iv = payload[:16]
                    data = decrypt_payload(self._key, iv, payload[16:])
                else:
                    data = payload
                fields = ttlv_decode(data)
                if fields:
                    self._on_telemetry(fields)
            except Exception as exc:
                _LOGGER.debug("Could not decode telemetry frame: %s", exc)

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
    aes_encrypt,
    aes_decrypt,
    build_frame,
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
        self._iv: bytes | None = None
        self._packet_id = 1000

    def _next_pid(self) -> int:
        self._packet_id += 1
        if self._packet_id >= 0xFFFF:
            self._packet_id = 1000
        return self._packet_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        _LOGGER.debug("oukitel: LAN connecting to %s:%s", self._host, _TCP_PORT)
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, _TCP_PORT),
                timeout=_CONNECT_TIMEOUT,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            raise LocalSessionError(f"Cannot reach {self._host}:{_TCP_PORT}") from exc

        _LOGGER.debug("oukitel: LAN TCP socket open, starting handshake")
        await self._handshake()
        _LOGGER.debug("oukitel: LAN subscribing to telemetry")
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
                _LOGGER.debug("oukitel: LAN read timeout for %s", self._host)
                return
            if not chunk:
                _LOGGER.debug("oukitel: LAN socket closed by peer")
                return
            for _pid, cmd, payload in self._assembler.feed(chunk):
                await self._handle(cmd, payload)

    async def send_write(self, tag: int, kind: str, value: Any) -> None:
        body = ttlv_encode([(tag, kind, value)])
        ciphertext = aes_encrypt(self._key, self._iv, body)
        frame = build_frame(self._next_pid(), _CMD_WRITE, ciphertext)
        self._writer.write(frame)
        await self._writer.drain()

    async def request_read(self) -> None:
        if not self._writer or self._writer.is_closing():
            return
        # CMD 35: Real Quectel telemetry query command
        cipher_empty = aes_encrypt(self._key, self._iv, b"")
        self._writer.write(build_frame(self._next_pid(), 35, cipher_empty))

        body_tags = b"".join(struct.pack(">H", t) for t in self._read_tags)
        cipher_tags = aes_encrypt(self._key, self._iv, body_tags)
        self._writer.write(build_frame(self._next_pid(), 35, cipher_tags))
        await self._writer.drain()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _send_raw(self, cmd: int, payload: bytes = b"") -> None:
        pid = self._next_pid()
        self._writer.write(build_frame(pid, cmd, payload))
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
        _LOGGER.debug("oukitel: LAN sending CMD_HELLO (%s)", _CMD_HELLO)
        await self._send_raw(_CMD_HELLO)

        nonce_payload = await self._recv_cmd(_CMD_NONCE)
        _LOGGER.debug("oukitel: LAN received CMD_NONCE (%s bytes)", len(nonce_payload))
        nonce_fields = ttlv_decode(nonce_payload)
        nonce_str = next(
            (v for v in nonce_fields.values() if isinstance(v, str)), None
        )
        if not nonce_str:
            raise LocalAuthError("Device did not send a nonce")

        self._iv = nonce_str.encode()
        _LOGGER.debug("oukitel: LAN extracted nonce and set session IV")

        token = session_token(self._key, nonce_str)
        token_bytes = token.encode()
        login_body = struct.pack(">H", (2 << 3) | 3) + struct.pack(">H", len(token_bytes)) + token_bytes
        _LOGGER.debug("oukitel: LAN sending CMD_LOGIN token")
        await self._send_raw(_CMD_LOGIN, login_body)

        result_payload = await self._recv_cmd(_CMD_LOGIN_OK)
        result_fields = ttlv_decode(result_payload)
        _LOGGER.debug("oukitel: LAN CMD_LOGIN_OK raw hex: %s, parsed fields: %s", result_payload.hex(), result_fields)
        
        result = next(
            (v for v in result_fields.values() if isinstance(v, (int, float))),
            None,
        )
        if result == 0:
            _LOGGER.info("oukitel: LAN login OK! Handshake succeeded with %s", self._host)
            return

        raise LocalAuthError(f"Station rejected login (result={result}, fields={result_fields})")

    async def _subscribe(self) -> None:
        # 1. Mode high-frequency LAN (cmd 19): tag 100 = 1 (局域网高频上报 - LAN high frequency report)
        body = ttlv_encode([(_TAG_REPORT_MODE, "num", 1)])
        ciphertext = aes_encrypt(self._key, self._iv, body)
        self._writer.write(build_frame(self._next_pid(), _CMD_WRITE, ciphertext))
        await self._writer.drain()

        # 2. Snapshot read all tags
        await self.request_read()

        # 3. Real Heartbeat (cmd 28727 / _CMD_PING)
        hb_cipher = aes_encrypt(self._key, self._iv, b"")
        self._writer.write(build_frame(self._next_pid(), _CMD_PING, hb_cipher))
        await self._writer.drain()
        _LOGGER.debug("oukitel: LAN subscription (mode 1) and heartbeat (cmd 28727) armed")

    async def resubscribe(self) -> None:
        """Re-arm high-frequency reporting on an existing socket."""
        await self._subscribe()

    async def _keepalive_loop(self) -> None:
        failures = 0
        while True:
            try:
                await asyncio.sleep(_KEEPALIVE_INTERVAL)
                await self._subscribe()
                failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                failures += 1
                _LOGGER.debug("oukitel: LAN keepalive tick failed (%s/3): %s", failures, exc)
                if failures >= 3:
                    _LOGGER.debug("oukitel: LAN keepalive failed 3 consecutive times, aborting keepalive loop")
                    break

    async def _handle(self, cmd: int, payload: bytes) -> None:
        if cmd in (_CMD_PING, _CMD_PONG, _CMD_KEEPALIVE):
            if cmd == _CMD_PING:
                await self._send_raw(_CMD_PONG)
            _LOGGER.debug("oukitel: LAN heartbeat frame received: cmd=%s (%#06x)", cmd, cmd)
            return
        if cmd == 28726: # WRITE_ACK
            try:
                data = aes_decrypt(self._key, self._iv, payload)
                _LOGGER.debug("oukitel: LAN WRITE_ACK: %s", ttlv_decode(data))
            except Exception as exc:
                _LOGGER.debug("oukitel: ACK decrypt error: %s", exc)
            return
        if cmd in (_CMD_TELEMETRY, _CMD_READ, _CMD_WRITE, 18, 20, 21, 36, 38):
            try:
                data = aes_decrypt(self._key, self._iv, payload)
                fields = ttlv_decode(data)
                if fields:
                    self._on_telemetry(fields)
                if cmd == _CMD_WRITE:
                    ack_body = ttlv_encode([(1, "num", 0)])
                    ack_cipher = aes_encrypt(self._key, self._iv, ack_body)
                    await self._send_raw(28726, ack_cipher)
            except Exception as exc:
                _LOGGER.debug("oukitel: Could not decode frame cmd=%s: %s", cmd, exc)
        else:
            _LOGGER.debug("oukitel: Unknown LAN frame received: cmd=%s (%#06x), len=%s", cmd, cmd, len(payload))

"""Async TCP session with a station on the local network.

Connects to TCP port 6607, completes the AES handshake, subscribes to
high-frequency telemetry and keeps the stream alive with periodic keepalives.
Decoded telemetry is delivered via a callback as {tag_id: value}.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import struct
import time
from collections.abc import Callable
from typing import Any

from .diag_logger import diag_log
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
    _CMD_WRITE_ACK,
    _DEFAULT_READ_TAGS,
    _REPORT_MODE_LAN,
    _TAG_REPORT_MODE,
    _TCP_PORT,
)

_LOGGER = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 15.0
_READ_TIMEOUT = 90.0
_KEEPALIVE_INTERVAL = 15.0
_MIN_READ_INTERVAL = 8.0
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
        self._write_lock = asyncio.Lock()
        self._last_read_sent: float = 0.0

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
        diag_log("LAN_CONNECT_START", host=self._host, port=_TCP_PORT)
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, _TCP_PORT),
                timeout=_CONNECT_TIMEOUT,
            )
        except (OSError, asyncio.TimeoutError) as exc:
            diag_log("LAN_CONNECT_FAIL", host=self._host, port=_TCP_PORT, error=str(exc))
            raise LocalSessionError(f"Cannot reach {self._host}:{_TCP_PORT}") from exc

        if self._writer is not None:
            sock = self._writer.get_extra_info("socket")
            if sock is not None:
                try:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except Exception:
                    pass

        _LOGGER.debug("oukitel: LAN TCP socket open, starting handshake")
        await self._handshake()
        _LOGGER.debug("oukitel: LAN subscribing to telemetry")
        await self._subscribe(force_read=True)
        self._keepalive_task = asyncio.ensure_future(self._keepalive_loop())

    async def close(self) -> None:
        diag_log("LAN_CLOSE", host=self._host)
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
                _LOGGER.info("oukitel: LAN read timeout for %s", self._host)
                diag_log("LAN_READ_TIMEOUT", host=self._host)
                return
            if not chunk:
                _LOGGER.info("oukitel: LAN socket closed by peer")
                diag_log("LAN_PEER_CLOSED", host=self._host)
                return
            for pid, cmd, payload in self._assembler.feed(chunk):
                await self._handle(cmd, payload, pid=pid)

    async def send_write(self, tag: int, kind: str, value: Any) -> None:
        body = ttlv_encode([(tag, kind, value)])
        ciphertext = aes_encrypt(self._key, self._iv, body)
        pid = self._next_pid()
        frame = build_frame(pid, _CMD_WRITE, ciphertext)
        diag_log("LAN_TX_WRITE", pid=pid, tag=tag, kind=kind, value=value)
        async with self._write_lock:
            if self._writer:
                self._writer.write(frame)
                await self._writer.drain()

    async def _send_read_tags(self, tags: tuple[int, ...]) -> None:
        body = b"".join(struct.pack(">H", t) for t in tags)
        ciphertext = aes_encrypt(self._key, self._iv, body)
        pid = self._next_pid()
        frame = build_frame(pid, _CMD_READ, ciphertext)
        self._last_read_sent = time.monotonic()
        diag_log("LAN_TX_READ", pid=pid, tags=list(tags))
        async with self._write_lock:
            if self._writer:
                self._writer.write(frame)
                await self._writer.drain()

    async def request_read(
        self,
        tags: tuple[int, ...] | None = None,
        force: bool = False,
    ) -> None:
        now = time.monotonic()
        if not force and self._last_read_sent > 0 and (now - self._last_read_sent) < _MIN_READ_INTERVAL:
            return
        target_tags = tags if tags is not None else self._read_tags
        await self._send_read_tags(target_tags)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _send_raw(self, cmd: int, payload: bytes = b"") -> None:
        pid = self._next_pid()
        frame = build_frame(pid, cmd, payload)
        async with self._write_lock:
            if self._writer:
                self._writer.write(frame)
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
            diag_log("LAN_HANDSHAKE_ERR", reason="no_nonce", fields=nonce_fields)
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
            diag_log("LAN_HANDSHAKE_OK", host=self._host, nonce=nonce_str)
            return

        diag_log("LAN_HANDSHAKE_REJECTED", host=self._host, result=result, fields=result_fields)
        raise LocalAuthError(f"Station rejected login (result={result}, fields={result_fields})")

    async def _send_heartbeat(self) -> None:
        hb_body = ttlv_encode([(1, "num", 30), (2, "num", 1)])
        hb_cipher = aes_encrypt(self._key, self._iv, hb_body)
        pid_hb = self._next_pid()
        async with self._write_lock:
            if self._writer:
                self._writer.write(build_frame(pid_hb, _CMD_KEEPALIVE, hb_cipher))
                await self._writer.drain()

    async def _subscribe(self, force_read: bool = False) -> None:
        # 1. Mode high-frequency LAN (cmd 19, tag 100 = 3)
        body = ttlv_encode([(_TAG_REPORT_MODE, "num", _REPORT_MODE_LAN)])
        ciphertext = aes_encrypt(self._key, self._iv, body)
        pid_mode = self._next_pid()
        diag_log("LAN_TX_REPORT_MODE", pid=pid_mode, tag=_TAG_REPORT_MODE, mode=_REPORT_MODE_LAN)
        async with self._write_lock:
            if self._writer:
                self._writer.write(build_frame(pid_mode, _CMD_WRITE, ciphertext))
                await self._writer.drain()

        await asyncio.sleep(0.15)

        # 2. Heartbeat (cmd 28729)
        await self._send_heartbeat()

        await asyncio.sleep(0.15)

        # 3. Single snapshot read of all tags (cmd 17) — rate-limited so we never interrupt an active 18-tag readout
        await self.request_read(force=force_read)
        _LOGGER.debug("oukitel: LAN subscription, heartbeat, and read armed")

    async def resubscribe(self) -> None:
        """Re-arm high-frequency reporting on an existing socket."""
        await self._subscribe(force_read=False)

    async def _keepalive_loop(self) -> None:
        tick = 0
        while True:
            try:
                await asyncio.sleep(_KEEPALIVE_INTERVAL)
                if not self._writer or self._writer.is_closing():
                    break
                tick += 1
                if tick % 2 == 0:
                    await self._subscribe(force_read=False)
                else:
                    await self._send_heartbeat()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _LOGGER.debug("oukitel: LAN keepalive tick notice: %s", exc)

    async def _handle(self, cmd: int, payload: bytes, pid: int = 0) -> None:
        if cmd == _CMD_PING:
            await self._send_raw(_CMD_PONG)
            return
        if cmd in (_CMD_TELEMETRY, _CMD_READ, _CMD_WRITE):
            try:
                data = aes_decrypt(self._key, self._iv, payload)
                fields = ttlv_decode(data)
                diag_log(
                    "LAN_RX_DATA",
                    pid=pid,
                    cmd=cmd,
                    tags_received=list(fields.keys()),
                    fields=fields,
                )
                if fields:
                    self._on_telemetry(fields)
                if cmd == _CMD_WRITE:
                    ack_body = ttlv_encode([(1, "num", 0)])
                    ack_cipher = aes_encrypt(self._key, self._iv, ack_body)
                    await self._send_raw(_CMD_WRITE_ACK, ack_cipher)
            except Exception as exc:
                diag_log("LAN_RX_DECODE_ERR", pid=pid, cmd=cmd, raw_len=len(payload), error=str(exc))
                _LOGGER.debug("oukitel: Could not decode frame cmd=%s: %s", cmd, exc)
        else:
            diag_log("LAN_RX_ACK_OR_CTRL", pid=pid, cmd=cmd, raw_len=len(payload))

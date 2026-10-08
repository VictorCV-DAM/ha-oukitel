"""UDP broadcast scan to find a station's current LAN IP from its device key."""

from __future__ import annotations

import asyncio
import logging
import socket

from .local_frame import FrameAssembler, build_frame, ttlv_decode

_LOGGER = logging.getLogger(__name__)

_UDP_PORT = 6606
_TCP_PORT = 6607

_CMD_SCAN_REQUEST = 28720
_CMD_SCAN_REPLY = 28721
_CMD_HELLO = 28722
_CMD_NONCE = 28723
_CMD_LOGIN = 28724
_CMD_LOGIN_OK = 28725
_CMD_WRITE_ACK = 28726
_CMD_PING = 28727
_CMD_PONG = 28728
_CMD_KEEPALIVE = 28729
_CMD_READ = 17
_CMD_WRITE = 19
_CMD_TELEMETRY = 20

_TAG_REPORT_MODE = 100
_REPORT_MODE_LAN = 3

_DEFAULT_READ_TAGS = (2, 8, 9, 6, 31, 7, 28, 27, 14, 12, 11, 5, 4, 3, 1, 34, 20, 100, 43, 44, 46, 33)

_SCAN_TIMEOUT = 6.0


def _parse_scan_reply(payload: bytes) -> tuple[str | None, str | None]:
    ip = mac = None
    for value in ttlv_decode(payload).values():
        if not isinstance(value, str):
            continue
        if value.count(".") == 3 and all(p.isdigit() for p in value.split(".")):
            ip = value
        elif len(value) == 12 and all(c in "0123456789abcdefABCDEF" for c in value):
            mac = value.lower()
    return ip, mac


class _ScanProtocol(asyncio.DatagramProtocol):
    def __init__(self, device_key: str, result: asyncio.Future[str]) -> None:
        self._dk = device_key.lower()
        self._result = result
        self._assembler = FrameAssembler()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        for _pid, cmd, payload in self._assembler.feed(data):
            if cmd != _CMD_SCAN_REPLY:
                continue
            ip, mac = _parse_scan_reply(payload)
            if mac and mac == self._dk and not self._result.done():
                resolved_ip = ip or addr[0]
                _LOGGER.info("oukitel: Device found on LAN! IP=%s (MAC=%s)", resolved_ip, mac)
                self._result.set_result(resolved_ip)

    def error_received(self, exc: Exception) -> None:
        _LOGGER.debug("oukitel: Scan socket error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        pass


def _broadcast_targets() -> list[str]:
    """Return both global and subnet-directed broadcast addresses."""
    targets = ["255.255.255.255"]
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 53))
        local_ip = s.getsockname()[0]
        s.close()
        directed = local_ip.rsplit(".", 1)[0] + ".255"
        if directed not in targets:
            targets.append(directed)
    except OSError:
        pass
    return targets


async def find_device_on_lan(device_key: str, timeout: float = _SCAN_TIMEOUT) -> str | None:
    loop = asyncio.get_running_loop()
    result: asyncio.Future[str] = loop.create_future()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        sock.bind(("", 0))
    except OSError as exc:
        _LOGGER.debug("oukitel: Failed to bind UDP scan socket: %s", exc)
        sock.close()
        return None

    transport, _ = await loop.create_datagram_endpoint(
        lambda: _ScanProtocol(device_key, result),
        sock=sock,
    )

    probe = build_frame(1000, _CMD_SCAN_REQUEST)
    targets = _broadcast_targets()
    _LOGGER.debug("oukitel: Sending UDP scan for device %s to %s", device_key, targets)

    try:
        for attempt in range(3):
            for target in targets:
                transport.sendto(probe, (target, _UDP_PORT))
            try:
                return await asyncio.wait_for(asyncio.shield(result), timeout=timeout / 3)
            except (asyncio.TimeoutError, TimeoutError):
                continue
        _LOGGER.debug("oukitel: Device %s not found on LAN after 3 UDP scans", device_key)
        return None
    finally:
        transport.close()

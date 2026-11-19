"""Local fake MQTT cloud, running inside the integration.

Why it exists: the station speaks EITHER cloud OR near-field LAN, never both.
Send it to the real cloud and we lose the LAN while the data travels through
China; leave it on the LAN and it keeps reconnecting to the cloud every 3-6
minutes (the "blips"). The third way is to be its cloud ourselves: the
station is pointed over BLE (command 0x7010) at `mqtt://<HA ip>:8886` and
connects here.

What this module does: a minimal MQTT broker (only what the station really
needs: CONNECT/SUBSCRIBE/PINGREQ/PUBLISH) that receives the 0xAAAA/TTLV
frames in the clear (the MQTT channel has none of the LAN's AES) and
hands them to the coordinator with the same raw fields as the LAN.

Includes the full QuecThing FCM100D lifecycle:
- 0x00B4 Device Configuration (Device Secret reset & persistent 32-char DS write)
- 0x00B8 / 0x00B9 Time-sync watchdog responder (keeping session active 24/7)
- 0x7014 (code 65534) and 0x7066 Cloud Binding Confirmations
- High-frequency reporting (HFR Tag 100 = 3) for sub-second telemetry push
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable

from .local_scan import _DEFAULT_READ_TAGS as KNOWN_TAG_IDS
from .local_frame import FrameAssembler, build_frame, ttlv_decode, ttlv_encode
from .diag_logger import diag_log

_LOGGER = logging.getLogger(__name__)

BROKER_PORT = 8886

HFR_TAG = 100
HFR_VALUE = 3
STIMULUS_SECONDS = 5.0

# 32-character persistent Device Secret for 100% offline local sessions
LOCAL_DEVICE_SECRET = "0123456789abcdef0123456789abcdef"

_CONNECT, _PUBLISH, _SUBSCRIBE, _PINGREQ = 1, 3, 8, 12


def _enc_varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n % 128
        n //= 128
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def _dec_varint(buf: bytearray | bytes, offset: int = 1) -> tuple[int | None, int]:
    val, mult, pos = 0, 1, offset
    while pos < len(buf):
        b = buf[pos]
        val += (b & 0x7F) * mult
        mult *= 128
        pos += 1
        if not (b & 0x80):
            return val, pos
    return None, offset


def _parse_mqtt_connect(body: bytes) -> tuple[str, str, str]:
    """Extract (client_id, username, password) from MQTT 3.1.1 CONNECT packet body."""
    try:
        idx = 0
        proto_len = int.from_bytes(body[idx:idx + 2], "big")
        idx += 2 + proto_len
        idx += 1  # proto_level
        flags = body[idx]
        idx += 3  # flags + keepalive (2 bytes)
        client_id_len = int.from_bytes(body[idx:idx + 2], "big")
        idx += 2
        client_id = body[idx:idx + client_id_len].decode("utf-8", "replace")
        idx += client_id_len
        username = ""
        password = ""
        if flags & 0x04:  # will flag
            w_top_len = int.from_bytes(body[idx:idx + 2], "big")
            idx += 2 + w_top_len
            w_msg_len = int.from_bytes(body[idx:idx + 2], "big")
            idx += 2 + w_msg_len
        if flags & 0x80:  # username flag
            u_len = int.from_bytes(body[idx:idx + 2], "big")
            idx += 2
            username = body[idx:idx + u_len].decode("utf-8", "replace")
            idx += u_len
        if flags & 0x40:  # password flag
            p_len = int.from_bytes(body[idx:idx + 2], "big")
            idx += 2
            password = body[idx:idx + p_len].decode("utf-8", "replace")
            idx += p_len
        return client_id, username, password
    except Exception:
        return "", "", ""


class CloudBridge:
    """The fake cloud."""

    def __init__(
        self,
        hass,
        on_telemetry: Callable[[dict[int, Any]], None],
        on_conn: Callable[[bool], None] | None = None,
        port: int = BROKER_PORT,
    ) -> None:
        self.hass = hass
        self._on_telemetry = on_telemetry
        self._on_conn = on_conn
        self._port = port
        self._server: asyncio.Server | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connections: set[asyncio.StreamWriter] = set()
        self._down_base: str | None = None
        self._pid = 2000
        self._stimulus_task: asyncio.Task | None = None
        self._unknown_ids: set[int] = set()
        self._has_telemetry: bool = False
        self._last_telemetry_at: float | None = None
        self._silence_logged: bool = False
        self._client_password: str = ""
        self._client_id: str = ""

    def update_callbacks(
        self,
        on_telemetry: Callable[[dict[int, Any]], None],
        on_conn: Callable[[bool], None] | None = None,
    ) -> None:
        self._on_telemetry = on_telemetry
        self._on_conn = on_conn

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, "0.0.0.0", self._port, reuse_address=True
        )
        self._stimulus_task = self.hass.async_create_background_task(
            self._stimulus_loop(), "oukitel fake cloud re-stimulus"
        )
        _LOGGER.info("oukitel: [Zero-Cloud] Local MQTT broker listening on port %s", self._port)

    async def close(self) -> None:
        if self._stimulus_task and not self._stimulus_task.done():
            self._stimulus_task.cancel()
            try:
                await self._stimulus_task
            except asyncio.CancelledError:
                pass
        self._stimulus_task = None
        self._writer = None
        for conn in list(self._connections):
            try:
                conn.close()
            except Exception:
                pass
        self._connections.clear()
        if self._server is not None:
            self._server.close()
            try:
                await asyncio.wait_for(self._server.wait_closed(), timeout=5.0)
            except (asyncio.TimeoutError, Exception):
                pass
            self._server = None
        _LOGGER.info("oukitel: [Zero-Cloud] Local broker stopped")

    @property
    def connected(self) -> bool:
        return self._writer is not None

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        eti = f"{peer[0]}:{peer[1]}" if peer else "?"
        diag_log("BRIDGE_CONNECT_RAW", peer=eti)
        asm = FrameAssembler()
        buf = bytearray()
        era_lei = False
        self._connections.add(writer)
        try:
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                if not buf and chunk[0] == 0x16:
                    _LOGGER.info("oukitel: %s tried TLS (0x16), closing to force plain MQTT fallback", eti)
                    break
                buf += chunk
                while len(buf) >= 2:
                    lung, i = _dec_varint(buf, 1)
                    if lung is None or len(buf) < i + lung:
                        break
                    tipo = buf[0] >> 4
                    flags = buf[0] & 0x0F
                    body = bytes(buf[i:i + lung])
                    del buf[:i + lung]
                    if await self._handle_packet(writer, eti, tipo, flags, body, asm):
                        era_lei = True
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        except Exception as exc:
            _LOGGER.info("oukitel: connection %s ended: %s", eti, exc)
        finally:
            self._connections.discard(writer)
            if self._writer is writer:
                self._writer = None
                self._down_base = None
                diag_log("BRIDGE_DISCONNECT", peer=eti)
                _LOGGER.info("oukitel: [Zero-Cloud] Station %s disconnected from local broker", eti)
                if self._on_conn:
                    self._on_conn(False)
            elif era_lei and self._on_conn:
                self._on_conn(False)
            try:
                writer.close()
            except Exception:
                pass

    async def _handle_packet(
        self, writer: asyncio.StreamWriter, eti: str, tipo: int, flags: int, body: bytes, asm: FrameAssembler
    ) -> bool:
        diag_log("BRIDGE_MQTT_PACKET", peer=eti, type=tipo, length=len(body))
        if tipo == _CONNECT:
            self._writer = writer
            cid, user, pwd = _parse_mqtt_connect(body)
            self._client_id = cid
            self._client_password = pwd
            diag_log("BRIDGE_CONNECT", peer=eti, client_id=cid, username=user, pwd_prefix=pwd[:10])
            _LOGGER.info(
                "oukitel: [Zero-Cloud] Station connected (%s) | ClientID: %s | User: %s | Password prefix: %s",
                eti, cid, user, pwd[:16] if pwd else "(none)"
            )
            writer.write(b"\x20\x02\x00\x00")  # CONNACK ok
            await writer.drain()
            if self._on_conn:
                self._on_conn(True)
            return True

        if tipo == _SUBSCRIBE:
            pid = body[0:2]
            req_qos = bytes([body[32]]) if len(body) > 32 and body[32] in (0, 1) else b"\x01"
            writer.write(b"\x90\x03" + pid + req_qos)
            await writer.drain()
            try:
                tl = int.from_bytes(body[2:4], "big")
                topic = body[4:4 + tl].decode("utf-8", "replace")
                self._down_base = topic[:-2] if topic.endswith("/+") else topic.rsplit("/", 1)[0]
                _LOGGER.info("oukitel: [Zero-Cloud] Station subscribed to %s (downlink %s)", topic, self._down_base)
            except Exception:
                pass

            # Check if station connects with transient vendor credentials (starts with '2;' or '0;')
            # and inject 0x00B4 {5: DS} to configure local persistent Device Secret (DS)
            pwd = self._client_password
            if pwd.startswith(("2;", "0;")) or not pwd.startswith("1;0002;"):
                _LOGGER.info("oukitel: [Zero-Cloud] Station connected with credentials ('%s'). Waiting 1.5s then writing local DS via 0x00B4...", pwd[:10])
                await asyncio.sleep(1.5)
                await self._send_device_secret_overwrite()
            else:
                _LOGGER.info("oukitel: [Zero-Cloud] Station authenticated with local persistent DS ('%s')!", pwd[:16])

            # Confirm pairing/binding so station solidifies Wi-Fi icon and exits pairing mode
            await self._confirm_binding()
            await self._stimulate()
            return True

        if tipo == 4:  # PUBACK
            return True

        if tipo == _PINGREQ:
            writer.write(b"\xd0\x00")
            await writer.drain()
            return True

        if tipo == _PUBLISH:
            qos = (flags >> 1) & 3
            tl = int.from_bytes(body[0:2], "big")
            topic = body[2:2 + tl].decode("utf-8", "replace")
            payload = body[2 + tl:]
            pid_int = 0
            if qos > 0 and len(payload) >= 2:
                pid_bytes = payload[0:2]
                pid_int = int.from_bytes(pid_bytes, "big")
                payload = payload[2:]
                writer.write((b"\x40" if qos == 1 else b"\x50") + _enc_varint(2) + pid_bytes)
                await writer.drain()

            frames = asm.feed(payload)
            if not frames and payload:
                try:
                    direct_tags = ttlv_decode(payload)
                    if direct_tags:
                        frames = [(0, 20, payload)]
                except Exception:
                    pass

            for _p, _c, frame_body in frames:
                diag_log("BRIDGE_FRAME", cmd=_c, pid=_p, len=len(frame_body))
                try:
                    campi = ttlv_decode(frame_body)
                except Exception as exc:
                    _LOGGER.warning("oukitel: bus frame ttlv_decode error: %s", exc)
                    continue

                if not campi:
                    continue

                # 1. Handle Time Sync Watchdog (CMD 184 / 0x00B8) -> Respond with CMD 185 / 0x00B9
                if _c == 184:  # 0x00B8
                    uptime_str = str(campi.get(25, "0"))
                    now_ms = str(int(time.time() * 1000))
                    _LOGGER.info(
                        "oukitel: [Zero-Cloud] Received 0x00B8 watchdog (uptime=%s ms). Answering 0x00B9 time-sync!",
                        uptime_str,
                    )
                    b9_payload = ttlv_encode([
                        (25, "str", uptime_str),
                        (26, "str", now_ms),
                        (27, "str", now_ms),
                    ])
                    frame_b9 = build_frame(_p if _p else self._pid, 185, b9_payload)
                    await self._send_downlink("sys", frame_b9, qos=1)
                    await self._send_downlink("sys_", b9_payload, qos=1)
                    continue

                # 2. Handle Station Pairing & Control Requests (drop from telemetry to avoid string/metadata tag pollution)
                elif _c == 28725:  # 0x7035 login request
                    _LOGGER.info("oukitel: [Zero-Cloud] Station requested login (0x7035), sending login ack (0x7065)")
                    await self._send_downlink("bus", build_frame(_p, 28773, ttlv_encode([(1, "num", 0), (2, "num", 0), (10, "num", 65534)])), qos=1)
                    continue
                elif _c == 28726:  # 0x7036 bind request
                    _LOGGER.info("oukitel: [Zero-Cloud] Station requested bind (0x7036), sending bind ack (0x7066)")
                    await self._send_downlink("bus", build_frame(_p, 28774, ttlv_encode([(1, "num", 0), (2, "num", 0), (10, "num", 65534)])), qos=1)
                    continue
                elif _c in (28753, 28755):
                    _LOGGER.info("oukitel: [Zero-Cloud] Station requested status (0x%04X), sending status ack (0x7054)", _c)
                    await self._send_downlink("bus", build_frame(_p, 28756, ttlv_encode([(1, "num", 0), (2, "num", 0)])), qos=1)
                    continue

                # Ignore non-telemetry protocol command frames
                if _c in (184, 185, 28720, 28721, 28722, 28723, 28724, 28725, 28726, 28727, 28728, 28753, 28754, 28755, 28756, 28773, 28774):
                    continue

                self._has_telemetry = True
                self._last_telemetry_at = time.monotonic()
                self._silence_logged = False

                for ident, value in campi.items():
                    if ident not in KNOWN_TAG_IDS and ident not in self._unknown_ids:
                        self._unknown_ids.add(ident)
                        _LOGGER.debug("oukitel: [Zero-Cloud] new tag %s = %r", ident, value)

                try:
                    self._on_telemetry(campi)
                except Exception as exc:
                    _LOGGER.warning("oukitel: telemetry callback error: %s", exc)
            return True

        return False

    def _pacchetto_publish(self, topic: bytes, frame: bytes, qos: int = 1, pid: int = 1) -> bytes:
        if qos == 1:
            return (
                b"\x32"
                + _enc_varint(2 + len(topic) + 2 + len(frame))
                + len(topic).to_bytes(2, "big")
                + topic
                + pid.to_bytes(2, "big")
                + frame
            )
        return (
            b"\x30"
            + _enc_varint(2 + len(topic) + len(frame))
            + len(topic).to_bytes(2, "big")
            + topic
            + frame
        )

    async def _send_downlink(self, sub: str, frame: bytes, qos: int = 0) -> None:
        writer = self._writer
        base = self._down_base
        if writer is None or base is None or writer.is_closing():
            return
        topic = f"{base}/{sub}".encode()
        self._mqtt_pid = (getattr(self, "_mqtt_pid", 0) % 65535) + 1
        pkt = self._pacchetto_publish(topic, frame, qos=qos, pid=self._mqtt_pid)
        diag_log("BRIDGE_DOWNLINK", topic=topic.decode(), qos=qos, hex=frame.hex())
        writer.write(pkt)
        await writer.drain()
        await asyncio.sleep(0.04)

    async def _manda_frame(self, frame: bytes) -> None:
        writer = self._writer
        base = self._down_base
        if writer is None or base is None or writer.is_closing():
            return
        await self._send_downlink("bus", frame, qos=1)
        await writer.drain()

    async def _send_device_secret_overwrite(self) -> None:
        """Send QuecThing 0x00B4 {5: DS} frame to establish local 32-char DS (omits {9} to prevent NVRAM corruption)."""
        if self._writer is None or self._down_base is None:
            return
        try:
            self._pid += 1
            # Frame {5: "<32-char DS>"} -> Set our persistent local Device Secret directly
            frame_set_ds = build_frame(self._pid, 180, ttlv_encode([(5, "str", LOCAL_DEVICE_SECRET)]))
            _LOGGER.info("oukitel: [Zero-Cloud] Sending 0x00B4 {5: '%s'} to establish local offline DS...", LOCAL_DEVICE_SECRET)
            for sub in ("sys", "bus"):
                await self._send_downlink(sub, frame_set_ds, qos=1)

            _LOGGER.info("oukitel: [Zero-Cloud] 0x00B4 local Device Secret dispatched successfully.")
        except Exception as exc:
            _LOGGER.warning("oukitel: [Zero-Cloud] Failed sending 0x00B4 sequence: %s", exc)

    async def _confirm_binding(self) -> None:
        """Confirm to the station that cloud activation and device binding succeeded."""
        if self._writer is None or self._down_base is None:
            return
        try:
            self._pid += 1
            frame_login_ack = build_frame(self._pid, 28773, ttlv_encode([(1, "num", 0), (2, "num", 0), (10, "num", 65534)]))
            self._pid += 1
            frame_bind_ack = build_frame(self._pid, 28774, ttlv_encode([(1, "num", 0), (2, "num", 0), (10, "num", 65534)]))
            self._pid += 1
            frame_status_ack = build_frame(self._pid, 28756, ttlv_encode([(1, "num", 0), (2, "num", 0)]))
            self._pid += 1
            success_ack_fe = build_frame(self._pid, 28692, ttlv_encode([(10, "num", 65534), (11, "num", 0), (1, "num", 0)]))

            # Send binary frames
            for sub in ("bus", "sys"):
                await self._send_downlink(sub, frame_login_ack, qos=1)
                await self._send_downlink(sub, frame_bind_ack, qos=1)
                await self._send_downlink(sub, frame_status_ack, qos=1)
                await self._send_downlink(sub, success_ack_fe, qos=1)

            _LOGGER.info("oukitel: [Zero-Cloud] Binding confirmations (0x7014/0x7065/0x7066) sent.")
        except Exception as exc:
            _LOGGER.warning("oukitel: [Zero-Cloud] confirm_binding failed: %s", exc)

    async def _stimulate(self, rumoroso: bool = True) -> None:
        """Request high-frequency reporting mode + all tag metrics."""
        if self._writer is None or self._down_base is None:
            return
        try:
            self._pid += 1
            # HFR tag 100 = 3
            await self._manda_frame(
                build_frame(self._pid, 19, ttlv_encode([(HFR_TAG, "num", HFR_VALUE)]))
            )
            self._pid += 1
            tag_bytes = b"".join(i.to_bytes(2, "big") for i in KNOWN_TAG_IDS)
            await self._manda_frame(
                build_frame(self._pid, 17, tag_bytes)
            )
            if rumoroso:
                _LOGGER.info("oukitel: [Zero-Cloud] Stimulus sent (high frequency reporting active)")
        except Exception as exc:
            _LOGGER.debug("oukitel: [Zero-Cloud] stimulus failed: %s", exc)

    async def _stimulus_loop(self) -> None:
        try:
            loop_count = 0
            while True:
                await asyncio.sleep(STIMULUS_SECONDS)
                if self._writer is not None:
                    loop_count += 1
                    if loop_count % 6 == 0:
                        await self._confirm_binding()
                    await self._stimulate(rumoroso=False)
        except asyncio.CancelledError:
            raise

    async def connect(self) -> None:
        return None

    async def read_loop(self) -> None:
        return None

    async def request_read(self) -> None:
        self._pid += 1
        await self._manda_frame(
            build_frame(self._pid, 17, b"".join(i.to_bytes(2, "big") for i in KNOWN_TAG_IDS))
        )

    async def resubscribe(self) -> None:
        await self._stimulate(rumoroso=False)

    async def send_write(self, tag: int, kind: str, value: Any) -> None:
        self._pid += 1
        await self._manda_frame(build_frame(self._pid, 19, ttlv_encode([(tag, kind, value)])))
        _LOGGER.debug("oukitel: [Zero-Cloud] bus command tag %s = %s", tag, value)

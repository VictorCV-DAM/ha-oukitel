"""Local fake MQTT cloud, running inside the integration.

Why it exists: the station speaks EITHER cloud OR near-field LAN, never both.
Send it to the real cloud and we lose the LAN while the data travels through
China; leave it on the LAN and it keeps reconnecting to the cloud every 3-6
minutes (the "blips"). The third way is to be its cloud ourselves: the
station is pointed over BLE (command 0x7010) at `mqtt://<HA ip>:8886` and
connects here.

What this module does: a minimal MQTT broker (only what the station really
needs: CONNECT/SUBSCRIBE/PINGREQ/PUBLISH) that receives the 0xAAAA/TTLV
frames **in the clear** (the MQTT channel has none of the LAN's AES) and
hands them to the coordinator with the same raw fields as the LAN.

The trick that keeps the rest of the code small: this class **behaves like a
LAN session** (`send_write` and `close`). That way the coordinator can put it
in `_lan_session` and commands, telemetry and the update cycle keep working
with no special cases.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

# The ids this station is known to report. A frame carrying anything else
# is a placeholder rather than a reading, and publishing those makes the
# entities flap. This repository already keeps such a list in
# local_scan.py, so the bridge borrows it instead of inventing its own.
from .local_scan import _DEFAULT_READ_TAGS as KNOWN_TAG_IDS
from .local_frame import FrameAssembler, build_frame, ttlv_decode, ttlv_encode

_LOGGER = logging.getLogger(__name__)

BROKER_PORT = 8886

# The station only publishes continuously in "high frequency" mode: without
# this it reports once, on request. Same tag the LAN side uses.
HFR_TAG = 100
HFR_VALUE = 3
STIMULUS_SECONDS = 20.0

# The MQTT packet types we care about
_CONNECT, _PUBLISH, _SUBSCRIBE, _PINGREQ = 1, 3, 8, 12

# The ids the vendor's model declares for this station.


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


def _dec_varint(buf: bytes | bytearray, i: int):
    """Read the MQTT 'remaining length'. (None, i) if not enough bytes yet."""
    mult, val = 1, 0
    while True:
        if i >= len(buf):
            return None, i
        b = buf[i]
        i += 1
        val += (b & 0x7F) * mult
        if not b & 0x80:
            return val, i
        mult *= 128


class CloudBridge:
    """MQTT broker that impersonates the station's cloud.

    Exposes `send_write` and `close` with the same signature as the LAN
    session, so the coordinator uses it in that one's place without noticing.
    """

    def __init__(
        self,
        hass,
        on_telemetry: Callable[[dict[int, Any]], None],
        on_conn: Callable[[bool], None] | None = None,
        porta: int = BROKER_PORT,
    ) -> None:
        self.hass = hass
        self._on_telemetry = on_telemetry
        self._on_conn = on_conn
        self._port = porta
        self._server: asyncio.AbstractServer | None = None
        self._writer: asyncio.StreamWriter | None = None  # the station
        # Every open connection, not just the station's: on shutdown they
        # all have to be closed, otherwise the server never finishes
        # stopping.
        self._connections: set[asyncio.StreamWriter] = set()
        self._down_base: str | None = None
        self._pid = 2000
        self._stimulus_task: asyncio.Task | None = None
        # Ids seen on the bus but not declared by the model: reported only
        # once, to find out whether the station is sending something useful
        # that we currently throw away without even looking at it.
        self._unknown_ids: set[int] = set()

    # -------------------------------------------------------------- startup

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, "0.0.0.0", self._port, reuse_address=True
        )
        # Background task: Home Assistant does not wait for it on shutdown.
        self._stimulus_task = self.hass.async_create_background_task(
            self._stimulus_loop(), "oukitel fake cloud re-stimulus"
        )
        _LOGGER.info("oukitel: fake cloud listening on %s", self._port)

    async def close(self) -> None:
        """Close everything. Same signature as the LAN session, so the
        coordinator's shutdown works without changes."""
        if self._stimulus_task and not self._stimulus_task.done():
            self._stimulus_task.cancel()
            try:
                await self._stimulus_task
            except asyncio.CancelledError:
                pass
        self._stimulus_task = None
        # ALL connections are closed, not just the station's: `wait_closed()`
        # waits for every handler to finish, and a handler parked in a read
        # would hang the unloading of the config entry forever (the
        # integration was seen stuck on "Unloading").
        self._writer = None
        for conn in list(self._connections):
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        self._connections.clear()
        if self._server is not None:
            self._server.close()
            try:
                # With a deadline: better to leave a socket behind for the
                # operating system than to keep Home Assistant blocked.
                await asyncio.wait_for(self._server.wait_closed(), timeout=5.0)
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                _LOGGER.debug("oukitel: fake cloud shutdown not clean, carrying on")
            self._server = None
        _LOGGER.info("oukitel: fake cloud stopped")

    @property
    def connected(self) -> bool:
        return self._writer is not None

    # ------------------------------------------------------------ connection

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        eti = f"{peer[0]}:{peer[1]}" if peer else "?"
        asm = FrameAssembler()
        buf = bytearray()
        era_lei = False
        self._connections.add(writer)
        try:
            while True:
                chunk = await reader.read(4096)
                if not chunk:
                    break
                # The station tries TLS first (with a PSK we do not have): we
                # shut the door on it and it falls back to plain MQTT.
                if not buf and chunk[0] == 0x16:
                    _LOGGER.debug("oukitel: %s tried TLS, closing", eti)
                    break
                buf += chunk
                while len(buf) >= 2:
                    lung, i = _dec_varint(buf, 1)
                    if lung is None or len(buf) < i + lung:
                        break
                    tipo = buf[0] >> 4
                    flags = buf[0] & 0x0F
                    body = bytes(buf[i : i + lung])
                    del buf[: i + lung]
                    if await self._handle_packet(writer, eti, tipo, flags, body, asm):
                        era_lei = True
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("oukitel: connection %s ended: %s", eti, exc)
        finally:
            self._connections.discard(writer)
            if self._writer is writer:
                self._writer = None
                self._down_base = None
                if self._on_conn:
                    self._on_conn(False)
            elif era_lei and self._on_conn:
                self._on_conn(False)
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    async def _handle_packet(
        self, writer: asyncio.StreamWriter, eti: str, tipo: int, flags: int, body: bytes, asm: FrameAssembler
    ) -> bool:
        """Answer one MQTT packet. Returns True if it is the station."""
        if tipo == _CONNECT:
            self._writer = writer
            writer.write(b"\x20\x02\x00\x00")  # CONNACK ok
            await writer.drain()
            _LOGGER.info("oukitel: station connected to the fake cloud (%s)", eti)
            if self._on_conn:
                self._on_conn(True)
            return True

        if tipo == _SUBSCRIBE:
            pid = body[0:2]
            writer.write(b"\x90" + _enc_varint(3) + pid + b"\x00")  # SUBACK
            await writer.drain()
            try:
                tl = int.from_bytes(body[2:4], "big")
                topic = body[4 : 4 + tl].decode("utf-8", "replace")
                self._down_base = topic[:-2] if topic.endswith("/+") else topic.rsplit("/", 1)[0]
                _LOGGER.info("oukitel: subscribed to %s (downlink %s)", topic, self._down_base)
            except Exception:  # noqa: BLE001
                pass
            # Without the SUBACK the station will not publish; without a
            # stimulus it publishes only once. The two together open the tap.
            await self._stimulate()
            return True

        if tipo == _PINGREQ:
            writer.write(b"\xd0\x00")
            await writer.drain()
            return True

        if tipo == _PUBLISH:
            qos = (flags >> 1) & 3
            tl = int.from_bytes(body[0:2], "big")
            resto = body[2 + tl :]
            if qos > 0 and len(resto) >= 2:
                pid = resto[0:2]
                resto = resto[2:]
                writer.write((b"\x40" if qos == 1 else b"\x50") + _enc_varint(2) + pid)
                await writer.drain()
            for _p, _c, payload in asm.feed(resto):
                try:
                    campi = ttlv_decode(payload)
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.debug("oukitel: bus frame not decoded: %s", exc)
                    continue
                if not campi:
                    continue
                for ident, value in campi.items():
                    if ident not in KNOWN_TAG_IDS and ident not in self._unknown_ids:
                        self._unknown_ids.add(ident)
                        _LOGGER.warning(
                            "oukitel: id %s is not in the model, value %r", ident, value
                        )

                # The RAW fields are handed over (id -> value): the coordinator
                # decodes them with the model exactly like the LAN ones.
                try:
                    self._on_telemetry(campi)
                except Exception as exc:  # noqa: BLE001
                    _LOGGER.warning("oukitel: bus telemetry not applied: %s", exc)
            return True

        return False

    # ------------------------------------------------------------- downlink

    def _pacchetto_publish(self, topic: bytes, frame: bytes) -> bytes:
        return (
            b"\x30"
            + _enc_varint(2 + len(topic) + len(frame))
            + len(topic).to_bytes(2, "big")
            + topic
            + frame
        )

    async def _manda_frame(self, frame: bytes) -> None:
        writer = self._writer
        base = self._down_base
        if writer is None or base is None:
            raise RuntimeError("no station connected to the fake cloud")
        writer.write(self._pacchetto_publish(f"{base}/rw".encode(), frame))
        await writer.drain()

    async def _stimulate(self, rumoroso: bool = True) -> None:
        """High-frequency mode + read of every id, like the real cloud does."""
        if self._writer is None or self._down_base is None:
            return
        try:
            self._pid += 1
            await self._manda_frame(
                build_frame(self._pid, 19, ttlv_encode([(HFR_TAG, "num", HFR_VALUE)]))
            )
            self._pid += 1
            await self._manda_frame(
                build_frame(self._pid, 17, b"".join(i.to_bytes(2, "big") for i in KNOWN_TAG_IDS))
            )
            if rumoroso:
                _LOGGER.info("oukitel: stimulus sent (high frequency + read)")
        except Exception as exc:  # noqa: BLE001
            _LOGGER.debug("oukitel: stimulus failed: %s", exc)

    async def _stimulus_loop(self) -> None:
        """Re-arm high-frequency mode now and then, if the station loses it."""
        try:
            while True:
                await asyncio.sleep(STIMULUS_SECONDS)
                if self._writer is not None:
                    await self._stimulate(rumoroso=False)
        except asyncio.CancelledError:
            raise

    # The rest of the LAN-session disguise: the coordinator calls these too,
    # and here they mean slightly different things with the same effect.

    async def connect(self) -> None:
        """Nothing to connect to: it is the station that comes to us."""
        return None

    async def read_loop(self) -> None:
        """The read loop is the server itself, no separate task needed."""
        return None

    async def request_read(self) -> None:
        """Ask the station to report everything (cmd 17), as the LAN does."""
        self._pid += 1
        await self._manda_frame(
            build_frame(self._pid, 17, b"".join(i.to_bytes(2, "big") for i in KNOWN_TAG_IDS))
        )

    async def resubscribe(self) -> None:
        """Re-arm high-frequency reporting."""
        await self._stimulate(rumoroso=False)

    async def send_write(self, tag: int, kind: str, value: Any) -> None:
        """Write a value to the station.

        Same signature as `LocalSession.send_write`, so the coordinator sends
        commands without knowing whether it is talking over the LAN or over
        the fake cloud.
        """
        self._pid += 1
        await self._manda_frame(build_frame(self._pid, 19, ttlv_encode([(tag, kind, value)])))
        _LOGGER.debug("oukitel: bus command id %s = %s", tag, value)

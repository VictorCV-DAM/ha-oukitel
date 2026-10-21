"""BLE pairing of the station (command 0x7010), from inside Home Assistant.

What it is for: telling the station which WiFi network to join and which
cloud or local broker to connect to. The cloud address is not hardcoded in the
firmware: it is handed to the station during provisioning.

Why this code lives in the integration: the station only accepts writes on
characteristic `9c40` over a connection without bonding. From inside HA we use
the official bluetooth stack (homeassistant.components.bluetooth and
bleak_retry_connector), which already coordinates local adapters and ESPHome
Bluetooth proxies and connects in the clear.

Practical notes:
- `9c40` is only open while the station is in pairing mode (WiFi icon blinking),
  typically after pressing and holding the IoT / WiFi reset button. Outside that
  window it answers Insufficient Authorization.
- A successful pairing closes that window: once the station accepts 0x7010,
  it joins the network and leaves pairing mode.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from .local_frame import FrameAssembler, build_frame, ttlv_decode

_LOGGER = logging.getLogger(__name__)

CMD_PROVISION = 28688  # 0x7010 request
CMD_CONFIRM = 28689   # 0x7011 station reply confirmation
CMD_PROGRESS = 28692  # 0x7014 pairing / connection in progress

CHARACTERISTIC_SHORT = "9c40"

# TTLV tag IDs inside the 0x7010 payload
ID_SSID = 1
ID_PASSWORD = 2
ID_ENDPOINT = 13

_TYPE_STRING = 3


def _ttlv_str(ident: int, text: str) -> bytes:
    data = text.encode("utf-8")
    return struct.pack(">H", (ident << 3) | _TYPE_STRING) + struct.pack(">H", len(data)) + data


def build_provisioning_frame(ssid: str, password: str, endpoint: str) -> bytes:
    """Build the 0x7010 provisioning frame: network SSID, password and target broker/cloud endpoint."""
    body = _ttlv_str(ID_SSID, ssid) + _ttlv_str(ID_PASSWORD, password) + _ttlv_str(ID_ENDPOINT, endpoint)
    return build_frame(1000, CMD_PROVISION, body)


def async_discover_oukitel_ble(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Scan for discoverable Oukitel power stations currently advertising over BLE."""
    results: list[dict[str, Any]] = []
    seen_addresses = set()
    for info in bluetooth.async_discovered_service_info(hass, connectable=True):
        addr = info.address
        if addr in seen_addresses:
            continue
        name = (info.name or "").strip()
        name_upper = name.upper()

        pk = ""
        dk = ""
        # Parse Quectel BLE beacon manufacturer data
        for data in (info.manufacturer_data or {}).values():
            try:
                if len(data) >= 6:
                    i = 4
                    length = data[i]
                    pk = data[i + 1 : i + 1 + length].decode("ascii")
                    i += 1 + length
                    length = data[i]
                    dk = data[i + 1 : i + 1 + length].hex()
            except Exception:
                continue

        is_candidate = (
            bool(pk and dk)
            or name_upper.startswith("QUEC_BLE")
            or any(
                p in name_upper
                for p in ("OUKITEL", "P2001", "BP2000", "P5000", "P1200", "P800", "CN505")
            )
        )
        if is_candidate:
            seen_addresses.add(addr)
            results.append({
                "address": addr,
                "name": name or f"Oukitel BLE ({addr})",
                "rssi": info.rssi,
                "source": getattr(info, "source", "local"),
                "device_key": dk,
                "product_key": pk,
            })
    return results


def async_get_bluetooth_sources(hass: HomeAssistant, mac: str = "") -> list[str]:
    """Return available Bluetooth adapter and ESPHome proxy sources."""
    sources = ["auto"]
    try:
        seen = set()
        if mac:
            for sd in bluetooth.async_scanner_devices_by_address(hass, mac, connectable=True):
                src = getattr(sd.scanner, "source", None)
                if src and src not in seen:
                    seen.add(src)
                    sources.append(src)
        if len(sources) == 1:
            scanner_obj = bluetooth.async_get_scanner(hass)
            for sc in getattr(scanner_obj, "scanners", []):
                src = getattr(sc, "source", None)
                if src and src not in seen:
                    seen.add(src)
                    sources.append(src)
    except Exception:
        pass
    return sources


async def point_station(
    hass: HomeAssistant,
    ssid: str,
    password: str,
    endpoint: str,
    mac: str,
    listen_for: float = 30.0,
    source: str = "",
) -> tuple[bool, str]:
    """Send the 0x7010 provisioning frame to the station over BLE and await confirmation.

    Returns (succeeded, human_readable_message).
    """
    if not ssid:
        return False, "El nombre de la red Wi-Fi (SSID) no puede estar vacío."
    if not password:
        return False, "La contraseña de la red Wi-Fi no puede estar vacía."
    if not endpoint:
        return False, "La dirección del endpoint / broker no puede estar vacía."
    if not mac:
        return False, "La dirección MAC Bluetooth de la estación es requerida."

    from bleak import BleakClient
    from bleak_retry_connector import establish_connection

    frame = build_provisioning_frame(ssid, password, endpoint)

    device = None
    if source and source != "auto":
        for sd in bluetooth.async_scanner_devices_by_address(hass, mac, connectable=True):
            if getattr(sd.scanner, "source", None) == source:
                device = sd.ble_device
                _LOGGER.info("oukitel: Using chosen Bluetooth adapter/proxy (%s)", source)
                break
        if device is None:
            _LOGGER.warning(
                "oukitel: The chosen Bluetooth source (%s) cannot see %s, falling back to auto",
                source,
                mac,
            )

    if device is None:
        device = bluetooth.async_ble_device_from_address(hass, mac, connectable=True)

    if device is None:
        return False, (
            f"No se detecta la estación por Bluetooth ({mac}). "
            "Asegúrate de que está encendida y en modo emparejamiento (icono Wi-Fi parpadeando)."
        )

    _LOGGER.info(
        "oukitel: Found BLE device %s (source=%s), connecting to provision Wi-Fi/Endpoint",
        mac,
        getattr(device, "details", {}),
    )

    asm = FrameAssembler()
    queue: asyncio.Queue = asyncio.Queue()

    def on_notify(_car, data: bytearray) -> None:
        for pid, cmd, payload in asm.feed(bytes(data)):
            queue.put_nowait((pid, cmd, payload))

    client = await establish_connection(BleakClient, device, mac, max_attempts=6)
    try:
        target_char = None
        for service in client.services:
            for ch in service.characteristics:
                if len(ch.uuid) >= 8 and ch.uuid[4:8].lower() == CHARACTERISTIC_SHORT:
                    target_char = ch
                    break
            if target_char is not None:
                break

        if target_char is None:
            return False, f"Característica {CHARACTERISTIC_SHORT} no encontrada en los servicios GATT de la estación."

        try:
            await client.start_notify(target_char, on_notify)
        except Exception as exc:
            _LOGGER.debug("oukitel: start_notify not supported or skipped on %s: %s", target_char.uuid, exc)

        try:
            await client.write_gatt_char(target_char, frame, response=True)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("oukitel: write_gatt_char with response failed (%s), retrying without response", exc)
            try:
                await client.write_gatt_char(target_char, frame, response=False)
            except Exception as exc2:
                if "Authorization" in str(exc2) or "133" in str(exc2):
                    return False, (
                        "La estación rechazó la orden (Autorización insuficiente). "
                        "Verifica que esté en modo emparejamiento con el icono Wi-Fi parpadeando."
                    )
                return False, f"Error al escribir en BLE ({target_char.uuid}): {exc2}"

        _LOGGER.info("oukitel: BLE provisioning frame 0x7010 sent, awaiting 0x7011 confirmation")

        confirmed = False
        deadline = time.monotonic() + listen_for
        while time.monotonic() < deadline:
            left = deadline - time.monotonic()
            try:
                _pid, cmd, payload = await asyncio.wait_for(queue.get(), timeout=left)
            except asyncio.TimeoutError:
                break

            if cmd == CMD_CONFIRM:
                confirmed = True
                try:
                    fields = ttlv_decode(payload)
                    _LOGGER.info("oukitel: BLE 0x7011 confirmation decoded: %s", fields)
                except Exception:  # noqa: BLE001
                    _LOGGER.info("oukitel: BLE 0x7011 confirmation received")
            elif cmd == CMD_PROGRESS:
                # Keep BLE link alive while station connects to Wi-Fi
                try:
                    fields = ttlv_decode(payload)
                    _LOGGER.info("oukitel: Station joining Wi-Fi network (0x7014 progress notification: %s)", fields)
                    if isinstance(fields, dict) and fields.get(11) == 0:
                        _LOGGER.info("oukitel: Station confirmed successful pairing on BLE (status 0)")
                        confirmed = True
                        break
                except Exception:
                    _LOGGER.info("oukitel: Station joining Wi-Fi network (0x7014 progress notification)")

                # Reply with 0x7014 success (tag 10 = 0, tag 11 = 0) so the station knows cloud binding is approved
                try:
                    success_frame = build_frame(1001, CMD_PROGRESS, ttlv_encode([(10, "num", 0), (11, "num", 0), (1, "num", 0)]))
                    await client.write_gatt_char(target_char, success_frame, response=False)
                    _LOGGER.info("oukitel: Sent 0x7014 success confirmation over BLE to station")
                except Exception as exc:
                    _LOGGER.debug("oukitel: Could not send 0x7014 success over BLE: %s", exc)

        try:
            await client.stop_notify(target_char)
        except Exception:
            pass

        if confirmed:
            return True, (
                f"Aprovisionamiento completado con éxito: Red '{ssid}', Endpoint '{endpoint}'. "
                "La estación se conectará a la red en breve."
            )
        return False, (
            "Se envió la trama de aprovisionamiento pero no se recibió la confirmación 0x7011 a tiempo."
        )
    finally:
        try:
            await client.disconnect()
        except Exception:  # noqa: BLE001
            pass

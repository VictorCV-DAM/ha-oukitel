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



from .local_frame import FrameAssembler, build_frame, ttlv_decode, ttlv_encode

from .diag_logger import diag_log



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





def _ttlv_num(ident: int, value: int) -> bytes:

    from .local_frame import _encode_int

    return struct.pack(">H", (ident << 3) | 2) + _encode_int(int(value))





def build_provisioning_frame(ssid: str, password: str, endpoint: str) -> bytes:

    """Build the official Quectel 0x7010 provisioning frame:

    Tag 1: SSID (str)

    Tag 2: Password (str)

    Tag 11: Provisioning timeout in seconds (num)

    Tag 13: Endpoint URI (str - e.g. mqtt://192.168.1.219:8886)

    Tag 12: MCC / Protocol (num - default 460)

    """

    import urllib.parse

    port = 8886 if "8886" in endpoint else 8883

    mcc = 214



    if "://" in endpoint:

        parsed = urllib.parse.urlparse(endpoint)

        if parsed.port:

            port = parsed.port

        url = endpoint

    elif ":" in endpoint:

        parts = endpoint.split(":")

        try:

            port = int(parts[1])

        except ValueError:

            pass

        url = f"mqtt://{endpoint}"

    else:

        url = f"mqtt://{endpoint}:{port}"



    if endpoint.strip().lower() in ("", "none", "lan"):

        # No cloud endpoint: join Wi-Fi and let the station expose its local

        # LAN server on 6607.

        body = _ttlv_str(1, ssid) + _ttlv_str(2, password)

        return build_frame(1000, CMD_PROVISION, body)



    body = (

        _ttlv_str(1, ssid)

        + _ttlv_str(2, password)

        + _ttlv_num(11, 60)  # tag 11 is a timeout; the port is in tag 13 URL

        + _ttlv_str(13, url)

        + _ttlv_num(12, mcc)

    )

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





async def _ble_keepalive_loop(hass, client, char) -> None:

    """Keep the provisioning BLE link alive with a harmless periodic write.



    The module drops the link shortly after the last GATT write, which also

    stops the MCU telemetry stream. A 10 s write keeps both alive.

    """

    while True:

        await asyncio.sleep(10)

        if not getattr(client, "is_connected", False):

            diag_log("BLE_KEEPALIVE_STOP")

            return

        try:

            await client.write_gatt_char(char, build_frame(1005, 28774, b""), response=False)

            diag_log("BLE_KEEPALIVE_TICK")

        except Exception as exc:  # noqa: BLE001

            diag_log("BLE_KEEPALIVE_ERR", error=str(exc))

            return





async def point_station(

    hass: HomeAssistant,

    ssid: str,

    password: str,

    endpoint: str,

    mac: str,

    listen_for: float = 180.0,

    source: str = "",

) -> tuple[bool, str]:

    """Send the 0x7010 provisioning frame to the station over BLE and await confirmation.



    Returns (succeeded, human_readable_message).

    """

    if not ssid:

        return False, "El nombre de la red Wi-Fi (SSID) no puede estar vacÃ­o."

    if not password:

        return False, "La contraseÃ±a de la red Wi-Fi no puede estar vacÃ­a."

    if not endpoint:

        return False, "La direcciÃ³n del endpoint / broker no puede estar vacÃ­a."

    if not mac:

        return False, "La direcciÃ³n MAC Bluetooth de la estaciÃ³n es requerida."



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

            f"No se detecta la estaciÃ³n por Bluetooth ({mac}). "

            "AsegÃºrate de que estÃ¡ encendida y en modo emparejamiento (icono Wi-Fi parpadeando)."

        )



    diag_log("BLE_POINT_STATION_CONNECTING", mac=mac, source=str(source), ssid=ssid, endpoint=endpoint)

    _LOGGER.info(

        "oukitel: Found BLE device %s (source=%s), connecting to provision Wi-Fi/Endpoint",

        mac,

        getattr(device, "details", {}),

    )



    asm = FrameAssembler()

    queue: asyncio.Queue = asyncio.Queue()



    def on_notify(_car, data: bytearray) -> None:

        diag_log("BLE_NOTIFY_RAW", hex=bytes(data).hex(), len=len(data))

        for pid, cmd, payload in asm.feed(bytes(data)):

            diag_log(

                "BLE_NOTIFY_PACKET",

                pid=pid,

                cmd=cmd,

                cmd_hex=f"0x{cmd:04X}" if isinstance(cmd, int) else str(cmd),

                len=len(payload),

                hex=payload.hex(),

            )

            queue.put_nowait((pid, cmd, payload))



    client = await establish_connection(BleakClient, device, mac, max_attempts=6)

    from .const import DOMAIN

    # Persist client in hass.data so the BLE connection is never garbage-collected or dropped

    hass.data.setdefault(DOMAIN, {})["ble_client"] = client



    def on_ble_disconnect(_c):

        _LOGGER.info("oukitel: Station BLE connection terminated naturally by peripheral")

        diag_log("BLE_STATION_DISCONNECTED_NATURALLY", mac=mac)

        hass.data.get(DOMAIN, {}).pop("ble_client", None)



    try:

        client.set_disconnected_callback(on_ble_disconnect)

    except Exception:

        pass

    try:

        try:

            table = [

                (

                    str(service.uuid),

                    [(str(ch.uuid), list(ch.properties)) for ch in service.characteristics],

                )

                for service in client.services

            ]

            diag_log("BLE_GATT_TABLE", services=table)

        except Exception as exc:  # noqa: BLE001

            diag_log("BLE_GATT_TABLE_ERROR", error=str(exc))



        target_char = None

        for service in client.services:

            for ch in service.characteristics:

                if len(ch.uuid) >= 8 and ch.uuid[4:8].lower() == CHARACTERISTIC_SHORT:

                    target_char = ch

                    break

            if target_char is not None:

                break



        if target_char is None:

            return False, f"CaracterÃ­stica {CHARACTERISTIC_SHORT} no encontrada en los servicios GATT de la estaciÃ³n."



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

                        "La estaciÃ³n rechazÃ³ la orden (AutorizaciÃ³n insuficiente). "

                        "Verifica que estÃ© en modo emparejamiento con el icono Wi-Fi parpadeando."

                    )

                return False, f"Error al escribir en BLE ({target_char.uuid}): {exc2}"



        diag_log(

            "BLE_PROVISION_0x7010_SENT",

            mac=mac,

            char=str(getattr(target_char, "uuid", "")),

            hex=frame.hex(),

        )

        _LOGGER.info("oukitel: BLE provisioning frame 0x7010 sent, awaiting 0x7011 confirmation")



        confirmed = False

        station_reached_cloud = False

        bind_ack = build_frame(

            1003,

            28774,

            ttlv_encode([(1, "num", 0), (2, "num", 0), (10, "num", 65534)]),

        )

        prog_ack = build_frame(1004, CMD_PROGRESS, ttlv_encode([(10, "num", 65534), (11, "num", 0)]))

        last_success_ack = 0.0

        loop_start = time.monotonic()

        deadline = loop_start + listen_for

        while time.monotonic() < deadline:

            left = deadline - time.monotonic()

            if left <= 0:

                break

            try:

                _pid, cmd, payload = await asyncio.wait_for(queue.get(), timeout=min(left, 3.0))

            except asyncio.TimeoutError:

                if not getattr(client, "is_connected", True):

                    _LOGGER.info("oukitel: Station disconnected BLE naturally, pairing finished!")

                    diag_log("BLE_STATION_NATURAL_DISCONNECT_IN_LOOP")

                    break

                bridge = hass.data.get(DOMAIN, {}).get("bridge")

                if bridge and getattr(bridge, "_has_telemetry", False) and station_reached_cloud:

                    diag_log("BLE_TELEMETRY_ACTIVE_REFRESHING_ACKS")

                    try:

                        await client.write_gatt_char(target_char, bind_ack, response=False)

                    except Exception:

                        pass

                # The station only emits 0x7014 progress when it actually has to

                # join Wi-Fi. If it is already associated it jumps straight to

                # streaming and the MCU never receives the 0xFFFE success code,

                # so its pairing timer keeps running and the stream is tied to

                # this BLE session. Re-send the definitive ack while we listen.

                if confirmed and (time.monotonic() - last_success_ack) >= 10:

                    try:

                        await client.write_gatt_char(target_char, bind_ack, response=False)

                        await asyncio.sleep(0.05)

                        await client.write_gatt_char(target_char, prog_ack, response=False)

                        last_success_ack = time.monotonic()

                        diag_log(

                            "BLE_SUCCESS_ACK_RESENT",

                            bind_hex=bind_ack.hex(),

                            prog_hex=prog_ack.hex(),

                        )

                    except Exception as exc:  # noqa: BLE001

                        _LOGGER.debug("oukitel: periodic success ack failed: %s", exc)

                continue



            if cmd == CMD_CONFIRM:

                confirmed = True

                try:

                    fields = ttlv_decode(payload)

                    _LOGGER.info("oukitel: BLE 0x7011 confirmation decoded: %s", fields)

                except Exception:  # noqa: BLE001

                    _LOGGER.info("oukitel: BLE 0x7011 confirmation received")

            elif cmd in (28773, 28725):  # 0x7065 (cloud login ack req) or 0x7035

                _LOGGER.info("oukitel: Station sent BLE cmd=0x%04X, replying with 0x7066 cloud ack", cmd)

                diag_log("BLE_REPLYING_0x7066", cmd=cmd)

                reply = build_frame(_pid if _pid else 1001, 28774, b"")

                diag_log("BLE_GATT_WRITE_0x7066", reason="0x7065-request", cmd=cmd, hex=reply.hex())

                try:

                    await client.write_gatt_char(target_char, reply, response=False)

                except Exception as exc:

                    _LOGGER.warning("oukitel: BLE write 0x7066 failed: %s", exc)

            elif cmd == 28726:  # 0x7036 (cloud bind req)

                _LOGGER.info("oukitel: Station sent BLE 0x7036 (bind query), replying with 0x7066 bind success ack")

                diag_log("BLE_REPLYING_0x7066_BIND", cmd=cmd)

                reply = build_frame(_pid if _pid else 1002, 28774, ttlv_encode([(1, "num", 0), (2, "num", 0), (10, "num", 65534)]))

                diag_log("BLE_GATT_WRITE_0x7066", reason="0x7036-request", cmd=cmd, hex=reply.hex())

                try:

                    await client.write_gatt_char(target_char, reply, response=False)

                except Exception as exc:

                    _LOGGER.warning("oukitel: BLE write 0x7066 failed: %s", exc)

            elif cmd == CMD_PROGRESS:

                raw_code = -1

                if len(payload) >= 2:

                    raw_code = struct.unpack(">H", payload[:2])[0]



                status_code = raw_code

                error_code = 0

                try:

                    fields = ttlv_decode(payload)

                    if isinstance(fields, dict):

                        if 10 in fields:

                            status_code = fields[10]

                        if 11 in fields:

                            error_code = fields[11]

                except Exception:

                    pass



                state_names = {

                    16: "scanning router (0x0010)",

                    32: "connecting router (0x0020)",

                    48: "cloud authing (0x0030)",

                    49: "cloud authing (0x0031)",

                    64: "cloud login (0x0040)",

                    80: "cloud resting (0x0050)",

                    96: "cloud binding (0x0060)",

                    65534: "SUCCESS (0xFFFE)",

                    65535: "FAIL (0xFFFF)",

                }

                desc = state_names.get(status_code, f"code {status_code} (0x{status_code:04X})" if status_code >= 0 else "unknown")

                _LOGGER.info("oukitel: 0x7014 station progress: %s (error=%s)", desc, error_code)

                diag_log(

                    "BLE_STATION_PROGRESS",

                    code=status_code,

                    error=error_code,

                    desc=desc,

                    raw=payload.hex(),

                )



                if status_code in (65534, 2):

                    _LOGGER.info("oukitel: *** Station confirmed SUCCESS (%s) ***", desc)

                    diag_log("BLE_STATION_SUCCESS_CONFIRMED", code=status_code)

                    confirmed = True

                    await asyncio.sleep(2.0)

                    break

                elif status_code in (48, 49, 64, 80, 96):

                    confirmed = True

                    station_reached_cloud = True

                    _LOGGER.info("oukitel: Station at %s, sending proactive 0x7066 & 0x7014 acks over BLE", desc)

                    diag_log("BLE_SENDING_PROACTIVE_ACKS", code=status_code)

                    bind_ack = build_frame(_pid if _pid else 1003, 28774, b"")

                    prog_ack = build_frame(_pid if _pid else 1004, CMD_PROGRESS, ttlv_encode([(10, "num", 65534), (11, "num", 0)]))

                    diag_log(

                        "BLE_PROACTIVE_ACKS_BUILD",

                        bind_hex=bind_ack.hex(),

                        prog_hex=prog_ack.hex(),

                        code=status_code,

                    )

                    try:

                        await client.write_gatt_char(target_char, bind_ack, response=False)

                        diag_log("BLE_GATT_WRITE_0x7066", reason="proactive", hex=bind_ack.hex())

                        await asyncio.sleep(0.05)

                        await client.write_gatt_char(target_char, prog_ack, response=False)

                        diag_log("BLE_GATT_WRITE_0x7014", reason="proactive", hex=prog_ack.hex())

                    except Exception as exc:

                        _LOGGER.warning("oukitel: BLE write proactive acks failed: %s", exc)

                    # NOTE: Do NOT break here! Keep notifications alive so station can finish pairing!



        diag_log(

            "BLE_WAIT_END",

            confirmed=confirmed,

            reached_cloud=station_reached_cloud,

            elapsed=round(time.monotonic() - loop_start, 1),

            connected=bool(getattr(client, "is_connected", False)),

        )

        try:

            await client.stop_notify(target_char)

        except Exception:

            pass



        if confirmed:

            hass.async_create_background_task(

                _ble_keepalive_loop(hass, client, target_char),

                "oukitel_ble_keepalive",

            )

            return True, (

                f"Aprovisionamiento completado con Ã©xito: Red '{ssid}', Endpoint '{endpoint}'. "

                "La estaciÃ³n se conectarÃ¡ a la red en breve."

            )

        return False, (

            "Se enviÃ³ la trama de aprovisionamiento pero no se recibiÃ³ la confirmaciÃ³n 0x7011 a tiempo."

        )

    finally:

        if not confirmed:

            hass.data.get(DOMAIN, {}).pop("ble_client", None)

            try:

                await client.disconnect()

            except Exception:  # noqa: BLE001

                pass

        else:

            _LOGGER.info("oukitel: BLE provisioning confirmed, keeping BLE client permanently referenced in hass.data")

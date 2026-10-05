"""Oukitel DataUpdateCoordinator — supports LAN (push) and Cloud (poll) modes.

On startup the coordinator tries to locate the device on the local network.
If found and an authKey is available it runs in LAN mode: a persistent TCP
session pushes telemetry in real time and the update interval is used only
as a safety net to request a fresh read.  If LAN is unavailable it falls
back transparently to the existing cloud polling logic.
"""

from datetime import timedelta
import json
import logging
import time
import asyncio
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AcceleronixCloudClient
from .const import (
    DEFAULT_CONNECTION_MODE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_WAKE_INTERVAL,
    DOMAIN,
    MODE_AUTO,
    MODE_CLOUD,
    MODE_LAN,
)
from .local_scan import find_device_on_lan
from .local_session import LocalSession, LocalAuthError, LocalSessionError

_LOGGER = logging.getLogger(__name__)

_LAN_STALE_TIMEOUT = 150.0
_LAN_RECONNECT_DELAY = 10.0


def _unpack_port_data(target: dict[str, Any]) -> None:
    """Unpack individual port metrics from LAN tags (6, 7, 8, 9) or Cloud TSL (AC_Info, USB_Info, etc.)."""
    def _parse_dict(val):
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {}

    # 1. AC Info: 2=AC output power (W), 3=AC output voltage (V)
    ac_val = _parse_dict(target.get(6) or target.get("6") or target.get("AC_Info"))
    if ac_val:
        p = ac_val.get(2) if 2 in ac_val else ac_val.get("2")
        v = ac_val.get(3) if 3 in ac_val else ac_val.get("3")
        if p is not None:
            target["ac_output_power"] = p
        if v is not None:
            target["ac_output_voltage"] = v

    # 2. USB Info: 2=USB-A power (W), 3=USB-C QC power (W)
    usb_val = _parse_dict(target.get(7) or target.get("7") or target.get("USB_Info"))
    if usb_val:
        usb_a = usb_val.get(2) if 2 in usb_val else usb_val.get("2")
        usb_c = usb_val.get(3) if 3 in usb_val else usb_val.get("3")
        if usb_a is not None:
            target["usb_a_power"] = usb_a
        if usb_c is not None:
            target["usb_c_qc_power"] = usb_c

    # 3. Type-C Info: 2=Type-C 1 (W), 5=Type-C 2 (W), 6=Type-C 3 (W), 7=Type-C 4 (W)
    typec_val = _parse_dict(target.get(8) or target.get("8") or target.get("TypeC_Info"))
    if typec_val:
        c1 = typec_val.get(2) if 2 in typec_val else typec_val.get("2")
        c2 = typec_val.get(5) if 5 in typec_val else typec_val.get("5")
        c3 = typec_val.get(6) if 6 in typec_val else typec_val.get("6")
        c4 = typec_val.get(7) if 7 in typec_val else typec_val.get("7")
        if c1 is not None:
            target["typec1_power"] = c1
        if c2 is not None:
            target["typec2_power"] = c2
        if c3 is not None:
            target["typec3_power"] = c3
        if c4 is not None:
            target["typec4_power"] = c4

    # 4. DC Info: 2=DC Car output power (W), 3=voltage (V), 4=current (A)
    dc_val = _parse_dict(target.get(9) or target.get("9") or target.get("DC_Info"))
    if dc_val:
        dc_p = dc_val.get(2) if 2 in dc_val else dc_val.get("2")
        dc_v = dc_val.get(3) if 3 in dc_val else dc_val.get("3")
        dc_a = dc_val.get(4) if 4 in dc_val else dc_val.get("4")
        if dc_p is not None:
            target["dc_output_power"] = dc_p
        if dc_v is not None:
            target["dc_output_voltage"] = dc_v
        if dc_a is not None:
            target["dc_output_current"] = dc_a

    # Default all individual power sensors to 0 if not present yet (avoids Unknown states)
    for k in (
        "ac_output_power",
        "usb_a_power",
        "usb_c_qc_power",
        "typec1_power",
        "typec2_power",
        "typec3_power",
        "typec4_power",
        "dc_output_power",
    ):
        if k not in target or target[k] is None:
            target[k] = 0


class OukitelDataCoordinator(DataUpdateCoordinator):
    """Fetches Oukitel station data; prefers LAN push, falls back to cloud polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AcceleronixCloudClient,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        connection_mode: str = DEFAULT_CONNECTION_MODE,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self.connection_mode = connection_mode
        self.last_wake_time: float = 0.0
        self.lan_host: str | None = None

        self._lan_session: LocalSession | None = None
        self._lan_listen_task: asyncio.Task | None = None
        self._lan_state: dict[int, Any] = {}
        self._lan_last_report: float | None = None
        self._lan_connected_at: float | None = None
        self._lan_active = False

    # ------------------------------------------------------------------
    # LAN lifecycle
    # ------------------------------------------------------------------

    async def async_setup_lan(self) -> None:
        """Try to start LAN mode; silently skips if device not found on LAN."""
        if self.connection_mode == MODE_CLOUD:
            _LOGGER.warning("oukitel: Connection mode set to Cloud Only — skipping LAN setup")
            return

        if not self.client.device_key:
            await self.hass.async_add_executor_job(self.client.fetch_device_info)

        _LOGGER.warning("oukitel: Scanning LAN for device %s …", self.client.device_key)
        host = await find_device_on_lan(self.client.device_key or "")
        if not host:
            _LOGGER.warning("oukitel: Device not found on LAN — running in cloud mode")
            return

        self.lan_host = host
        auth_key = await self.hass.async_add_executor_job(self.client.fetch_auth_key)
        if not auth_key:
            _LOGGER.warning("oukitel: authKey unavailable — running in cloud mode")
            return

        _LOGGER.warning("oukitel: Device found at %s — starting LAN session", host)
        await self._start_lan_session(host, auth_key)

    async def _start_lan_session(self, host: str, auth_key: str) -> None:
        self._lan_session = LocalSession(
            host=host,
            auth_key_b64=auth_key,
            on_telemetry=self._on_lan_telemetry,
        )
        try:
            await self._lan_session.connect()
        except (LocalSessionError, LocalAuthError) as exc:
            _LOGGER.warning("oukitel: LAN session failed to start: %s — using cloud", exc)
            self._lan_session = None
            return

        self._lan_active = True
        self._lan_connected_at = time.monotonic()
        _LOGGER.warning("oukitel: LAN session established and active with %s!", host)
        self._lan_listen_task = asyncio.ensure_future(self._lan_read_loop(host, auth_key))

    async def _lan_read_loop(self, host: str, auth_key: str) -> None:
        while True:
            try:
                await self._lan_session.read_loop()
            except Exception as exc:
                _LOGGER.debug("oukitel: LAN read loop ended: %s", exc)

            if self._lan_session:
                await self._lan_session.close()
                self._lan_session = None

            _LOGGER.info("oukitel: LAN disconnected — reconnecting in %ss", _LAN_RECONNECT_DELAY)
            await asyncio.sleep(_LAN_RECONNECT_DELAY)

            # Re-scan: device IP may have changed
            host_new = await find_device_on_lan(self.client.device_key or "")
            target = host_new or host
            self._lan_session = LocalSession(
                host=target,
                auth_key_b64=auth_key,
                on_telemetry=self._on_lan_telemetry,
            )
            try:
                await self._lan_session.connect()
                self._lan_connected_at = time.monotonic()
            except (LocalSessionError, LocalAuthError) as exc:
                _LOGGER.warning("oukitel: LAN reconnect failed: %s", exc)
                self._lan_session = None
                self._lan_active = False
                return

    def _on_lan_telemetry(self, fields: dict[int, Any]) -> None:
        self._lan_last_report = time.monotonic()
        
        # Base LAN tag mapping to HA sensor keys
        tag_map = {
            1: "battery_percentage",
            2: "remain_time",
            3: "remain_charging_time",
            4: "total_input_power",
            5: "total_output_power",
            11: "ac_input",
            12: "dc_input",
            14: "temp",
            31: "AC_Version",
            33: "inverter_temp",
            34: "BMS_Version",
        }
        
        current_data = dict(self._lan_state or self.data or {})
        for tag, val in fields.items():
            if tag in tag_map:
                current_data[tag_map[tag]] = val
            if tag == 2:
                current_data["remaining_time"] = val
            current_data[str(tag)] = val
            if tag in (6, 7, 8, 9):
                current_data[tag] = val

        _unpack_port_data(current_data)

        self._lan_state = current_data
        self.hass.loop.call_soon_threadsafe(
            self.async_set_updated_data, dict(self._lan_state)
        )

    async def async_shutdown_lan(self) -> None:
        if self._lan_listen_task and not self._lan_listen_task.done():
            self._lan_listen_task.cancel()
            try:
                await self._lan_listen_task
            except asyncio.CancelledError:
                pass
        if self._lan_session:
            await self._lan_session.close()
            self._lan_session = None
        self._lan_active = False

    # ------------------------------------------------------------------
    # DataUpdateCoordinator
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        if self.connection_mode == MODE_CLOUD:
            return await self._update_cloud()
        if self._lan_active:
            return await self._update_lan()
        if self.connection_mode == MODE_LAN:
            raise UpdateFailed("LAN session not active and mode is set to LAN Only")
        return await self._update_cloud()

    async def _update_lan(self) -> dict:
        now = time.monotonic()
        stale = (
            self._lan_last_report is not None
            and (now - self._lan_last_report) > _LAN_STALE_TIMEOUT
        )
        if stale:
            if self.connection_mode == MODE_LAN:
                _LOGGER.warning("oukitel: LAN telemetry stale (LAN Only mode — keeping state)")
            else:
                _LOGGER.warning("oukitel: LAN telemetry stale — falling back to cloud")
                self._lan_active = False
                return await self._update_cloud()

        if self._lan_session:
            try:
                await self._lan_session.request_read()
            except Exception:
                pass

        if not self._lan_state:
            raise UpdateFailed("LAN session connected but no telemetry received yet")

        return dict(self._lan_state)

    async def _update_cloud(self) -> dict:
        now = time.time()
        if now - self.last_wake_time >= DEFAULT_WAKE_INTERVAL:
            await self.hass.async_add_executor_job(self.client.wake_device)
            self.last_wake_time = now

        data = await self.hass.async_add_executor_job(self.client.get_telemetry)
        if not data:
            await self.hass.async_add_executor_job(self.client.wake_device)
            self.last_wake_time = time.time()
            data = await self.hass.async_add_executor_job(self.client.get_telemetry)

        if not data:
            raise UpdateFailed("Failed to communicate with Oukitel Cloud")

        _unpack_port_data(data)

        return data

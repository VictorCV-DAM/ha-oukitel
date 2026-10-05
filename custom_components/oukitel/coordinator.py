"""Oukitel DataUpdateCoordinator — supports LAN (push) and Cloud (poll) modes.

On startup the coordinator tries to locate the device on the local network.
If found and an authKey is available it runs in LAN mode: a persistent TCP
session pushes telemetry in real time and the update interval is used only
as a safety net to request a fresh read.  If LAN is unavailable it falls
back transparently to the existing cloud polling logic.
"""

from datetime import timedelta
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
        
        current_data = dict(self.data or {})
        for tag, val in fields.items():
            if tag in tag_map:
                current_data[tag_map[tag]] = val
            if tag == 2:
                current_data["remaining_time"] = val
            current_data[str(tag)] = val
            
            # Struct sub-tags for individual ports & detailed measurements
            if tag == 6 and isinstance(val, dict):
                # AC Info: 2=AC output power (W), 3=AC output voltage (V)
                if 2 in val:
                    current_data["ac_output_power"] = val[2]
                if 3 in val:
                    current_data["ac_output_voltage"] = val[3]
            elif tag == 7 and isinstance(val, dict):
                # USB Info: 2=USB-A power (W), 3=USB-C QC power (W)
                if 2 in val:
                    current_data["usb_a_power"] = val[2]
                if 3 in val:
                    current_data["usb_c_qc_power"] = val[3]
            elif tag == 8 and isinstance(val, dict):
                # Type-C Info: 2=Type-C 1 (W), 5=Type-C 2 (W), 6=Type-C 3 (W), 7=Type-C 4 (W)
                if 2 in val:
                    current_data["typec1_power"] = val[2]
                if 5 in val:
                    current_data["typec2_power"] = val[5]
                if 6 in val:
                    current_data["typec3_power"] = val[6]
                if 7 in val:
                    current_data["typec4_power"] = val[7]
            elif tag == 9 and isinstance(val, dict):
                # DC Info: 2=DC Car output power (W), 3=voltage (V), 4=current (A)
                if 2 in val:
                    current_data["dc_output_power"] = val[2]
                if 3 in val:
                    current_data["dc_output_voltage"] = val[3]
                if 4 in val:
                    current_data["dc_output_current"] = val[4]

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

        return data

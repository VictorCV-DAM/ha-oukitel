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
from .const import DEFAULT_POLL_INTERVAL, DEFAULT_WAKE_INTERVAL, DOMAIN
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
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self.last_wake_time: float = 0.0

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
        if not self.client.device_key:
            await self.hass.async_add_executor_job(self.client.fetch_device_info)

        _LOGGER.debug("Scanning LAN for device %s …", self.client.device_key)
        host = await find_device_on_lan(self.client.device_key or "")
        if not host:
            _LOGGER.info("Device not found on LAN — running in cloud mode")
            return

        auth_key = await self.hass.async_add_executor_job(self.client.fetch_auth_key)
        if not auth_key:
            _LOGGER.info("authKey unavailable — running in cloud mode")
            return

        _LOGGER.info("Device found at %s — starting LAN session", host)
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
            _LOGGER.warning("LAN session failed to start: %s — using cloud", exc)
            self._lan_session = None
            return

        self._lan_active = True
        self._lan_connected_at = time.monotonic()
        self._lan_listen_task = asyncio.ensure_future(self._lan_read_loop(host, auth_key))

    async def _lan_read_loop(self, host: str, auth_key: str) -> None:
        while True:
            try:
                await self._lan_session.read_loop()
            except Exception as exc:
                _LOGGER.debug("LAN read loop ended: %s", exc)

            if self._lan_session:
                await self._lan_session.close()
                self._lan_session = None

            _LOGGER.info("LAN disconnected — reconnecting in %ss", _LAN_RECONNECT_DELAY)
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
                _LOGGER.warning("LAN reconnect failed: %s", exc)
                self._lan_session = None
                self._lan_active = False
                return

    def _on_lan_telemetry(self, fields: dict[int, Any]) -> None:
        self._lan_last_report = time.monotonic()
        self._lan_state.update(fields)
        # Convert int-keyed LAN tags to string resourceCodes where possible
        # and schedule an HA state push
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
        if self._lan_active:
            return await self._update_lan()
        return await self._update_cloud()

    async def _update_lan(self) -> dict:
        now = time.monotonic()
        stale = (
            self._lan_last_report is not None
            and (now - self._lan_last_report) > _LAN_STALE_TIMEOUT
        )
        if stale:
            _LOGGER.warning("LAN telemetry stale — falling back to cloud")
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

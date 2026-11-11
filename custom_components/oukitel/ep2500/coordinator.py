"""DataUpdateCoordinator for Oukitel EP2500."""

from datetime import timedelta
import logging
from typing import Any, Optional
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from ..const import DOMAIN
from .client import OukitelEP2500LocalClient
from .const import DEFAULT_EP2500_POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)


class OukitelEP2500Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator managing telemetry polling and state dispatch for Oukitel EP2500."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: OukitelEP2500LocalClient,
        poll_interval: int = DEFAULT_EP2500_POLL_INTERVAL,
    ) -> None:
        """Initialize EP2500 coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"Oukitel EP2500 ({client.host})",
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self.device_id = client.device_id
        self.host = client.host

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest telemetry frames from EP2500 local socket."""
        try:
            data = await self.client.async_fetch_status()
            if not data and not self.client.is_connected:
                err_msg = self.client.last_error or "Offline or unreachable"
                raise UpdateFailed(f"Oukitel EP2500 at {self.host} connection failed: {err_msg}")
            return data
        except Exception as err:
            if isinstance(err, UpdateFailed):
                raise
            raise UpdateFailed(f"Error communicating with EP2500 at {self.host}: {err}") from err

    async def async_set_dp(self, dp_id: str, value: Any) -> bool:
        """Dispatch a set datapoint command and refresh listeners."""
        success = await self.client.async_set_dp(dp_id, value)
        if success:
            # Update local coordinator data cache optimistically
            if self.data is not None:
                self.data[str(dp_id)] = value
            self.async_update_listeners()
        return success

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant DeviceInfo for Oukitel EP2500."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"ep2500_{self.device_id}")},
            name=f"Oukitel EP2500 ({self.device_id[-4:]})",
            manufacturer="Oukitel",
            model="EP2500 Balcony Energy Storage",
            sw_version="1.02 / 1.17",
            configuration_url=f"http://{self.host}",
        )

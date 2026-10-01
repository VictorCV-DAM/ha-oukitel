"""Oukitel DataUpdateCoordinator."""

from datetime import datetime, timedelta
import logging
import time
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AcceleronixCloudClient
from .const import DEFAULT_POLL_INTERVAL, DEFAULT_WAKE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class OukitelDataCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Oukitel data from the cloud."""

    def __init__(self, hass: HomeAssistant, client: AcceleronixCloudClient, poll_interval: int = DEFAULT_POLL_INTERVAL):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self.last_wake_time = 0

    async def _async_update_data(self):
        """Fetch data from Cloud API and maintain device awake."""
        now = time.time()
        # Keep alive every 25 seconds
        if now - self.last_wake_time >= DEFAULT_WAKE_INTERVAL:
            await self.hass.async_add_executor_job(self.client.wake_device)
            self.last_wake_time = now

        data = await self.hass.async_add_executor_job(self.client.get_telemetry)
        if not data:
            # If empty, try one wake and retry
            await self.hass.async_add_executor_job(self.client.wake_device)
            self.last_wake_time = time.time()
            data = await self.hass.async_add_executor_job(self.client.get_telemetry)

        if not data:
            raise UpdateFailed("Failed to communicate with Oukitel Cloud")

        return data

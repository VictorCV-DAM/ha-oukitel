"""Local asynchronous client for Oukitel EP2500 using Tuya 3.5 protocol."""

import asyncio
import logging
from typing import Any, Optional
import tinytuya
from homeassistant.core import HomeAssistant

from .const import (
    DEFAULT_EP2500_PORT,
    TUYA_PROTOCOL_VERSION,
)

_LOGGER = logging.getLogger(__name__)

# Constants for plausibility & 16-bit uint conversion
UINT16_THRESHOLD = 32768
NEGATIVE_ALLOWED_DPS = {"128", "137"}
PLAUSIBLE_MAX: dict[str, int] = {
    "143": 5000,  # PV total power max
    "147": 1200,  # PV1 max 1000W
    "151": 1200,  # PV3 max 1000W
    "164": 1200,  # PV2 max 1000W
    "180": 1200,  # PV4 max 1000W
    "155": 3000,  # AC output max
    "128": 3000,  # Battery power max
    "137": 3000,  # Grid power max
    "141": 3000,  # Off-grid load max
}


class OukitelEP2500LocalClient:
    """Asynchronous client interfacing with Oukitel EP2500 locally."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        device_id: str,
        local_key: str,
        port: int = DEFAULT_EP2500_PORT,
    ) -> None:
        """Initialize EP2500 local client."""
        self._hass = hass
        self.host = host
        self.device_id = device_id
        self.local_key = local_key
        self.port = port

        self._device: Optional[tinytuya.OutletDevice] = None
        self._dps_cache: dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._is_connected = False
        self._last_error: Optional[str] = None

    def _init_device(self) -> tinytuya.OutletDevice:
        """Create and configure synchronous tinytuya device."""
        dev = tinytuya.OutletDevice(
            dev_id=self.device_id,
            address=self.host,
            local_key=self.local_key,
            port=self.port,
        )
        dev.set_version(TUYA_PROTOCOL_VERSION)
        dev.set_socketTimeout(8)
        dev.set_socketRetryLimit(2)
        return dev

    async def async_connect(self) -> bool:
        """Establish local session and obtain initial status."""
        async with self._lock:
            return await self._hass.async_add_executor_job(self._sync_connect)

    def _sync_connect(self) -> bool:
        """Synchronous connect implementation."""
        try:
            if not self._device:
                self._device = self._init_device()

            status = self._device.status()
            if isinstance(status, dict) and "dps" in status:
                self._update_cache(status["dps"])
                self._is_connected = True
                self._last_error = None
                _LOGGER.debug(
                    "oukitel_ep2500: Connected successfully to %s. Seeded %d datapoints.",
                    self.host,
                    len(status["dps"]),
                )
                return True

            err_msg = status.get("Error", "Unexpected payload from device") if isinstance(status, dict) else str(status)
            self._last_error = f"Tuya error: {err_msg}"
            _LOGGER.warning("oukitel_ep2500: Connection attempt failed for %s: %s", self.host, self._last_error)
            self._is_connected = False
            return False

        except Exception as err:
            self._last_error = str(err)
            _LOGGER.warning("oukitel_ep2500: Connection exception for %s: %s", self.host, err)
            self._is_connected = False
            return False

    async def async_fetch_status(self) -> dict[str, Any]:
        """Fetch updated status or delta frames from the device."""
        async with self._lock:
            return await self._hass.async_add_executor_job(self._sync_fetch_status)

    def _sync_fetch_status(self) -> dict[str, Any]:
        """Synchronous fetch status implementation with local cache retention."""
        try:
            if not self._device or not self._is_connected:
                if not self._sync_connect():
                    return dict(self._dps_cache)

            status = self._device.status()
            if isinstance(status, dict) and "dps" in status:
                self._update_cache(status["dps"])
                self._is_connected = True
                self._last_error = None
            elif isinstance(status, dict) and "Error" in status:
                _LOGGER.debug("oukitel_ep2500: Poll returned notice from %s: %s", self.host, status["Error"])
                # Try heartbeat to keep socket fresh
                try:
                    self._device.heartbeat()
                except Exception:
                    self._is_connected = False

        except Exception as err:
            _LOGGER.debug("oukitel_ep2500: Poll failed for %s: %s", self.host, err)
            self._is_connected = False
            self._last_error = str(err)

        return dict(self._dps_cache)

    def _update_cache(self, raw_dps: dict[str, Any]) -> None:
        """Merge delta frames into cache with plausibility corrections."""
        for dp_id, raw_val in raw_dps.items():
            parsed_val = raw_val

            # Plausibility filter for 16-bit uint overflow
            if isinstance(raw_val, int):
                if raw_val >= UINT16_THRESHOLD and dp_id in NEGATIVE_ALLOWED_DPS:
                    # Convert to signed int
                    parsed_val = raw_val - 65536
                elif raw_val >= UINT16_THRESHOLD:
                    # Unsigned overflow on sensor that should never be negative
                    continue

                if dp_id in PLAUSIBLE_MAX and parsed_val > PLAUSIBLE_MAX[dp_id]:
                    # Exclude impossible spike/noise
                    continue

            self._dps_cache[str(dp_id)] = parsed_val

    async def async_set_dp(self, dp_id: str, value: Any) -> bool:
        """Send a set datapoint command asynchronously."""
        async with self._lock:
            return await self._hass.async_add_executor_job(self._sync_set_dp, dp_id, value)

    def _sync_set_dp(self, dp_id: str, value: Any) -> bool:
        """Synchronous write datapoint implementation."""
        try:
            if not self._device:
                self._device = self._init_device()

            payload = {str(dp_id): value}
            res = self._device.set_value(dp_id, value)
            _LOGGER.debug("oukitel_ep2500: Sent DP %s = %s, response: %s", dp_id, value, res)

            # Optimistic local cache update
            self._dps_cache[str(dp_id)] = value
            return True

        except Exception as err:
            _LOGGER.error("oukitel_ep2500: Failed to write DP %s = %s: %s", dp_id, value, err)
            return False

    @property
    def is_connected(self) -> bool:
        """Return connection status."""
        return self._is_connected

    @property
    def last_error(self) -> Optional[str]:
        """Return last recorded error message."""
        return self._last_error

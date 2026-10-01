"""Number platform for Oukitel Power Station settings."""

import asyncio
import logging
import time
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OukitelDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Oukitel number entities based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OukitelDataCoordinator = data["coordinator"]
    client = data["client"]

    entities = [
        OukitelChargingLimitNumber(coordinator, client)
    ]
    async_add_entities(entities)


class OukitelChargingLimitNumber(CoordinatorEntity, NumberEntity):
    """Control for AC Upper Limit Charging Power slider (3% to 100%)."""

    def __init__(self, coordinator: OukitelDataCoordinator, client):
        super().__init__(coordinator)
        self.client = client
        self._key = "ac_charging_limit"
        self._attr_name = f"{client.device_name} AC Charging Limit"
        self._attr_unique_id = f"oukitel_{client.device_key}_{self._key}"
        self._attr_icon = "mdi:gauge"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_native_min_value = 3
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER
        self._attr_entity_category = EntityCategory.CONFIG

        self._target_state = None
        self._target_timestamp = 0

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.client.device_key)},
            name=self.client.device_name,
            manufacturer="OUKITEL",
            model="P2001 Plus",
            sw_version="Cloud API 1.0.0",
        )

    @property
    def native_value(self) -> float:
        """Return the current configured charge limit percentage."""
        now = time.time()
        if self._target_state is not None and (now - self._target_timestamp < 15):
            if self.coordinator.data and self._key in self.coordinator.data:
                if int(self.coordinator.data[self._key]) == int(self._target_state):
                    self._target_state = None
                    return float(self.coordinator.data[self._key])
            return float(self._target_state)

        self._target_state = None
        if not self.coordinator.data:
            return 100.0
        val = self.coordinator.data.get(self._key, 100)
        try:
            return float(val)
        except (ValueError, TypeError):
            return 100.0

    async def async_set_native_value(self, value: float) -> None:
        """Set new AC charging limit."""
        target_val = int(round(value))
        target_val = max(3, min(100, target_val))

        self._target_state = target_val
        self._target_timestamp = time.time()
        if self.coordinator.data:
            self.coordinator.data[self._key] = target_val
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: target_val}]
        )
        if not success:
            _LOGGER.error("Failed to set %s to %s", self._key, target_val)
            self._target_state = None
            self.async_write_ha_state()
            return

        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

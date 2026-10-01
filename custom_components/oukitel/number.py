"""Number platform for Oukitel Power Station settings."""

import asyncio
import logging
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

        # Solid internal state cache
        initial_val = 100.0
        if coordinator.data and self._key in coordinator.data:
            try:
                initial_val = float(coordinator.data[self._key])
            except (ValueError, TypeError):
                initial_val = 100.0
        self._attr_native_value = initial_val

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.client.device_key)},
            name=self.client.device_name,
            manufacturer="OUKITEL",
            model="P2001 Plus",
            sw_version="Cloud API 1.0.0",
        )

    def _handle_coordinator_update(self) -> None:
        """Update from coordinator when new data arrives."""
        if self.coordinator.data and self._key in self.coordinator.data:
            try:
                self._attr_native_value = float(self.coordinator.data[self._key])
            except (ValueError, TypeError):
                pass
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Set new AC charging limit."""
        target_val = int(round(value))
        target_val = max(3, min(100, target_val))

        # 1. Immediately pin local value in UI
        self._attr_native_value = float(target_val)
        if self.coordinator.data:
            self.coordinator.data[self._key] = target_val
        self.async_write_ha_state()

        # 2. Send command to cloud
        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: target_val}]
        )
        if not success:
            _LOGGER.error("Failed to set %s to %s", self._key, target_val)
            if self.coordinator.data and self._key in self.coordinator.data:
                self._attr_native_value = float(self.coordinator.data[self._key])
            self.async_write_ha_state()

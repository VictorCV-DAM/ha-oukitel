"""Binary sensor platform for Oukitel Power Station."""

import logging
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OukitelDataCoordinator
from .sensor import _build_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Oukitel binary sensor entities based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OukitelDataCoordinator = data["coordinator"]
    client = data["client"]

    async_add_entities([OukitelOnBatteryBinarySensor(coordinator, client)])


class OukitelOnBatteryBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating if the power station is currently running on battery (mains/solar input absent)."""

    def __init__(self, coordinator: OukitelDataCoordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self._attr_name = f"{client.device_name} Battery-powered (Inferred)"
        self._attr_unique_id = f"oukitel_{client.device_key}_on_battery"

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(self.coordinator, self.client)

    @property
    def icon(self) -> str:
        if self.is_on:
            return "mdi:power-plug-off"
        return "mdi:power-plug"

    @property
    def is_on(self) -> bool | None:
        """Return True if running on battery (inputs absent or <= 5W), False if connected to grid/solar power."""
        if not self.coordinator.data:
            return None

        total_in = self.coordinator.data.get("total_input_power")
        ac_in = self.coordinator.data.get("ac_input")
        dc_in = self.coordinator.data.get("dc_input")

        if total_in is None and ac_in is None and dc_in is None:
            return None

        tin = float(total_in or 0)
        ain = float(ac_in or 0)
        din = float(dc_in or 0)

        # On battery when no significant charging power is entering the station
        return tin <= 5.0 and ain <= 5.0 and din <= 5.0

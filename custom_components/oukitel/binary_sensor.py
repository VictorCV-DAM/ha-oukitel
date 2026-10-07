"""Binary sensor platform for Oukitel Power Station."""

import logging
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
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

    async_add_entities([
        OukitelOnBatteryBinarySensor(coordinator, client),
        OukitelConnectionBinarySensor(coordinator, client),
    ])


class OukitelOnBatteryBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating if the power station is currently running on battery (mains/solar input absent)."""

    def __init__(self, coordinator: OukitelDataCoordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self._attr_name = f"{client.device_name} Battery-powered (Inferred)"
        self._attr_unique_id = f"oukitel_{client.device_key}_on_battery"
        self._last_state: bool = False

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
        """Return True if running on battery (actively discharging or inputs absent), False if net charging."""
        if self.coordinator.is_paused:
            return False
        if not self.coordinator.data:
            return None

        total_in = float(self.coordinator.data.get("total_input_power") or 0)
        total_out = float(self.coordinator.data.get("total_output_power") or 0)
        ac_in = float(self.coordinator.data.get("ac_input") or 0)
        dc_in = float(self.coordinator.data.get("dc_input") or 0)
        ac_out = float(self.coordinator.data.get("ac_output_power") or 0)
        dc_out = float(self.coordinator.data.get("dc_output_power") or 0)

        real_in = max(total_in, ac_in + dc_in)
        real_out = max(total_out, ac_out + dc_out)

        # 1. Inputs absent (<= 5W): running on battery
        if real_in <= 5.0:
            self._last_state = True
            return True

        # 2. Inputs present: apply hysteresis around net balance to prevent flutter
        delta = real_out - real_in
        if self._last_state:
            # Currently on battery -> only switch to charging if inputs clearly exceed load (>10W)
            if delta < -10.0:
                self._last_state = False
        else:
            # Currently on mains/charging -> only switch to battery if load clearly exceeds inputs (>15W)
            if delta > 15.0:
                self._last_state = True

        return self._last_state


class OukitelConnectionBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating if the power station is currently online/connected."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: OukitelDataCoordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self._attr_name = f"{client.device_name} Device Online"
        self._attr_unique_id = f"oukitel_{client.device_key}_online"

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(self.coordinator, self.client)

    @property
    def is_on(self) -> bool:
        """Return True if device is online and communication is active."""
        if self.coordinator.is_paused:
            return False
        if self.coordinator.connection_mode != "cloud" and self.coordinator._lan_active:
            return True
        if self.coordinator.data and "online" in self.coordinator.data:
            return bool(self.coordinator.data["online"])
        return bool(getattr(self.client, "is_online", True))

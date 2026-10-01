"""Switch platform for Oukitel Power Station."""

import asyncio
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OukitelDataCoordinator

_LOGGER = logging.getLogger(__name__)

SWITCH_TYPES = [
    ("ac_switch", "AC Output", "mdi:power-socket-eu"),
    ("dc_switch", "DC 12V Output", "mdi:car-electric"),
    ("usb_switch", "USB Output", "mdi:usb-port"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Oukitel switch entities based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OukitelDataCoordinator = data["coordinator"]
    client = data["client"]

    entities = [
        OukitelSwitch(coordinator, client, key, name, icon)
        for key, name, icon in SWITCH_TYPES
    ]
    async_add_entities(entities)


class OukitelSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of an Oukitel switch with solid state retention."""

    def __init__(self, coordinator: OukitelDataCoordinator, client, key, name, icon):
        super().__init__(coordinator)
        self.client = client
        self._key = key
        self._attr_name = f"{client.device_name} {name}"
        self._attr_unique_id = f"oukitel_{client.device_key}_{key}"
        self._attr_icon = icon

        # Local state overrides coordinator while hardware/cloud syncs
        self._state_override = None

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
    def is_on(self) -> bool:
        """Return the current state of the switch."""
        if self._state_override is not None:
            # Check if coordinator telemetry has now matched our override
            if self.coordinator.data and self._key in self.coordinator.data:
                telemetry_state = bool(self.coordinator.data[self._key])
                if telemetry_state == self._state_override:
                    # Cloud has finally confirmed our state change! Release override.
                    self._state_override = None
                    return telemetry_state
            # Still waiting for cloud to catch up; keep the user's commanded state
            return self._state_override

        if not self.coordinator.data:
            return False
        return bool(self.coordinator.data.get(self._key, False))

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        # 1. Immediately force local state in Home Assistant
        self._state_override = True
        if self.coordinator.data:
            self.coordinator.data[self._key] = True
        self.async_write_ha_state()

        # 2. Fire hardware command to cloud API
        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: True}]
        )
        if not success:
            _LOGGER.error("Failed to turn on %s", self._key)
            self._state_override = None
            if self.coordinator.data:
                self.coordinator.data[self._key] = False
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        # 1. Immediately force local state in Home Assistant
        self._state_override = False
        if self.coordinator.data:
            self.coordinator.data[self._key] = False
        self.async_write_ha_state()

        # 2. Fire hardware command to cloud API
        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: False}]
        )
        if not success:
            _LOGGER.error("Failed to turn off %s", self._key)
            self._state_override = None
            if self.coordinator.data:
                self.coordinator.data[self._key] = True
            self.async_write_ha_state()

"""Switch platform for Oukitel Power Station."""

import asyncio
import logging
import time
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
    """Representation of an Oukitel switch."""

    def __init__(self, coordinator: OukitelDataCoordinator, client, key, name, icon):
        super().__init__(coordinator)
        self.client = client
        self._key = key
        self._attr_name = f"{client.device_name} {name}"
        self._attr_unique_id = f"oukitel_{client.device_key}_{key}"
        self._attr_icon = icon

        # Optimistic local state and timestamp to prevent immediate rollback
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
    def is_on(self) -> bool:
        """Return the current state of the switch."""
        now = time.time()
        # Hold optimistic state for up to 15 seconds while cloud telemetry propagates
        if self._target_state is not None and (now - self._target_timestamp < 15):
            if self.coordinator.data and self._key in self.coordinator.data:
                # If telemetry caught up with our target state, release lock early
                if bool(self.coordinator.data[self._key]) == self._target_state:
                    self._target_state = None
                    return bool(self.coordinator.data[self._key])
            return self._target_state

        # Release optimistic lock if expired
        self._target_state = None
        if not self.coordinator.data:
            return False
        return bool(self.coordinator.data.get(self._key, False))

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        # Set optimistic state immediately
        self._target_state = True
        self._target_timestamp = time.time()
        if self.coordinator.data:
            self.coordinator.data[self._key] = True
        self.async_write_ha_state()

        # Send hardware command
        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: True}]
        )
        if not success:
            _LOGGER.error("Failed to turn on %s", self._key)
            self._target_state = None
            if self.coordinator.data:
                self.coordinator.data[self._key] = False
            self.async_write_ha_state()
            return

        # Wait 3 seconds for physical hardware and cloud to acknowledge, then refresh
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        # Set optimistic state immediately
        self._target_state = False
        self._target_timestamp = time.time()
        if self.coordinator.data:
            self.coordinator.data[self._key] = False
        self.async_write_ha_state()

        # Send hardware command
        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: False}]
        )
        if not success:
            _LOGGER.error("Failed to turn off %s", self._key)
            self._target_state = None
            if self.coordinator.data:
                self.coordinator.data[self._key] = True
            self.async_write_ha_state()
            return

        # Wait 3 seconds for physical hardware and cloud to acknowledge, then refresh
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()

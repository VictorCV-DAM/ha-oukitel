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
    """Representation of an Oukitel switch with temporal latch lock."""

    def __init__(self, coordinator: OukitelDataCoordinator, client, key, name, icon):
        super().__init__(coordinator)
        self.client = client
        self._key = key
        self._attr_name = f"{client.device_name} {name}"
        self._attr_unique_id = f"oukitel_{client.device_key}_{key}"
        self._attr_icon = icon

        # Local state cache
        initial_val = False
        if coordinator.data and key in coordinator.data:
            initial_val = bool(coordinator.data[key])
        self._attr_is_on = initial_val

        # Temporal latch lock
        self._user_locked_state = None
        self._user_locked_until = 0

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
        """Handle updated data from the coordinator."""
        now = time.time()
        # If user recently flipped the switch, ignore stale telemetry for 15s unless matched
        if self._user_locked_state is not None:
            if now < self._user_locked_until:
                if self.coordinator.data and self._key in self.coordinator.data:
                    telemetry_val = bool(self.coordinator.data[self._key])
                    if telemetry_val == self._user_locked_state:
                        # Cloud caught up with our commanded state, release lock early
                        self._user_locked_state = None
                # Maintain commanded state without rollback
                return
            else:
                self._user_locked_state = None

        if self.coordinator.data and self._key in self.coordinator.data:
            self._attr_is_on = bool(self.coordinator.data[self._key])
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        # 1. Lock switch ON for 15s to guarantee no bounce
        self._user_locked_state = True
        self._user_locked_until = time.time() + 15
        self._attr_is_on = True
        if self.coordinator.data:
            self.coordinator.data[self._key] = True
        self.async_write_ha_state()

        # 2. Fire hardware command to cloud API
        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: True}]
        )
        if not success:
            _LOGGER.error("Failed to turn on %s", self._key)
            self._user_locked_state = None
            if self.coordinator.data and self._key in self.coordinator.data:
                self._attr_is_on = bool(self.coordinator.data[self._key])
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        # 1. Lock switch OFF for 15s to guarantee no bounce
        self._user_locked_state = False
        self._user_locked_until = time.time() + 15
        self._attr_is_on = False
        if self.coordinator.data:
            self.coordinator.data[self._key] = False
        self.async_write_ha_state()

        # 2. Fire hardware command to cloud API
        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: False}]
        )
        if not success:
            _LOGGER.error("Failed to turn off %s", self._key)
            self._user_locked_state = None
            if self.coordinator.data and self._key in self.coordinator.data:
                self._attr_is_on = bool(self.coordinator.data[self._key])
            self.async_write_ha_state()

"""Switch platform for Oukitel Power Station."""

import asyncio
import logging
import time
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OukitelDataCoordinator
from .sensor import _build_device_info

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

    entities: list[SwitchEntity] = [
        OukitelSwitch(coordinator, client, key, name, icon)
        for key, name, icon in SWITCH_TYPES
    ]
    entities.append(OukitelPauseSwitch(coordinator, client))
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
        self._action_lock = asyncio.Lock()

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(self.coordinator, self.client)

    @property
    def available(self) -> bool:
        """Return True if switch is available; disabled and greyed out when paused."""
        if self.coordinator.is_paused:
            return False
        return super().available

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._action_lock.locked():
            return
        if self.coordinator.data and self._key in self.coordinator.data:
            self._attr_is_on = bool(self.coordinator.data[self._key])
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on with reentrancy lock and optimistic hold."""
        async with self._action_lock:
            # 1. Update UI and coordinator cache immediately with active override
            self._attr_is_on = True
            self.coordinator.async_set_user_override(self._key, True, ttl=60.0, min_hold=5.0)
            self.async_write_ha_state()

            # 2. Fire hardware command to cloud API
            success = await self.hass.async_add_executor_job(
                self.client.control_device, [{self._key: True}]
            )
            if not success:
                _LOGGER.error("oukitel: Failed to turn on %s", self._key)
                self.coordinator.async_clear_user_override(self._key)
                if self.coordinator.data and self._key in self.coordinator.data:
                    self._attr_is_on = bool(self.coordinator.data[self._key])
                self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off with reentrancy lock and optimistic hold."""
        async with self._action_lock:
            # 1. Update UI and coordinator cache immediately with active override
            self._attr_is_on = False
            self.coordinator.async_set_user_override(self._key, False, ttl=60.0, min_hold=5.0)
            self.async_write_ha_state()

            # 2. Fire hardware command to cloud API
            success = await self.hass.async_add_executor_job(
                self.client.control_device, [{self._key: False}]
            )
            if not success:
                _LOGGER.error("oukitel: Failed to turn off %s", self._key)
                self.coordinator.async_clear_user_override(self._key)
                if self.coordinator.data and self._key in self.coordinator.data:
                    self._attr_is_on = bool(self.coordinator.data[self._key])
                self.async_write_ha_state()


class OukitelPauseSwitch(CoordinatorEntity, SwitchEntity, RestoreEntity):
    """Switch to pause/resume integration requests, disconnect LAN and stop wake-up calls."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: OukitelDataCoordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self._attr_name = f"{client.device_name} Pause Integration"
        self._attr_unique_id = f"oukitel_{client.device_key}_pause_integration"
        self._attr_icon = "mdi:pause-circle"

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(self.coordinator, self.client)

    @property
    def available(self) -> bool:
        """Always available so user can toggle pause state."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True if integration is currently paused."""
        return self.coordinator.is_paused

    @property
    def icon(self) -> str:
        """Dynamic icon."""
        return "mdi:pause-circle" if self.coordinator.is_paused else "mdi:play-circle-outline"

    async def async_added_to_hass(self) -> None:
        """Restore previous state on reload/restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state == "on":
            _LOGGER.info("oukitel: Restoring paused integration state from previous session")
            await self.coordinator.async_set_paused(True)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on pause (pauses polling, disconnects LAN, stops wake-up calls)."""
        await self.coordinator.async_set_paused(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off pause (resumes normal communication)."""
        await self.coordinator.async_set_paused(False)
        self.async_write_ha_state()

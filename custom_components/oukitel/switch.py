"""Switch platform for Oukitel Power Station."""

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
    """Representation of an Oukitel switch."""

    def __init__(self, coordinator: OukitelDataCoordinator, client, key, name, icon):
        super().__init__(coordinator)
        self.client = client
        self._key = key
        self._attr_name = f"{client.device_name} {name}"
        self._attr_unique_id = f"oukitel_{client.device_key}_{key}"
        self._attr_icon = icon

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
        if not self.coordinator.data:
            return False
        return bool(self.coordinator.data.get(self._key, False))

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: True}]
        )
        if success:
            if self.coordinator.data:
                self.coordinator.data[self._key] = True
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: False}]
        )
        if success:
            if self.coordinator.data:
                self.coordinator.data[self._key] = False
            self.async_write_ha_state()
            await self.coordinator.async_request_refresh()

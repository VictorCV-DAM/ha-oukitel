"""Button platform for Oukitel Power Station."""

import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTITY_DESCRIPTIONS, get_entity_description
from .coordinator import OukitelDataCoordinator
from .sensor import _build_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Oukitel button entities based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OukitelDataCoordinator = data["coordinator"]
    client = data["client"]

    async_add_entities([OukitelReloadButton(coordinator, client, entry.entry_id)])


class OukitelReloadButton(CoordinatorEntity, ButtonEntity):
    """Button entity that triggers a complete reload of the Oukitel integration entry."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:reload"

    def __init__(self, coordinator: OukitelDataCoordinator, client, entry_id: str) -> None:
        super().__init__(coordinator)
        self.client = client
        self._entry_id = entry_id
        self._attr_name = f"{client.device_name} Reload"
        self._attr_unique_id = f"oukitel_{client.device_key}_reload"

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(self.coordinator, self.client)

    @property
    def extra_state_attributes(self) -> dict:
        return {"description": get_entity_description("reload", self.hass)}

    @property
    def available(self) -> bool:
        """Always available as recovery action."""
        return True

    async def async_press(self) -> None:
        """Reload the config entry."""
        _LOGGER.info("oukitel: Reload button pressed — reloading entry %s", self._entry_id)
        self.hass.async_create_task(self.hass.config_entries.async_reload(self._entry_id))

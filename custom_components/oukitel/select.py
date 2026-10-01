"""Select platform for Oukitel Power Station settings."""

import asyncio
import logging
import time
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OukitelDataCoordinator

_LOGGER = logging.getLogger(__name__)

# Frequency Mapping: Cloud val 0 -> 50Hz, 1 -> 60Hz
FREQ_MAP_TO_NAME = {"0": "50Hz", 0: "50Hz", "1": "60Hz", 1: "60Hz"}
FREQ_MAP_TO_VAL = {"50Hz": 0, "60Hz": 1}

# Voltage Mapping: Cloud string '200'..'240'
VOLTAGE_OPTIONS = ["200V", "208V", "220V", "230V", "240V"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Oukitel select entities based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OukitelDataCoordinator = data["coordinator"]
    client = data["client"]

    entities = [
        OukitelFrequencySelect(coordinator, client),
        OukitelVoltageSelect(coordinator, client),
    ]
    async_add_entities(entities)


class OukitelFrequencySelect(CoordinatorEntity, SelectEntity):
    """Output Frequency Setting (50Hz / 60Hz)."""

    def __init__(self, coordinator: OukitelDataCoordinator, client):
        super().__init__(coordinator)
        self.client = client
        self._key = "Frequency_Switchover"
        self._attr_name = f"{client.device_name} Output Frequency"
        self._attr_unique_id = f"oukitel_{client.device_key}_{self._key}"
        self._attr_icon = "mdi:sine-wave"
        self._attr_options = ["50Hz", "60Hz"]
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
    def current_option(self) -> str:
        now = time.time()
        if self._target_state is not None and (now - self._target_timestamp < 15):
            return self._target_state

        if not self.coordinator.data:
            return "50Hz"
        raw_val = self.coordinator.data.get(self._key, 0)
        return FREQ_MAP_TO_NAME.get(str(raw_val), "50Hz")

    async def async_select_option(self, option: str) -> None:
        """Change output frequency."""
        if option not in self._attr_options:
            return

        cloud_val = FREQ_MAP_TO_VAL[option]
        self._target_state = option
        self._target_timestamp = time.time()
        if self.coordinator.data:
            self.coordinator.data[self._key] = cloud_val
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: cloud_val}]
        )
        if not success:
            _LOGGER.error("Failed to set output frequency to %s", option)
            self._target_state = None
            self.async_write_ha_state()
            return

        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()


class OukitelVoltageSelect(CoordinatorEntity, SelectEntity):
    """Output Voltage Setting (200V, 208V, 220V, 230V, 240V)."""

    def __init__(self, coordinator: OukitelDataCoordinator, client):
        super().__init__(coordinator)
        self.client = client
        self._key = "ACvoltage_Switchover"
        self._attr_name = f"{client.device_name} Output Voltage"
        self._attr_unique_id = f"oukitel_{client.device_key}_{self._key}"
        self._attr_icon = "mdi:lightning-bolt-circle"
        self._attr_options = VOLTAGE_OPTIONS
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
    def current_option(self) -> str:
        now = time.time()
        if self._target_state is not None and (now - self._target_timestamp < 15):
            return self._target_state

        if not self.coordinator.data:
            return "230V"
        raw_val = str(self.coordinator.data.get(self._key, 230)).replace("V", "").strip()
        formatted = f"{raw_val}V"
        return formatted if formatted in VOLTAGE_OPTIONS else "230V"

    async def async_select_option(self, option: str) -> None:
        """Change output voltage."""
        if option not in self._attr_options:
            return

        clean_num = int(option.replace("V", ""))
        self._target_state = option
        self._target_timestamp = time.time()
        if self.coordinator.data:
            self.coordinator.data[self._key] = clean_num
        self.async_write_ha_state()

        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: clean_num}]
        )
        if not success:
            _LOGGER.error("Failed to set output voltage to %s", option)
            self._target_state = None
            self.async_write_ha_state()
            return

        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()

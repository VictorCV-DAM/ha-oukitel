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
from .sensor import _build_device_info

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

        # Solid internal state cache
        initial_opt = "50Hz"
        if coordinator.data and self._key in coordinator.data:
            initial_opt = FREQ_MAP_TO_NAME.get(str(coordinator.data[self._key]), "50Hz")
        self._attr_current_option = initial_opt

        self._user_locked_value = None
        self._user_locked_until = 0

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(self.coordinator, self.client)

    @property
    def available(self) -> bool:
        """Return True if select is available; disabled and greyed out when paused."""
        if self.coordinator.is_paused:
            return False
        return super().available

    def _handle_coordinator_update(self) -> None:
        """Update from coordinator when new data arrives."""
        now = time.time()
        if self._user_locked_value is not None:
            if now < self._user_locked_until:
                if self.coordinator.data and self._key in self.coordinator.data:
                    telemetry_opt = FREQ_MAP_TO_NAME.get(str(self.coordinator.data[self._key]))
                    if telemetry_opt == self._user_locked_value:
                        self._user_locked_value = None
                return
            else:
                self._user_locked_value = None

        if self.coordinator.data and self._key in self.coordinator.data:
            self._attr_current_option = FREQ_MAP_TO_NAME.get(str(self.coordinator.data[self._key]), "50Hz")
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Change output frequency."""
        if option not in self._attr_options:
            return

        cloud_val = FREQ_MAP_TO_VAL[option]

        # 1. Lock option for 15s to eliminate bounce
        self._user_locked_value = option
        self._user_locked_until = time.time() + 15
        self._attr_current_option = option
        if self.coordinator.data:
            self.coordinator.data[self._key] = cloud_val
        self.async_write_ha_state()

        # 2. Send command to cloud
        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: cloud_val}]
        )
        if not success:
            _LOGGER.error("oukitel: Failed to set output frequency to %s", option)
            self._user_locked_value = None
            if self.coordinator.data and self._key in self.coordinator.data:
                self._attr_current_option = FREQ_MAP_TO_NAME.get(str(self.coordinator.data[self._key]), "50Hz")
            self.async_write_ha_state()


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

        # Solid internal state cache
        initial_opt = "230V"
        if coordinator.data and self._key in coordinator.data:
            raw = str(coordinator.data[self._key]).replace("V", "").strip()
            formatted = f"{raw}V"
            if formatted in VOLTAGE_OPTIONS:
                initial_opt = formatted
        self._attr_current_option = initial_opt

        self._user_locked_value = None
        self._user_locked_until = 0

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(self.coordinator, self.client)

    @property
    def available(self) -> bool:
        """Return True if select is available; disabled and greyed out when paused."""
        if self.coordinator.is_paused:
            return False
        return super().available

    def _handle_coordinator_update(self) -> None:
        """Update from coordinator when new data arrives."""
        now = time.time()
        if self._user_locked_value is not None:
            if now < self._user_locked_until:
                if self.coordinator.data and self._key in self.coordinator.data:
                    raw = str(self.coordinator.data[self._key]).replace("V", "").strip()
                    if f"{raw}V" == self._user_locked_value:
                        self._user_locked_value = None
                return
            else:
                self._user_locked_value = None

        if self.coordinator.data and self._key in self.coordinator.data:
            raw = str(self.coordinator.data[self._key]).replace("V", "").strip()
            formatted = f"{raw}V"
            if formatted in VOLTAGE_OPTIONS:
                self._attr_current_option = formatted
        super()._handle_coordinator_update()

    async def async_select_option(self, option: str) -> None:
        """Change output voltage."""
        if option not in self._attr_options:
            return

        clean_num = int(option.replace("V", ""))

        # 1. Lock option for 15s to eliminate bounce
        self._user_locked_value = option
        self._user_locked_until = time.time() + 15
        self._attr_current_option = option
        if self.coordinator.data:
            self.coordinator.data[self._key] = clean_num
        self.async_write_ha_state()

        # 2. Send command to cloud
        success = await self.hass.async_add_executor_job(
            self.client.control_device, [{self._key: clean_num}]
        )
        if not success:
            _LOGGER.error("oukitel: Failed to set output voltage to %s", option)
            self._user_locked_value = None
            if self.coordinator.data and self._key in self.coordinator.data:
                raw = str(self.coordinator.data[self._key]).replace("V", "").strip()
                formatted = f"{raw}V"
                if formatted in VOLTAGE_OPTIONS:
                    self._attr_current_option = formatted
            self.async_write_ha_state()

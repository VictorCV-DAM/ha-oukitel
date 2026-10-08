"""Number platform for Oukitel Power Station settings."""

import asyncio
import logging
import time
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTITY_DESCRIPTIONS, MODE_LAN, get_entity_description
from .coordinator import OukitelDataCoordinator
from .sensor import _build_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Oukitel number entities based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OukitelDataCoordinator = data["coordinator"]
    client = data["client"]

    entities = [
        OukitelChargingLimitNumber(coordinator, client)
    ]
    async_add_entities(entities)


class OukitelChargingLimitNumber(CoordinatorEntity, NumberEntity):
    """Control for AC Upper Limit Charging Power slider (3% to 100%)."""

    _attr_has_entity_name = True
    _attr_translation_key = "ac_charging_limit"

    def __init__(self, coordinator: OukitelDataCoordinator, client):
        super().__init__(coordinator)
        self.client = client
        self._key = "ac_charging_limit"
        self._attr_name = "AC Charging Limit"
        self._attr_unique_id = f"oukitel_{client.device_key}_{self._key}"
        self._attr_icon = "mdi:gauge"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_native_min_value = 3
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER
        self._attr_entity_category = EntityCategory.CONFIG

        # Solid internal state cache
        initial_val = 100.0
        if coordinator.data and self._key in coordinator.data:
            try:
                initial_val = float(coordinator.data[self._key])
            except (ValueError, TypeError):
                initial_val = 100.0
        self._attr_native_value = initial_val
        self._pending_task: asyncio.Task | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(self.coordinator, self.client)

    @property
    def extra_state_attributes(self) -> dict:
        return {"description": get_entity_description("ac_charging_limit", self.hass)}

    @property
    def available(self) -> bool:
        """Return True if slider is available; disabled and greyed out when paused."""
        if self.coordinator.is_paused:
            return False
        return super().available

    def _handle_coordinator_update(self) -> None:
        """Update from coordinator when new data arrives."""
        if self._pending_task and not self._pending_task.done():
            return
        if self.coordinator.data and self._key in self.coordinator.data:
            try:
                self._attr_native_value = float(self.coordinator.data[self._key])
            except (ValueError, TypeError):
                pass
        super()._handle_coordinator_update()

    async def async_set_native_value(self, value: float) -> None:
        """Set new AC charging limit with 500ms debounce to prevent slider jitter."""
        target_val = int(round(value))
        target_val = max(3, min(100, target_val))

        # 1. Update UI and coordinator cache immediately with active override
        self._attr_native_value = float(target_val)
        self.coordinator.async_set_user_override(self._key, target_val, ttl=10.0, min_hold=2.0)
        self.async_write_ha_state()

        # 2. Cancel any pending dispatch and schedule a new debounced send
        if self._pending_task and not self._pending_task.done():
            self._pending_task.cancel()

        self._pending_task = self.hass.async_create_task(
            self._async_dispatch_debounced(target_val)
        )

    async def _async_dispatch_debounced(self, target_val: int) -> None:
        """Wait 500ms before firing hardware command to allow drag completion."""
        try:
            await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            return

        lan_ok = False
        if self.coordinator._lan_active and self.coordinator._lan_session:
            try:
                await self.coordinator._lan_session.send_write(20, "num", target_val)
                lan_ok = True
                _LOGGER.debug("oukitel: Instant LAN write for AC charging limit: 20 = %s", target_val)
            except Exception as exc:
                _LOGGER.warning("oukitel: LAN write failed for charging limit: %s", exc)

        # Synchronize clean single-property charging limit to Cloud only if not LAN-only
        cloud_ok = False
        if self.coordinator.connection_mode != MODE_LAN:
            cloud_ok = await self.hass.async_add_executor_job(
                self.client.control_device,
                [{self._key: target_val}],
            )
        if not cloud_ok and not lan_ok:
            _LOGGER.error("oukitel: Failed to set %s to %s", self._key, target_val)
            self.coordinator.async_clear_user_override(self._key)
            if self.coordinator.data and self._key in self.coordinator.data:
                try:
                    self._attr_native_value = float(self.coordinator.data[self._key])
                except (ValueError, TypeError):
                    pass
            self.async_write_ha_state()

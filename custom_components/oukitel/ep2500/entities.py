"""Native Home Assistant entities for Oukitel EP2500."""

import logging
from typing import Any, Optional
from homeassistant.components.button import ButtonEntity
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DP_ANTI_BACKFLOW,
    DP_MAX_BATTERY_CHARGE_POWER,
    DP_MAX_FEED_IN_POWER,
    DP_OFFGRID_OUTLET,
    DP_PV_CHARGE_LIMIT,
    DP_SOC_CHARGE_STOP,
    DP_SOC_DISCHARGE_STOP,
    EP2500SensorEntityDescription,
    LIMIT_CHARGE_MAX,
    LIMIT_CHARGE_MIN,
    LIMIT_FEED_IN_MAX,
    LIMIT_FEED_IN_MIN,
    SOC_MAX_ALLOWED,
    SOC_MIN_ALLOWED,
)
from .coordinator import OukitelEP2500Coordinator

_LOGGER = logging.getLogger(__name__)


class OukitelEP2500Sensor(CoordinatorEntity[OukitelEP2500Coordinator], SensorEntity):
    """Representation of an Oukitel EP2500 telemetry sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OukitelEP2500Coordinator,
        desc: EP2500SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.desc = desc
        self._attr_unique_id = f"oukitel_ep2500_{coordinator.device_id}_{desc.key}"
        self._attr_name = desc.name
        self._attr_native_unit_of_measurement = desc.native_unit_of_measurement
        self._attr_device_class = desc.device_class
        self._attr_state_class = desc.state_class
        self._attr_icon = desc.icon
        if desc.suggested_display_precision is not None:
            self._attr_suggested_display_precision = desc.suggested_display_precision

    @property
    def device_info(self):
        """Return parent device information."""
        return self.coordinator.device_info

    @property
    def native_value(self) -> Any:
        """Return scaled telemetry value from coordinator data cache."""
        if not self.coordinator.data:
            return None

        val = self.coordinator.data.get(self.desc.dp)
        if val is None:
            return None

        if isinstance(val, (int, float)):
            if self.desc.scale_factor != 1.0:
                return round(val * self.desc.scale_factor, self.desc.suggested_display_precision or 2)
            return val

        return val


class OukitelEP2500Switch(CoordinatorEntity[OukitelEP2500Coordinator], SwitchEntity):
    """Interactive toggle switch for EP2500 features."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OukitelEP2500Coordinator,
        dp: str,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._dp = dp
        self._key = key
        self._attr_unique_id = f"oukitel_ep2500_{coordinator.device_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon

    @property
    def device_info(self):
        """Return parent device information."""
        return self.coordinator.device_info

    @property
    def is_on(self) -> Optional[bool]:
        """Return switch state."""
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self._dp)
        return bool(val) if val is not None else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn switch on."""
        await self.coordinator.async_set_dp(self._dp, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn switch off."""
        await self.coordinator.async_set_dp(self._dp, False)


class OukitelEP2500Number(CoordinatorEntity[OukitelEP2500Coordinator], NumberEntity):
    """Configurable numerical limit or threshold for EP2500."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: OukitelEP2500Coordinator,
        dp: str,
        key: str,
        name: str,
        min_value: float,
        max_value: float,
        step: float,
        unit: Optional[str],
        icon: str,
    ) -> None:
        """Initialize the number slider/box."""
        super().__init__(coordinator)
        self._dp = dp
        self._key = key
        self._attr_unique_id = f"oukitel_ep2500_{coordinator.device_id}_{key}"
        self._attr_name = name
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon

    @property
    def device_info(self):
        """Return parent device information."""
        return self.coordinator.device_info

    @property
    def native_value(self) -> Optional[float]:
        """Return current numerical value."""
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(self._dp)
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Dispatch numerical value to EP2500."""
        await self.coordinator.async_set_dp(self._dp, int(value))


class OukitelEP2500ReloadButton(CoordinatorEntity[OukitelEP2500Coordinator], ButtonEntity):
    """Button entity to trigger immediate telemetry polling and session refresh."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: OukitelEP2500Coordinator) -> None:
        """Initialize reload button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"oukitel_ep2500_{coordinator.device_id}_reload"
        self._attr_name = "Reload EP2500 Connection"

    @property
    def device_info(self):
        """Return parent device information."""
        return self.coordinator.device_info

    async def async_press(self) -> None:
        """Trigger immediate coordinator refresh."""
        await self.coordinator.async_refresh()


def create_ep2500_switches(coordinator: OukitelEP2500Coordinator) -> list[SwitchEntity]:
    """Instantiate standard EP2500 switches."""
    return [
        OukitelEP2500Switch(
            coordinator,
            dp=DP_OFFGRID_OUTLET,
            key="offgrid_outlet",
            name="Off-Grid Output Socket",
            icon="mdi:power-socket-eu",
        ),
        OukitelEP2500Switch(
            coordinator,
            dp=DP_ANTI_BACKFLOW,
            key="anti_backflow",
            name="Anti-Backflow (Block Grid Export)",
            icon="mdi:transmission-tower-off",
        ),
    ]


def create_ep2500_numbers(coordinator: OukitelEP2500Coordinator) -> list[NumberEntity]:
    """Instantiate standard EP2500 configurable numbers."""
    return [
        OukitelEP2500Number(
            coordinator,
            dp=DP_MAX_FEED_IN_POWER,
            key="max_feed_in_power",
            name="Maximum Feed-In Power",
            min_value=LIMIT_FEED_IN_MIN,
            max_value=LIMIT_FEED_IN_MAX,
            step=10,
            unit="W",
            icon="mdi:transmission-tower-export",
        ),
        OukitelEP2500Number(
            coordinator,
            dp=DP_MAX_BATTERY_CHARGE_POWER,
            key="max_battery_charge_power",
            name="Maximum Battery Charge Power",
            min_value=LIMIT_CHARGE_MIN,
            max_value=LIMIT_CHARGE_MAX,
            step=50,
            unit="W",
            icon="mdi:battery-charging-high",
        ),
        OukitelEP2500Number(
            coordinator,
            dp=DP_PV_CHARGE_LIMIT,
            key="pv_charge_limit",
            name="Solar PV Charge Limit",
            min_value=LIMIT_CHARGE_MIN,
            max_value=LIMIT_CHARGE_MAX,
            step=50,
            unit="W",
            icon="mdi:solar-power",
        ),
        OukitelEP2500Number(
            coordinator,
            dp=DP_SOC_CHARGE_STOP,
            key="soc_charge_stop",
            name="Battery Charge Stop SoC",
            min_value=SOC_MIN_ALLOWED,
            max_value=SOC_MAX_ALLOWED,
            step=1,
            unit="%",
            icon="mdi:battery-charging-100",
        ),
        OukitelEP2500Number(
            coordinator,
            dp=DP_SOC_DISCHARGE_STOP,
            key="soc_discharge_stop",
            name="Battery Discharge Stop SoC",
            min_value=SOC_MIN_ALLOWED,
            max_value=SOC_MAX_ALLOWED,
            step=1,
            unit="%",
            icon="mdi:battery-low",
        ),
    ]

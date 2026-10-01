"""Sensor platform for Oukitel Power Station."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OukitelDataCoordinator

SENSOR_TYPES = [
    ("battery_percentage", "Battery", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, "mdi:battery-charging"),
    ("total_input_power", "Total Input Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:solar-power"),
    ("total_output_power", "Total Output Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:flash"),
    ("ac_input", "AC Input Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:transmission-tower"),
    ("dc_input", "DC Solar Input Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:solar-panel"),
    ("temp", "Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, "mdi:thermometer"),
    ("remain_time", "Remaining Discharge Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-outline"),
    ("remain_charging_time", "Remaining Charge Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-sand"),
    ("ac_charging_limit", "AC Charging Limit", PERCENTAGE, None, SensorStateClass.MEASUREMENT, "mdi:gauge"),
    ("wifi_signal", "WiFi Signal", SIGNAL_STRENGTH_DECIBELS_MILLIWATT, SensorDeviceClass.SIGNAL_STRENGTH, SensorStateClass.MEASUREMENT, "mdi:wifi"),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Oukitel sensor entities based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OukitelDataCoordinator = data["coordinator"]
    client = data["client"]

    entities = [
        OukitelSensor(coordinator, client, key, name, unit, dev_class, state_class, icon)
        for key, name, unit, dev_class, state_class, icon in SENSOR_TYPES
    ]
    async_add_entities(entities)


class OukitelSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Oukitel sensor."""

    def __init__(self, coordinator: OukitelDataCoordinator, client, key, name, unit, dev_class, state_class, icon):
        super().__init__(coordinator)
        self.client = client
        self._key = key
        self._attr_name = f"{client.device_name} {name}"
        self._attr_unique_id = f"oukitel_{client.device_key}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = dev_class
        self._attr_state_class = state_class
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
    def icon(self):
        """Return dynamic animated icon for battery depending on level and charging state."""
        if self._key == "battery_percentage":
            val = self.native_value
            if val is not None:
                # Calculate charging state from input power
                is_charging = False
                if self.coordinator.data:
                    total_in = self.coordinator.data.get("total_input_power", 0) or 0
                    ac_in = self.coordinator.data.get("ac_input", 0) or 0
                    dc_in = self.coordinator.data.get("dc_input", 0) or 0
                    if total_in > 5 or ac_in > 5 or dc_in > 5:
                        is_charging = True

                rounded = int(round(val / 10.0) * 10)
                rounded = max(10, min(100, rounded))
                if is_charging:
                    if rounded == 100:
                        return "mdi:battery-charging-100"
                    return f"mdi:battery-charging-{rounded}"
                else:
                    if rounded == 100:
                        return "mdi:battery"
                    return f"mdi:battery-{rounded}"
        return self._attr_icon

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._key)

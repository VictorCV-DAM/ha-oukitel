"""Sensor platform for Oukitel Power Station."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
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

# (key, name, unit, dev_class, state_class, icon, entity_category)
SENSOR_TYPES = [
    ("battery_percentage", "Battery", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, "mdi:battery-charging", None),
    ("total_input_power", "Total Input Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:solar-power", None),
    ("total_output_power", "Total Output Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:flash", None),
    ("ac_input", "AC Input Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:transmission-tower", None),
    ("dc_input", "DC Solar Input Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:solar-panel", None),
    ("temp", "Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, "mdi:thermometer", None),
    ("remain_time", "Remaining Discharge Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-outline", None),
    ("remain_charging_time", "Remaining Charge Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-sand", None),
    ("wifi_signal", "WiFi Signal", SIGNAL_STRENGTH_DECIBELS_MILLIWATT, SensorDeviceClass.SIGNAL_STRENGTH, SensorStateClass.MEASUREMENT, "mdi:wifi", EntityCategory.DIAGNOSTIC),
    ("BMS_Version", "BMS Version", None, None, None, "mdi:chip", EntityCategory.DIAGNOSTIC),
    ("AC_Version", "Inverter Version", None, None, None, "mdi:sine-wave", EntityCategory.DIAGNOSTIC),
    ("device_fault_status", "Hardware Fault Status", None, None, None, "mdi:shield-check", EntityCategory.DIAGNOSTIC),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Oukitel sensor entities based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OukitelDataCoordinator = data["coordinator"]
    client = data["client"]

    entities = [
        OukitelSensor(coordinator, client, key, name, unit, dev_class, state_class, icon, category)
        for key, name, unit, dev_class, state_class, icon, category in SENSOR_TYPES
    ]
    entities.append(OukitelConnectionModeSensor(coordinator, client))
    async_add_entities(entities)


class OukitelSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Oukitel sensor."""

    def __init__(self, coordinator: OukitelDataCoordinator, client, key, name, unit, dev_class, state_class, icon, category=None):
        super().__init__(coordinator)
        self.client = client
        self._key = key
        self._attr_name = f"{client.device_name} {name}"
        self._attr_unique_id = f"oukitel_{client.device_key}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = dev_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        if category:
            self._attr_entity_category = category

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

        if self._key == "device_fault_status":
            if self.native_value == "Normal":
                return "mdi:shield-check"
            return "mdi:alert-octagon"

        return self._attr_icon

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None

        if self._key == "device_fault_status":
            # Real-time health audit
            faults = []
            temp = self.coordinator.data.get("temp", 0)
            if temp and temp >= 65:
                faults.append(f"Over-Temperature ({temp}°C)")
            elif temp and temp <= -10:
                faults.append(f"Under-Temperature ({temp}°C)")

            batt = self.coordinator.data.get("battery_percentage", 100)
            if batt is not None and batt == 0:
                faults.append("Critical Low Battery (0%)")

            # Check for any error/fault codes in telemetry payload
            for k, v in self.coordinator.data.items():
                if any(x in k.lower() for x in ["fault", "alarm", "error", "protect"]):
                    if v and str(v).lower() not in ["0", "false", "none", "normal", "ok"]:
                        faults.append(f"{k}: {v}")

            return "; ".join(faults) if faults else "Normal"

        return self.coordinator.data.get(self._key)


class OukitelConnectionModeSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor that reports the active connection mode."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_name = "Connection Mode"
    _attr_icon = "mdi:lan-connect"

    def __init__(self, coordinator: OukitelDataCoordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self._attr_unique_id = f"oukitel_{client.device_key}_connection_mode"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.client.device_key)},
            name=self.client.device_name,
            manufacturer="OUKITEL",
            model="P2001 Plus",
        )

    @property
    def native_value(self) -> str:
        return "LAN" if self.coordinator._lan_active else "Cloud"

    @property
    def icon(self) -> str:
        return "mdi:lan-connect" if self.coordinator._lan_active else "mdi:cloud-outline"

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {}
        if self.coordinator._lan_active and self.coordinator._lan_last_report:
            import time
            age = round(time.monotonic() - self.coordinator._lan_last_report, 1)
            attrs["last_lan_report_ago_s"] = age
        return attrs

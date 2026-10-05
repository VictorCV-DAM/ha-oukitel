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
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OukitelDataCoordinator


def _format_mac(dk: str) -> str:
    if dk and len(dk) == 12:
        return ":".join(dk[i:i+2] for i in range(0, 12, 2)).upper()
    return dk or ""


def _build_device_info(coordinator: OukitelDataCoordinator, client) -> DeviceInfo:
    mac = _format_mac(client.device_key or "")
    host = getattr(coordinator, "lan_host", None)
    mode = getattr(coordinator, "connection_mode", "auto").upper()

    connections = set()
    if mac and ":" in mac:
        connections.add((CONNECTION_NETWORK_MAC, mac))

    hw_info = f"IP: {host} [{mode}]" if host else f"Cloud [{mode}]"

    return DeviceInfo(
        identifiers={(DOMAIN, client.device_key)},
        connections=connections,
        name=client.device_name,
        manufacturer="OUKITEL",
        model=getattr(client, "product_name", "P2001 Plus") or "P2001 Plus",
        sw_version="Cloud+LAN API 1.2.5",
        hw_version=hw_info,
        serial_number=mac if mac else client.device_key,
        configuration_url=f"http://{host}" if host else None,
    )

# (key, name, unit, dev_class, state_class, icon, entity_category, enabled_default)
SENSOR_TYPES = [
    # Core Telemetry
    ("battery_percentage", "Battery", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, "mdi:battery-charging", None, True),
    ("total_input_power", "Total Input Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:solar-power", None, True),
    ("total_output_power", "Total Output Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:flash", None, True),
    ("ac_input", "AC Input Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:transmission-tower", None, True),
    ("dc_input", "DC Solar Input Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:solar-panel", None, True),
    ("temp", "Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, "mdi:thermometer", None, True),
    ("inverter_temp", "Inverter Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, "mdi:thermometer-lines", None, False),

    # Time calculations (LCD display, distinct discharge vs charging)
    ("remaining_time", "Remaining Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-outline", None, True),
    ("remain_time", "Remaining Discharge Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-outline", None, True),
    ("remain_charging_time", "Remaining Charge Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-sand", None, True),

    # Per-port Individual Outputs (W / V / A)
    ("ac_output_power", "AC Output Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:lightning-bolt", None, True),
    ("ac_output_voltage", "AC Output Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "mdi:sine-wave", None, False),
    ("usb_a_power", "USB-A Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-port", None, True),
    ("usb_c_qc_power", "USB-C (QC) Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, True),
    ("typec1_power", "Type-C 1 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, True),
    ("typec2_power", "Type-C 2 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, True),
    ("typec3_power", "Type-C 3 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, True),
    ("typec4_power", "Type-C 4 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, True),
    ("dc_output_power", "DC (Car) Output Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:car-electric", None, True),
    ("dc_output_voltage", "DC (Car) Output Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "mdi:car-battery", None, False),
    ("dc_output_current", "DC (Car) Output Current", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, "mdi:current-dc", None, False),

    # Diagnostic & Health
    ("wifi_signal", "WiFi Signal", SIGNAL_STRENGTH_DECIBELS_MILLIWATT, SensorDeviceClass.SIGNAL_STRENGTH, SensorStateClass.MEASUREMENT, "mdi:wifi", EntityCategory.DIAGNOSTIC, True),
    ("BMS_Version", "BMS Version", None, None, None, "mdi:chip", EntityCategory.DIAGNOSTIC, True),
    ("AC_Version", "Inverter Version", None, None, None, "mdi:sine-wave", EntityCategory.DIAGNOSTIC, True),
    ("device_fault_status", "Hardware Fault Status", None, None, None, "mdi:shield-check", EntityCategory.DIAGNOSTIC, True),
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Oukitel sensor entities based on a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OukitelDataCoordinator = data["coordinator"]
    client = data["client"]

    entities = [
        OukitelSensor(coordinator, client, key, name, unit, dev_class, state_class, icon, category, enabled_default)
        for key, name, unit, dev_class, state_class, icon, category, enabled_default in SENSOR_TYPES
    ]
    entities.append(OukitelConnectionModeSensor(coordinator, client))
    async_add_entities(entities)


class OukitelSensor(CoordinatorEntity, SensorEntity):
    """Representation of an Oukitel sensor."""

    def __init__(self, coordinator: OukitelDataCoordinator, client, key, name, unit, dev_class, state_class, icon, category=None, enabled_default=True):
        super().__init__(coordinator)
        self.client = client
        self._key = key
        self._attr_name = f"{client.device_name} {name}"
        self._attr_unique_id = f"oukitel_{client.device_key}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = dev_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        self._attr_entity_registry_enabled_default = enabled_default
        if category:
            self._attr_entity_category = category

    @property
    def device_info(self) -> DeviceInfo:
        return _build_device_info(self.coordinator, self.client)

    @property
    def icon(self):
        """Return dynamic animated icon for battery depending on level and charging state."""
        if self._key == "battery_percentage":
            val = self.native_value
            if val is not None:
                # Calculate charging state from net power
                is_charging = False
                if self.coordinator.data:
                    total_in = float(self.coordinator.data.get("total_input_power") or 0)
                    total_out = float(self.coordinator.data.get("total_output_power") or 0)
                    ac_in = float(self.coordinator.data.get("ac_input") or 0)
                    dc_in = float(self.coordinator.data.get("dc_input") or 0)
                    ac_out = float(self.coordinator.data.get("ac_output_power") or 0)
                    dc_out = float(self.coordinator.data.get("dc_output_power") or 0)
                    real_in = max(total_in, ac_in + dc_in)
                    real_out = max(total_out, ac_out + dc_out)
                    if real_in > real_out + 5.0:
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

        # 1. Remaining Time: General LCD display value (what appears on station LCD)
        if self._key == "remaining_time":
            val = self.coordinator.data.get("remain_time")
            if val is None or val == 0:
                val = self.coordinator.data.get("remain_charging_time")
            return val if val is not None else 0

        # Calculate accurate net power balance
        # Positive net_power = charging battery; Negative net_power = discharging battery
        total_in = float(self.coordinator.data.get("total_input_power") or 0)
        total_out = float(self.coordinator.data.get("total_output_power") or 0)
        ac_in = float(self.coordinator.data.get("ac_input") or 0)
        dc_in = float(self.coordinator.data.get("dc_input") or 0)
        ac_out = float(self.coordinator.data.get("ac_output_power") or 0)
        dc_out = float(self.coordinator.data.get("dc_output_power") or 0)

        real_in = max(total_in, ac_in + dc_in)
        real_out = max(total_out, ac_out + dc_out)
        net_power = real_in - real_out

        # 2. Remaining Discharge Time: Autonomy remaining while draining battery
        if self._key == "remain_time":
            # If net power is charging or idle (real_in >= real_out - 5W), battery is NOT discharging
            if net_power >= -5.0:
                return 0

            # Battery is draining: return station BMS discharge autonomy
            val = self.coordinator.data.get("remain_time", 0) or 0
            if val == 0:
                batt = self.coordinator.data.get("battery_percentage", 0) or 0
                if batt > 0 and abs(net_power) > 5.0:
                    val = int(((batt / 100.0) * 2048.0 / abs(net_power)) * 60)
            return val

        # 3. Remaining Charge Time: Estimated time to reach 100% full
        if self._key == "remain_charging_time":
            batt = self.coordinator.data.get("battery_percentage")
            if batt is not None and batt >= 100:
                return 0

            # If net power is discharging or idle (real_in <= real_out + 5W), battery is NOT charging
            if net_power <= 5.0:
                return 0

            # Battery is charging: get station charge time estimate
            val = self.coordinator.data.get("remain_charging_time")
            if val is None or val == 0:
                val = self.coordinator.data.get("remain_time", 0) or 0
            if val == 0:
                batt_pct = batt or 0
                if net_power > 5.0:
                    needed_wh = ((100.0 - batt_pct) / 100.0) * 2048.0
                    val = int((needed_wh / net_power) * 60)
            return val

        # 4. Individual port outputs default to 0 if None/inactive (prevents "Unknown" states)
        if self._key in (
            "ac_output_power",
            "dc_output_power",
            "usb_a_power",
            "usb_c_qc_power",
            "typec1_power",
            "typec2_power",
            "typec3_power",
            "typec4_power",
        ):
            val = self.coordinator.data.get(self._key)
            return val if val is not None else 0

        # 5. Version string formatting (e.g. 215, 106)
        if self._key in ("BMS_Version", "AC_Version"):
            val = self.coordinator.data.get(self._key)
            if val is not None:
                try:
                    return str(int(val))
                except (ValueError, TypeError):
                    return str(val)
            return None

        # 6. Fault status audit
        if self._key == "device_fault_status":
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
                if isinstance(k, str) and any(x in k.lower() for x in ["fault", "alarm", "error", "protect"]):
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
        return _build_device_info(self.coordinator, self.client)

    @property
    def native_value(self) -> str:
        return "LAN" if self.coordinator._lan_active else "Cloud"

    @property
    def icon(self) -> str:
        return "mdi:lan-connect" if self.coordinator._lan_active else "mdi:cloud-outline"

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {
            "configured_mode": getattr(self.coordinator, "connection_mode", "auto"),
            "lan_ip": getattr(self.coordinator, "lan_host", None),
            "device_mac": _format_mac(self.client.device_key or ""),
        }
        if self.coordinator._lan_active and self.coordinator._lan_last_report:
            import time
            age = round(time.monotonic() - self.coordinator._lan_last_report, 1)
            attrs["last_lan_report_ago_s"] = age
        return attrs

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

from .const import DOMAIN, VERSION
from .coordinator import OukitelDataCoordinator


def _format_mac(dk: str) -> str:
    if dk and len(dk) == 12:
        return ":".join(dk[i:i+2] for i in range(0, 12, 2)).upper()
    return dk or ""


def _clean_model_name(raw: str | None) -> str:
    if not raw:
        return "Oukitel Power Station"
    name = raw.replace("-PLUS-", " Plus ").replace("-PLUS", " Plus").replace("PLUS", " Plus")
    name = name.replace("-TT", "").replace(" TT", "").replace("_", " ").replace("/", " / ")
    parts = [p for p in name.split() if p.upper() != "TT" and not (len(p) == 4 and all(c in "0123456789ABCDEFabcdef" for c in p))]
    name = " ".join(parts)
    while "  " in name:
        name = name.replace("  ", " ")
    return name.strip() or "Oukitel Power Station"


def _build_device_info(coordinator: OukitelDataCoordinator, client) -> DeviceInfo:
    mac = _format_mac(client.device_key or "")
    host = getattr(coordinator, "lan_host", None)
    mode = getattr(coordinator, "connection_mode", "auto").upper()

    connections = set()
    if mac and ":" in mac:
        connections.add((CONNECTION_NETWORK_MAC, mac))

    hw_info = f"IP: {host} [{mode}]" if host else f"Cloud [{mode}]"
    raw_model = getattr(client, "product_name", None) or getattr(client, "device_name", None)

    return DeviceInfo(
        identifiers={(DOMAIN, client.device_key)},
        connections=connections,
        name=client.device_name,
        manufacturer="OUKITEL",
        model=_clean_model_name(raw_model),
        sw_version=f"Cloud+LAN {VERSION}",
        hw_version=hw_info,
        serial_number=mac if mac else client.device_key,
        configuration_url=f"http://{host}" if host else None,
    )

FAULT_STATUS_OPTIONS = [
    "Normal",
    "High Temperature Warning",
    "Over-Temperature",
    "Under-Temperature",
    "Low Battery Warning",
    "Critical Low Battery",
    "Overload Protection",
    "Hardware Fault",
]

# (key, name, unit, dev_class, state_class, icon, entity_category, enabled_default)
SENSOR_TYPES = [
    # Core Telemetry
    ("battery_percentage", "Battery", PERCENTAGE, SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, "mdi:battery-charging", None, True),
    ("total_input_power", "Total Input Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:solar-power", None, True),
    ("total_output_power", "Total Output Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:flash", None, True),
    ("ac_input", "AC Input Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:transmission-tower", None, True),
    ("dc_input", "DC Solar Input Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:solar-panel", None, True),
    ("temp", "Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, "mdi:thermometer", None, True),
    ("inverter_temp", "Inverter Temperature", UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT, "mdi:thermometer-lines", None, True),

    # Time calculations (LCD display, distinct discharge vs charging)
    ("remaining_time", "Remaining Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-outline", None, True),
    ("remain_time", "Remaining Discharge Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-outline", None, True),
    ("remain_charging_time", "Remaining Charge Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-sand", None, True),

    # Per-port Individual Outputs (W / V / A)
    ("ac_output_power", "AC Output Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:lightning-bolt", None, True),
    ("ac_output_voltage", "AC Output Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "mdi:sine-wave", None, True),
    ("usb_a_power", "USB-A Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-port", None, True),
    ("usb_c_qc_power", "USB-C (QC) Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, True),
    ("typec1_power", "Type-C 1 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, True),
    ("typec2_power", "Type-C 2 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, True),
    ("typec3_power", "Type-C 3 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, True),
    ("typec4_power", "Type-C 4 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, True),
    ("dc_output_power", "DC (Car) Output Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:car-electric", None, True),
    ("dc_output_voltage", "DC (Car) Output Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "mdi:car-battery", None, True),
    ("dc_output_current", "DC (Car) Output Current", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, "mdi:current-dc", None, True),

    # Diagnostic & Health
    ("wifi_signal", "WiFi Signal", SIGNAL_STRENGTH_DECIBELS_MILLIWATT, SensorDeviceClass.SIGNAL_STRENGTH, SensorStateClass.MEASUREMENT, "mdi:wifi", EntityCategory.DIAGNOSTIC, True),
    ("BMS_Version", "BMS Version", None, None, None, "mdi:chip", EntityCategory.DIAGNOSTIC, True),
    ("AC_Version", "Inverter Version", None, None, None, "mdi:sine-wave", EntityCategory.DIAGNOSTIC, True),
    ("device_fault_status", "Hardware Fault Status", None, SensorDeviceClass.ENUM, None, "mdi:shield-check", EntityCategory.DIAGNOSTIC, True),
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
        if key == "device_fault_status":
            self._attr_options = FAULT_STATUS_OPTIONS

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
            val = self.native_value
            if val == "Normal":
                return "mdi:shield-check"
            elif "Warning" in str(val):
                return "mdi:alert"
            return "mdi:alert-octagon"

        return self._attr_icon

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._key == "device_fault_status":
            details = []
            temp = float(self.coordinator.data.get("temp") or 0)
            batt = self.coordinator.data.get("battery_percentage")
            total_out = float(self.coordinator.data.get("total_output_power") or 0)

            if temp >= 65.0:
                details.append(f"Temperature is critical: {temp}°C (limit 65°C)")
            elif temp >= 55.0:
                details.append(f"Temperature is high: {temp}°C")
            elif temp < -10.0 and temp != 0:
                details.append(f"Temperature is freezing: {temp}°C")

            if batt is not None and batt <= 10:
                details.append(f"Battery is low: {batt}%")

            if total_out > 2400.0:
                details.append(f"Output power ({total_out}W) exceeds rated 2400W")

            for k, v in self.coordinator.data.items():
                if isinstance(k, str) and any(x in k.lower() for x in ["fault", "alarm", "error", "protect"]):
                    if v and str(v).lower() not in ["0", "false", "none", "normal", "ok"]:
                        details.append(f"{k}: {v}")

            return {
                "fault_details": "; ".join(details) if details else "None",
                "possible_states": FAULT_STATUS_OPTIONS,
            }
        return None

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None

        # 1. Remaining Time: General LCD display value (what appears on station LCD)
        if self._key == "remaining_time":
            val = self.coordinator.data.get("remain_time")
            if val is None or val == 0:
                val = self.coordinator.data.get("remain_charging_time")
            if val is None:
                val = 0
            if (val == 0 or val >= 5940) and abs(net_power) > 5.0:
                batt = self.coordinator.data.get("battery_percentage", 0) or 0
                if net_power < -5.0 and batt > 0:
                    val = int(((batt / 100.0) * 2048.0 / abs(net_power)) * 60)
                elif net_power > 5.0 and batt < 100:
                    val = int((((100.0 - batt) / 100.0) * 2048.0 / net_power) * 60)
            return val

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
            if val == 0 or val >= 5940:
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
            if val is None or val == 0 or val >= 5940:
                val = self.coordinator.data.get("remain_time", 0) or 0
            if val == 0 or val >= 5940:
                batt_pct = batt or 0
                if net_power > 5.0:
                    needed_wh = ((100.0 - batt_pct) / 100.0) * 2048.0
                    val = int((needed_wh / net_power) * 60)
            return val

        # 4. AC Output Voltage: 230V (or configured ACvoltage_Switchover) when AC output/switch active, 0V when off
        if self._key == "ac_output_voltage":
            val = self.coordinator.data.get("ac_output_voltage")
            if val is not None and val > 0:
                return val
            ac_p = float(self.coordinator.data.get("ac_output_power") or 0)
            ac_sw = bool(self.coordinator.data.get("ac_switch", False))
            if ac_p > 0 or ac_sw:
                v_enum = self.coordinator.data.get("ACvoltage_Switchover")
                enum_map = {0: 100, 1: 110, 2: 120, 3: 220, 4: 230}
                return enum_map.get(v_enum, 230)
            return 0

        # 5. DC Car Output Voltage & Current: 12V when active, otherwise 0
        if self._key == "dc_output_voltage":
            val = self.coordinator.data.get("dc_output_voltage")
            if val is not None and val > 0:
                return val
            dc_p = float(self.coordinator.data.get("dc_output_power") or 0)
            dc_sw = bool(self.coordinator.data.get("dc_switch", False))
            if dc_p > 0 or dc_sw:
                return 12.0
            return 0.0

        if self._key == "dc_output_current":
            val = self.coordinator.data.get("dc_output_current")
            if val is not None and val > 0:
                return val
            dc_p = float(self.coordinator.data.get("dc_output_power") or 0)
            if dc_p > 0:
                return round(dc_p / 12.0, 2)
            return 0.0

        # 6. Inverter Temperature: fallback to unit temperature (temp) if tag 33 is absent
        if self._key == "inverter_temp":
            val = self.coordinator.data.get("inverter_temp")
            if val is not None and val > 0:
                return val
            val = self.coordinator.data.get("temp")
            return val if val is not None else 0.0

        # 7. Individual port outputs and power metrics default to 0 if None/inactive (prevents "Unknown" states)
        if self._key in (
            "ac_output_power",
            "dc_output_power",
            "usb_a_power",
            "usb_c_qc_power",
            "typec1_power",
            "typec2_power",
            "typec3_power",
            "typec4_power",
            "total_input_power",
            "total_output_power",
            "ac_input",
            "dc_input",
        ):
            val = self.coordinator.data.get(self._key)
            return val if val is not None else 0

        # 8. Temperature default to 0.0 if not received
        if self._key == "temp":
            val = self.coordinator.data.get("temp")
            return val if val is not None else 0.0

        # 9. Battery default to 0 if not received
        if self._key == "battery_percentage":
            val = self.coordinator.data.get("battery_percentage")
            return val if val is not None else 0

        # 10. WiFi signal default
        if self._key == "wifi_signal":
            val = self.coordinator.data.get("wifi_signal")
            return val if val is not None else -100

        # 11. Version string formatting (e.g. 215, 106)
        if self._key in ("BMS_Version", "AC_Version"):
            val = self.coordinator.data.get(self._key)
            if val is not None:
                try:
                    return str(int(val))
                except (ValueError, TypeError):
                    return str(val)
            return None

        # 12. Fault status audit (returns exact match from FAULT_STATUS_OPTIONS)
        if self._key == "device_fault_status":
            temp = float(self.coordinator.data.get("temp") or 0)
            batt = self.coordinator.data.get("battery_percentage")
            total_out = float(self.coordinator.data.get("total_output_power") or 0)

            # 1. Critical Temperature
            if temp >= 65.0:
                return "Over-Temperature"
            if temp < -10.0 and temp != 0:
                return "Under-Temperature"

            # 2. Critical Battery (0% with active load)
            if batt is not None and batt == 0 and total_out > 0:
                return "Critical Low Battery"

            # 3. Overload Protection (exceeds rated 2400W)
            if total_out > 2400.0:
                return "Overload Protection"

            # 4. Hardware fault codes reported by BMS / Inverter
            for k, v in self.coordinator.data.items():
                if isinstance(k, str) and any(x in k.lower() for x in ["fault", "alarm", "error", "protect"]):
                    if v and str(v).lower() not in ["0", "false", "none", "normal", "ok"]:
                        return "Hardware Fault"

            # 5. Warning levels
            if temp >= 55.0:
                return "High Temperature Warning"
            if batt is not None and batt <= 10 and total_out > 0:
                return "Low Battery Warning"

            return "Normal"

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
        if self.coordinator.is_paused:
            return "Paused"
        return "LAN" if self.coordinator._lan_active else "Cloud"

    @property
    def icon(self) -> str:
        if self.coordinator.is_paused:
            return "mdi:pause-circle-outline"
        return "mdi:lan-connect" if self.coordinator._lan_active else "mdi:cloud-outline"

    @property
    def extra_state_attributes(self) -> dict:
        attrs: dict = {
            "configured_mode": getattr(self.coordinator, "connection_mode", "auto"),
            "lan_ip": getattr(self.coordinator, "lan_host", None),
            "device_mac": _format_mac(self.client.device_key or ""),
            "is_paused": self.coordinator.is_paused,
        }
        if self.coordinator._lan_active and self.coordinator._lan_last_report:
            import time
            age = round(time.monotonic() - self.coordinator._lan_last_report, 1)
            attrs["last_lan_report_ago_s"] = age
        return attrs

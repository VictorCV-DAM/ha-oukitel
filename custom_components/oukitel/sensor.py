import time

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
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CURRENCY,
    CONF_FIXED_PRICE,
    CONF_PRICE_SENSOR,
    DEFAULT_CURRENCY,
    DEFAULT_FIXED_PRICE,
    DOMAIN,
    VERSION,
)
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


def _get_battery_capacity_wh(client) -> float:
    raw = (getattr(client, "product_name", None) or getattr(client, "device_name", "") or "").lower()
    if "5000" in raw:
        return 5120.0
    if "3000" in raw:
        return 3072.0
    if "1000" in raw or "1024" in raw:
        return 1024.0
    if "1200" in raw or "960" in raw:
        return 960.0
    if "500" in raw or "505" in raw:
        return 505.0
    return 2048.0


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


def _build_calculated_device_info(coordinator: OukitelDataCoordinator, client) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"{client.device_key}_calculated")},
        via_device=(DOMAIN, client.device_key),
        name=f"{client.device_name} Calculated Sensors",
        manufacturer="OUKITEL",
        model="Calculated Energy & Financial Metrics",
        sw_version=f"Cloud+LAN {VERSION}",
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
    ("remaining_time", "Remaining Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-outline", None, False),
    ("remain_time", "Remaining Discharge Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-outline", None, True),
    ("remain_charging_time", "Remaining Charge Time", UnitOfTime.MINUTES, SensorDeviceClass.DURATION, SensorStateClass.MEASUREMENT, "mdi:timer-sand", None, True),

    # Per-port Individual Outputs (W / V / A)
    ("ac_output_power", "AC Output Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:lightning-bolt", None, True),
    ("ac_output_voltage", "AC Output Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "mdi:sine-wave", None, True),
    ("usb_a_power", "USB-A Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-port", None, False),
    ("usb_c_qc_power", "USB-C (QC) Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, False),
    ("typec1_power", "Type-C 1 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, False),
    ("typec2_power", "Type-C 2 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, False),
    ("typec3_power", "Type-C 3 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, False),
    ("typec4_power", "Type-C 4 Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:usb-c-port", None, False),
    ("dc_output_power", "DC (Car) Output Power", UnitOfPower.WATT, SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:car-electric", None, True),
    ("dc_output_voltage", "DC (Car) Output Voltage", UnitOfElectricPotential.VOLT, SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "mdi:car-battery", None, False),
    ("dc_output_current", "DC (Car) Output Current", UnitOfElectricCurrent.AMPERE, SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, "mdi:current-dc", None, False),

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
    entities.append(OukitelInverterIdlePowerSensor(coordinator, client))
    entities.append(OukitelInverterEfficiencySensor(coordinator, client))
    entities.append(OukitelInverterLossPowerSensor(coordinator, client))
    entities.append(OukitelBatteryCyclesSensor(coordinator, client))
    entities.append(OukitelBatteryHealthSensor(coordinator, client))
    entities.append(OukitelDaysSinceFullChargeSensor(coordinator, client))

    # Options for dynamic electricity pricing
    price_sensor = entry.options.get(
        CONF_PRICE_SENSOR,
        entry.data.get(CONF_PRICE_SENSOR, "")
    )
    fixed_price = entry.options.get(
        CONF_FIXED_PRICE,
        entry.data.get(CONF_FIXED_PRICE, DEFAULT_FIXED_PRICE)
    )

    # 1. Calculated Energy Sensors (kWh) - Linked device
    calc_energy_specs = [
        ("ac_input", "AC Input (kWh)", "calc_ac_input_kwh", "mdi:transmission-tower", False),
        ("dc_input", "DC Solar Input (kWh)", "calc_dc_input_kwh", "mdi:solar-power", False),
        ("total_output_power", "Total Output (kWh)", "calc_total_output_kwh", "mdi:flash", False),
        ("ac_output_power", "AC Output (kWh)", "calc_ac_output_kwh", "mdi:lightning-bolt", False),
        ("battery_discharged", "Battery Discharged (kWh)", "calc_battery_discharged_kwh", "mdi:battery-arrow-down", False),
        ("ac_input", "Daily AC Input (kWh)", "calc_daily_ac_input_kwh", "mdi:calendar-today", True),
    ]
    for src, name_sfx, u_sfx, icon, is_d in calc_energy_specs:
        entities.append(
            OukitelCalculatedEnergySensor(
                coordinator,
                client,
                source_key=src,
                name_suffix=name_sfx,
                unique_suffix=u_sfx,
                icon=icon,
                is_daily=is_d,
                enabled_default=True,
            )
        )

    # 2. Calculated Financial Sensors - Charging Cost, Solar Savings & Net Balance
    hass_curr = getattr(hass.config, "currency", "EUR")
    default_curr = "€" if hass_curr == "EUR" else (hass_curr or DEFAULT_CURRENCY)
    currency = (
        entry.options.get(CONF_CURRENCY)
        or entry.data.get(CONF_CURRENCY)
        or default_curr
    )

    calc_savings_specs = [
        (f"Daily Charging Cost ({currency})", "calc_daily_charging_cost_eur", "daily", "charging_cost", "mdi:cash-minus"),
        (f"Monthly Charging Cost ({currency})", "calc_monthly_charging_cost_eur", "monthly", "charging_cost", "mdi:cash-minus"),
        (f"Daily Solar Savings ({currency})", "calc_daily_savings_eur", "daily", "solar_savings", "mdi:cash-plus"),
        (f"Monthly Solar Savings ({currency})", "calc_monthly_savings_eur", "monthly", "solar_savings", "mdi:cash-plus"),
        (f"Daily Net Savings ({currency})", "calc_daily_net_savings_eur", "daily", "net_savings", "mdi:scale-balance"),
        (f"Lifetime Solar Savings ({currency})", "calc_lifetime_savings_eur", "lifetime", "solar_savings", "mdi:cash-multiple"),
        (f"Lifetime Charging Cost ({currency})", "calc_lifetime_charging_cost_eur", "lifetime", "charging_cost", "mdi:cash-refund"),
    ]
    for name_sfx, u_sfx, period, m_kind, m_icon in calc_savings_specs:
        entities.append(
            OukitelCalculatedSavingsSensor(
                coordinator,
                client,
                name_suffix=name_sfx,
                unique_suffix=u_sfx,
                period_type=period,
                metric_kind=m_kind,
                icon=m_icon,
                price_sensor=price_sensor,
                fixed_price=float(fixed_price or DEFAULT_FIXED_PRICE),
                currency=currency,
                enabled_default=True,
            )
        )

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


class OukitelInverterIdlePowerSensor(CoordinatorEntity, SensorEntity):
    """Calculated standby / idle consumption of the AC inverter in Watts."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:power-sleep"
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: OukitelDataCoordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self._attr_name = f"{client.device_name} Inverter Idle Power"
        self._attr_unique_id = f"oukitel_{client.device_key}_inverter_idle_power"

    @property
    def device_info(self) -> DeviceInfo:
        return _build_calculated_device_info(self.coordinator, self.client)

    @property
    def native_value(self) -> float:
        if not self.coordinator.data or self.coordinator.is_paused:
            return 0.0
        ac_switch = bool(self.coordinator.data.get("ac_switch", False))
        if not ac_switch:
            return 0.0
        return 18.0

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data or self.coordinator.is_paused:
            return {}
        ac_switch = bool(self.coordinator.data.get("ac_switch", False))
        ac_out = float(self.coordinator.data.get("ac_output_power") or 0.0)
        return {
            "ac_switch": "ON" if ac_switch else "OFF",
            "inverter_state": "Standby (Idle)" if (ac_switch and ac_out <= 5.0) else ("Inverting" if ac_switch else "Off"),
            "nominal_idle_draw_w": 18.0,
        }


class OukitelInverterEfficiencySensor(CoordinatorEntity, SensorEntity):
    """Real-time calculated efficiency percentage of the AC inverter."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:gauge"
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: OukitelDataCoordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self._attr_name = f"{client.device_name} Inverter Efficiency"
        self._attr_unique_id = f"oukitel_{client.device_key}_inverter_efficiency"

    @property
    def device_info(self) -> DeviceInfo:
        return _build_calculated_device_info(self.coordinator, self.client)

    @property
    def native_value(self) -> float:
        if not self.coordinator.data or self.coordinator.is_paused:
            return 0.0
        ac_switch = bool(self.coordinator.data.get("ac_switch", False))
        if not ac_switch:
            return 0.0

        ac_out = float(self.coordinator.data.get("ac_output_power") or 0.0)
        if ac_out <= 5.0:
            return 0.0

        ac_in = float(self.coordinator.data.get("ac_input") or 0.0)

        # 1. UPS Bypass mode: AC mains feeds loads directly through bypass relay
        if ac_in > 10.0 and ac_in >= (ac_out - 15.0):
            return round(min(98.5, max(95.0, (ac_out / (ac_out + 3.5)) * 100.0)), 1)

        # 2. Inverting mode (DC bus / Battery / Solar to AC):
        # Calibrated quadratic loss model for Oukitel bidirectional inverter
        p_loss = 18.0 + (0.035 * ac_out) + (0.000025 * (ac_out ** 2))
        p_in = ac_out + p_loss
        eff = (ac_out / p_in) * 100.0
        return round(min(93.5, max(10.0, eff)), 1)

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data or self.coordinator.is_paused:
            return {}
        ac_switch = bool(self.coordinator.data.get("ac_switch", False))
        ac_out = float(self.coordinator.data.get("ac_output_power") or 0.0)
        ac_in = float(self.coordinator.data.get("ac_input") or 0.0)
        is_bypass = ac_switch and (ac_in > 10.0 and ac_in >= (ac_out - 15.0))
        return {
            "mode": "Bypass (Grid Passthrough)" if is_bypass else ("Inverting (Battery/Solar)" if ac_switch else "Off"),
            "ac_output_power_w": ac_out,
        }


class OukitelInverterLossPowerSensor(CoordinatorEntity, SensorEntity):
    """Real-time calculated internal power loss of the AC inverter in Watts."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:fire-alert"
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: OukitelDataCoordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self._attr_name = f"{client.device_name} Inverter Loss Power"
        self._attr_unique_id = f"oukitel_{client.device_key}_inverter_loss_power"

    @property
    def device_info(self) -> DeviceInfo:
        return _build_calculated_device_info(self.coordinator, self.client)

    @property
    def native_value(self) -> float:
        if not self.coordinator.data or self.coordinator.is_paused:
            return 0.0
        ac_switch = bool(self.coordinator.data.get("ac_switch", False))
        if not ac_switch:
            return 0.0

        ac_out = float(self.coordinator.data.get("ac_output_power") or 0.0)
        if ac_out <= 5.0:
            return 18.0

        ac_in = float(self.coordinator.data.get("ac_input") or 0.0)
        if ac_in > 10.0 and ac_in >= (ac_out - 15.0):
            return round(min(25.0, max(2.0, ac_out * 0.015)), 1)

        p_loss = 18.0 + (0.035 * ac_out) + (0.000025 * (ac_out ** 2))
        return round(p_loss, 1)


class OukitelBatteryCyclesSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Cumulative battery full equivalent cycles (IEC 62620 standard)."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_icon = "mdi:battery-sync"
    _attr_native_unit_of_measurement = "cycles"
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: OukitelDataCoordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self._attr_name = f"{client.device_name} Battery Equivalent Cycles"
        self._attr_unique_id = f"oukitel_{client.device_key}_battery_cycles_count"
        self._capacity_wh = _get_battery_capacity_wh(client)
        self._cycles: float = 0.0
        self._last_time: float | None = None
        self._last_power: float | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return _build_calculated_device_info(self.coordinator, self.client)

    @property
    def native_value(self) -> float:
        return round(self._cycles, 2)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "nominal_capacity_wh": self._capacity_wh,
            "total_discharged_kwh": round(self._cycles * (self._capacity_wh / 1000.0), 3),
            "rated_cycle_life": 3500,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._cycles = float(last_state.state)
            except ValueError:
                self._cycles = 0.0

    def _handle_coordinator_update(self) -> None:
        cur_time = time.monotonic()
        if not self.coordinator.data or self.coordinator.is_paused:
            self._last_time = cur_time
            self.async_write_ha_state()
            return

        batt_p = float(self.coordinator.data.get("battery_power") or 0.0)
        if batt_p <= 0:
            tot_in = float(self.coordinator.data.get("total_input_power") or 0.0)
            tot_out = float(self.coordinator.data.get("total_output_power") or 0.0)
            ac_in = float(self.coordinator.data.get("ac_input") or 0.0)
            if ac_in <= 10.0 and tot_out > tot_in:
                batt_p = max(0.0, tot_out - tot_in)
            else:
                batt_p = 0.0

        if self._last_time is not None and self._last_power is not None:
            delta_s = cur_time - self._last_time
            if 0 < delta_s < 120.0 and (self._last_power > 0 or batt_p > 0):
                avg_watts = (self._last_power + batt_p) / 2.0
                delta_wh = (avg_watts * delta_s) / 3600.0
                delta_cycles = delta_wh / self._capacity_wh
                self._cycles += delta_cycles

        self._last_time = cur_time
        self._last_power = batt_p
        self.async_write_ha_state()


class OukitelBatteryHealthSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Estimated Battery State of Health (SoH %) based on LiFePO4 cycle degradation."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:battery-heart-variant"
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: OukitelDataCoordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self._attr_name = f"{client.device_name} Battery Health (SoH)"
        self._attr_unique_id = f"oukitel_{client.device_key}_battery_state_of_health_estimated"
        self._capacity_wh = _get_battery_capacity_wh(client)
        self._soh: float = 100.0

    @property
    def device_info(self) -> DeviceInfo:
        return _build_calculated_device_info(self.coordinator, self.client)

    @property
    def native_value(self) -> float:
        return round(self._soh, 1)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "battery_chemistry": "LiFePO4 (LFP)",
            "rated_cycles_to_80_pct": 3500,
            "health_status": "Excellent" if self._soh >= 95.0 else ("Good" if self._soh >= 88.0 else "Fair"),
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._soh = float(last_state.state)
            except ValueError:
                self._soh = 100.0

    def _handle_coordinator_update(self) -> None:
        if self.hass:
            cycle_entity_id = f"sensor.oukitel_{self.client.device_key}_battery_cycles_count"
            st = self.hass.states.get(cycle_entity_id)
            if st and st.state not in (None, "unknown", "unavailable"):
                try:
                    cycles = float(st.state)
                    loss = cycles * (20.0 / 3500.0)
                    self._soh = max(80.0, min(100.0, 100.0 - loss))
                except ValueError:
                    pass
        self.async_write_ha_state()


class OukitelDaysSinceFullChargeSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Days since last 100% full charge for LiFePO4 cell balancing and calibration."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:calendar-clock"
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: OukitelDataCoordinator, client) -> None:
        super().__init__(coordinator)
        self.client = client
        self._attr_name = f"{client.device_name} Days Since Full Charge"
        self._attr_unique_id = f"oukitel_{client.device_key}_days_since_last_full_charge"
        self._last_full_charge_ts: float = time.time()

    @property
    def device_info(self) -> DeviceInfo:
        return _build_calculated_device_info(self.coordinator, self.client)

    @property
    def native_value(self) -> float:
        now_ts = time.time()
        elapsed_s = max(0.0, now_ts - self._last_full_charge_ts)
        return round(elapsed_s / 86400.0, 1)

    @property
    def extra_state_attributes(self) -> dict:
        days = self.native_value
        return {
            "last_full_charge_timestamp": dt_util.utc_from_timestamp(self._last_full_charge_ts).isoformat(),
            "calibration_needed": days >= 30.0,
            "recommended_action": "BMS calibrated and balanced" if days < 30.0 else "Charge to 100% to calibrate cell balance",
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.attributes:
            iso_ts = last_state.attributes.get("last_full_charge_timestamp")
            if iso_ts:
                try:
                    parsed = dt_util.parse_datetime(iso_ts)
                    if parsed:
                        self._last_full_charge_ts = parsed.timestamp()
                except Exception:
                    pass

    def _handle_coordinator_update(self) -> None:
        if not self.coordinator.data or self.coordinator.is_paused:
            self.async_write_ha_state()
            return

        batt = self.coordinator.data.get("battery_percentage")
        try:
            if batt is not None and float(batt) >= 100.0:
                self._last_full_charge_ts = time.time()
        except (ValueError, TypeError):
            pass

        self.async_write_ha_state()


class OukitelCalculatedEnergySensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Calculated energy sensor using trapezoidal Riemann integration in kWh."""

    def __init__(
        self,
        coordinator: OukitelDataCoordinator,
        client,
        source_key: str,
        name_suffix: str,
        unique_suffix: str,
        icon: str,
        is_daily: bool = False,
        enabled_default: bool = True,
    ):
        super().__init__(coordinator)
        self.client = client
        self._source_key = source_key
        self._is_daily = is_daily
        self._attr_name = f"{client.device_name} {name_suffix}"
        self._attr_unique_id = f"oukitel_{client.device_key}_{unique_suffix}"
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL if is_daily else SensorStateClass.TOTAL_INCREASING
        self._attr_icon = icon
        self._attr_suggested_display_precision = 3
        self._attr_entity_registry_enabled_default = enabled_default

        self._state: float = 0.0
        self._last_time: float | None = None
        self._last_power: float | None = None
        self._last_reset_day: int | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return _build_calculated_device_info(self.coordinator, self.client)

    @property
    def native_value(self) -> float:
        return round(self._state, 3)

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {}
        if self._is_daily:
            attrs["last_reset_day"] = self._last_reset_day
        return attrs

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._state = float(last_state.state)
            except ValueError:
                self._state = 0.0
        if last_state and last_state.attributes:
            self._last_reset_day = last_state.attributes.get("last_reset_day")

    def _get_current_power(self) -> float:
        if not self.coordinator.data:
            return 0.0
        if self._source_key == "battery_discharged":
            batt_p = float(self.coordinator.data.get("battery_power") or 0.0)
            if batt_p > 0:
                return batt_p
            tot_in = float(self.coordinator.data.get("total_input_power") or 0.0)
            tot_out = float(self.coordinator.data.get("total_output_power") or 0.0)
            ac_in = float(self.coordinator.data.get("ac_input") or 0.0)
            if ac_in <= 10.0 and tot_out > tot_in:
                return max(0.0, tot_out - tot_in)
            return 0.0
        val = self.coordinator.data.get(self._source_key)
        try:
            return max(0.0, float(val or 0.0))
        except (ValueError, TypeError):
            return 0.0

    def _handle_coordinator_update(self) -> None:
        now_dt = dt_util.now()
        cur_time = time.monotonic()

        if self._is_daily:
            if self._last_reset_day is None:
                self._last_reset_day = now_dt.day
            elif self._last_reset_day != now_dt.day:
                self._state = 0.0
                self._last_reset_day = now_dt.day

        current_power = self._get_current_power()

        if self._last_time is not None and self._last_power is not None:
            delta_s = cur_time - self._last_time
            if 0 < delta_s < 120.0:
                avg_watts = (self._last_power + current_power) / 2.0
                delta_kwh = (avg_watts * delta_s) / 3600000.0
                self._state += delta_kwh

        self._last_time = cur_time
        self._last_power = current_power
        self.async_write_ha_state()


class OukitelCalculatedSavingsSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """Calculated financial sensor: Charging Cost, Solar Savings, or Net Balance."""

    def __init__(
        self,
        coordinator: OukitelDataCoordinator,
        client,
        name_suffix: str,
        unique_suffix: str,
        period_type: str,
        metric_kind: str,
        icon: str,
        price_sensor: str,
        fixed_price: float,
        currency: str = DEFAULT_CURRENCY,
        enabled_default: bool = True,
    ):
        super().__init__(coordinator)
        self.client = client
        self._period_type = period_type
        self._metric_kind = metric_kind
        self._price_sensor = price_sensor
        self._fixed_price = fixed_price
        self._currency = currency
        self._attr_name = f"{client.device_name} {name_suffix}"
        self._attr_unique_id = f"oukitel_{client.device_key}_{unique_suffix}"
        self._attr_native_unit_of_measurement = currency
        self._attr_device_class = SensorDeviceClass.MONETARY
        self._attr_state_class = SensorStateClass.TOTAL if period_type in ("daily", "monthly") else SensorStateClass.TOTAL_INCREASING
        self._attr_icon = icon
        self._attr_suggested_display_precision = 2
        self._attr_entity_registry_enabled_default = enabled_default

        self._state: float = 0.0
        self._last_time: float | None = None
        self._last_power: float | None = None
        self._last_reset_day: int | None = None
        self._last_reset_month: int | None = None

    @property
    def device_info(self) -> DeviceInfo:
        return _build_calculated_device_info(self.coordinator, self.client)

    @property
    def native_value(self) -> float:
        return round(self._state, 2)

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {
            "metric_kind": self._metric_kind,
            "currency": self._currency,
            "price_sensor_configured": self._price_sensor or "None (Fixed fallback)",
            "effective_price_per_kwh": self._get_current_price(),
        }
        if self._period_type == "daily":
            attrs["last_reset_day"] = self._last_reset_day
        elif self._period_type == "monthly":
            attrs["last_reset_month"] = self._last_reset_month
        return attrs

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._state = float(last_state.state)
            except ValueError:
                self._state = 0.0
        if last_state and last_state.attributes:
            self._last_reset_day = last_state.attributes.get("last_reset_day")
            self._last_reset_month = last_state.attributes.get("last_reset_month")

    def _get_current_price(self) -> float:
        if self._price_sensor and self.hass:
            st = self.hass.states.get(self._price_sensor)
            if st and st.state not in (None, "unknown", "unavailable"):
                try:
                    price_val = float(st.state)
                    unit = str(st.attributes.get("unit_of_measurement", "")).lower()
                    if "c" in unit or "cent" in unit:
                        return price_val / 100.0
                    return price_val
                except (ValueError, TypeError):
                    pass
        return self._fixed_price

    def _get_metric_power(self) -> float:
        if not self.coordinator.data:
            return 0.0
        dc_solar = max(0.0, float(self.coordinator.data.get("dc_input") or 0.0))
        ac_in = max(0.0, float(self.coordinator.data.get("ac_input") or 0.0))

        if self._metric_kind == "charging_cost":
            return ac_in
        elif self._metric_kind == "solar_savings":
            return dc_solar
        elif self._metric_kind == "net_savings":
            return dc_solar - ac_in
        return 0.0

    def _handle_coordinator_update(self) -> None:
        now_dt = dt_util.now()
        cur_time = time.monotonic()

        if self._period_type == "daily":
            if self._last_reset_day is None:
                self._last_reset_day = now_dt.day
            elif self._last_reset_day != now_dt.day:
                self._state = 0.0
                self._last_reset_day = now_dt.day

        if self._period_type == "monthly":
            if self._last_reset_month is None:
                self._last_reset_month = now_dt.month
            elif self._last_reset_month != now_dt.month:
                self._state = 0.0
                self._last_reset_month = now_dt.month

        current_w = self._get_metric_power()
        cur_price = self._get_current_price()

        if self._last_time is not None and self._last_power is not None:
            delta_s = cur_time - self._last_time
            if 0 < delta_s < 120.0:
                avg_watts = (self._last_power + current_w) / 2.0
                delta_kwh = (avg_watts * delta_s) / 3600000.0
                self._state += delta_kwh * cur_price

        self._last_time = cur_time
        self._last_power = current_w
        self.async_write_ha_state()

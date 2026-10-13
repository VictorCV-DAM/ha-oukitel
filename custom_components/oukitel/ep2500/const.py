"""Constants for the Oukitel EP2500 Balcony Energy Storage system."""

from dataclasses import dataclass
from typing import Any, Optional
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)

# Configuration Keys
CONF_DEVICE_FAMILY = "device_family"
FAMILY_PORTABLE = "portable"
FAMILY_EP2500 = "ep2500"

CONF_EP2500_ID = "ep2500_device_id"
CONF_EP2500_KEY = "ep2500_local_key"
CONF_EP2500_HOST = "ep2500_host"
CONF_EP2500_PORT = "ep2500_port"

DEFAULT_EP2500_PORT = 6668
DEFAULT_EP2500_POLL_INTERVAL = 10
TUYA_PROTOCOL_VERSION = 3.5

# Hardware Limits
LIMIT_FEED_IN_MIN = 0
LIMIT_FEED_IN_MAX = 2500  # W (EU grid regulation allows up to 800W, hardware inverter up to 2500W)
LIMIT_CHARGE_MIN = 0
LIMIT_CHARGE_MAX = 4000   # W (Solar MPPT total + Grid)
SOC_MIN_ALLOWED = 0
SOC_MAX_ALLOWED = 100

# Tuya DataPoints (DPs) mapped for Oukitel EP2500 (Model WXY001)
DP_SOC = "102"
DP_OPERATING_MODE = "117"
DP_ANTI_BACKFLOW = "118"
DP_OFFGRID_OUTLET = "119"
DP_ANTI_BACKFLOW_REG = "120"
DP_MAX_FEED_IN_POWER = "121"
DP_MAX_BATTERY_CHARGE_POWER = "122"
DP_SOC_CHARGE_STOP = "123"
DP_SOC_DISCHARGE_STOP = "124"
DP_PV_ENERGY_TODAY = "125"
DP_PV_ENERGY_TOTAL = "126"
DP_BATTERY_VOLTAGE = "127"
DP_BATTERY_POWER = "128"
DP_CELL_VOLTAGE_MAX = "130"
DP_CELL_VOLTAGE_MIN = "131"
DP_TEMPERATURE_1 = "132"
DP_TEMPERATURE_2 = "133"
DP_STATUS = "134"
DP_OFFGRID_VOLTAGE = "135"
DP_GRID_CURRENT = "136"
DP_GRID_POWER = "137"
DP_GRID_FREQUENCY = "138"
DP_GRID_VOLTAGE = "139"
DP_OFFGRID_CURRENT = "140"
DP_OFFGRID_LOAD = "141"
DP_OFFGRID_LOAD_2 = "142"
DP_PV_TOTAL_POWER = "143"
DP_SYSTEM_FAULT = "149"
DP_PV1_POWER = "147"
DP_PV1_VOLTAGE = "148"
DP_PV1_CURRENT = "150"
DP_PV3_POWER = "151"
DP_AC_OUTPUT_POWER = "155"
DP_PV_CHARGE_LIMIT = "156"
DP_PV3_CURRENT = "163"
DP_PV2_POWER = "164"
DP_PV2_VOLTAGE = "178"
DP_PV2_CURRENT = "179"
DP_PV4_POWER = "180"
DP_PV4_VOLTAGE = "181"
DP_PV4_CURRENT = "182"
DP_PV3_VOLTAGE = "183"


@dataclass(frozen=True)
class EP2500SensorEntityDescription:
    """Metadata for an EP2500 sensor."""
    dp: str
    key: str
    name: str
    native_unit_of_measurement: Optional[str] = None
    device_class: Optional[SensorDeviceClass] = None
    state_class: Optional[SensorStateClass] = None
    scale_factor: float = 1.0
    suggested_display_precision: Optional[int] = None
    icon: Optional[str] = None


# Sensors Definition
EP2500_SENSORS: list[EP2500SensorEntityDescription] = [
    # Battery & System State
    EP2500SensorEntityDescription(
        dp=DP_SOC,
        key="ep2500_soc",
        name="State of Charge",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:battery-high",
    ),
    EP2500SensorEntityDescription(
        dp=DP_BATTERY_POWER,
        key="ep2500_battery_power",
        name="Battery Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:battery-charging",
    ),
    EP2500SensorEntityDescription(
        dp=DP_BATTERY_VOLTAGE,
        key="ep2500_battery_voltage",
        name="Battery Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.01,
        suggested_display_precision=2,
        icon="mdi:sine-wave",
    ),
    EP2500SensorEntityDescription(
        dp=DP_CELL_VOLTAGE_MAX,
        key="ep2500_cell_voltage_max",
        name="Cell Voltage Max",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:battery-arrow-up",
    ),
    EP2500SensorEntityDescription(
        dp=DP_CELL_VOLTAGE_MIN,
        key="ep2500_cell_voltage_min",
        name="Cell Voltage Min",
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:battery-arrow-down",
    ),
    EP2500SensorEntityDescription(
        dp=DP_TEMPERATURE_1,
        key="ep2500_temperature_1",
        name="Battery Temperature 1",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.1,
        suggested_display_precision=1,
        icon="mdi:thermometer",
    ),
    EP2500SensorEntityDescription(
        dp=DP_TEMPERATURE_2,
        key="ep2500_temperature_2",
        name="Battery Temperature 2",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.1,
        suggested_display_precision=1,
        icon="mdi:thermometer",
    ),

    # AC & Grid Power
    EP2500SensorEntityDescription(
        dp=DP_AC_OUTPUT_POWER,
        key="ep2500_ac_output_power",
        name="AC Output Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:transmission-tower-export",
    ),
    EP2500SensorEntityDescription(
        dp=DP_GRID_POWER,
        key="ep2500_grid_power",
        name="Grid Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:transmission-tower",
    ),
    EP2500SensorEntityDescription(
        dp=DP_GRID_VOLTAGE,
        key="ep2500_grid_voltage",
        name="Grid Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.1,
        suggested_display_precision=1,
        icon="mdi:sine-wave",
    ),
    EP2500SensorEntityDescription(
        dp=DP_GRID_CURRENT,
        key="ep2500_grid_current",
        name="Grid Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.1,
        suggested_display_precision=1,
        icon="mdi:current-ac",
    ),
    EP2500SensorEntityDescription(
        dp=DP_GRID_FREQUENCY,
        key="ep2500_grid_frequency",
        name="Grid Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.01,
        suggested_display_precision=2,
        icon="mdi:sine-wave",
    ),

    # Solar PV Overview & Energy
    EP2500SensorEntityDescription(
        dp=DP_PV_TOTAL_POWER,
        key="ep2500_pv_total_power",
        name="Total Solar Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:solar-power-variant",
    ),
    EP2500SensorEntityDescription(
        dp=DP_PV_ENERGY_TODAY,
        key="ep2500_pv_energy_today",
        name="Solar Energy Today",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:solar-power",
    ),
    EP2500SensorEntityDescription(
        dp=DP_PV_ENERGY_TOTAL,
        key="ep2500_pv_energy_total",
        name="Solar Energy Lifetime",
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:counter",
    ),

    # MPPT 1
    EP2500SensorEntityDescription(
        dp=DP_PV1_POWER,
        key="ep2500_pv1_power",
        name="Solar String 1 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:solar-panel",
    ),
    EP2500SensorEntityDescription(
        dp=DP_PV1_VOLTAGE,
        key="ep2500_pv1_voltage",
        name="Solar String 1 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.1,
        suggested_display_precision=1,
        icon="mdi:lightning-bolt",
    ),
    EP2500SensorEntityDescription(
        dp=DP_PV1_CURRENT,
        key="ep2500_pv1_current",
        name="Solar String 1 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.01,
        suggested_display_precision=2,
        icon="mdi:current-dc",
    ),

    # MPPT 2
    EP2500SensorEntityDescription(
        dp=DP_PV2_POWER,
        key="ep2500_pv2_power",
        name="Solar String 2 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:solar-panel",
    ),
    EP2500SensorEntityDescription(
        dp=DP_PV2_VOLTAGE,
        key="ep2500_pv2_voltage",
        name="Solar String 2 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.1,
        suggested_display_precision=1,
        icon="mdi:lightning-bolt",
    ),
    EP2500SensorEntityDescription(
        dp=DP_PV2_CURRENT,
        key="ep2500_pv2_current",
        name="Solar String 2 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.01,
        suggested_display_precision=2,
        icon="mdi:current-dc",
    ),

    # MPPT 3
    EP2500SensorEntityDescription(
        dp=DP_PV3_POWER,
        key="ep2500_pv3_power",
        name="Solar String 3 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:solar-panel",
    ),
    EP2500SensorEntityDescription(
        dp=DP_PV3_VOLTAGE,
        key="ep2500_pv3_voltage",
        name="Solar String 3 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.1,
        suggested_display_precision=1,
        icon="mdi:lightning-bolt",
    ),
    EP2500SensorEntityDescription(
        dp=DP_PV3_CURRENT,
        key="ep2500_pv3_current",
        name="Solar String 3 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.01,
        suggested_display_precision=2,
        icon="mdi:current-dc",
    ),

    # MPPT 4
    EP2500SensorEntityDescription(
        dp=DP_PV4_POWER,
        key="ep2500_pv4_power",
        name="Solar String 4 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:solar-panel",
    ),
    EP2500SensorEntityDescription(
        dp=DP_PV4_VOLTAGE,
        key="ep2500_pv4_voltage",
        name="Solar String 4 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.1,
        suggested_display_precision=1,
        icon="mdi:lightning-bolt",
    ),
    EP2500SensorEntityDescription(
        dp=DP_PV4_CURRENT,
        key="ep2500_pv4_current",
        name="Solar String 4 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.01,
        suggested_display_precision=2,
        icon="mdi:current-dc",
    ),

    # Off-Grid Output
    EP2500SensorEntityDescription(
        dp=DP_OFFGRID_LOAD,
        key="ep2500_offgrid_power",
        name="Off-Grid Output Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:power-socket-eu",
    ),
    EP2500SensorEntityDescription(
        dp=DP_OFFGRID_VOLTAGE,
        key="ep2500_offgrid_voltage",
        name="Off-Grid Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.1,
        suggested_display_precision=1,
        icon="mdi:sine-wave",
    ),
    EP2500SensorEntityDescription(
        dp=DP_OFFGRID_CURRENT,
        key="ep2500_offgrid_current",
        name="Off-Grid Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        scale_factor=0.1,
        suggested_display_precision=1,
        icon="mdi:current-ac",
    ),

    # Operational Diagnostic Sensors
    EP2500SensorEntityDescription(
        dp=DP_STATUS,
        key="ep2500_status",
        name="Operational Status",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        scale_factor=1.0,
        suggested_display_precision=None,
        icon="mdi:information-outline",
    ),
    EP2500SensorEntityDescription(
        dp=DP_OPERATING_MODE,
        key="ep2500_operating_mode",
        name="Operating Mode",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        scale_factor=1.0,
        suggested_display_precision=None,
        icon="mdi:tune",
    ),
    EP2500SensorEntityDescription(
        dp=DP_SYSTEM_FAULT,
        key="ep2500_system_fault",
        name="System Fault Code",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
        scale_factor=1.0,
        suggested_display_precision=0,
        icon="mdi:alert-circle-outline",
    ),
]

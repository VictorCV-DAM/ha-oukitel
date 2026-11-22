import asyncio
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Mock homeassistant namespace so unit tests can run in environments without HA installed
if "homeassistant" not in sys.modules:
    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    sys.modules["homeassistant"] = ha
else:
    ha = sys.modules["homeassistant"]

if "homeassistant.components" not in sys.modules:
    components = types.ModuleType("homeassistant.components")
    components.__path__ = []
    sys.modules["homeassistant.components"] = components
    ha.components = components
else:
    components = sys.modules["homeassistant.components"]

class CoordinatorEntity:
    def __init__(self, coordinator=None):
        self.coordinator = coordinator

class RestoreEntity:
    pass

class SensorEntity:
    pass

class BinarySensorEntity:
    pass

if "homeassistant.components.binary_sensor" not in sys.modules:
    bs = types.ModuleType("homeassistant.components.binary_sensor")
    bs.BinarySensorDeviceClass = MagicMock()
    bs.BinarySensorEntity = BinarySensorEntity
    sys.modules["homeassistant.components.binary_sensor"] = bs
    components.binary_sensor = bs

if "homeassistant.components.sensor" not in sys.modules:
    sensor = types.ModuleType("homeassistant.components.sensor")
    sensor.SensorDeviceClass = MagicMock()
    sensor.SensorEntity = SensorEntity
    sensor.SensorStateClass = MagicMock()
    sys.modules["homeassistant.components.sensor"] = sensor
    components.sensor = sensor

if "homeassistant.helpers" not in sys.modules:
    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sys.modules["homeassistant.helpers"] = helpers
    ha.helpers = helpers
else:
    helpers = sys.modules["homeassistant.helpers"]

for hname in ["entity", "entity_platform", "restore_state", "device_registry", "update_coordinator"]:
    if f"homeassistant.helpers.{hname}" not in sys.modules:
        mod = MagicMock()
        sys.modules[f"homeassistant.helpers.{hname}"] = mod
        setattr(helpers, hname, mod)
    else:
        setattr(helpers, hname, sys.modules[f"homeassistant.helpers.{hname}"])

helpers.update_coordinator.CoordinatorEntity = CoordinatorEntity
helpers.restore_state.RestoreEntity = RestoreEntity

for name in ["config_entries", "const", "core", "exceptions", "util"]:
    if f"homeassistant.{name}" not in sys.modules:
        mod = MagicMock()
        sys.modules[f"homeassistant.{name}"] = mod
        setattr(ha, name, mod)
    else:
        setattr(ha, name, sys.modules[f"homeassistant.{name}"])

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

COMPONENT = REPO_ROOT / "custom_components" / "oukitel"
if str(COMPONENT) not in sys.path:
    sys.path.insert(0, str(COMPONENT))

from custom_components.oukitel.binary_sensor import OukitelOnBatteryBinarySensor  # noqa: E402
from custom_components.oukitel.cloud_bridge import CloudBridge  # noqa: E402


class MockCoordinator:
    def __init__(self, data=None):
        self.data = data or {}
        self.is_paused = False
        self.hass = MagicMock()


class MockClient:
    device_key = "test_device_key"
    product_key = "test_product"
    device_name = "Oukitel Test"
    product_name = "P1000E Plus"


class OnBatterySensorTests(unittest.TestCase):
    def setUp(self):
        self.client = MockClient()

    def test_mains_ups_bypass_no_flutter(self):
        """In UPS bypass mode (mains connected with AC load), sensor must stay False regardless of load fluctuations."""
        coord = MockCoordinator({
            "total_input_power": 700.0,
            "total_output_power": 700.0,
            "ac_input": 700.0,
            "dc_input": 0.0,
            "ac_output_power": 700.0,
            "dc_output_power": 0.0,
        })
        sensor = OukitelOnBatteryBinarySensor(coord, self.client)
        self.assertFalse(sensor.is_on)

        # Fluctuation where load spikes by 25W due to inverter/server activity
        coord.data["ac_output_power"] = 725.0
        coord.data["total_output_power"] = 725.0
        self.assertFalse(sensor.is_on)

        # Fluctuation where input reads slightly lower
        coord.data["ac_input"] = 690.0
        coord.data["total_input_power"] = 690.0
        self.assertFalse(sensor.is_on)

    def test_mains_unplugged_triggers_battery_mode(self):
        """When mains cable is disconnected (ac_in drops to 0), sensor switches to True."""
        coord = MockCoordinator({
            "total_input_power": 0.0,
            "total_output_power": 650.0,
            "ac_input": 0.0,
            "dc_input": 0.0,
            "ac_output_power": 650.0,
            "dc_output_power": 0.0,
        })
        sensor = OukitelOnBatteryBinarySensor(coord, self.client)
        self.assertTrue(sensor.is_on)

    def test_solar_offgrid_behavior(self):
        """When offgrid, solar > load + margin keeps sensor False, load > solar + margin turns sensor True."""
        # Solar exceeds load
        coord = MockCoordinator({
            "total_input_power": 250.0,
            "total_output_power": 100.0,
            "ac_input": 0.0,
            "dc_input": 250.0,
            "ac_output_power": 100.0,
            "dc_output_power": 0.0,
        })
        sensor = OukitelOnBatteryBinarySensor(coord, self.client)
        self.assertFalse(sensor.is_on)

        # Solar drops, load exceeds solar -> battery discharges
        coord.data["dc_input"] = 50.0
        coord.data["total_input_power"] = 50.0
        coord.data["ac_output_power"] = 200.0
        coord.data["total_output_power"] = 200.0
        self.assertTrue(sensor.is_on)


class CloudBridgeDisconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_client_keeps_server_alive(self):
        """disconnect_client must close client connection but leave listening server active."""
        hass = MagicMock()
        mock_task = MagicMock()
        hass.async_create_background_task.return_value = mock_task

        bridge = CloudBridge(hass, on_telemetry=MagicMock(), port=18886)
        mock_server = MagicMock()
        mock_server.close = MagicMock()
        bridge._server = mock_server

        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        bridge._writer = mock_writer
        bridge._connections.add(mock_writer)

        self.assertTrue(bridge.connected)

        bridge.disconnect_client()

        # Client writer closed and cleared
        mock_writer.close.assert_called_once()
        self.assertFalse(bridge.connected)
        self.assertEqual(len(bridge._connections), 0)

        # Listening server was NOT closed!
        mock_server.close.assert_not_called()
        self.assertIs(bridge._server, mock_server)


if __name__ == "__main__":
    unittest.main()

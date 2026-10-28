import sys
import types
import unittest
from unittest.mock import MagicMock
from pathlib import Path

# Mock homeassistant namespace so unit tests can run in environments without HA installed
if "homeassistant" not in sys.modules:
    ha = types.ModuleType("homeassistant")
    ha.__path__ = []
    sys.modules["homeassistant"] = ha
    sys.modules["homeassistant.config_entries"] = MagicMock()
    sys.modules["homeassistant.const"] = MagicMock()
    sys.modules["homeassistant.core"] = MagicMock()
    sys.modules["homeassistant.exceptions"] = MagicMock()
    sys.modules["homeassistant.helpers"] = MagicMock()
    sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()
    sys.modules["homeassistant.util"] = MagicMock()

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custom_components.oukitel.coordinator import OukitelDataCoordinator  # noqa: E402


class DummyClient:
    def __init__(self, product_key=None, product_name=None, device_name=None):
        self.product_key = product_key
        self.product_name = product_name
        self.device_name = device_name
        self.device_key = "test_key"


class DummyCoord(OukitelDataCoordinator):
    pass

    def __init__(self, client, lan_state=None, data=None):
        self.client = client
        self._use_struct_switch_protocol = None
        self._lan_state = lan_state or {}
        self.data = data or {}


class SwitchProtocolDetectionTests(unittest.TestCase):
    def test_bp2000_product_key_uses_struct(self):
        coord = DummyCoord(DummyClient(product_key="p11ssr"))
        self.assertTrue(coord._detect_switch_protocol())

    def test_bp2000_name_uses_struct(self):
        coord = DummyCoord(DummyClient(product_name="Oukitel BP2000 Pro"))
        self.assertTrue(coord._detect_switch_protocol())

    def test_p2001_plus_product_key_uses_flat(self):
        coord = DummyCoord(DummyClient(product_key="p11wn7"))
        self.assertFalse(coord._detect_switch_protocol())

    def test_p1000_plus_p11uve_uses_flat(self):
        """Regression test for Issue #8: p11uve (P1000 Plus / P1500 Plus) must use flat tags."""
        coord = DummyCoord(DummyClient(product_key="p11uve", product_name="P1000PLUS/P1500PLUS"))
        # Even if tag 6 is a dict in telemetry (as on all P-series stations)
        coord._lan_state = {6: {2: 400}}
        self.assertFalse(coord._detect_switch_protocol())

    def test_p2001_plus_g2_device_name_uses_flat(self):
        """Pete's station: 2001_plus_g2 must use flat tags."""
        coord = DummyCoord(DummyClient(device_name="2001_plus_g2_4362"))
        coord._lan_state = {6: {2: 450}, 9: {1: 0}}
        self.assertFalse(coord._detect_switch_protocol())

    def test_flat_tags_in_telemetry_force_flat(self):
        coord = DummyCoord(DummyClient(product_key="unknown"), lan_state={46: False})
        self.assertFalse(coord._detect_switch_protocol())

    def test_default_fallback_is_flat(self):
        coord = DummyCoord(DummyClient())
        self.assertFalse(coord._detect_switch_protocol())


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "oukitel"
sys.path.append(str(COMPONENT))

from device_selection import select_device  # noqa: E402

DEVICES = [
    {"deviceKey": "p1000", "deviceName": "Oukitel P1000E Plus"},
    {"deviceKey": "ieetek", "deviceName": "IEETek P1800"},
]


class DeviceSelectionTests(unittest.TestCase):
    def test_matching_key_wins(self):
        self.assertEqual(select_device(DEVICES, "ieetek"), DEVICES[1])

    def test_missing_key_with_multiple_devices_is_rejected(self):
        self.assertIsNone(select_device(DEVICES, "old-key"))

    def test_missing_key_with_single_device_is_accepted(self):
        self.assertEqual(select_device([DEVICES[0]], "old-key"), DEVICES[0])

    def test_legacy_name_match(self):
        self.assertEqual(
            select_device(DEVICES, None, "IEETek P1800"),
            DEVICES[1],
        )

    def test_legacy_unknown_name_with_multiple_devices_is_rejected(self):
        self.assertIsNone(select_device(DEVICES, None, "Unknown"))

    def test_no_key_or_name_falls_back_to_first(self):
        self.assertEqual(select_device(DEVICES), DEVICES[0])

    def test_empty_account(self):
        self.assertIsNone(select_device([], "p1000"))


if __name__ == "__main__":
    unittest.main()

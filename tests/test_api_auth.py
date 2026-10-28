import sys
import types
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import requests

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
    uc = types.ModuleType("homeassistant.helpers.update_coordinator")
    uc.DataUpdateCoordinator = type("DataUpdateCoordinator", (), {}); uc.UpdateFailed = type("UpdateFailed", (Exception,), {})
    sys.modules["homeassistant.helpers.update_coordinator"] = uc
    sys.modules["homeassistant.util"] = MagicMock()

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from custom_components.oukitel.api import (  # noqa: E402
    AcceleronixCloudClient,
    OukitelAuthError,
    OukitelConnectionError,
)


class ApiAuthTests(unittest.TestCase):
    def setUp(self):
        self.client = AcceleronixCloudClient("test@example.com", "secret", region="EU")
        self.client.device_key = "dev123"
        self.client.product_key = "prod123"

    @patch("requests.post")
    def test_login_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "code": 200,
            "data": {
                "accessToken": {"token": "acc_123", "expirationTime": 9999999999},
                "refreshToken": {"token": "ref_123"},
            },
        }
        mock_post.return_value = mock_resp
        self.assertTrue(self.client.login())
        self.assertEqual(self.client.access_token, "acc_123")

    @patch("requests.post")
    def test_login_auth_failure_raises_auth_error(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"code": 10001, "msg": "account or password incorrect"}
        mock_post.return_value = mock_resp
        with self.assertRaises(OukitelAuthError):
            self.client.login()

    @patch("requests.post")
    def test_login_network_error_raises_connection_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("DNS failure")
        with self.assertRaises(OukitelConnectionError):
            self.client.login()

    @patch("requests.get")
    def test_get_telemetry_single_retry_on_5032_then_success(self, mock_get):
        self.client.access_token = "old_token"
        self.client.token_expiry = 9999999999

        resp_5032 = MagicMock()
        resp_5032.json.return_value = {"code": 5032, "msg": "token expired"}

        resp_200 = MagicMock()
        resp_200.json.return_value = {
            "code": 200,
            "data": {
                "deviceData": {"isOnline": True, "signalStrength": -65},
                "customizeTslInfo": [
                    {
                        "key": "temp",
                        "resourceCode": "temp",
                        "resourceValce": "25",
                        "dataType": "INT",
                    }
                ],
            },
        }

        mock_get.side_effect = [resp_5032, resp_200]

        with patch.object(self.client, "login", return_value=True) as mock_login:
            res = self.client.get_telemetry()
            self.assertEqual(mock_login.call_count, 1)
            self.assertEqual(res.get("temp"), 25)

    @patch("requests.get")
    def test_get_telemetry_5032_raises_auth_error_no_infinite_recursion(self, mock_get):
        self.client.access_token = "old_token"
        self.client.token_expiry = 9999999999

        resp_5032 = MagicMock()
        resp_5032.json.return_value = {"code": 5032, "msg": "token invalid"}
        mock_get.return_value = resp_5032

        with patch.object(self.client, "login", return_value=True) as mock_login:
            with self.assertRaises(OukitelAuthError):
                self.client.get_telemetry()
            self.assertEqual(mock_login.call_count, 1)

    @patch("requests.get")
    def test_get_devices_list_5032_raises_auth_error_no_infinite_recursion(self, mock_get):
        self.client.access_token = "old_token"
        self.client.token_expiry = 9999999999

        resp_5032 = MagicMock()
        resp_5032.json.return_value = {"code": 5032, "msg": "token invalid"}
        mock_get.return_value = resp_5032

        with patch.object(self.client, "login", return_value=True) as mock_login:
            with self.assertRaises(OukitelAuthError):
                self.client.get_devices_list()
            self.assertEqual(mock_login.call_count, 1)

    @patch("requests.post")
    def test_control_device_5032_raises_auth_error_no_infinite_recursion(self, mock_post):
        self.client.access_token = "old_token"
        self.client.token_expiry = 9999999999

        resp_5032 = MagicMock()
        resp_5032.json.return_value = {"code": 5032, "msg": "token invalid"}
        mock_post.return_value = resp_5032

        with patch.object(self.client, "login", return_value=True) as mock_login:
            with self.assertRaises(OukitelAuthError):
                self.client.control_device([{"ac_switch": 1}])
            self.assertEqual(mock_login.call_count, 1)


if __name__ == "__main__":
    unittest.main()

"""Acceleronix / Quectel Cloud API client for Oukitel power stations."""

import asyncio
from base64 import b64encode
import hashlib
import json
import logging
import random
import string
import time
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import requests

from .const import REGION_SERVERS
from .device_selection import select_device

_LOGGER = logging.getLogger(__name__)


class OukitelError(Exception):
    """Base exception for Oukitel integration."""


class OukitelAuthError(OukitelError):
    """Authentication failure (e.g. invalid credentials or expired session)."""


class OukitelConnectionError(OukitelError):
    """Network connection or server communication error."""


class AcceleronixCloudClient:
    """Client to authenticate and interact with Acceleronix / Quectel Cloud API."""

    def __init__(
        self,
        email: str,
        password: str,
        region: str = "EU",
        device_key: str | None = None,
        device_name: str | None = None,
    ):
        self.email = email
        self.password = password
        self.region = region.upper() if region.upper() in REGION_SERVERS else "EU"

        reg_data = REGION_SERVERS[self.region]
        self.base_url = reg_data["base_url"]
        self.user_domain = reg_data["user_domain"]
        self.user_domain_secret = reg_data["user_domain_secret"]
        self.app_id = reg_data["appid"]
        self.app_version = reg_data["appversion"]

        self.access_token = None
        self.refresh_token = None
        self.token_expiry = 0
        self.device_key = device_key
        self.product_key = None
        self.device_name = device_name
        self.product_name = None
        self.auth_key = None
        self.is_online: bool = True

    def _parse_device_online_status(self, dev: dict) -> bool:
        """Parse online/offline status from userDeviceList response."""
        for key in ("onlineStatus", "isOnline", "deviceStatus", "online", "status"):
            if key in dev and dev[key] is not None:
                val = dev[key]
                if isinstance(val, bool):
                    return val
                if isinstance(val, (int, float)):
                    return int(val) == 1
                if isinstance(val, str):
                    return val.strip().lower() in ("1", "true", "online")
        return True

    def _encrypt_password(self, password: str, random_str: str) -> str:
        md5_hash = hashlib.md5(random_str.encode("utf-8")).hexdigest().upper()
        aes_key = md5_hash[8:24].encode("utf-8")
        iv = (md5_hash[16:24] + md5_hash[8:16]).encode("utf-8")
        cipher = AES.new(aes_key, AES.MODE_CBC, iv)
        padded = pad(password.encode("utf-8"), 16)
        return b64encode(cipher.encrypt(padded)).decode("utf-8")

    def _calculate_signature(self, email: str, pwd_b64: str, random_str: str) -> str:
        raw = email + pwd_b64 + random_str + self.user_domain_secret
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def login(self) -> bool:
        """Authenticate with Acceleronix / Quectel Cloud."""
        chars = string.ascii_letters + string.digits
        random_str = "".join(random.choice(chars) for _ in range(16))

        pwd_encrypted = self._encrypt_password(self.password, random_str)
        signature = self._calculate_signature(self.email, pwd_encrypted, random_str)

        url = f"{self.base_url}/v2/enduser/enduserapi/emailPwdLogin"
        headers = {
            "appversion": self.app_version,
            "appsystemtype": "android",
            "appid": self.app_id,
            "User-Agent": "okhttp/4.9.3",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        payload = {
            "email": self.email,
            "pwd": pwd_encrypted,
            "random": random_str,
            "userDomain": self.user_domain,
            "signature": signature,
        }

        try:
            r = requests.post(url, headers=headers, data=payload, timeout=15)
        except requests.RequestException as err:
            _LOGGER.error("oukitel: Network exception during login: %s", err)
            raise OukitelConnectionError(f"Connection error during login: {err}") from err
        except Exception as err:
            _LOGGER.error("oukitel: Exception during login: %s", err)
            raise OukitelConnectionError(f"Unexpected error during login: {err}") from err

        try:
            res = r.json()
        except Exception as err:
            _LOGGER.error("oukitel: Failed to decode login response JSON: %s", err)
            raise OukitelConnectionError(f"Invalid login response JSON: {err}") from err

        code = res.get("code")
        if code == 200:
            data = res["data"]
            self.access_token = data["accessToken"]["token"]
            self.token_expiry = data["accessToken"].get("expirationTime", int(time.time()) + 7000)
            self.refresh_token = data["refreshToken"]["token"]
            _LOGGER.debug("oukitel: Session authenticated successfully.")
            return True

        _LOGGER.error("oukitel: Login failed: %s (code %s)", res.get("msg"), code)
        raise OukitelAuthError(f"Login failed: {res.get('msg')} (code {code})")

    def ensure_authenticated(self):
        """Ensure token is valid; renew automatically if close to expiration."""
        if not self.access_token or time.time() > (self.token_expiry - 120):
            return self.login()
        return True

    def get_auth_headers(self) -> dict:
        return {
            "appversion": self.app_version,
            "appsystemtype": "android",
            "appid": self.app_id,
            "Authorization": self.access_token,
            "User-Agent": "okhttp/4.9.3",
        }

    def get_devices_list(self, retry_on_auth: bool = True) -> list[dict]:
        """Fetch all bound devices in the user account."""
        if retry_on_auth:
            self.ensure_authenticated()
        url = f"{self.base_url}/v2/binding/enduserapi/userDeviceList"
        try:
            r = requests.get(url, headers=self.get_auth_headers(), timeout=15)
            res = r.json()
            code = res.get("code")
            if code == 200:
                return res.get("data", {}).get("list", [])
            if code == 5032:
                if retry_on_auth:
                    _LOGGER.info("oukitel: Token expired (5032), refreshing login session...")
                    self.access_token = None
                    self.login()
                    return self.get_devices_list(retry_on_auth=False)
                raise OukitelAuthError("Authentication token expired and re-login failed (code 5032)")
            _LOGGER.error("oukitel: Error fetching devices list: %s (code %s)", res.get("msg"), code)
            return []
        except (OukitelAuthError, OukitelConnectionError):
            raise
        except requests.RequestException as err:
            _LOGGER.error("oukitel: Network error in get_devices_list: %s", err)
            raise OukitelConnectionError(f"Network error in get_devices_list: {err}") from err
        except Exception as err:
            _LOGGER.error("oukitel: Exception in get_devices_list: %s", err)
            return []

    def fetch_device_info(self) -> bool:
        """Fetch bound device key and product key for target device (or first available)."""
        devices = self.get_devices_list()
        if not devices:
            _LOGGER.error("oukitel: No bound devices found in account.")
            return False

        dev = select_device(devices, self.device_key, self.device_name)
        if dev is None:
            _LOGGER.error(
                "oukitel: Configured device %s is not in the account list; "
                "refusing to switch to another station",
                self.device_key,
            )
            return False

        self.device_key = dev["deviceKey"]
        self.product_key = dev["productKey"]
        self.device_name = dev.get("deviceName", "Oukitel P2001")
        self.product_name = dev.get("productName") or dev.get("deviceName", "Oukitel Power Station")
        self.auth_key = dev.get("authKey")
        self.is_online = self._parse_device_online_status(dev)
        _LOGGER.debug(
            "oukitel: Device ready — %s (%s), authKey present: %s, is_online: %s",
            self.device_name,
            self.device_key,
            bool(self.auth_key),
            self.is_online,
        )
        return True

    def regenerate_auth_key(self) -> str | None:
        """Fetch the CURRENT LAN authKey from the vendor cloud.

        This is the app's own authKey fetch. Unlike the copy embedded in
        ``userDeviceList``, it is not frozen at binding time on shared accounts.
        Repeated calls return the same key and do not disturb the vendor app.
        """
        self.ensure_authenticated()
        if not (self.product_key and self.device_key):
            return None
        url = f"{self.base_url}/v2/binding/enduserapi/regenerateAuthKey"
        try:
            response = requests.post(
                url,
                headers=self.get_auth_headers(),
                data={"pk": self.product_key, "dk": self.device_key},
                timeout=15,
            )
            payload = response.json()
        except Exception as err:  # noqa: BLE001 - cloud/transport failure is not fatal
            _LOGGER.warning("oukitel: regenerateAuthKey request failed: %s", err)
            return None
        if payload.get("code") != 200:
            _LOGGER.warning(
                "oukitel: regenerateAuthKey rejected: %s", payload.get("msg")
            )
            return None
        key = (payload.get("data") or {}).get("authKey")
        if not key:
            return None
        self.auth_key = key
        return key

    def refresh_auth_key(self) -> bool:
        """Refresh the LAN authKey, falling back to the device list."""
        if self.regenerate_auth_key():
            return True
        return self.fetch_device_info()

    def control_device(self, properties_list: list, retry_on_auth: bool = True) -> bool:
        """Send hardware control commands via batchControlDevice."""
        if retry_on_auth:
            self.ensure_authenticated()
        if not self.device_key or not self.product_key:
            if not self.fetch_device_info():
                return False

        url = f"{self.base_url}/v2/binding/enduserapi/batchControlDevice"
        headers = {**self.get_auth_headers(), "Content-Type": "application/json"}
        payload = {
            "data": json.dumps(properties_list),
            "deviceList": [{"deviceKey": self.device_key, "productKey": self.product_key}],
            "cacheTime": 60,
            "isCache": 1,
            "isCover": 1,
            "dataFormat": 0,
            "type": 2,
        }

        try:
            r = requests.post(url, headers=headers, json=payload, timeout=12)
            res = r.json()
            code = res.get("code")

            if code == 200:
                _LOGGER.debug("oukitel: Cloud command succeeded: %s", properties_list)
                return True
            if code == 5032:
                if retry_on_auth:
                    _LOGGER.info("oukitel: Token expired (5032) during control_device, refreshing session...")
                    self.access_token = None
                    self.login()
                    return self.control_device(properties_list, retry_on_auth=False)
                raise OukitelAuthError("Authentication token expired and re-login failed during device control (code 5032)")
            if code == 5340:
                _LOGGER.warning(
                    "oukitel: Cloud control transient timeout/batch ACK delay (code 5340): %s — verification needed",
                    res.get("msg"),
                )
                return False
            _LOGGER.error("oukitel: Cloud control error: %s (code %s)", res.get("msg"), code)
            return False
        except (OukitelAuthError, OukitelConnectionError):
            raise
        except requests.RequestException as err:
            _LOGGER.error("oukitel: Network error in control_device: %s", err)
            raise OukitelConnectionError(f"Network error in control_device: {err}") from err
        except Exception as err:
            _LOGGER.error("oukitel: Exception in control_device: %s", err)
            return False

    def wake_device(self) -> bool:
        """Wake device and maintain high-frequency telemetry reporting."""
        return self.control_device([{"high_frequency_reporting": 3}])

    def get_telemetry(self, retry_on_auth: bool = True) -> dict:
        """Retrieve real-time telemetry from Cloud API."""
        if retry_on_auth:
            self.ensure_authenticated()
        if not self.device_key or not self.product_key:
            if not self.fetch_device_info():
                return {}

        url = f"{self.base_url}/v2/binding/enduserapi/getDeviceBusinessAttributes"
        params = {"pk": self.product_key, "dk": self.device_key}

        try:
            r = requests.get(url, headers=self.get_auth_headers(), params=params, timeout=10)
            res = r.json()
            code = res.get("code")

            if code == 5032:
                if retry_on_auth:
                    _LOGGER.info("oukitel: Token expired (5032) during get_telemetry, refreshing session...")
                    self.access_token = None
                    self.login()
                    return self.get_telemetry(retry_on_auth=False)
                raise OukitelAuthError("Authentication token expired and re-login failed during telemetry fetch (code 5032)")

            if code != 200:
                _LOGGER.warning("oukitel: Telemetry response not OK: %s", res)
                return {}

            data = res.get("data", {})
            device_data = data.get("deviceData", {})
            tsl_list = data.get("customizeTslInfo", [])

            is_online = self.is_online
            for key in ("isOnline", "onlineStatus", "online"):
                if key in device_data and device_data[key] is not None:
                    val = device_data[key]
                    if isinstance(val, bool):
                        is_online = val
                        break
                    if isinstance(val, (int, float)):
                        is_online = int(val) == 1
                        break
                    if isinstance(val, str):
                        is_online = val.strip().lower() in ("1", "true", "online")
                        break

            sig = device_data.get("signalStrength")
            if sig is None:
                for sk in ("rssi", "wifi_signal", "signal", "wifiSignal"):
                    if sk in device_data and device_data[sk] is not None:
                        sig = device_data[sk]
                        break
            metrics = {
                "online": is_online,
                "wifi_signal": sig if sig is not None else -100,
            }

            for item in tsl_list:
                code = item.get("resourceCode")
                val_raw = item.get("resourceValce")
                dtype = item.get("dataType")

                if not code or val_raw is None:
                    continue

                if dtype == "INT":
                    try:
                        metrics[code] = int(val_raw)
                    except ValueError:
                        metrics[code] = 0
                elif dtype == "BOOL":
                    metrics[code] = str(val_raw).lower() == "true"
                elif dtype == "STRUCT":
                    try:
                        metrics[code] = json.loads(val_raw)
                    except Exception:
                        metrics[code] = val_raw
                else:
                    metrics[code] = val_raw

            if "temp" in metrics and ("inverter_temp" not in metrics or metrics["inverter_temp"] is None):
                metrics["inverter_temp"] = metrics["temp"]

            return metrics

        except (OukitelAuthError, OukitelConnectionError):
            raise
        except requests.RequestException as err:
            _LOGGER.debug("oukitel: Cloud telemetry network error: %s", err)
            raise OukitelConnectionError(f"Cloud telemetry network error: {err}") from err
        except Exception as err:
            _LOGGER.debug("oukitel: Cloud telemetry unavailable (offline): %s", err)
            return {}

    def fetch_auth_key(self) -> str | None:
        """Return the per-device AES authKey (already stored from device list)."""
        return self.auth_key

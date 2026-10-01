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

_LOGGER = logging.getLogger(__name__)


class AcceleronixCloudClient:
    """Client to authenticate and interact with Acceleronix / Quectel Cloud API."""

    def __init__(self, email: str, password: str, region: str = "EU"):
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
        self.device_key = None
        self.product_key = None
        self.device_name = None

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
            res = r.json()
            if res.get("code") == 200:
                data = res["data"]
                self.access_token = data["accessToken"]["token"]
                self.token_expiry = data["accessToken"].get("expirationTime", int(time.time()) + 7000)
                self.refresh_token = data["refreshToken"]["token"]
                _LOGGER.debug("Session authenticated successfully.")
                return True
            _LOGGER.error("Login failed: %s (code %s)", res.get("msg"), res.get("code"))
            return False
        except Exception as err:
            _LOGGER.error("Exception during login: %s", err)
            return False

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

    def fetch_device_info(self) -> bool:
        """Fetch bound device key and product key."""
        self.ensure_authenticated()
        url = f"{self.base_url}/v2/binding/enduserapi/userDeviceList"
        try:
            r = requests.get(url, headers=self.get_auth_headers(), timeout=15)
            res = r.json()
            if res.get("code") == 200:
                devices = res.get("data", {}).get("list", [])
                if devices:
                    dev = devices[0]
                    self.device_key = dev["deviceKey"]
                    self.product_key = dev["productKey"]
                    self.device_name = dev.get("deviceName", "Oukitel P2001")
                    return True
                _LOGGER.error("No bound devices found in account.")
                return False
            if res.get("code") == 5032:
                self.login()
                return self.fetch_device_info()
            _LOGGER.error("Error fetching device info: %s", res.get("msg"))
            return False
        except Exception as err:
            _LOGGER.error("Exception in fetch_device_info: %s", err)
            return False

    def control_device(self, properties_list: list) -> bool:
        """Send hardware control commands via batchControlDevice."""
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
            r = requests.post(url, headers=headers, json=payload, timeout=10)
            res = r.json()
            code = res.get("code")

            if code == 200:
                _LOGGER.debug("Cloud command succeeded: %s", properties_list)
                return True
            if code == 5032:
                self.login()
                return self.control_device(properties_list)
            _LOGGER.error("Cloud control error: %s (code %s)", res.get("msg"), code)
            return False
        except Exception as err:
            _LOGGER.error("Exception in control_device: %s", err)
            return False

    def wake_device(self) -> bool:
        """Wake device and maintain high-frequency telemetry reporting."""
        return self.control_device([{"high_frequency_reporting": 3}])

    def get_telemetry(self) -> dict:
        """Retrieve real-time telemetry from Cloud API."""
        self.ensure_authenticated()
        if not self.device_key or not self.product_key:
            if not self.fetch_device_info():
                return {}

        url = f"{self.base_url}/v2/binding/enduserapi/getDeviceBusinessAttributes"
        params = {"pk": self.product_key, "dk": self.device_key}

        try:
            r = requests.get(url, headers=self.get_auth_headers(), params=params, timeout=10)
            res = r.json()

            if res.get("code") == 5032:
                self.login()
                return self.get_telemetry()

            if res.get("code") != 200:
                _LOGGER.warning("Telemetry response not OK: %s", res)
                return {}

            data = res.get("data", {})
            device_data = data.get("deviceData", {})
            tsl_list = data.get("customizeTslInfo", [])

            is_online = bool(
                device_data.get("isOnline", device_data.get("onlineStatus", device_data.get("online", True)))
            )

            metrics = {
                "online": is_online,
                "wifi_signal": device_data.get("signalStrength", -100),
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

            return metrics

        except Exception as err:
            _LOGGER.error("Exception fetching telemetry: %s", err)
            return {}

    def fetch_auth_key(self) -> str | None:
        """Fetch the per-device AES authKey required for local LAN sessions."""
        self.ensure_authenticated()
        if not self.device_key or not self.product_key:
            if not self.fetch_device_info():
                return None

        url = f"{self.base_url}/v2/binding/enduserapi/getDeviceAuthKey"
        params = {"pk": self.product_key, "dk": self.device_key}

        try:
            r = requests.get(url, headers=self.get_auth_headers(), params=params, timeout=10)
            res = r.json()
            if res.get("code") == 200:
                return res.get("data", {}).get("authKey")
            if res.get("code") == 5032:
                self.login()
                return self.fetch_auth_key()
            _LOGGER.debug("authKey endpoint returned code %s — LAN mode unavailable", res.get("code"))
            return None
        except Exception as err:
            _LOGGER.debug("Could not fetch authKey: %s", err)
            return None

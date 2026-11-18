"""Config flow and Options flow for Oukitel Power Station integration."""

from __future__ import annotations

import logging
import socket
from typing import Any, Mapping
import urllib.parse
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

try:
    from homeassistant.components import bluetooth
except ImportError:
    bluetooth = None

from .api import AcceleronixCloudClient, OukitelAuthError, OukitelConnectionError
from .ble_provision import (
    async_discover_oukitel_ble,
    async_get_bluetooth_sources,
    point_station,
)
from .const import (
    CONF_AUTH_KEY,
    CONF_BLE_ENDPOINT,
    CONF_BLE_MAC,
    CONF_BLE_PASSWORD,
    CONF_BLE_SOURCE,
    CONF_BLE_SSID,
    CONF_BRIDGE_PORT,
    CONF_CLOUD_BRIDGE,
    CONF_CONNECTION_MODE,
    CONF_CURRENCY,
    CONF_EMAIL,
    CONF_FIXED_PRICE,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_PRICE_SENSOR,
    CONF_REGION,
    CONNECTION_MODES,
    CURRENCY_OPTIONS,
    DEFAULT_BRIDGE_PORT,
    DEFAULT_CONNECTION_MODE,
    DEFAULT_CURRENCY,
    DEFAULT_FIXED_PRICE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_REGION,
    DOMAIN,
    MODE_AUTO,
    MODE_CLOUD,
    MODE_LAN,
    MODE_ZERO_CLOUD,
    REGION_SERVERS,
)

_LOGGER = logging.getLogger(__name__)

REGIONS_OPTIONS = {k: f"{v['name']}" for k, v in REGION_SERVERS.items()}


def _detect_ha_ip(hass) -> str:
    """Best-effort discovery of local Home Assistant IP address."""
    try:
        from homeassistant.helpers.network import get_url
        url = get_url(hass, prefer_internal=True)
        host = urllib.parse.urlparse(url).hostname
        if host and host not in ("localhost", "127.0.0.1", "homeassistant.local"):
            return host
    except Exception:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "192.168.1.xxx"


class OukitelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Oukitel Power Station."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow state."""
        self._discovered_devices: list[dict] = []
        self._user_credentials: dict = {}
        self._ble_discovery: dict[str, Any] = {}
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Present top-level connection choice."""
        return self.async_show_menu(
            step_id="user",
            menu_options={
                "zero_cloud": "Zero-Cloud / Broker Local (100% Offline, Sin Nube)",
                "cloud": "Cuenta Cloud Oficial (Estándar / App Oficial)",
                "ble_provision": "Aprovisionar Wi-Fi de la estación por Bluetooth (BLE)",
            },
        )

    async def async_step_zero_cloud(self, user_input=None) -> FlowResult:
        """Set up 100% offline Zero-Cloud local broker."""
        errors = {}
        if user_input is not None:
            station_name = user_input.get("station_name", "Oukitel Station").strip() or "Oukitel Station"
            port = int(user_input.get(CONF_BRIDGE_PORT, DEFAULT_BRIDGE_PORT))

            entry_data = {
                "device_name": station_name,
                "device_key": "zero_cloud_station",
                CONF_EMAIL: "",
                CONF_PASSWORD: "",
                CONF_CONNECTION_MODE: MODE_ZERO_CLOUD,
                CONF_CLOUD_BRIDGE: True,
                CONF_BRIDGE_PORT: port,
                CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
            }
            return self.async_create_entry(
                title=f"{station_name} (Zero-Cloud)",
                data=entry_data,
            )

        schema = vol.Schema(
            {
                vol.Required("station_name", default="Oukitel Station"): cv.string,
                vol.Required(CONF_BRIDGE_PORT, default=DEFAULT_BRIDGE_PORT): NumberSelector(
                    NumberSelectorConfig(
                        min=1024,
                        max=65535,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="zero_cloud",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_cloud(self, user_input=None) -> FlowResult:
        """Set up official cloud connection."""
        errors = {}
        if user_input is not None:
            client = AcceleronixCloudClient(
                email=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
                region=user_input.get(CONF_REGION, DEFAULT_REGION),
            )

            try:
                success = await self.hass.async_add_executor_job(client.login)
                if not success:
                    errors["base"] = "invalid_auth"
            except OukitelAuthError:
                errors["base"] = "invalid_auth"
            except (OukitelConnectionError, Exception):
                errors["base"] = "cannot_connect"

            if "base" not in errors:
                try:
                    devices = await self.hass.async_add_executor_job(client.get_devices_list)
                except OukitelAuthError:
                    errors["base"] = "invalid_auth"
                except Exception:
                    errors["base"] = "cannot_connect"

            if "base" not in errors:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    self._discovered_devices = devices
                    self._user_credentials = user_input

                    configured_ids = {
                        entry.unique_id for entry in self._async_current_entries()
                    }
                    available = [
                        d for d in devices
                        if f"oukitel_{d.get('deviceKey')}" not in configured_ids
                    ]

                    if not available:
                        return self.async_abort(reason="already_configured")

                    if len(available) == 1:
                        return await self._async_create_device_entry(available[0])

                    return await self.async_step_device()

        schema = vol.Schema(
            {
                vol.Required(CONF_REGION, default=DEFAULT_REGION): vol.In(REGIONS_OPTIONS),
                vol.Required(CONF_EMAIL): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(
                    CONF_POLL_INTERVAL,
                    default=DEFAULT_POLL_INTERVAL,
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=3,
                        max=120,
                        step=1,
                        mode=NumberSelectorMode.SLIDER,
                        unit_of_measurement="s",
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="cloud",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_device(self, user_input=None) -> FlowResult:
        """Handle multiple devices selection step."""
        configured_ids = {
            entry.unique_id for entry in self._async_current_entries()
        }
        available_devices = [
            d for d in self._discovered_devices
            if f"oukitel_{d.get('deviceKey')}" not in configured_ids
        ]

        if not available_devices:
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            chosen_key = user_input["device"]
            chosen = next(
                (d for d in available_devices if d.get("deviceKey") == chosen_key),
                None,
            )
            if chosen:
                return await self._async_create_device_entry(chosen)

        device_options = {
            d.get("deviceKey"): (
                f"{d.get('deviceName', 'Oukitel Station')} "
                f"({d.get('deviceKey')}) "
                f"[{'Online' if d.get('isOnline') else 'Offline'}]"
            )
            for d in available_devices
        }

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {vol.Required("device"): vol.In(device_options)}
            ),
        )

    async def _async_create_device_entry(self, device: dict) -> FlowResult:
        """Create entry for a selected device."""
        device_key = device.get("deviceKey")
        unique_id = f"oukitel_{device_key}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        device_name = device.get("deviceName") or "Oukitel Power Station"
        entry_data = {
            CONF_REGION: self._user_credentials.get(CONF_REGION, DEFAULT_REGION),
            CONF_EMAIL: self._user_credentials[CONF_EMAIL],
            CONF_PASSWORD: self._user_credentials[CONF_PASSWORD],
            CONF_POLL_INTERVAL: self._user_credentials.get(
                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
            ),
            "device_key": device_key,
            "product_key": device.get("productKey"),
            "device_name": device_name,
            "product_name": device.get("productName", device_name),
            CONF_CONNECTION_MODE: DEFAULT_CONNECTION_MODE,
        }

        return self.async_create_entry(
            title=f"{device_name} ({device_key})",
            data=entry_data,
        )

    async def async_step_ble_provision(self, user_input=None) -> FlowResult:
        """Scan and point station via Bluetooth."""
        errors = {}
        ha_ip = _detect_ha_ip(self.hass)
        default_endpoint = f"mqtt://{ha_ip}:{DEFAULT_BRIDGE_PORT}"

        if user_input is not None:
            target_mac = user_input.get(CONF_BLE_MAC, "").strip()
            ssid = user_input.get(CONF_BLE_SSID, "").strip()
            pwd = user_input.get(CONF_BLE_PASSWORD, "")
            endpoint = user_input.get(CONF_BLE_ENDPOINT, default_endpoint).strip()
            source = user_input.get(CONF_BLE_SOURCE, "auto")

            try:
                success, msg = await point_station(
                    self.hass,
                    ssid=ssid,
                    password=pwd,
                    endpoint=endpoint,
                    mac=target_mac,
                    source=source,
                )
            except Exception as exc:
                _LOGGER.exception("oukitel: BLE provisioning unexpected error: %s", exc)
                success, msg = False, str(exc)

            if not success:
                errors["base"] = "ble_provision_failed"
                _LOGGER.warning("oukitel: BLE provisioning failed: %s", msg)
            else:
                _LOGGER.info("oukitel: BLE provisioning succeeded: %s", msg)
                port = DEFAULT_BRIDGE_PORT
                if "://" in endpoint:
                    try:
                        p = urllib.parse.urlparse(endpoint).port
                        if p:
                            port = p
                    except Exception:
                        pass

                station_name = user_input.get("station_name", "Oukitel Station").strip() or "Oukitel Station"
                entry_data = {
                    "device_name": station_name,
                    "device_key": "zero_cloud_station",
                    CONF_EMAIL: "",
                    CONF_PASSWORD: "",
                    CONF_CONNECTION_MODE: MODE_ZERO_CLOUD,
                    CONF_CLOUD_BRIDGE: True,
                    CONF_BRIDGE_PORT: port,
                    CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                    CONF_BLE_MAC: target_mac,
                    CONF_BLE_SSID: ssid,
                    CONF_BLE_ENDPOINT: endpoint,
                }
                return self.async_create_entry(
                    title=f"{station_name} (Zero-Cloud)",
                    data=entry_data,
                )

        discovered = async_discover_oukitel_ble(self.hass)
        device_choices = {}
        for dev in discovered:
            label = f"{dev.get('name', 'Oukitel')} ({dev.get('address')})"
            device_choices[dev.get("address")] = label

        sources = async_get_bluetooth_sources(self.hass)
        suggested_mac = discovered[0]["address"] if discovered else ""

        schema_dict = {}
        if device_choices:
            schema_dict[vol.Required(CONF_BLE_MAC, default=suggested_mac)] = vol.In(device_choices)
        else:
            schema_dict[vol.Optional(CONF_BLE_MAC, default="")] = cv.string

        schema_dict.update({
            vol.Required(CONF_BLE_SSID): cv.string,
            vol.Required(CONF_BLE_PASSWORD): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Required(CONF_BLE_ENDPOINT, default=default_endpoint): cv.string,
            vol.Optional("station_name", default="Oukitel Station"): cv.string,
            vol.Optional(CONF_BLE_SOURCE, default="auto"): SelectSelector(
                SelectSelectorConfig(
                    options=sources,
                    mode=SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                )
            ),
        })

        return self.async_show_form(
            step_id="ble_provision",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "discovered": f"{len(discovered)} device(s) found" if discovered else "None detected (Ensure IoT button held 3s)",
            },
        )

    async def async_step_bluetooth(
        self, discovery_info: bluetooth.BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery of an Oukitel / Quectel station."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._ble_discovery = {
            "name": discovery_info.name or "QUEC_BLE_Station",
            "address": discovery_info.address,
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(self, user_input=None) -> FlowResult:
        """Confirm pairing of discovered BLE station."""
        errors = {}
        target_name = self._ble_discovery.get("name", "Oukitel Station")
        target_mac = self._ble_discovery.get("address", "")
        ha_ip = _detect_ha_ip(self.hass)
        default_endpoint = f"mqtt://{ha_ip}:{DEFAULT_BRIDGE_PORT}"

        if user_input is not None:
            ssid = user_input.get(CONF_BLE_SSID, "").strip()
            pwd = user_input.get(CONF_BLE_PASSWORD, "")
            endpoint = user_input.get(CONF_BLE_ENDPOINT, default_endpoint).strip()

            success, msg = await point_station(
                self.hass,
                ssid=ssid,
                password=pwd,
                endpoint=endpoint,
                mac=target_mac,
            )
            if not success:
                errors["base"] = "ble_provision_failed"
            else:
                port = DEFAULT_BRIDGE_PORT
                if "://" in endpoint:
                    try:
                        p = urllib.parse.urlparse(endpoint).port
                        if p:
                            port = p
                    except Exception:
                        pass
                entry_data = {
                    "device_name": target_name,
                    "device_key": "zero_cloud_station",
                    CONF_EMAIL: "",
                    CONF_PASSWORD: "",
                    CONF_CONNECTION_MODE: MODE_ZERO_CLOUD,
                    CONF_CLOUD_BRIDGE: True,
                    CONF_BRIDGE_PORT: port,
                    CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                    CONF_BLE_MAC: target_mac,
                    CONF_BLE_SSID: ssid,
                    CONF_BLE_ENDPOINT: endpoint,
                }
                return self.async_create_entry(
                    title=f"{target_name} (Zero-Cloud)",
                    data=entry_data,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_BLE_SSID): cv.string,
                vol.Required(CONF_BLE_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(CONF_BLE_ENDPOINT, default=default_endpoint): cv.string,
            }
        )
        return self.async_show_form(
            step_id="bluetooth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "name": target_name,
                "address": target_mac,
            },
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauthorization request from an existing entry."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthorization confirmation."""
        errors: dict[str, str] = {}
        if not self._reauth_entry:
            return self.async_abort(reason="reauth_entry_not_found")

        current_email = self._reauth_entry.data.get(CONF_EMAIL, "")
        current_region = self._reauth_entry.data.get(CONF_REGION, DEFAULT_REGION)

        if user_input is not None:
            password = user_input[CONF_PASSWORD]
            client = AcceleronixCloudClient(
                email=current_email,
                password=password,
                region=current_region,
            )
            try:
                success = await self.hass.async_add_executor_job(client.login)
                if not success:
                    errors["base"] = "invalid_auth"
            except OukitelAuthError:
                errors["base"] = "invalid_auth"
            except (OukitelConnectionError, Exception):
                errors["base"] = "cannot_connect"

            if "base" not in errors:
                new_data = dict(self._reauth_entry.data)
                new_data[CONF_PASSWORD] = password
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=new_data
                )
                await self.hass.config_entries.async_reload(
                    self._reauth_entry.entry_id
                )
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                }
            ),
            description_placeholders={"email": current_email},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return OukitelOptionsFlowHandler(config_entry)


class OukitelOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Oukitel Power Station integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage options."""
        if user_input is not None:
            if user_input.get("reconfigure_ble"):
                return await self.async_step_ble_provision()
            user_input.pop("reconfigure_ble", None)
            return self.async_create_entry(title="", data=user_input)

        current_interval = self._config_entry.options.get(
            CONF_POLL_INTERVAL,
            self._config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )
        current_mode = self._config_entry.options.get(
            CONF_CONNECTION_MODE,
            self._config_entry.data.get(CONF_CONNECTION_MODE, DEFAULT_CONNECTION_MODE),
        )
        current_host = self._config_entry.options.get(
            CONF_HOST,
            self._config_entry.data.get(CONF_HOST, ""),
        )
        current_auth_key = self._config_entry.options.get(
            CONF_AUTH_KEY,
            self._config_entry.data.get(CONF_AUTH_KEY, ""),
        )
        current_currency = self._config_entry.options.get(
            CONF_CURRENCY,
            self._config_entry.data.get(CONF_CURRENCY, DEFAULT_CURRENCY),
        )
        current_fixed_price = self._config_entry.options.get(
            CONF_FIXED_PRICE,
            self._config_entry.data.get(CONF_FIXED_PRICE, DEFAULT_FIXED_PRICE),
        )
        current_price_sensor = self._config_entry.options.get(
            CONF_PRICE_SENSOR,
            self._config_entry.data.get(CONF_PRICE_SENSOR, ""),
        )

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_CONNECTION_MODE,
                    default=current_mode,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            {"value": k, "label": v}
                            for k, v in CONNECTION_MODES.items()
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_HOST,
                ): cv.string,
                vol.Optional(
                    CONF_AUTH_KEY,
                ): cv.string,
                vol.Required(
                    CONF_POLL_INTERVAL,
                    default=current_interval,
                ): vol.All(cv.positive_int, vol.Range(min=3, max=120)),
                vol.Optional(
                    CONF_PRICE_SENSOR,
                ): EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_CURRENCY,
                    default=current_currency,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=CURRENCY_OPTIONS,
                        custom_value=True,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_FIXED_PRICE,
                    default=float(current_fixed_price),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=0.0,
                        max=5.0,
                        step=0.01,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement=f"{current_currency}/kWh",
                    )
                ),
                vol.Optional("reconfigure_ble", default=False): cv.boolean,
            }
        )

        suggested_values = {}
        if current_host:
            suggested_values[CONF_HOST] = current_host
        if current_auth_key:
            suggested_values[CONF_AUTH_KEY] = current_auth_key
        if current_price_sensor:
            suggested_values[CONF_PRICE_SENSOR] = current_price_sensor

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            suggested_values=suggested_values,
        )

    async def async_step_ble_provision(self, user_input=None):
        """On-demand Bluetooth provisioning to set Wi-Fi network or change broker endpoint."""
        errors = {}
        ha_ip = _detect_ha_ip(self.hass)
        default_endpoint = f"mqtt://{ha_ip}:{DEFAULT_BRIDGE_PORT}"

        if user_input is not None:
            target_mac = user_input.get(CONF_BLE_MAC, "").strip()
            ssid = user_input.get(CONF_BLE_SSID, "").strip()
            pwd = user_input.get(CONF_BLE_PASSWORD, "")
            endpoint = user_input.get(CONF_BLE_ENDPOINT, default_endpoint).strip()
            source = user_input.get(CONF_BLE_SOURCE, "auto")

            try:
                success, msg = await point_station(
                    self.hass,
                    ssid=ssid,
                    password=pwd,
                    endpoint=endpoint,
                    mac=target_mac,
                    source=source,
                )
            except Exception as exc:
                _LOGGER.exception("oukitel: BLE provisioning unexpected error: %s", exc)
                success, msg = False, str(exc)

            if not success:
                errors["base"] = "ble_provision_failed"
                _LOGGER.warning("oukitel: BLE provisioning failed: %s", msg)
            else:
                _LOGGER.info("oukitel: BLE provisioning succeeded: %s", msg)
                updated_options = dict(self._config_entry.options)
                updated_options[CONF_BLE_SSID] = ssid
                updated_options[CONF_BLE_ENDPOINT] = endpoint
                if endpoint.startswith("mqtt://") and not endpoint.startswith("mqtt://iot-south"):
                    updated_options[CONF_CONNECTION_MODE] = MODE_ZERO_CLOUD
                return self.async_create_entry(title="", data=updated_options)

        discovered = async_discover_oukitel_ble(self.hass)
        suggested_ssid = self._config_entry.options.get(
            CONF_BLE_SSID,
            self._config_entry.data.get(CONF_BLE_SSID, "OUKITEL"),
        )
        sources = async_get_bluetooth_sources(self.hass)
        schema = vol.Schema(
            {
                vol.Optional(CONF_BLE_MAC, default=self._config_entry.data.get(CONF_BLE_MAC, "")): cv.string,
                vol.Required(CONF_BLE_SSID, default=suggested_ssid): cv.string,
                vol.Required(CONF_BLE_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_BLE_ENDPOINT,
                    default=self._config_entry.options.get(CONF_BLE_ENDPOINT, default_endpoint),
                ): cv.string,
                vol.Optional(CONF_BLE_SOURCE, default="auto"): SelectSelector(
                    SelectSelectorConfig(
                        options=sources,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
            }
        )
        return self.async_show_form(
            step_id="ble_provision",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "discovered": f"{len(discovered)} device(s) found" if discovered else "none in range",
            },
        )

"""Config flow and Options flow for Oukitel Power Station integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
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

from .api import AcceleronixCloudClient
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
    DEFAULT_CONNECTION_MODE,
    DEFAULT_CURRENCY,
    DEFAULT_FIXED_PRICE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_REGION,
    DOMAIN,
    MODE_AUTO,
    MODE_CLOUD,
    MODE_LAN,
    REGION_SERVERS,
)

_LOGGER = logging.getLogger(__name__)

REGIONS_OPTIONS = {k: f"{v['name']}" for k, v in REGION_SERVERS.items()}

STEP_USER_DATA_SCHEMA = vol.Schema(
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


class OukitelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Oukitel Power Station."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow state."""
        self._discovered_devices: list[dict] = []
        self._user_credentials: dict = {}
        self._ble_discovery: dict[str, Any] = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            client = AcceleronixCloudClient(
                email=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
                region=user_input[CONF_REGION],
            )

            success = await self.hass.async_add_executor_job(client.login)
            if not success:
                errors["base"] = "invalid_auth"
            else:
                devices = await self.hass.async_add_executor_job(client.get_devices_list)
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

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_device(self, user_input=None):
        """Handle multiple devices selection step."""
        configured_ids = {
            entry.unique_id for entry in self._async_current_entries()
        }
        available = [
            d for d in self._discovered_devices
            if f"oukitel_{d.get('deviceKey')}" not in configured_ids
        ]

        if not available:
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            chosen_key = user_input["device_key"]
            dev = next((d for d in available if d.get("deviceKey") == chosen_key), None)
            if dev:
                return await self._async_create_device_entry(dev)

        device_options = {
            d["deviceKey"]: f"{d.get('deviceName', 'Oukitel')} ({d.get('productName', 'Power Station')}) - [{d['deviceKey'][-4:]}]"
            for d in available
        }

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({
                vol.Required("device_key", default=next(iter(device_options.keys()))): vol.In(device_options)
            }),
        )

    async def _async_create_device_entry(self, dev: dict):
        """Create config entry for a specific Oukitel device."""
        unique_id = f"oukitel_{dev['deviceKey']}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        entry_data = dict(self._user_credentials)
        entry_data["device_key"] = dev["deviceKey"]
        entry_data["product_key"] = dev.get("productKey")
        entry_data["device_name"] = dev.get("deviceName", "Oukitel P2001")
        if dev.get("productName"):
            entry_data["product_name"] = dev["productName"]
        if dev.get("authKey"):
            entry_data[CONF_AUTH_KEY] = dev["authKey"]

        title = f"{dev.get('deviceName', 'Oukitel')} ({dev['deviceKey'][-4:]})"
        return self.async_create_entry(
            title=title,
            data=entry_data,
        )

    async def async_step_bluetooth(self, discovery_info):
        """Handle automatic discovery of an Oukitel/Quectel station over Bluetooth."""
        dk = pk = ""
        for data in (discovery_info.manufacturer_data or {}).values():
            try:
                if len(data) >= 6:
                    i = 4
                    length = data[i]
                    pk = data[i + 1 : i + 1 + length].decode("ascii")
                    i += 1 + length
                    length = data[i]
                    dk = data[i + 1 : i + 1 + length].hex()
            except Exception:
                continue

        unique_id = f"oukitel_{dk}" if dk else f"oukitel_{discovery_info.address.replace(':', '').lower()}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        self._ble_discovery = {
            "mac": discovery_info.address,
            "device_key": dk,
            "product_key": pk,
            "name": discovery_info.name or f"Oukitel ({discovery_info.address})",
        }
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(self, user_input=None):
        """Confirm pairing and configure Wi-Fi for the discovered Bluetooth station."""
        errors = {}
        if user_input is not None:
            mac = self._ble_discovery.get("mac", "")
            ssid = user_input.get(CONF_BLE_SSID, "").strip()
            pwd = user_input.get(CONF_BLE_PASSWORD, "")
            endpoint = user_input.get(CONF_BLE_ENDPOINT, "mqtt://iot-south.acceleronix.io:8883").strip()
            source = user_input.get(CONF_BLE_SOURCE, "auto")

            success, msg = await point_station(
                self.hass,
                ssid=ssid,
                password=pwd,
                endpoint=endpoint,
                mac=mac,
                source=source,
            )

            if not success:
                errors["base"] = "ble_provision_failed"
                _LOGGER.warning("oukitel: BLE provisioning failed: %s", msg)
            else:
                dk = self._ble_discovery.get("device_key") or mac.replace(":", "").lower()
                pk = self._ble_discovery.get("product_key", "")
                name = self._ble_discovery.get("name", "Oukitel Station")
                entry_data = {
                    "device_key": dk,
                    "product_key": pk,
                    "device_name": name,
                    CONF_CONNECTION_MODE: MODE_AUTO,
                    CONF_POLL_INTERVAL: DEFAULT_POLL_INTERVAL,
                    CONF_BLE_MAC: mac,
                }
                return self.async_create_entry(
                    title=f"{name} ({mac[-5:]})",
                    data=entry_data,
                )

        sources = async_get_bluetooth_sources(self.hass, self._ble_discovery.get("mac", ""))
        schema = vol.Schema(
            {
                vol.Required(CONF_BLE_SSID): cv.string,
                vol.Required(CONF_BLE_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_BLE_ENDPOINT,
                    default="mqtt://iot-south.acceleronix.io:8883",
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
            step_id="bluetooth_confirm",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "name": self._ble_discovery.get("name", "Oukitel"),
                "mac": self._ble_discovery.get("mac", ""),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow handler to adjust settings per device."""
        return OukitelOptionsFlowHandler(config_entry)


class OukitelOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle per-device options like polling update interval."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        super().__init__()
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage per-device settings."""
        if user_input is not None:
            if user_input.pop("reconfigure_ble", False):
                return await self.async_step_ble_provision()
            return self.async_create_entry(title="", data=user_input)

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
        current_interval = self._config_entry.options.get(
            CONF_POLL_INTERVAL,
            self._config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )
        current_price_sensor = self._config_entry.options.get(
            CONF_PRICE_SENSOR,
            self._config_entry.data.get(CONF_PRICE_SENSOR, ""),
        )
        current_fixed_price = self._config_entry.options.get(
            CONF_FIXED_PRICE,
            self._config_entry.data.get(CONF_FIXED_PRICE, DEFAULT_FIXED_PRICE),
        )

        hass_currency = getattr(self.hass.config, "currency", "EUR")
        default_currency_symbol = {
            "EUR": "€",
            "USD": "$",
            "GBP": "£",
            "CHF": "CHF",
            "JPY": "¥",
            "CNY": "¥",
            "BRL": "R$",
            "PLN": "zł",
            "SEK": "kr",
            "NOK": "kr",
            "DKK": "kr",
        }.get(hass_currency, hass_currency or DEFAULT_CURRENCY)

        current_currency = (
            self._config_entry.options.get(CONF_CURRENCY)
            or self._config_entry.data.get(CONF_CURRENCY)
            or default_currency_symbol
        )

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_CONNECTION_MODE,
                    default=current_mode,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[MODE_AUTO, MODE_LAN, MODE_CLOUD],
                        translation_key="connection_mode",
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Optional(
                    CONF_HOST,
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.TEXT)
                ),
                vol.Optional(
                    CONF_AUTH_KEY,
                ): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
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
                vol.Optional(
                    "reconfigure_ble",
                    default=False,
                ): cv.boolean,
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
            data_schema=self.add_suggested_values_to_schema(options_schema, suggested_values),
            description_placeholders={"device_name": self._config_entry.title},
        )

    async def async_step_ble_provision(self, user_input=None):
        """On-demand Bluetooth provisioning to set Wi-Fi network or change broker endpoint."""
        errors = {}
        if user_input is not None:
            target_mac = user_input.get(CONF_BLE_MAC, "").strip()
            discovered_choice = user_input.get("discovered_device")
            if discovered_choice and discovered_choice != "manual":
                target_mac = discovered_choice

            ssid = user_input.get(CONF_BLE_SSID, "").strip()
            pwd = user_input.get(CONF_BLE_PASSWORD, "")
            endpoint = user_input.get(CONF_BLE_ENDPOINT, "mqtt://iot-south.acceleronix.io:8883").strip()
            source = user_input.get(CONF_BLE_SOURCE, "auto")

            success, msg = await point_station(
                self.hass,
                ssid=ssid,
                password=pwd,
                endpoint=endpoint,
                mac=target_mac,
                source=source,
            )

            if not success:
                errors["base"] = "ble_provision_failed"
                _LOGGER.warning("oukitel: BLE provisioning failed: %s", msg)
            else:
                _LOGGER.info("oukitel: BLE provisioning succeeded: %s", msg)
                return self.async_create_entry(
                    title="",
                    data=dict(self._config_entry.options),
                )

        discovered = async_discover_oukitel_ble(self.hass)
        discovered_options = {
            d["address"]: f"{d['name']} ({d['address']}) [RSSI: {d['rssi']} dBm]"
            for d in discovered
        }
        discovered_options["manual"] = "Introducir dirección MAC manualmente / Manual MAC"

        default_mac = next(iter(discovered_options.keys())) if discovered else "manual"
        sources = async_get_bluetooth_sources(self.hass)

        schema = vol.Schema(
            {
                vol.Required("discovered_device", default=default_mac): vol.In(discovered_options),
                vol.Optional(CONF_BLE_MAC, default=self._config_entry.data.get(CONF_BLE_MAC, "")): cv.string,
                vol.Required(CONF_BLE_SSID): cv.string,
                vol.Required(CONF_BLE_PASSWORD): TextSelector(
                    TextSelectorConfig(type=TextSelectorType.PASSWORD)
                ),
                vol.Required(
                    CONF_BLE_ENDPOINT,
                    default="mqtt://iot-south.acceleronix.io:8883",
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
        )

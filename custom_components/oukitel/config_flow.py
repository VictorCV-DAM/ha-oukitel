"""Config flow and Options flow for Oukitel Power Station integration."""

import logging
import voluptuous as vol
from collections.abc import Mapping
from typing import Any
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

from .api import AcceleronixCloudClient, OukitelAuthError, OukitelConnectionError
from .const import (
    CONF_AUTH_KEY,
    CONF_CONNECTION_MODE,
    CONF_CURRENCY,
    CONF_EMAIL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_PRICE_SENSOR,
    CONF_FIXED_PRICE,
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
        self._reauth_entry: config_entries.ConfigEntry | None = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            client = AcceleronixCloudClient(
                email=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
                region=user_input[CONF_REGION],
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

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle initiation of re-authentication with new credentials."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle credential re-authentication dialog."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry or self.hass.config_entries.async_get_entry(self.context["entry_id"])
        email = entry.data.get(CONF_EMAIL, "")
        region = entry.data.get(CONF_REGION, DEFAULT_REGION)

        if user_input is not None:
            new_password = user_input[CONF_PASSWORD]
            client = AcceleronixCloudClient(
                email=email,
                password=new_password,
                region=region,
                device_key=entry.data.get("device_key"),
                device_name=entry.data.get("device_name"),
            )
            try:
                success = await self.hass.async_add_executor_job(client.login)
                if not success:
                    errors["base"] = "invalid_auth"
            except OukitelAuthError:
                errors["base"] = "invalid_auth"
            except (OukitelConnectionError, Exception):
                errors["base"] = "cannot_connect"

            if not errors:
                try:
                    await self.hass.async_add_executor_job(client.fetch_device_info)
                except Exception:
                    pass

                new_data = dict(entry.data)
                new_data[CONF_PASSWORD] = new_password
                if client.auth_key:
                    new_data[CONF_AUTH_KEY] = client.auth_key

                self.hass.config_entries.async_update_entry(entry, data=new_data)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({
                vol.Required(CONF_PASSWORD): cv.string,
            }),
            description_placeholders={"email": email},
            errors=errors,
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
            return self.async_create_entry(title="", data=user_input)

        current_mode = self._config_entry.options.get(
            CONF_CONNECTION_MODE,
            self._config_entry.data.get(CONF_CONNECTION_MODE, DEFAULT_CONNECTION_MODE)
        )
        current_host = self._config_entry.options.get(
            CONF_HOST,
            self._config_entry.data.get(CONF_HOST, "")
        )
        current_auth_key = self._config_entry.options.get(
            CONF_AUTH_KEY,
            self._config_entry.data.get(CONF_AUTH_KEY, "")
        )
        current_interval = self._config_entry.options.get(
            CONF_POLL_INTERVAL,
            self._config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )
        current_price_sensor = self._config_entry.options.get(
            CONF_PRICE_SENSOR,
            self._config_entry.data.get(CONF_PRICE_SENSOR, "")
        )
        current_fixed_price = self._config_entry.options.get(
            CONF_FIXED_PRICE,
            self._config_entry.data.get(CONF_FIXED_PRICE, DEFAULT_FIXED_PRICE)
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

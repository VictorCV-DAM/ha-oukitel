"""Config flow and Options flow for Oukitel Power Station integration."""

import logging
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
from .const import (
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
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(cv.positive_int, vol.Range(min=3, max=120)),
    }
)


class OukitelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Oukitel Power Station."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow state."""
        self._discovered_devices: list[dict] = []
        self._user_credentials: dict = {}

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

        title = f"{dev.get('deviceName', 'Oukitel')} ({dev['deviceKey'][-4:]})"
        return self.async_create_entry(
            title=title,
            data=entry_data,
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
        if current_price_sensor:
            suggested_values[CONF_PRICE_SENSOR] = current_price_sensor

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(options_schema, suggested_values),
            description_placeholders={"device_name": self._config_entry.title},
        )

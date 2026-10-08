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
                dev_success = await self.hass.async_add_executor_job(client.fetch_device_info)
                if not dev_success:
                    errors["base"] = "no_devices"
                else:
                    unique_id = f"oukitel_{client.device_key}"
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"{client.device_name} ({client.device_key[-4:]})",
                        data=user_input,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
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
                ): vol.In(CONNECTION_MODES),
                vol.Optional(
                    CONF_HOST,
                    description={"suggested_value": current_host} if current_host else {},
                ): cv.string,
                vol.Required(
                    CONF_POLL_INTERVAL,
                    default=current_interval,
                ): vol.All(cv.positive_int, vol.Range(min=3, max=120)),
                vol.Optional(
                    CONF_PRICE_SENSOR,
                    description={"suggested_value": current_price_sensor} if current_price_sensor else {},
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

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )

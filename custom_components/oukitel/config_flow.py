"""Config flow and Options flow for Oukitel Power Station integration."""

import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .api import AcceleronixCloudClient
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_REGION,
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
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(cv.positive_int, vol.Range(min=5, max=60)),
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
    def async_get_options_flow(config_entry):
        """Get the options flow handler to adjust settings per device."""
        return OukitelOptionsFlowHandler(config_entry)


class OukitelOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle per-device options like polling update interval."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage per-device settings."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_POLL_INTERVAL,
            self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )

        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_POLL_INTERVAL,
                    default=current_interval,
                ): vol.All(cv.positive_int, vol.Range(min=3, max=120)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )

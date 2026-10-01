"""The Oukitel Power Station integration."""

from datetime import timedelta
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import AcceleronixCloudClient
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_REGION,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_REGION,
    DOMAIN,
)
from .coordinator import OukitelDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Oukitel Power Station from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    region = entry.data.get(CONF_REGION, DEFAULT_REGION)
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    # Poll interval priority: options -> data -> default
    poll_interval = entry.options.get(
        CONF_POLL_INTERVAL,
        entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    )

    client = AcceleronixCloudClient(email=email, password=password, region=region)
    success = await hass.async_add_executor_job(client.login)
    if not success:
        _LOGGER.error("Failed to login to Oukitel cloud")
        return False

    await hass.async_add_executor_job(client.fetch_device_info)

    coordinator = OukitelDataCoordinator(hass, client, poll_interval=poll_interval)
    await coordinator.async_config_entry_first_refresh()

    # Attempt LAN mode in the background — does not block setup
    hass.async_create_task(coordinator.async_setup_lan())

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: OukitelDataCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    await coordinator.async_shutdown_lan()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

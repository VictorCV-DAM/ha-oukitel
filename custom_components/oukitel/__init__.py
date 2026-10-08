"""The Oukitel Power Station integration."""

from datetime import timedelta
import logging
import os
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import AcceleronixCloudClient
from .const import (
    CONF_CONNECTION_MODE,
    CONF_EMAIL,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_REGION,
    DEFAULT_CONNECTION_MODE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_REGION,
    DOMAIN,
    MODE_CLOUD,
)
from .coordinator import OukitelDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Oukitel Power Station from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Register frontend Lovelace cards
    if not hass.data[DOMAIN].get("frontend_registered"):
        frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
        if os.path.isdir(frontend_dir):
            try:
                from homeassistant.components.http import StaticPathConfig
                await hass.http.async_register_static_paths([
                    StaticPathConfig(
                        "/oukitel_frontend",
                        frontend_dir,
                        cache_headers=False,
                    )
                ])
                hass.data[DOMAIN]["frontend_registered"] = True
                _LOGGER.debug("oukitel: Registered frontend static path at /oukitel_frontend")
            except (ImportError, AttributeError):
                try:
                    hass.http.register_static_path("/oukitel_frontend", frontend_dir, cache_headers=False)
                    hass.data[DOMAIN]["frontend_registered"] = True
                except Exception:
                    pass
            except Exception as err:
                _LOGGER.debug("oukitel: Frontend registration notice: %s", err)

    region = entry.data.get(CONF_REGION, DEFAULT_REGION)
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    # Poll interval priority: options -> data -> default
    poll_interval = entry.options.get(
        CONF_POLL_INTERVAL,
        entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
    )
    connection_mode = entry.options.get(
        CONF_CONNECTION_MODE,
        entry.data.get(CONF_CONNECTION_MODE, DEFAULT_CONNECTION_MODE)
    )

    host = entry.options.get(
        CONF_HOST,
        entry.data.get(CONF_HOST)
    )

    _LOGGER.debug("oukitel: Setting up entry for %s (mode=%s, host=%s)", email, connection_mode, host)
    client = AcceleronixCloudClient(email=email, password=password, region=region)
    success = await hass.async_add_executor_job(client.login)
    if not success:
        _LOGGER.error("oukitel: Failed to login to Oukitel cloud")
        return False

    await hass.async_add_executor_job(client.fetch_device_info)
    _LOGGER.debug("oukitel: Fetched device info. authKey present: %s", bool(client.auth_key))

    coordinator = OukitelDataCoordinator(
        hass,
        client,
        poll_interval=poll_interval,
        connection_mode=connection_mode,
        host=host,
    )
    
    # Attempt LAN mode in the background immediately if not forced to Cloud
    if connection_mode != MODE_CLOUD:
        _LOGGER.debug("oukitel: Creating background task for LAN setup")
        hass.async_create_task(coordinator.async_setup_lan())

    _LOGGER.debug("oukitel: Awaiting first cloud refresh")
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("oukitel: First refresh failed (%s): %s", type(err).__name__, err)
        raise

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

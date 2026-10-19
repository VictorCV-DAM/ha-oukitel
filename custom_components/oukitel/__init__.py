"""The Oukitel Power Station integration."""

from datetime import timedelta
import logging
import os
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import AcceleronixCloudClient
from .const import (
    CONF_AUTH_KEY,
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

            try:
                from homeassistant.components.frontend import add_extra_js_url
                add_extra_js_url(hass, "/oukitel_frontend/oukitel-station.js?v=3.5.0")
            except Exception as err:
                _LOGGER.debug("oukitel: Frontend extra JS notice: %s", err)

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
    device_key = entry.data.get("device_key")

    _LOGGER.debug(
        "oukitel: Setting up entry for %s (device_key=%s, mode=%s, host=%s)",
        email, device_key, connection_mode, host,
    )
    client = AcceleronixCloudClient(
        email=email,
        password=password,
        region=region,
        device_key=device_key,
    )

    cloud_connected = False
    try:
        login_timeout = 4.0 if connection_mode != MODE_CLOUD else 10.0
        success = await hass.async_add_executor_job(client.login, login_timeout)
        if success:
            cloud_connected = True
            await hass.async_add_executor_job(client.fetch_device_info)
            _LOGGER.debug(
                "oukitel: Fetched device info for %s (%s). authKey present: %s",
                client.device_name, client.device_key, bool(client.auth_key),
            )

            # Persist credentials and metadata to config entry data for offline restarts
            new_data = dict(entry.data)
            updated = False
            for k, val in (
                (CONF_AUTH_KEY, client.auth_key),
                ("product_key", client.product_key),
                ("device_name", client.device_name),
                ("product_name", client.product_name),
                ("device_key", client.device_key),
            ):
                if val and new_data.get(k) != val:
                    new_data[k] = val
                    updated = True
            if updated:
                hass.config_entries.async_update_entry(entry, data=new_data)
                _LOGGER.debug("oukitel: Persisted device credentials to config entry data")
        else:
            _LOGGER.warning("oukitel: Failed to login to Oukitel cloud (unsuccessful credentials or response)")
    except Exception as exc:
        _LOGGER.warning("oukitel: Exception connecting to Oukitel cloud (network/DNS/timeout): %s", exc)

    if not cloud_connected:
        cached_auth_key = entry.options.get(CONF_AUTH_KEY) or entry.data.get(CONF_AUTH_KEY)
        if connection_mode == MODE_CLOUD:
            raise ConfigEntryNotReady(
                "Oukitel cloud unreachable and integration is configured for Cloud Only mode. Retrying automatically..."
            )
        if not cached_auth_key:
            raise ConfigEntryNotReady(
                "Oukitel cloud unreachable and no cached LAN authKey found in configuration. Retrying automatically..."
            )

        _LOGGER.info(
            "oukitel: Cloud unreachable during startup — starting in offline LAN mode using persisted credentials for %s",
            entry.data.get("device_name", "Oukitel Station"),
        )
        client.auth_key = cached_auth_key
        client.product_key = entry.data.get("product_key")
        client.device_name = entry.data.get("device_name", "Oukitel Power Station")
        client.product_name = entry.data.get("product_name", entry.data.get("device_name", "Oukitel Power Station"))
        client.device_key = entry.data.get("device_key") or device_key
        client.is_online = True

    coordinator = OukitelDataCoordinator(
        hass,
        client,
        poll_interval=poll_interval,
        connection_mode=connection_mode,
        host=host,
        config_entry=entry,
    )
    
    # Setup LAN mode if not forced to Cloud
    if connection_mode != MODE_CLOUD:
        if not cloud_connected:
            _LOGGER.info("oukitel: Offline boot — establishing LAN session before first coordinator refresh...")
            await coordinator.async_setup_lan()
            if not coordinator._lan_active:
                raise ConfigEntryNotReady(
                    f"Oukitel station '{host or 'auto-discovery'}' unreachable on LAN and cloud is offline. Retrying automatically..."
                )
        else:
            _LOGGER.debug("oukitel: Creating background task for LAN setup")
            hass.async_create_task(coordinator.async_setup_lan())

    _LOGGER.debug("oukitel: Awaiting initial coordinator refresh")
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("oukitel: First refresh failed (%s): %s", type(err).__name__, err)
        raise ConfigEntryNotReady(f"Initial coordinator refresh failed ({type(err).__name__}): {err}") from err

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

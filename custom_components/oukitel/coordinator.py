"""Oukitel DataUpdateCoordinator — supports LAN (push) and Cloud (poll) modes.

On startup the coordinator tries to locate the device on the local network.
If found and an authKey is available it runs in LAN mode: a persistent TCP
session pushes telemetry in real time and the update interval is used only
as a safety net to request a fresh read.  If LAN is unavailable it falls
back transparently to the existing cloud polling logic.
"""

from datetime import datetime, timedelta
import json
import logging
import time
import asyncio
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AcceleronixCloudClient
from .const import (
    DEFAULT_CONNECTION_MODE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_WAKE_INTERVAL,
    DOMAIN,
    MODE_AUTO,
    MODE_CLOUD,
    MODE_LAN,
    get_battery_capacity_wh,
)
from .local_scan import find_device_on_lan
from .local_session import LocalSession, LocalAuthError, LocalSessionError

_LOGGER = logging.getLogger(__name__)

_LAN_STALE_TIMEOUT = 150.0
_LAN_RECONNECT_DELAY = 10.0


def _unpack_port_data(target: dict[str, Any]) -> None:
    """Unpack individual port metrics from LAN tags (6, 7, 8, 9) or Cloud TSL (AC_Info, USB_Info, etc.)."""
    def _parse_dict(val):
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {}

    # 1. AC Info: 1=ac_switch, 2=AC output power (W), 3=AC output voltage (V)
    ac_val = _parse_dict(target.get(6) or target.get("6") or target.get("AC_Info"))
    if ac_val:
        sw = ac_val.get(1) if 1 in ac_val else (ac_val.get("1") if "1" in ac_val else ac_val.get("ac_switch"))
        if sw is not None:
            target["ac_switch"] = bool(sw)
        p = ac_val.get(2) if 2 in ac_val else ac_val.get("2")
        v = ac_val.get(3) if 3 in ac_val else ac_val.get("3")
        if p is not None:
            target["ac_output_power"] = p
        if v is not None:
            target["ac_output_voltage"] = v

    # 2. USB Info: 1=usb_switch, 2=USB-A power (W), 3=USB-C QC power (W)
    usb_val = _parse_dict(target.get(7) or target.get("7") or target.get("USB_Info"))
    if usb_val:
        sw = usb_val.get(1) if 1 in usb_val else (usb_val.get("1") if "1" in usb_val else usb_val.get("usb_switch"))
        if sw is not None:
            target["usb_switch"] = bool(sw)
        usb_a = usb_val.get(2) if 2 in usb_val else usb_val.get("2")
        usb_c = usb_val.get(3) if 3 in usb_val else usb_val.get("3")
        if usb_a is not None:
            target["usb_a_power"] = usb_a
        if usb_c is not None:
            target["usb_c_qc_power"] = usb_c

    # 3. Type-C Info: 2=Type-C 1 (W), 5=Type-C 2 (W), 6=Type-C 3 (W), 7=Type-C 4 (W)
    typec_val = _parse_dict(target.get(8) or target.get("8") or target.get("TypeC_Info"))
    if typec_val:
        c1 = typec_val.get(2) if 2 in typec_val else typec_val.get("2")
        c2 = typec_val.get(5) if 5 in typec_val else typec_val.get("5")
        c3 = typec_val.get(6) if 6 in typec_val else typec_val.get("6")
        c4 = typec_val.get(7) if 7 in typec_val else typec_val.get("7")
        if c1 is not None:
            target["typec1_power"] = c1
        if c2 is not None:
            target["typec2_power"] = c2
        if c3 is not None:
            target["typec3_power"] = c3
        if c4 is not None:
            target["typec4_power"] = c4

    # 4. DC Info: 1=dc_switch, 2=DC Car output power (W), 3=voltage (V), 4=current (A)
    dc_val = _parse_dict(target.get(9) or target.get("9") or target.get("DC_Info"))
    if dc_val:
        sw = dc_val.get(1) if 1 in dc_val else (dc_val.get("1") if "1" in dc_val else dc_val.get("dc_switch"))
        if sw is not None:
            target["dc_switch"] = bool(sw)
        dc_p = dc_val.get(2) if 2 in dc_val else dc_val.get("2")
        dc_v = dc_val.get(3) if 3 in dc_val else dc_val.get("3")
        dc_a = dc_val.get(4) if 4 in dc_val else dc_val.get("4")
        if dc_p is not None:
            target["dc_output_power"] = dc_p
        if dc_v is not None:
            target["dc_output_voltage"] = dc_v
        if dc_a is not None:
            target["dc_output_current"] = dc_a

    # 5. Direct switch tags (LAN TTLV 43=ac_switch, 44=usb_switch, 46=dc_switch)
    for sw_k, sw_tag in (("ac_switch", 43), ("usb_switch", 44), ("dc_switch", 46)):
        if target.get(sw_tag) is not None:
            target[sw_k] = bool(target[sw_tag])
        elif target.get(str(sw_tag)) is not None:
            target[sw_k] = bool(target[str(sw_tag)])

    # Default all individual power sensors to 0 if not present yet (avoids Unknown states)
    for k in (
        "ac_output_power",
        "usb_a_power",
        "usb_c_qc_power",
        "typec1_power",
        "typec2_power",
        "typec3_power",
        "typec4_power",
        "dc_output_power",
    ):
        if k not in target or target[k] is None:
            target[k] = 0


def _build_paused_data(source: dict[str, Any] | None) -> dict[str, Any]:
    """Zero out active wattage, currents, remaining times, and outputs when paused while preserving battery SoC and temps."""
    data = dict(source or {})
    zero_fields = (
        "total_input_power",
        "total_output_power",
        "ac_input",
        "dc_input",
        "ac_output_power",
        "ac_output_voltage",
        "dc_output_power",
        "dc_output_voltage",
        "dc_output_current",
        "usb_a_power",
        "usb_c_qc_power",
        "typec1_power",
        "typec2_power",
        "typec3_power",
        "typec4_power",
        "remain_time",
        "remain_charging_time",
        "remaining_time",
    )
    for field in zero_fields:
        data[field] = 0

    # Also zero out numeric and string tags for remaining times and power
    for tag in (2, 3, 4, 5, 11, 12):
        data[tag] = 0
        data[str(tag)] = 0

    return data


class OukitelPredictiveTracker:
    """Calculates smoothed predictive discharge autonomy and charge time with a 15-minute moving average filter."""

    def __init__(self, client, window_seconds: float = 900.0) -> None:
        self.client = client
        self.window_seconds = window_seconds
        self.discharge_samples: list[tuple[float, float]] = []  # (monotonic_time, drain_w)
        self.charge_samples: list[tuple[float, float]] = []     # (monotonic_time, charge_w)
        self.operating_mode: str = "Idle"                       # "Discharging", "Charging", "Idle", "Full", "Paused", "Offline"

        self.smoothed_drain_w: float = 0.0
        self.smoothed_charge_w: float = 0.0
        self.empty_timestamp: datetime | None = None
        self.full_charge_timestamp: datetime | None = None
        self.smoothed_discharge_minutes: int | None = None
        self.smoothed_charge_minutes: int | None = None
        self.battery_remaining_wh: float = 0.0
        self.battery_needed_wh: float = 0.0
        self.battery_percentage: float = 0.0

    def update(self, data: dict[str, Any] | None) -> None:
        if not data or data.get("paused"):
            self.operating_mode = "Paused" if data and data.get("paused") else "Offline"
            self.empty_timestamp = None
            self.full_charge_timestamp = None
            self.smoothed_discharge_minutes = None
            self.smoothed_charge_minutes = None
            return

        now = time.monotonic()
        total_in = float(data.get("total_input_power") or 0.0)
        ac_in = float(data.get("ac_input") or 0.0)
        dc_in = float(data.get("dc_input") or 0.0)
        total_out = float(data.get("total_output_power") or 0.0)
        ac_out = float(data.get("ac_output_power") or 0.0)
        dc_out = float(data.get("dc_output_power") or 0.0)

        real_in = max(total_in, ac_in + dc_in)
        real_out = max(total_out, ac_out + dc_out)
        net_power = real_in - real_out

        raw_batt = data.get("battery_percentage")
        try:
            batt_pct = float(raw_batt) if raw_batt is not None else 0.0
        except (ValueError, TypeError):
            batt_pct = 0.0
        self.battery_percentage = batt_pct

        capacity_wh = get_battery_capacity_wh(self.client)
        self.battery_remaining_wh = round((batt_pct / 100.0) * capacity_wh, 1)
        self.battery_needed_wh = round(max(0.0, ((100.0 - batt_pct) / 100.0) * capacity_wh), 1)

        # Detect operating state
        if net_power < -5.0 and batt_pct > 0:
            current_mode = "Discharging"
        elif net_power > 5.0 and batt_pct < 100:
            current_mode = "Charging"
        elif batt_pct >= 100 and net_power >= -5.0:
            current_mode = "Full"
        else:
            current_mode = "Idle"

        self.operating_mode = current_mode
        cutoff = now - self.window_seconds

        if current_mode == "Discharging":
            drain_w = abs(net_power)
            self.discharge_samples.append((now, drain_w))
            self.charge_samples.clear()
            self.discharge_samples = [(t, w) for t, w in self.discharge_samples if t >= cutoff]

            self.smoothed_drain_w = sum(w for _, w in self.discharge_samples) / len(self.discharge_samples)

            if self.smoothed_drain_w > 5.0 and self.battery_remaining_wh > 0:
                hours = self.battery_remaining_wh / self.smoothed_drain_w
                minutes = hours * 60.0
                self.smoothed_discharge_minutes = max(1, round(minutes))
                target_dt = dt_util.utcnow() + timedelta(minutes=self.smoothed_discharge_minutes)
                self.empty_timestamp = target_dt.replace(second=0, microsecond=0)
            else:
                self.smoothed_discharge_minutes = None
                self.empty_timestamp = None

            self.full_charge_timestamp = None
            self.smoothed_charge_minutes = None
            self.smoothed_charge_w = 0.0

        elif current_mode == "Charging":
            charge_w = net_power
            self.charge_samples.append((now, charge_w))
            self.discharge_samples.clear()
            self.charge_samples = [(t, w) for t, w in self.charge_samples if t >= cutoff]

            self.smoothed_charge_w = sum(w for _, w in self.charge_samples) / len(self.charge_samples)

            if self.smoothed_charge_w > 5.0 and self.battery_needed_wh > 0:
                hours = self.battery_needed_wh / self.smoothed_charge_w
                minutes = hours * 60.0
                self.smoothed_charge_minutes = max(1, round(minutes))
                target_dt = dt_util.utcnow() + timedelta(minutes=self.smoothed_charge_minutes)
                self.full_charge_timestamp = target_dt.replace(second=0, microsecond=0)
            else:
                self.smoothed_charge_minutes = None
                self.full_charge_timestamp = None

            self.empty_timestamp = None
            self.smoothed_discharge_minutes = None
            self.smoothed_drain_w = 0.0

        else:  # Idle or Full
            if self.discharge_samples and (now - self.discharge_samples[-1][0] > 60.0):
                self.discharge_samples.clear()
                self.smoothed_drain_w = 0.0
            if self.charge_samples and (now - self.charge_samples[-1][0] > 60.0):
                self.charge_samples.clear()
                self.smoothed_charge_w = 0.0

            self.empty_timestamp = None
            self.full_charge_timestamp = None
            self.smoothed_discharge_minutes = None
            self.smoothed_charge_minutes = None


class OukitelDataCoordinator(DataUpdateCoordinator):
    """Fetches Oukitel station data; prefers LAN push, falls back to cloud polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: AcceleronixCloudClient,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        connection_mode: str = DEFAULT_CONNECTION_MODE,
        host: str | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self.connection_mode = connection_mode
        self.last_wake_time: float = 0.0
        self.lan_host: str | None = host.strip() if (host and isinstance(host, str) and host.strip()) else None
        self.predictive_tracker = OukitelPredictiveTracker(client)

        self._lan_session: LocalSession | None = None
        self._lan_listen_task: asyncio.Task | None = None
        self._lan_state: dict[int, Any] = {}
        self._lan_last_report: float | None = None
        self._lan_connected_at: float | None = None
        self._lan_active = False
        self._paused: bool = False
        self._user_overrides: dict[str, tuple] = {}
        self._last_device_list_check: float = 0.0
        self.last_user_command_time: float = 0.0

    def async_set_updated_data(self, data: dict[str, Any]) -> None:
        """Update coordinator data and refresh predictive autonomy tracker."""
        if hasattr(self, "predictive_tracker") and self.predictive_tracker is not None:
            self.predictive_tracker.update(data)
        super().async_set_updated_data(data)

    @property
    def is_paused(self) -> bool:
        """Return True if communication with the power station is paused."""
        return self._paused

    def async_set_user_override(
        self, key: str, value: Any, ttl: float = 60.0, min_hold: float = 5.0
    ) -> None:
        """Record user command override so stale telemetry does not overwrite commanded state."""
        now = time.time()
        self.last_user_command_time = now
        self._user_overrides[key] = (value, now + ttl, now + min_hold)
        if self.data is not None:
            self.data[key] = value
        if self._lan_state is not None:
            self._lan_state[key] = value

    def async_clear_user_override(self, key: str) -> None:
        """Cancel user command override immediately (e.g. if cloud command failed)."""
        self._user_overrides.pop(key, None)

    async def async_send_switch_command(self, key: str, value: bool) -> bool:
        """Send switch command immediately via LAN if active, and synchronize with Cloud."""
        tag_map = {
            "ac_switch": 43,
            "usb_switch": 44,
            "dc_switch": 46,
        }
        tag = tag_map.get(key)
        lan_ok = False
        if tag is not None and self._lan_active and self._lan_session:
            try:
                await self._lan_session.send_write(tag, "bool", value)
                lan_ok = True
                _LOGGER.debug("oukitel: Instant LAN switch write: tag %s = %s", tag, value)
            except Exception as exc:
                _LOGGER.warning("oukitel: LAN write failed: %s", exc)

        # Always synchronize clean single-property switch command to Cloud if not LAN-only
        # (exact same method as voltage), so Quectel cloud shadow aligns immediately and WonderFree stops bouncing
        cloud_ok = False
        if self.connection_mode != MODE_LAN:
            try:
                cloud_ok = await self.hass.async_add_executor_job(
                    self.client.control_device,
                    [{key: value}],
                )
            except Exception as exc:
                _LOGGER.warning("oukitel: Cloud switch sync failed: %s", exc)

        return lan_ok or cloud_ok

    async def _async_sync_physical_change_to_cloud(self, key: str, value: bool) -> None:
        """Propagate physical hardware switch changes to Cloud shadow so WonderFree updates in < 1s."""
        try:
            await self.hass.async_add_executor_job(
                self.client.control_device,
                [{key: value}],
            )
            _LOGGER.debug("oukitel: Successfully synced physical switch %s=%s to Cloud", key, value)
        except Exception as exc:
            _LOGGER.debug("oukitel: Failed to sync physical switch %s to Cloud: %s", key, exc)

    def _apply_user_overrides(self, target: dict[str, Any]) -> None:
        """Apply active user overrides to incoming telemetry dictionary."""
        now = time.time()
        expired = []
        for k, entry in list(self._user_overrides.items()):
            if len(entry) == 3:
                v, until, min_hold = entry
            else:
                v, until = entry
                min_hold = 0.0

            if now < until:
                if k in target:
                    val_t = target[k]
                    # Only allow expiring after min_hold has elapsed to prevent jitter from out-of-order packets
                    if now >= min_hold:
                        if isinstance(v, bool):
                            if bool(val_t) == v:
                                expired.append(k)
                                continue
                        elif isinstance(v, (int, float)):
                            try:
                                if abs(float(val_t) - float(v)) < 0.1:
                                    expired.append(k)
                                    continue
                            except (ValueError, TypeError):
                                pass
                        elif str(val_t).strip().lower() == str(v).strip().lower():
                            expired.append(k)
                            continue
                target[k] = v
            else:
                expired.append(k)
        for k in expired:
            self._user_overrides.pop(k, None)

    async def async_set_paused(self, paused: bool) -> None:
        """Pause or resume polling, LAN connection, and wake-up commands."""
        if self._paused == paused:
            return
        self._paused = paused
        if paused:
            _LOGGER.info(
                "oukitel: Pausing integration — disconnecting LAN, stopping wake requests, setting active power to 0W"
            )
            await self.async_shutdown_lan()
            paused_data = _build_paused_data(self.data or self._lan_state)
            self._lan_state = paused_data
            self.async_set_updated_data(paused_data)
        else:
            _LOGGER.info(
                "oukitel: Resuming integration — re-establishing connection and requesting refresh"
            )
            if self.connection_mode != MODE_CLOUD:
                self.hass.async_create_task(self.async_setup_lan())
            await self.async_request_refresh()

    # ------------------------------------------------------------------
    # LAN lifecycle
    # ------------------------------------------------------------------

    async def async_setup_lan(self) -> None:
        """Try to start LAN mode; silently skips if device not found on LAN or paused."""
        if self._paused:
            _LOGGER.debug("oukitel: Skipping LAN setup — integration is paused")
            return

        if self.connection_mode == MODE_CLOUD:
            _LOGGER.info("oukitel: Connection mode set to Cloud Only — skipping LAN setup")
            return

        if not self.client.device_key:
            await self.hass.async_add_executor_job(self.client.fetch_device_info)

        host = self.lan_host
        if host:
            _LOGGER.info("oukitel: Using configured static host %s for LAN connection", host)
        else:
            _LOGGER.info("oukitel: Scanning LAN for device %s …", self.client.device_key)
            host = await find_device_on_lan(self.client.device_key or "")
            if not host:
                _LOGGER.info("oukitel: Device not found on LAN — running in cloud mode")
                return
            self.lan_host = host

        auth_key = await self.hass.async_add_executor_job(self.client.fetch_auth_key)
        if not auth_key:
            _LOGGER.info("oukitel: authKey unavailable — running in cloud mode")
            return

        # Seed static diagnostics (BMS_Version, AC_Version, etc.) from Cloud shadow if reachable
        try:
            cloud_snapshot = await self.hass.async_add_executor_job(self.client.get_telemetry)
            if cloud_snapshot:
                static_keys = (
                    "BMS_Version",
                    "AC_Version",
                    "Frequency_Switchover",
                    "ACvoltage_Switchover",
                    "ac_charging_limit",
                )
                for k in static_keys:
                    if k in cloud_snapshot and cloud_snapshot[k] is not None:
                        self._lan_state[k] = cloud_snapshot[k]
                _unpack_port_data(self._lan_state)
        except Exception as exc:
            _LOGGER.debug("oukitel: Could not seed initial static metadata from cloud: %s", exc)

        _LOGGER.info("oukitel: Device found at %s — starting LAN session", host)
        await self._start_lan_session(host, auth_key)

    async def _start_lan_session(self, host: str, auth_key: str) -> None:
        self._lan_session = LocalSession(
            host=host,
            auth_key_b64=auth_key,
            on_telemetry=self._on_lan_telemetry,
        )
        try:
            await self._lan_session.connect()
        except (LocalSessionError, LocalAuthError) as exc:
            _LOGGER.warning("oukitel: LAN session failed to start: %s — using cloud", exc)
            self._lan_session = None
            return

        self._lan_active = True
        self._lan_connected_at = time.monotonic()
        _LOGGER.info("oukitel: LAN session established and active with %s!", host)
        self._lan_listen_task = asyncio.ensure_future(self._lan_read_loop(host, auth_key))

    async def _lan_read_loop(self, host: str, auth_key: str) -> None:
        while True:
            if self._paused:
                _LOGGER.debug("oukitel: LAN read loop stopped because integration is paused")
                break
            try:
                await self._lan_session.read_loop()
            except Exception as exc:
                _LOGGER.debug("oukitel: LAN read loop ended: %s", exc)

            if self._lan_session:
                await self._lan_session.close()
                self._lan_session = None

            if self._paused:
                break

            _LOGGER.info("oukitel: LAN disconnected — reconnecting in %ss", _LAN_RECONNECT_DELAY)
            await asyncio.sleep(_LAN_RECONNECT_DELAY)

            if self._paused:
                break

            # Re-scan: device IP may have changed
            host_new = await find_device_on_lan(self.client.device_key or "")
            target = host_new or host
            self._lan_session = LocalSession(
                host=target,
                auth_key_b64=auth_key,
                on_telemetry=self._on_lan_telemetry,
            )
            try:
                await self._lan_session.connect()
                self._lan_connected_at = time.monotonic()
            except (LocalSessionError, LocalAuthError) as exc:
                _LOGGER.warning("oukitel: LAN reconnect failed: %s", exc)
                self._lan_session = None
                self._lan_active = False
                return

    def _on_lan_telemetry(self, fields: dict[int, Any]) -> None:
        if self._paused:
            return
        self._lan_last_report = time.monotonic()
        
        # Base LAN tag mapping to HA sensor keys
        tag_map = {
            1: "battery_percentage",
            2: "remain_time",
            3: "remain_charging_time",
            4: "total_input_power",
            5: "total_output_power",
            11: "ac_input",
            12: "dc_input",
            14: "temp",
            20: "ac_charging_limit",
            27: "Frequency_Switchover",
            28: "ACvoltage_Switchover",
            31: "AC_Version",
            33: "inverter_temp",
            34: "BMS_Version",
            43: "ac_switch",
            44: "usb_switch",
            46: "dc_switch",
        }
        
        current_data = dict(self._lan_state or self.data or {})
        for tag, val in fields.items():
            if tag in tag_map:
                current_data[tag_map[tag]] = val
            if tag == 2:
                current_data["remaining_time"] = val
            current_data[str(tag)] = val
            if tag in (6, 7, 8, 9, 43, 44, 46):
                current_data[tag] = val

        _unpack_port_data(current_data)
        self._apply_user_overrides(current_data)

        # In Auto mode, synchronize physical button changes to Cloud shadow immediately
        # so Wonderfree app reflects physical presses in < 1s instead of waiting ~40s
        if self.connection_mode != MODE_LAN and self._lan_state:
            for sw_key in ("ac_switch", "usb_switch", "dc_switch"):
                old_val = self._lan_state.get(sw_key)
                new_val = current_data.get(sw_key)
                if (
                    old_val is not None
                    and new_val is not None
                    and old_val != new_val
                    and sw_key not in self._user_overrides
                ):
                    _LOGGER.debug(
                        "oukitel: Physical change detected for %s (%s -> %s), syncing to Cloud shadow",
                        sw_key, old_val, new_val,
                    )
                    self.hass.async_create_task(
                        self._async_sync_physical_change_to_cloud(sw_key, new_val)
                    )

        self._lan_state = current_data
        self.hass.loop.call_soon_threadsafe(
            self.async_set_updated_data, dict(self._lan_state)
        )

    async def async_shutdown_lan(self) -> None:
        if self._lan_listen_task and not self._lan_listen_task.done():
            self._lan_listen_task.cancel()
            try:
                await self._lan_listen_task
            except asyncio.CancelledError:
                pass
        if self._lan_session:
            await self._lan_session.close()
            self._lan_session = None
        self._lan_active = False

    # ------------------------------------------------------------------
    # DataUpdateCoordinator
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        if self._paused:
            _LOGGER.debug("oukitel: Polling skipped — integration is paused (returning zeroed power metrics)")
            return _build_paused_data(self.data or self._lan_state)

        if self.connection_mode == MODE_CLOUD:
            return await self._update_cloud()
        if self._lan_active and self._lan_state:
            return await self._update_lan()
        if self.connection_mode == MODE_LAN:
            # If LAN session is initializing in the background during setup, wait up to 4s
            for _ in range(40):
                if self._lan_active and self._lan_state:
                    return await self._update_lan()
                await asyncio.sleep(0.1)
            if self._lan_active:
                return await self._update_lan()
            # If this is the initial setup/refresh and LAN hasn't connected yet,
            # seed from cloud snapshot so Home Assistant doesn't fail with ConfigEntryNotReady
            if not self.data:
                _LOGGER.warning(
                    "oukitel: LAN session not established during initial setup; seeding baseline from Cloud while LAN connects in background"
                )
                try:
                    cloud_baseline = await self._update_cloud()
                    if cloud_baseline:
                        return cloud_baseline
                except Exception as exc:
                    _LOGGER.debug("oukitel: Cloud initial fallback attempt failed: %s", exc)
            raise UpdateFailed("LAN session not active and mode is set to LAN Only")
        return await self._update_cloud()

    async def _update_lan(self) -> dict:
        if self._paused:
            return _build_paused_data(self._lan_state or self.data)

        now = time.monotonic()
        stale = (
            self._lan_last_report is not None
            and (now - self._lan_last_report) > _LAN_STALE_TIMEOUT
        )
        if stale:
            if self.connection_mode == MODE_LAN:
                _LOGGER.debug("oukitel: LAN telemetry stale (LAN Only mode — keeping state)")
            else:
                _LOGGER.info("oukitel: LAN telemetry stale — falling back to cloud")
                self._lan_active = False
                return await self._update_cloud()

        if self._lan_session:
            try:
                await self._lan_session.request_read()
            except Exception:
                pass

        if not self._lan_state:
            for _ in range(40):
                if self._lan_state:
                    break
                await asyncio.sleep(0.1)

        if not self._lan_state:
            if self.data:
                return dict(self.data)
            raise UpdateFailed("LAN session connected but no telemetry received yet")


        data = dict(self._lan_state)
        # Preserve static/cloud-only diagnostic tags if already known
        if self.data:
            for k in (
                "ACvoltage_Switchover",
                "Frequency_Switchover",
                "BMS_Version",
                "AC_Version",
                "wifi_signal",
            ):
                if k in self.data and k not in data:
                    data[k] = self.data[k]
        self._apply_user_overrides(data)
        return data

    async def _update_cloud(self) -> dict:
        if self._paused:
            return _build_paused_data(self.data)

        now = time.time()
        # Periodically refresh device list from cloud (every 60s) to keep onlineStatus accurate
        if now - self._last_device_list_check >= 60.0:
            self._last_device_list_check = now
            await self.hass.async_add_executor_job(self.client.fetch_device_info)

        # If device is reported offline in userDeviceList, do not send keep-alive or expect live telemetry
        if not getattr(self.client, "is_online", True):
            _LOGGER.debug("oukitel: Device is offline on Cloud gateway")
            offline_data = _build_paused_data(self.data)
            offline_data["online"] = False
            return offline_data

        # Do not issue wake_device if a user command was recently sent (within 15s)
        # to prevent isCover or command clashes on the battery's MQTT queue
        can_wake = (now - self.last_user_command_time) >= 15.0
        if (now - self.last_wake_time >= DEFAULT_WAKE_INTERVAL) and can_wake:
            await self.hass.async_add_executor_job(self.client.wake_device)
            self.last_wake_time = now

        data = await self.hass.async_add_executor_job(self.client.get_telemetry)
        if not data:
            # Device might have just gone offline, verify immediately via userDeviceList
            await self.hass.async_add_executor_job(self.client.fetch_device_info)
            if not getattr(self.client, "is_online", True):
                _LOGGER.info("oukitel: Device confirmed offline via userDeviceList")
                offline_data = _build_paused_data(self.data)
                offline_data["online"] = False
                return offline_data

            if can_wake:
                await self.hass.async_add_executor_job(self.client.wake_device)
                self.last_wake_time = time.time()
            data = await self.hass.async_add_executor_job(self.client.get_telemetry)

        if not data:
            raise UpdateFailed("Failed to communicate with Oukitel Cloud")

        merged = dict(self.data or {})
        merged.update(data)
        _unpack_port_data(merged)
        self._apply_user_overrides(merged)

        return merged

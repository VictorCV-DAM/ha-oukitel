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
from .switch_protocol import SWITCH_PROTOCOLS

_LOGGER = logging.getLogger(__name__)

_LAN_STALE_TIMEOUT = 150.0
_LAN_RECONNECT_DELAY = 10.0
_CLOUD_SNAPSHOT_INTERVAL = 60.0

STATIC_METADATA_KEYS = (
    "temp",
    "inverter_temp",
    "BMS_Version",
    "AC_Version",
    "wifi_signal",
    "Frequency_Switchover",
    "ACvoltage_Switchover",
    "ac_charging_limit",
)


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
    ac_val = _parse_dict(target.get(6) or target.get("6") or target.get("AC_Info") or target.get("ac_data"))
    if ac_val:
        sw = ac_val.get(1) if 1 in ac_val else (ac_val.get("1") if "1" in ac_val else ac_val.get("ac_switch"))
        if sw is not None:
            target["ac_switch"] = bool(sw)
        p = ac_val.get(2) if 2 in ac_val else ac_val.get("2")
        if p is None and "ac1_output" in ac_val:
            try:
                p = float(ac_val["ac1_output"])
            except (ValueError, TypeError):
                p = 0
        v = ac_val.get(3) if 3 in ac_val else ac_val.get("3")
        if p is not None:
            target["ac_output_power"] = p
        if v is not None:
            target["ac_output_voltage"] = v

    # 2. USB Info: 1=usb_switch, 2=USB-A power (W), 3=USB-C QC power (W)
    usb_val = _parse_dict(target.get(7) or target.get("7") or target.get("USB_Info") or target.get("usb_data"))
    if usb_val:
        sw = usb_val.get(1) if 1 in usb_val else (usb_val.get("1") if "1" in usb_val else usb_val.get("usb_switch"))
        if sw is not None:
            target["usb_switch"] = bool(sw)
        usb_a = usb_val.get(2) if 2 in usb_val else usb_val.get("2")
        usb_c = usb_val.get(3) if 3 in usb_val else usb_val.get("3")
        if usb_a is None and "USB_QC1_output" in usb_val:
            try:
                usb_a = float(usb_val["USB_QC1_output"])
            except (ValueError, TypeError):
                pass
        if usb_c is None and "USB_QC2_output" in usb_val:
            try:
                usb_c = float(usb_val["USB_QC2_output"])
            except (ValueError, TypeError):
                pass
        if usb_a is not None:
            target["usb_a_power"] = usb_a
        if usb_c is not None:
            target["usb_c_qc_power"] = usb_c

    # 3. Type-C Info: 2=Type-C 1 (W), 5=Type-C 2 (W), 6=Type-C 3 (W), 7=Type-C 4 (W)
    typec_val = _parse_dict(target.get(8) or target.get("8") or target.get("TypeC_Info") or target.get("typec_data"))
    if typec_val:
        c1 = typec_val.get(2) if 2 in typec_val else typec_val.get("2")
        c2 = typec_val.get(5) if 5 in typec_val else typec_val.get("5")
        c3 = typec_val.get(6) if 6 in typec_val else typec_val.get("6")
        c4 = typec_val.get(7) if 7 in typec_val else typec_val.get("7")
        if c1 is None and "Typec1_output" in typec_val:
            try:
                c1 = float(typec_val["Typec1_output"])
            except (ValueError, TypeError):
                pass
        if c2 is None and "Typec2_output" in typec_val:
            try:
                c2 = float(typec_val["Typec2_output"])
            except (ValueError, TypeError):
                pass
        if c3 is None and "Typec3_output" in typec_val:
            try:
                c3 = float(typec_val["Typec3_output"])
            except (ValueError, TypeError):
                pass
        if c4 is None and "Typec4_output" in typec_val:
            try:
                c4 = float(typec_val["Typec4_output"])
            except (ValueError, TypeError):
                pass
        if c1 is not None:
            target["typec1_power"] = c1
        if c2 is not None:
            target["typec2_power"] = c2
        if c3 is not None:
            target["typec3_power"] = c3
        if c4 is not None:
            target["typec4_power"] = c4

    # 4. DC Info: 1=dc_switch, 2=DC Car output power (W), 3=voltage (V), 4=current (A)
    dc_val = _parse_dict(target.get(9) or target.get("9") or target.get("DC_Info") or target.get("dc_data"))
    if dc_val:
        sw = dc_val.get(1) if 1 in dc_val else (dc_val.get("1") if "1" in dc_val else dc_val.get("dc_switch"))
        if sw is not None:
            target["dc_switch"] = bool(sw)
        dc_p = dc_val.get(2) if 2 in dc_val else dc_val.get("2")
        if dc_p is None and "car1_output" in dc_val:
            try:
                dc_p = float(dc_val["car1_output"])
            except (ValueError, TypeError):
                pass
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
        config_entry_id: str | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.client = client
        self.config_entry_id = config_entry_id
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
        self._static_metadata: dict[str, Any] = {}
        self._last_cloud_snapshot: float = 0.0

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
        self, key: str, value: Any, ttl: float = 10.0, min_hold: float = 2.0
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
        """Send a switch command using the product's registered protocol."""
        product_key = getattr(self.client, "product_key", None)
        strategy, exact_match = SWITCH_PROTOCOLS.resolve(product_key)
        if not exact_match:
            _LOGGER.debug(
                "oukitel: No switch protocol registered for product_key %s; using %s",
                product_key,
                strategy.name,
            )

        lan_write = strategy.lan_write(key, value)
        if lan_write is None:
            return False

        lan_ok = False
        if self._lan_active and self._lan_session:
            try:
                await self._lan_session.send_write(
                    lan_write.tag, lan_write.kind, lan_write.value
                )
                lan_ok = True
                _LOGGER.debug(
                    "oukitel: Instant LAN %s switch write: tag %s kind %s = %s",
                    strategy.name,
                    lan_write.tag,
                    lan_write.kind,
                    lan_write.value,
                )
            except Exception as exc:
                _LOGGER.warning("oukitel: LAN write failed: %s", exc)

        cloud_ok = False
        cloud_mode = self.connection_mode != MODE_LAN
        should_sync_cloud = cloud_mode and (
            not lan_ok or strategy.sync_cloud_after_lan
        )
        cloud_payload = strategy.cloud_payload(key, value)
        if should_sync_cloud and cloud_payload is not None:
            try:
                cloud_ok = await self.hass.async_add_executor_job(
                    self.client.control_device,
                    cloud_payload,
                )
            except Exception as exc:
                _LOGGER.warning("oukitel: Cloud switch sync failed: %s", exc)
        elif should_sync_cloud and cloud_payload is None and not lan_ok:
            _LOGGER.error(
                "oukitel: Cloud switch control is not available for protocol %s; use LAN mode",
                strategy.name,
            )

        return lan_ok or cloud_ok

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

        # Seed static diagnostics (temp, BMS_Version, AC_Version, wifi_signal, etc.) from Cloud shadow
        try:
            cloud_snapshot = await self.hass.async_add_executor_job(self.client.get_telemetry)
            if cloud_snapshot:
                for k in STATIC_METADATA_KEYS:
                    val = cloud_snapshot.get(k)
                    if val is not None:
                        self._static_metadata[k] = val
                        self._lan_state[k] = val
                if "temp" in cloud_snapshot and "inverter_temp" not in self._static_metadata:
                    self._static_metadata["inverter_temp"] = cloud_snapshot["temp"]
                    self._lan_state["inverter_temp"] = cloud_snapshot["temp"]
                _unpack_port_data(self._lan_state)
                self._last_cloud_snapshot = time.monotonic()
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
            if self.connection_mode == MODE_LAN:
                _LOGGER.error(
                    "oukitel: LAN session failed to connect to %s: %s (Solo LAN mode — Cloud fallback disabled)",
                    host, exc,
                )
            else:
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

            # Re-scan or retry static host
            if self.lan_host:
                target = self.lan_host
            else:
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
                key = tag_map[tag]
                current_data[key] = val
                if tag == 14:
                    current_data["inverter_temp"] = current_data.get("inverter_temp") or val
                    self._static_metadata["temp"] = val
                    self._static_metadata["inverter_temp"] = self._static_metadata.get("inverter_temp") or val
                elif tag == 33:
                    current_data["temp"] = current_data.get("temp") or val
                    self._static_metadata["inverter_temp"] = val
                    self._static_metadata["temp"] = self._static_metadata.get("temp") or val
                elif key in STATIC_METADATA_KEYS:
                    self._static_metadata[key] = val
            if tag == 2:
                current_data["remaining_time"] = val
            current_data[str(tag)] = val
            if tag in (6, 7, 8, 9, 43, 44, 46):
                current_data[tag] = val

        # Ensure static metadata (temp, versions, switchovers, wifi signal) is always preserved
        for k, v in self._static_metadata.items():
            if k not in current_data or current_data[k] is None:
                current_data[k] = v

        _unpack_port_data(current_data)
        self._apply_user_overrides(current_data)

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
            # If LAN session is initializing in the background during setup, wait briefly
            for _ in range(60):
                if self._lan_active and self._lan_state:
                    return await self._update_lan()
                await asyncio.sleep(0.1)
            if self._lan_active and self._lan_state:
                return await self._update_lan()
            raise UpdateFailed(
                f"LAN session not active for host '{self.lan_host or 'auto'}'. Cloud fallback is disabled in Solo LAN mode."
            )
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
        # Preserve static/cloud-only diagnostic tags from metadata cache and prior state
        for k, v in self._static_metadata.items():
            if k not in data or data[k] is None:
                data[k] = v
        if self.data:
            for k in STATIC_METADATA_KEYS:
                if k in self.data and (k not in data or data[k] is None):
                    data[k] = self.data[k]
        self._apply_user_overrides(data)

        # Trigger background cloud shadow refresh every 60s in auto/cloud mode
        now = time.monotonic()
        if (
            self.connection_mode != MODE_LAN
            and (now - self._last_cloud_snapshot) >= _CLOUD_SNAPSHOT_INTERVAL
        ):
            self.hass.async_create_task(self._async_refresh_cloud_shadow())

        return data

    async def _async_refresh_cloud_shadow(self) -> None:
        """Periodic background refresh of cloud-only metrics (temp, wifi_signal, versions) while LAN runs."""
        if self._paused or not getattr(self.client, "access_token", None):
            return
        self._last_cloud_snapshot = time.monotonic()
        try:
            cloud_snapshot = await self.hass.async_add_executor_job(self.client.get_telemetry)
            if cloud_snapshot:
                updated = False
                for k in STATIC_METADATA_KEYS:
                    val = cloud_snapshot.get(k)
                    if val is not None and self._static_metadata.get(k) != val:
                        self._static_metadata[k] = val
                        if self._lan_state is not None:
                            self._lan_state[k] = val
                        updated = True
                if "temp" in cloud_snapshot and "inverter_temp" not in self._static_metadata:
                    self._static_metadata["inverter_temp"] = cloud_snapshot["temp"]
                    if self._lan_state is not None:
                        self._lan_state["inverter_temp"] = cloud_snapshot["temp"]
                    updated = True

                if updated and self.data:
                    merged = dict(self.data)
                    for k in STATIC_METADATA_KEYS:
                        if k in self._static_metadata:
                            merged[k] = self._static_metadata[k]
                    self.async_set_updated_data(merged)
        except Exception as exc:
            _LOGGER.debug("oukitel: Cloud shadow refresh notice: %s", exc)

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

        data = await self.hass.async_add_executor_job(self.client.get_telemetry)
        if not data:
            # Device might have just gone offline, verify immediately via userDeviceList
            await self.hass.async_add_executor_job(self.client.fetch_device_info)
            if not getattr(self.client, "is_online", True):
                _LOGGER.info("oukitel: Device confirmed offline via userDeviceList")
                offline_data = _build_paused_data(self.data)
                offline_data["online"] = False
                return offline_data

            can_wake = (now - self.last_user_command_time) >= 15.0
            if can_wake and (now - self.last_wake_time >= DEFAULT_WAKE_INTERVAL):
                await self.hass.async_add_executor_job(self.client.wake_device)
                self.last_wake_time = time.time()
                data = await self.hass.async_add_executor_job(self.client.get_telemetry)

        if not data:
            raise UpdateFailed("Failed to communicate with Oukitel Cloud")

        merged = dict(self.data or {})
        merged.update(data)
        for k in STATIC_METADATA_KEYS:
            if k in merged and merged[k] is not None:
                self._static_metadata[k] = merged[k]
        _unpack_port_data(merged)
        self._apply_user_overrides(merged)

        return merged

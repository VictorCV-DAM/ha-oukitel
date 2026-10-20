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

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AcceleronixCloudClient
from .const import (
    CONF_AUTH_KEY,
    CONF_HOST,
    DEFAULT_CONNECTION_MODE,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_WAKE_INTERVAL,
    DOMAIN,
    MODE_AUTO,
    MODE_CLOUD,
    MODE_LAN,
    get_battery_capacity_wh,
)
from .diag_logger import diag_log
from .local_scan import find_device_on_lan
from .local_session import LocalSession, LocalAuthError, LocalSessionError

_LOGGER = logging.getLogger(__name__)

_LAN_STALE_TIMEOUT = 150.0
_LAN_RECONNECT_DELAY = 10.0
_CLOUD_SNAPSHOT_INTERVAL = 60.0
_LAN_RETRY_INTERVAL = 20.0
_LAN_SILENCE_TIMEOUT = 150.0
_LAN_REARM_TIMEOUT = 65.0
_LAN_REARM_INTERVAL = 30.0

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

PERSISTED_SNAPSHOT_KEYS = (
    "battery_percentage",
    "total_input_power",
    "total_output_power",
    "ac_input",
    "dc_input",
    "ac_output_power",
    "ac_output_voltage",
    "dc_output_power",
    "dc_output_current",
    "dc_output_voltage",
    "usb_a_power",
    "usb_c_qc_power",
    "typec1_power",
    "typec2_power",
    "typec3_power",
    "typec4_power",
    "remain_time",
    "remaining_time",
    "remain_charging_time",
    "ac_switch",
    "dc_switch",
    "usb_switch",
    "ac_charging_limit",
    "Frequency_Switchover",
    "ACvoltage_Switchover",
    "BMS_Version",
    "AC_Version",
    "temp",
    "inverter_temp",
    "wifi_signal",
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
            try:
                target["ac_output_power"] = int(round(float(p)))
            except (ValueError, TypeError):
                target["ac_output_power"] = p
        if v is not None:
            try:
                target["ac_output_voltage"] = int(round(float(v)))
            except (ValueError, TypeError):
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
            try:
                target["usb_a_power"] = int(round(float(usb_a)))
            except (ValueError, TypeError):
                target["usb_a_power"] = usb_a
        if usb_c is not None:
            try:
                target["usb_c_qc_power"] = int(round(float(usb_c)))
            except (ValueError, TypeError):
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
        for c_idx, c_val in ((1, c1), (2, c2), (3, c3), (4, c4)):
            if c_val is not None:
                try:
                    target[f"typec{c_idx}_power"] = int(round(float(c_val)))
                except (ValueError, TypeError):
                    target[f"typec{c_idx}_power"] = c_val

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
            try:
                target["dc_output_power"] = int(round(float(dc_p)))
            except (ValueError, TypeError):
                target["dc_output_power"] = dc_p
        if dc_v is not None:
            try:
                target["dc_output_voltage"] = int(round(float(dc_v)))
            except (ValueError, TypeError):
                target["dc_output_voltage"] = dc_v
        if dc_a is not None:
            try:
                target["dc_output_current"] = round(float(dc_a), 2)
            except (ValueError, TypeError):
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
        config_entry: ConfigEntry | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll_interval),
        )
        self.config_entry = config_entry
        self.client = client
        self.connection_mode = connection_mode
        self.last_wake_time: float = 0.0

        resolved_host = host
        if not resolved_host and config_entry:
            resolved_host = config_entry.options.get(CONF_HOST) or config_entry.data.get(CONF_HOST)
        self.lan_host: str | None = (
            resolved_host.strip()
            if (resolved_host and isinstance(resolved_host, str) and resolved_host.strip())
            else None
        )
        self.predictive_tracker = OukitelPredictiveTracker(client)

        self._lan_session: LocalSession | None = None
        self._lan_listen_task: asyncio.Task | None = None
        self._lan_state: dict[int, Any] = {}
        self._lan_last_report: float | None = None
        self._lan_connected_at: float | None = None
        self._lan_active = False
        self._lan_has_valid_telemetry: bool = False
        self._last_lan_attempt: float = time.monotonic()
        self._lan_setup_in_flight: bool = False
        self._lan_last_rearm: float = 0.0
        self._cached_auth_key: str | None = (
            getattr(client, "auth_key", None)
            or (config_entry.options.get(CONF_AUTH_KEY) if config_entry else None)
            or (config_entry.data.get(CONF_AUTH_KEY) if config_entry else None)
        )
        self._paused: bool = False
        self._user_overrides: dict[str, tuple] = {}
        self._last_device_list_check: float = 0.0
        self.last_user_command_time: float = 0.0
        self._static_metadata: dict[str, Any] = dict(
            (config_entry.data.get("static_metadata") or {}) if config_entry else {}
        )
        self._last_cloud_snapshot: float = 0.0
        self._last_entry_persist: float = -60.0
        self._use_struct_switch_protocol: bool | None = None
        self._last_valid_battery: float | None = (
            config_entry.data.get("last_battery_percentage") if config_entry else None
        )
        if config_entry and isinstance(config_entry.data.get("last_telemetry_snapshot"), dict):
            for k, v in config_entry.data["last_telemetry_snapshot"].items():
                if v is not None and k not in self._lan_state:
                    self._lan_state[k] = v
                if k in STATIC_METADATA_KEYS and v is not None and k not in self._static_metadata:
                    self._static_metadata[k] = v
            # Seed raw tag keys so _unpack_port_data doesn't revert to uninitialized states
            sw_tag_map = {"ac_switch": 43, "usb_switch": 44, "dc_switch": 46}
            for sw_k, sw_tag in sw_tag_map.items():
                if sw_k in self._lan_state:
                    self._lan_state[sw_tag] = self._lan_state[sw_k]
                    self._lan_state[str(sw_tag)] = self._lan_state[sw_k]
            if "total_input_power" in self._lan_state:
                self._lan_state[4] = self._lan_state["total_input_power"]
                self._lan_state["4"] = self._lan_state["total_input_power"]
            if "total_output_power" in self._lan_state:
                self._lan_state[5] = self._lan_state["total_output_power"]
                self._lan_state["5"] = self._lan_state["total_output_power"]

    def async_set_updated_data(self, data: dict[str, Any]) -> None:
        """Update coordinator data and refresh predictive autonomy tracker."""
        if data and self.config_entry:
            try:
                now_mono = time.monotonic()
                new_data = None
                batt = data.get("battery_percentage")
                batt_changed = False
                if batt is not None:
                    batt_int = int(round(float(batt)))
                    if batt_int > 0:
                        self._last_valid_battery = batt_int
                        if self.config_entry.data.get("last_battery_percentage") != batt_int:
                            new_data = dict(self.config_entry.data)
                            new_data["last_battery_percentage"] = batt_int
                            batt_changed = True

                # Check if static metadata gained any new keys
                persisted_meta = dict(self.config_entry.data.get("static_metadata") or {})
                meta_changed = False
                for k in STATIC_METADATA_KEYS:
                    val = self._static_metadata.get(k) if k in self._static_metadata else data.get(k)
                    if val is not None and persisted_meta.get(k) != val:
                        persisted_meta[k] = val
                        self._static_metadata[k] = val
                        meta_changed = True

                if batt_changed or meta_changed or (now_mono - self._last_entry_persist >= 60.0):
                    if new_data is None:
                        new_data = dict(self.config_entry.data)
                    new_data["static_metadata"] = persisted_meta
                    snapshot = dict(self.config_entry.data.get("last_telemetry_snapshot") or {})
                    for k in PERSISTED_SNAPSHOT_KEYS:
                        if k in data and data[k] is not None:
                            snapshot[k] = data[k]
                    new_data["last_telemetry_snapshot"] = snapshot
                    self._last_entry_persist = now_mono
                    if new_data != self.config_entry.data:
                        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            except Exception:
                pass
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

        # Sync raw and string tag keys into state so _unpack_port_data doesn't revert to stale values
        tag_key_map = {
            "ac_switch": 43,
            "usb_switch": 44,
            "dc_switch": 46,
            "ac_charging_limit": 20,
            "Frequency_Switchover": 27,
            "ACvoltage_Switchover": 28,
        }
        if key in tag_key_map:
            tag = tag_key_map[key]
            tag_val = value
            if key == "Frequency_Switchover" and isinstance(value, str):
                tag_val = 0 if "50" in value else 1
            elif key == "ACvoltage_Switchover" and isinstance(value, str):
                try:
                    tag_val = int(value.replace("V", "").strip())
                except Exception:
                    tag_val = value
            if self.data is not None:
                self.data[tag] = tag_val
                self.data[str(tag)] = tag_val
            if self._lan_state is not None:
                self._lan_state[tag] = tag_val
                self._lan_state[str(tag)] = tag_val

    def async_clear_user_override(self, key: str) -> None:
        """Cancel user command override immediately (e.g. if cloud command failed)."""
        self._user_overrides.pop(key, None)

    def _detect_switch_protocol(self) -> bool:
        """Detect whether the station uses nested STRUCT TSL tags (BP series/P5000) or flat tags (P2001 Plus)."""
        if self._use_struct_switch_protocol is not None:
            return self._use_struct_switch_protocol

        # 1. Check known product_key
        pk = (getattr(self.client, "product_key", None) or "").strip().lower()
        if pk in ("p11wn7",):  # P2001 Plus
            self._use_struct_switch_protocol = False
            return False
        if pk in ("p11ssr",):  # BP2000 Pro / BP2000
            self._use_struct_switch_protocol = True
            return True

        # 2. If station reported direct flat switch tags 43, 44 or 46
        for t in (43, 44, 46):
            if self._lan_state and (t in self._lan_state or str(t) in self._lan_state):
                self._use_struct_switch_protocol = False
                return False
            if self.data and (t in self.data or str(t) in self.data):
                self._use_struct_switch_protocol = False
                return False

        # 3. Check telemetry signature: if station reports Tag 6, 7 or 9 as nested struct with subtag 1
        for t in (6, 7, 9):
            d = (self._lan_state.get(t) if self._lan_state else None) or (self.data.get(t) if self.data else None)
            if isinstance(d, dict) and (1 in d or "1" in d):
                self._use_struct_switch_protocol = True
                return True

        # Default fallback to flat tags (P2001 Plus baseline)
        self._use_struct_switch_protocol = False
        return False

    async def async_send_switch_command(self, key: str, value: bool) -> bool:
        """Send switch command adaptively via LAN if active, and synchronize with Cloud."""
        is_struct = self._detect_switch_protocol()

        for attempt in range(2):
            # 1. LAN write dispatch
            lan_ok = False
            session = self._lan_session
            if self._lan_active and session and session._writer and session._iv:
                try:
                    if is_struct:
                        struct_map = {
                            "ac_switch": (6, 1),
                            "usb_switch": (7, 1),
                            "dc_switch": (9, 1),
                        }
                        if key in struct_map:
                            tag, subtag = struct_map[key]
                            await session.send_write(tag, "struct", [(subtag, "bool", value)])
                            lan_ok = True
                            _LOGGER.debug(
                                "oukitel: Instant LAN struct switch write: tag %s subtag %s = %s",
                                tag, subtag, value,
                            )
                    else:
                        tag_map = {
                            "ac_switch": 43,
                            "usb_switch": 44,
                            "dc_switch": 46,
                        }
                        tag = tag_map.get(key)
                        if tag is not None:
                            await session.send_write(tag, "bool", value)
                            lan_ok = True
                            _LOGGER.debug("oukitel: Instant LAN flat switch write: tag %s = %s", tag, value)
                except Exception as exc:
                    _LOGGER.warning("oukitel: LAN write failed: %s", exc)

            # If LAN write succeeded, return True immediately without blocking on cloud!
            if lan_ok:
                return True

            # 2. Cloud fallback only if LAN failed, not in Solo LAN mode, and authenticated
            cloud_ok = False
            if self.connection_mode != MODE_LAN and getattr(self.client, "access_token", None):
                try:
                    if is_struct:
                        cloud_struct_map = {
                            "ac_switch": "ac_data",
                            "usb_switch": "usb_data",
                            "dc_switch": "dc_data",
                        }
                        prop = cloud_struct_map.get(key)
                        if prop:
                            cloud_payload = [{prop: {key: value}}]
                        else:
                            cloud_payload = [{key: value}]
                    else:
                        cloud_payload = [{key: value}]

                    cloud_ok = await self.hass.async_add_executor_job(
                        self.client.control_device,
                        cloud_payload,
                    )
                except Exception as exc:
                    _LOGGER.warning("oukitel: Cloud switch sync failed: %s", exc)

            if cloud_ok:
                return True

            if attempt == 0:
                await asyncio.sleep(0.5)

        return False

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

        if self._lan_setup_in_flight:
            _LOGGER.debug("oukitel: LAN setup already in flight — skipping concurrent attempt")
            return

        self._lan_setup_in_flight = True
        try:
            if not self.client.device_key and getattr(self.client, "access_token", None):
                await self.hass.async_add_executor_job(self.client.fetch_device_info)

            # In Auto mode, if cloud confirms the station is powered off / offline, defer LAN setup
            if (
                self.connection_mode != MODE_LAN
                and getattr(self.client, "access_token", None)
                and not getattr(self.client, "is_online", True)
            ):
                _LOGGER.debug(
                    "oukitel: Station is confirmed offline via cloud device list — deferring initial LAN dial"
                )
                return

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
                if (
                    self.config_entry
                    and not self.config_entry.options.get(CONF_HOST)
                    and self.config_entry.data.get(CONF_HOST) != host
                ):
                    new_data = dict(self.config_entry.data)
                    new_data[CONF_HOST] = host
                    self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)

            auth_key = getattr(self.client, "auth_key", None) or self._cached_auth_key
            if not auth_key and getattr(self.client, "access_token", None):
                auth_key = await self.hass.async_add_executor_job(self.client.fetch_auth_key)
            if not auth_key:
                auth_key = self._cached_auth_key
            if not auth_key:
                _LOGGER.info("oukitel: authKey unavailable — running in cloud mode")
                return
            self._cached_auth_key = auth_key

            if (
                self.config_entry
                and auth_key
                and self.config_entry.data.get(CONF_AUTH_KEY) != auth_key
            ):
                new_data = dict(self.config_entry.data)
                new_data[CONF_AUTH_KEY] = auth_key
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)

            # Seed only static metadata (BMS_Version, AC_Version, etc.) from Cloud shadow — never pollute LAN state with stale dynamic metrics
            if getattr(self.client, "access_token", None):
                try:
                    cloud_snapshot = await self.hass.async_add_executor_job(self.client.get_telemetry)
                    if cloud_snapshot:
                        for k in STATIC_METADATA_KEYS:
                            val = cloud_snapshot.get(k)
                            if val is not None:
                                self._static_metadata[k] = val
                        self._last_cloud_snapshot = time.monotonic()
                except Exception as exc:
                    _LOGGER.debug("oukitel: Could not seed static metadata from cloud: %s", exc)

            _LOGGER.info("oukitel: Target device host %s — initiating LAN session", host)
            await self._start_lan_session(host, auth_key)
        finally:
            self._lan_setup_in_flight = False

    async def _start_lan_session(self, host: str, auth_key: str) -> None:
        session = LocalSession(
            host=host,
            auth_key_b64=auth_key,
            on_telemetry=self._on_lan_telemetry,
        )
        max_attempts = 3
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                await session.connect()
                last_exc = None
                break
            except (LocalSessionError, LocalAuthError) as exc:
                last_exc = exc
                if attempt < max_attempts:
                    _LOGGER.info(
                        "oukitel: LAN session attempt %s/%s failed (%s), retrying in 2s...",
                        attempt, max_attempts, exc,
                    )
                    await asyncio.sleep(2.0)

        if last_exc:
            # Fallback: if configured host failed, perform UDP broadcast scan to discover IP change
            discovered = None
            try:
                _LOGGER.info("oukitel: Host %s unreachable — scanning LAN via UDP broadcast for %s...", host, self.client.device_key)
                discovered = await find_device_on_lan(self.client.device_key or "")
            except Exception as scan_exc:
                _LOGGER.debug("oukitel: Fallback UDP scan failed: %s", scan_exc)

            if discovered and discovered != host:
                _LOGGER.info("oukitel: Device discovered at new IP %s (was %s) — connecting...", discovered, host)
                host = discovered
                self.lan_host = discovered
                session = LocalSession(
                    host=host,
                    auth_key_b64=auth_key,
                    on_telemetry=self._on_lan_telemetry,
                )
                try:
                    await session.connect()
                    last_exc = None
                except (LocalSessionError, LocalAuthError) as exc:
                    last_exc = exc

        if last_exc:
            if self.connection_mode == MODE_LAN or not getattr(self.client, "access_token", None):
                _LOGGER.error(
                    "oukitel: LAN session failed to connect to %s: %s (Offline/LAN mode — scheduling persistent reconnect)",
                    host, last_exc,
                )
            else:
                _LOGGER.warning("oukitel: LAN session failed to start on %s: %s — scheduling persistent reconnect and using cloud", host, last_exc)
            self._lan_session = None
            self._lan_active = False
            self._lan_last_report = None
            self._lan_last_rearm = 0.0
            # Launch background reconnect loop so it recovers automatically as soon as the station is ready
            if self._lan_listen_task is None or self._lan_listen_task.done():
                self._lan_listen_task = asyncio.ensure_future(self._lan_read_loop(host, auth_key))
            return

        self._lan_session = session
        self._lan_active = True
        self._lan_last_report = None
        self._lan_connected_at = time.monotonic()
        self._lan_last_rearm = 0.0
        _LOGGER.info("oukitel: LAN session established and active with %s!", host)
        self._lan_listen_task = asyncio.ensure_future(self._lan_read_loop(host, auth_key))

    async def _lan_read_loop(self, host: str, auth_key: str) -> None:
        reconnect_delay = _LAN_RECONNECT_DELAY
        reported_disconnect = False
        target = host
        while True:
            if self._paused:
                _LOGGER.debug("oukitel: LAN read loop stopped because integration is paused")
                break
            if self._lan_session and self._lan_active:
                try:
                    await self._lan_session.read_loop()
                except Exception as exc:
                    _LOGGER.debug("oukitel: LAN read loop ended: %s", exc)

                if self._lan_session:
                    await self._lan_session.close()
                    self._lan_session = None

                self._lan_active = False
                self._lan_last_report = None
                self._lan_last_rearm = 0.0

            if self._paused:
                break

            if not reported_disconnect:
                _LOGGER.info(
                    "oukitel: LAN disconnected — retrying connection in background (initial delay %.1fs)",
                    reconnect_delay,
                )
                reported_disconnect = True
            else:
                _LOGGER.debug("oukitel: LAN waiting to reconnect in %.1fs", reconnect_delay)

            await asyncio.sleep(reconnect_delay)

            if self._paused:
                break

            # Try connecting to current target host
            session = LocalSession(
                host=target,
                auth_key_b64=auth_key,
                on_telemetry=self._on_lan_telemetry,
            )
            try:
                await session.connect()
                self._lan_session = session
                self._lan_active = True
                self._lan_last_report = None
                self._lan_connected_at = time.monotonic()
                self._lan_last_rearm = 0.0
                reconnect_delay = _LAN_RECONNECT_DELAY
                reported_disconnect = False
                _LOGGER.info("oukitel: LAN session re-established with %s!", target)
            except (LocalSessionError, LocalAuthError) as exc:
                _LOGGER.debug("oukitel: LAN reconnect to %s failed: %s", target, exc)
                self._lan_session = None
                self._lan_active = False
                self._lan_last_report = None
                self._lan_last_rearm = 0.0
                # If target failed, scan LAN via UDP to see if IP changed on router
                try:
                    discovered = await find_device_on_lan(self.client.device_key or "")
                    if discovered and discovered != target:
                        _LOGGER.info("oukitel: Discovered station at new IP %s — updating target", discovered)
                        target = discovered
                        self.lan_host = discovered
                except Exception:
                    pass
                reconnect_delay = min(reconnect_delay * 1.5, 30.0)
                continue

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
        
        current_data = dict(self.data or {})
        if self._lan_state:
            current_data.update(self._lan_state)

        for tag, val in fields.items():
            if tag in tag_map:
                key = tag_map[tag]
                # Filter out transient 0% battery glitch from handshake frames
                if key == "battery_percentage":
                    try:
                        val_float = float(val) if val is not None else 0.0
                    except (ValueError, TypeError):
                        val_float = 0.0

                    if val_float <= 0:
                        tot_in = float(current_data.get("total_input_power") or 0.0)
                        ac_out = float(current_data.get("ac_output_power") or 0.0)
                        if self._last_valid_battery is not None and self._last_valid_battery > 0:
                            _LOGGER.debug(
                                "oukitel: Preserving valid battery %s%% against 0%% transient frame",
                                self._last_valid_battery,
                            )
                            val = int(round(self._last_valid_battery))
                        elif tot_in > 50.0 or ac_out > 0.0:
                            _LOGGER.debug(
                                "oukitel: Station is active (in=%sW, out=%sW) — rejecting 0%% battery frame",
                                tot_in, ac_out,
                            )
                            continue
                        else:
                            val = 0
                    else:
                        batt_int = int(round(val_float))
                        self._last_valid_battery = batt_int
                        val = batt_int

                # Convert integer sensor values cleanly
                elif key in (
                    "total_input_power",
                    "total_output_power",
                    "ac_input",
                    "dc_input",
                    "ac_charging_limit",
                    "remain_time",
                    "remain_charging_time",
                    "temp",
                    "inverter_temp",
                ):
                    try:
                        val = int(round(float(val)))
                    except (ValueError, TypeError):
                        pass

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
                try:
                    current_data["remaining_time"] = int(round(float(val)))
                except (ValueError, TypeError):
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

        # Fall back to last known valid battery if not present in packet
        if current_data.get("battery_percentage") is None and self._last_valid_battery is not None:
            current_data["battery_percentage"] = int(round(self._last_valid_battery))

        # Zero out individual port outputs if corresponding switch is OFF
        if not current_data.get("ac_switch", True):
            current_data["ac_output_power"] = 0
            current_data["ac_output_voltage"] = 0
        if not current_data.get("dc_switch", True):
            current_data["dc_output_power"] = 0
            current_data["dc_output_current"] = 0.0
            current_data["dc_output_voltage"] = 0
        if not current_data.get("usb_switch", True):
            current_data["usb_a_power"] = 0
            current_data["usb_c_qc_power"] = 0
            current_data["typec1_power"] = 0
            current_data["typec2_power"] = 0
            current_data["typec3_power"] = 0
            current_data["typec4_power"] = 0

        # Calculate total output power from port outputs if tag 5 is missing/0 but ports are active
        ac_out = int(round(float(current_data.get("ac_output_power") or 0)))
        dc_out = int(round(float(current_data.get("dc_output_power") or 0)))
        usb_out = (
            int(round(float(current_data.get("usb_a_power") or 0)))
            + int(round(float(current_data.get("usb_c_qc_power") or 0)))
            + int(round(float(current_data.get("typec1_power") or 0)))
            + int(round(float(current_data.get("typec2_power") or 0)))
            + int(round(float(current_data.get("typec3_power") or 0)))
            + int(round(float(current_data.get("typec4_power") or 0)))
        )
        calculated_out = ac_out + dc_out + usb_out
        reported_out = int(round(float(current_data.get("total_output_power") or 0)))

        if 5 in fields and reported_out > 0:
            current_data["total_output_power"] = reported_out
        elif ("5" not in current_data) or any(t in fields for t in (6, 7, 8, 9)) or (reported_out == 0 and calculated_out > 0):
            current_data["total_output_power"] = calculated_out if calculated_out > 0 else reported_out
        else:
            current_data["total_output_power"] = reported_out

        # Derive missing AC or DC input power if total_input_power is present
        tot_in = current_data.get("total_input_power")
        dc_in = current_data.get("dc_input")
        ac_in = current_data.get("ac_input")
        if dc_in is None:
            dc_in = 0
            current_data["dc_input"] = 0
        else:
            dc_in = int(round(float(dc_in)))
            current_data["dc_input"] = dc_in

        if tot_in is not None:
            tot_in_int = int(round(float(tot_in)))
            current_data["total_input_power"] = tot_in_int
            if ac_in is None or "11" not in current_data:
                tot_out_int = int(round(float(current_data.get("total_output_power") or 0)))
                if tot_in_int > tot_out_int and tot_out_int > 0:
                    current_data["ac_input"] = max(0, tot_in_int - tot_out_int - dc_in)
                else:
                    current_data["ac_input"] = max(0, tot_in_int - dc_in)
            else:
                current_data["ac_input"] = int(round(float(ac_in)))
        elif ac_in is not None:
            ac_v = int(round(float(ac_in)))
            current_data["ac_input"] = ac_v
            current_data["total_input_power"] = ac_v + dc_in
        else:
            current_data["total_input_power"] = 0
            current_data["ac_input"] = 0

        if current_data.get("total_output_power") is None:
            current_data["total_output_power"] = 0

        if current_data.get("battery_percentage") is not None:
            self._lan_has_valid_telemetry = True

        self._lan_state = current_data
        diag_log(
            "COORD_LAN_STATE_UPDATED",
            tags_in_frame=list(fields.keys()),
            battery_percentage=current_data.get("battery_percentage"),
            raw_tag_1_present="1" in current_data,
            total_input_power=current_data.get("total_input_power"),
            total_output_power=current_data.get("total_output_power"),
            ac_input=current_data.get("ac_input"),
            dc_input=current_data.get("dc_input"),
            ac_switch=current_data.get("ac_switch"),
            dc_switch=current_data.get("dc_switch"),
            usb_switch=current_data.get("usb_switch"),
        )
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
        self._lan_has_valid_telemetry = False
        self._lan_last_rearm = 0.0

    async def _async_rearm_lan(self) -> bool:
        """Re-arm high-frequency telemetry subscription on an existing silent socket."""
        session = self._lan_session
        if session is None or not getattr(session, "is_ready", False):
            return False
        self._lan_last_rearm = time.monotonic()
        _LOGGER.debug(
            "oukitel: LAN telemetry silent > %.1fs — re-arming subscription on existing socket",
            _LAN_REARM_TIMEOUT,
        )
        try:
            await session.resubscribe()
            await session.request_read(force=True)
        except Exception as exc:
            _LOGGER.debug("oukitel: LAN re-arm failed: %s", exc)
            return False
        return True

    async def _force_lan_reconnect(self) -> None:
        """Drop a silent session so the background read loop cleanly reconnects."""
        _LOGGER.info(
            "oukitel: LAN session silent for > %.1fs (no telemetry) — dropping socket to force clean reconnect",
            _LAN_SILENCE_TIMEOUT,
        )
        self._lan_last_report = None
        self._lan_active = False
        self._lan_has_valid_telemetry = False
        self._lan_last_rearm = 0.0
        if self._lan_session is not None:
            try:
                await self._lan_session.close()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # DataUpdateCoordinator
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        if self._paused:
            _LOGGER.debug("oukitel: Polling skipped — integration is paused (returning zeroed power metrics)")
            return _build_paused_data(self.data or self._lan_state)

        # In Auto mode, if LAN session is dead or never started, periodically retry starting LAN
        now = time.monotonic()
        if (
            self.connection_mode == MODE_AUTO
            and not self._lan_active
            and (self._lan_listen_task is None or self._lan_listen_task.done())
            and (now - self._last_lan_attempt >= _LAN_RETRY_INTERVAL)
        ):
            self._last_lan_attempt = now
            self.hass.async_create_task(self.async_setup_lan())

        # Check if active LAN session has gone silent (station answering ACKs but suspended telemetry streaming)
        if self._lan_active and self.connection_mode != MODE_CLOUD:
            reference = self._lan_last_report or self._lan_connected_at
            silent_for = None if reference is None else (now - reference)
            if silent_for is not None and silent_for > _LAN_SILENCE_TIMEOUT:
                await self._force_lan_reconnect()
            elif (
                silent_for is not None
                and silent_for > _LAN_REARM_TIMEOUT
                and (now - self._lan_last_rearm) >= _LAN_REARM_INTERVAL
            ):
                await self._async_rearm_lan()

        if self.connection_mode == MODE_CLOUD:
            data = await self._update_cloud()
        elif self._lan_active and self._lan_session:
            data = await self._update_lan()
        elif self.connection_mode == MODE_LAN or not getattr(self.client, "access_token", None):
            # If LAN session is initializing in the background during setup or running offline, request read and wait
            if self._lan_session and getattr(self._lan_session, "is_ready", False):
                try:
                    await self._lan_session.request_read()
                except Exception:
                    pass

            for _ in range(35 if not self.data else 15):
                if self._lan_active and self._lan_state:
                    data = await self._update_lan()
                    break
                await asyncio.sleep(0.1)
            else:
                if self._lan_active and self._lan_state:
                    data = await self._update_lan()
                elif self.data:
                    _LOGGER.debug("oukitel: Preserving previous telemetry snapshot while LAN reconnects")
                    data = dict(self.data)
                else:
                    _LOGGER.info("oukitel: LAN session active but first frame pending — bootstrapping with baseline telemetry")
                    init_data: dict[str, Any] = {
                        "online": True,
                        "connection_mode": "LAN",
                    }
                    if self._last_valid_battery is not None:
                        init_data["battery_percentage"] = int(round(self._last_valid_battery))
                    for k, v in self._static_metadata.items():
                        init_data[k] = v
                    data = init_data
        else:
            try:
                data = await self._update_cloud()
            except Exception as exc:
                if self.data or self._lan_state:
                    _LOGGER.debug("oukitel: Cloud unreachable (%s) — using local/cached state", exc)
                    data = dict(self._lan_state or self.data)
                else:
                    raise UpdateFailed(f"Error communicating with Oukitel cloud API: {exc}") from exc

        if hasattr(self, "predictive_tracker") and self.predictive_tracker is not None:
            self.predictive_tracker.update(data)

        return data

    async def _update_lan(self) -> dict:
        if self._paused:
            return _build_paused_data(self._lan_state or self.data)

        now = time.monotonic()
        stale = (
            self._lan_last_report is not None
            and (now - self._lan_last_report) > _LAN_STALE_TIMEOUT
        )
        if stale:
            if self.connection_mode == MODE_LAN or not getattr(self.client, "access_token", None):
                _LOGGER.debug("oukitel: LAN telemetry stale (Cloud fallback unavailable — keeping state)")
            else:
                _LOGGER.info("oukitel: LAN telemetry stale — falling back to cloud")
                self._lan_active = False
                return await self._update_cloud()

        if not self.data:
            # Wait up to 4.5s on initial boot for the station's 18-tag sequence (44->43->46->7->20->1->5->4)
            for _ in range(45):
                if (
                    self._lan_state
                    and "1" in self._lan_state
                    and ("4" in self._lan_state or "5" in self._lan_state)
                    and ("4" in self._lan_state and "5" in self._lan_state or "6" in self._lan_state)
                ):
                    break
                await asyncio.sleep(0.1)

        if not self._lan_state:
            if self.data:
                return dict(self.data)
            _LOGGER.info("oukitel: LAN connected, initial frame pending — returning baseline telemetry to complete setup")
            init_data = {
                "online": True,
                "connection_mode": "LAN",
            }
            if self._last_valid_battery is not None:
                init_data["battery_percentage"] = int(round(self._last_valid_battery))
            for k, v in self._static_metadata.items():
                init_data[k] = v
            return init_data


        data = dict(self._lan_state)
        if data.get("battery_percentage") is None and self._last_valid_battery is not None:
            data["battery_percentage"] = int(round(self._last_valid_battery))
        # Preserve static/cloud-only diagnostic tags from metadata cache and prior state
        for k, v in self._static_metadata.items():
            if k not in data or data[k] is None:
                data[k] = v
        if self.data:
            for k in STATIC_METADATA_KEYS:
                if k in self.data and (k not in data or data[k] is None):
                    data[k] = self.data[k]
        self._apply_user_overrides(data)

        # Trigger background cloud shadow refresh in auto mode (only if online with authenticated token)
        now = time.monotonic()
        if (
            self.connection_mode == MODE_AUTO
            and self.hass.is_running
            and getattr(self.client, "access_token", None)
            and (now - self._last_cloud_snapshot) >= _CLOUD_SNAPSHOT_INTERVAL
        ):
            self.hass.async_create_task(self._async_refresh_cloud_shadow())

        return data

    async def _async_refresh_cloud_shadow(self) -> None:
        """Periodic background refresh of cloud-only metrics (temp, wifi_signal, versions) while LAN runs."""
        if self._paused or not self.hass.is_running:
            return

        self._last_cloud_snapshot = time.monotonic()

        # If started offline, attempt to reconnect to cloud opportunistically with strict timeout
        if not getattr(self.client, "access_token", None):
            try:
                logged_in = await asyncio.wait_for(
                    self.hass.async_add_executor_job(self.client.login),
                    timeout=3.0,
                )
                if not logged_in:
                    return
                await asyncio.wait_for(
                    self.hass.async_add_executor_job(self.client.fetch_device_info),
                    timeout=3.0,
                )
                _LOGGER.info("oukitel: Successfully reconnected to Oukitel cloud after offline startup")
                if (
                    self.config_entry
                    and self.client.auth_key
                    and self.config_entry.data.get(CONF_AUTH_KEY) != self.client.auth_key
                ):
                    new_data = dict(self.config_entry.data)
                    new_data[CONF_AUTH_KEY] = self.client.auth_key
                    self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            except Exception as exc:
                _LOGGER.debug("oukitel: Opportunistic cloud reconnect notice: %s", exc)
                return

        try:
            cloud_snapshot = await asyncio.wait_for(
                self.hass.async_add_executor_job(self.client.get_telemetry),
                timeout=4.0,
            )
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

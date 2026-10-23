"""Pure multi-device selection helpers."""

from __future__ import annotations

from typing import Any


def select_device(
    devices: list[dict[str, Any]],
    device_key: str | None = None,
    device_name: str | None = None,
) -> dict[str, Any] | None:
    """Pick the configured device and never silently switch to another one.

    - A matching ``device_key`` wins.
    - If it is missing but there is only one device in the account, that device
      is accepted (the key may have changed after a rebind).
    - If there are several devices and the key is missing, return ``None`` so
      the caller can fail instead of reading another station.
    - Legacy entries without a key can match by ``device_name``.
    """
    if not devices:
        return None

    if device_key:
        for device in devices:
            if device.get("deviceKey") == device_key:
                return device
        if len(devices) == 1:
            return devices[0]
        return None

    if device_name:
        for device in devices:
            if device.get("deviceName") == device_name:
                return device
        if len(devices) == 1:
            return devices[0]
        return None

    return devices[0]

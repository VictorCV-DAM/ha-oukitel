"""Auth-key refresh decision logic, isolated from Home Assistant for testing."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

DEFAULT_REFRESH_INTERVAL = 300.0


async def try_refresh_auth_key(
    client: Any,
    stale_key: str | None,
    last_attempt: float,
    now: float,
    run_in_executor: Callable[..., Awaitable[Any]],
    min_interval: float = DEFAULT_REFRESH_INTERVAL,
) -> tuple[bool, str | None, float]:
    """Try to refresh a stale LAN authKey from the cloud device list.

    Returns ``(refreshed, key, last_attempt)``.  ``last_attempt`` is moved to
    ``now`` on every attempted refresh (successful or not) so a broken cloud
    cannot trigger a request storm.

    The helper never logs the key and never raises: any cloud/transport error
    is reported as a failed refresh so the caller can keep its previous
    behaviour.
    """
    if now - last_attempt < min_interval:
        return False, stale_key, last_attempt

    if not getattr(client, "access_token", None):
        return False, stale_key, now

    expected_device_key = getattr(client, "device_key", None)

    try:
        ok = await run_in_executor(client.fetch_device_info)
    except Exception:  # noqa: BLE001 - cloud/transport failure is not fatal
        return False, stale_key, now

    # Never accept a key that belongs to a different device of the account.
    if expected_device_key and getattr(client, "device_key", None) != expected_device_key:
        return False, stale_key, now

    new_key = getattr(client, "auth_key", None)
    if not ok or not new_key or new_key == stale_key:
        return False, stale_key, now

    return True, new_key, now

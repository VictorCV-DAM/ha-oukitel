"""The "client" for when there is no vendor account at all.

Why the cloud can be done without: when the station talks to the fake cloud
at home (see `cloud_bridge.py`) the frames travel **in the clear**, so no
authKey has to be fetched from anywhere. The only reason the integration ever
asked for an email and a password was precisely that key (and the device
list): with the bridge they are not needed any more.

This object takes the place of `AcceleronixCloudClient` and politely says no
to everything that would like to reach the internet. That way the rest of the
integration (coordinator, entities, platforms) does not have to know anything
about the difference and does not get filled up with checks.
"""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)


class LocalOnlyClient:
    """Stands in for the cloud client, without ever leaving the house."""

    #: For anyone who wants to tell the two cases apart without isinstance.
    local_only = True

    def __init__(
        self,
        device_key: str | None = None,
        product_key: str | None = None,
        device_name: str | None = None,
    ) -> None:
        self.email = ""
        self.password = ""
        self.region = "EU"
        self.base_url = ""
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = 0

        self.device_key = device_key
        self.product_key = product_key
        self.device_name = device_name or "Powerstation"
        self.product_name = self.device_name
        # No key: on the fake cloud's channel the frames are not encrypted.
        self.auth_key = None
        self.is_online = True

    # ---------------------------------------------------------- login (none)

    def login(self) -> bool:
        return True

    def ensure_authenticated(self) -> bool:
        return True

    def get_auth_headers(self) -> dict:
        return {}

    # --------------------------------------------------- devices and data

    def get_devices_list(self, *_a, **_k) -> list[dict]:
        return []

    def fetch_device_info(self, *_a, **_k) -> bool:
        # Name and product key come from the config entry.
        return bool(self.device_key)

    def fetch_auth_key(self) -> str | None:
        return None

    def get_telemetry(self, *_a, **_k) -> dict:
        # In local-only mode the data comes from the fake cloud, not from here.
        raise RuntimeError(
            "oukitel: configured without an account, telemetry comes from the local fake cloud"
        )

    # ------------------------------------------------------------ commands

    def control_device(self, *_a, **_k) -> bool:
        # Commands go through the bridge; getting here means there is no route.
        _LOGGER.debug("oukitel: cloud command ignored (configured without an account)")
        return False

    def wake_device(self) -> bool:
        return False

    # -------------------------------------------------------- smart plugs

    def elenco_prese(self) -> list[dict]:
        # The plugs live on the cloud: without an account they do not exist.
        return []

    def leggi_presa(self, *_a, **_k):
        return None

    def comanda_presa(self, *_a, **_k) -> bool:
        return False

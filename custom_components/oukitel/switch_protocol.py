"""Extensible switch command strategies keyed by cloud product key."""

from dataclasses import dataclass
from typing import Any, Iterable, Protocol


@dataclass(frozen=True)
class LanSwitchWrite:
    """One LAN write in the station's TTLV format."""

    tag: int
    kind: str
    value: Any


class SwitchProtocol(Protocol):
    """Build switch commands for one station communication protocol."""

    name: str
    sync_cloud_after_lan: bool

    def lan_write(self, key: str, value: bool) -> LanSwitchWrite | None:
        """Return the LAN write for a switch, or None when unsupported."""

    def cloud_payload(self, key: str, value: bool) -> list[dict[str, Any]] | None:
        """Return the Cloud payload, or None when Cloud writes are unsupported."""


class DirectTagSwitchProtocol:
    """Build direct-tag LAN and flat Cloud commands for existing models."""

    name = "direct_tags"
    sync_cloud_after_lan = True
    _TAGS = {
        "ac_switch": 43,
        "usb_switch": 44,
        "dc_switch": 46,
    }

    def lan_write(self, key: str, value: bool) -> LanSwitchWrite | None:
        tag = self._TAGS.get(key)
        if tag is None:
            return None
        return LanSwitchWrite(tag, "bool", bool(value))

    def cloud_payload(self, key: str, value: bool) -> list[dict[str, Any]] | None:
        if key not in self._TAGS:
            return None
        return [{key: bool(value)}]


class BP2000ProSwitchProtocol:
    """Build nested-struct LAN commands for the BP2000 Pro protocol."""

    name = "nested_struct"
    sync_cloud_after_lan = False

    _COMMANDS = {
        "ac_switch": (6, 1),
        "usb_switch": (7, 1),
        "dc_switch": (9, 1),
    }
    _CLOUD_STRUCT_PROPERTIES = {
        "ac_switch": "ac_data",
        "usb_switch": "usb_data",
        "dc_switch": "dc_data",
    }

    def lan_write(self, key: str, value: bool) -> LanSwitchWrite | None:
        command = self._COMMANDS.get(key)
        if command is None:
            return None
        tag, subtag = command
        return LanSwitchWrite(tag, "struct", [(subtag, "bool", bool(value))])

    def cloud_payload(self, key: str, value: bool) -> list[dict[str, Any]] | None:
        property_code = self._CLOUD_STRUCT_PROPERTIES.get(key)
        if property_code is None:
            return None
        # The Cloud TSL defines Boolean struct options with string values.
        struct_value = [{key: "true" if value else "false"}]
        return [{property_code: struct_value}]


class SwitchProtocolRegistry:
    """Resolve a switch strategy by exact product key, with a compatibility default."""

    def __init__(
        self,
        default: SwitchProtocol,
        registrations: dict[str, SwitchProtocol] | None = None,
    ) -> None:
        self._default = default
        self._by_product_key = {
            self._normalize(product_key): strategy
            for product_key, strategy in (registrations or {}).items()
        }

    @staticmethod
    def _normalize(product_key: str) -> str:
        return product_key.strip().casefold()

    def register(self, product_keys: Iterable[str], strategy: SwitchProtocol) -> None:
        """Register a strategy for one or more exact product keys."""
        for product_key in product_keys:
            normalized = self._normalize(product_key)
            if not normalized:
                raise ValueError("product_key cannot be empty")
            self._by_product_key[normalized] = strategy

    def resolve(self, product_key: str | None) -> tuple[SwitchProtocol, bool]:
        """Return the matching strategy and whether an exact key matched."""
        normalized = self._normalize(product_key) if product_key else ""
        strategy = self._by_product_key.get(normalized)
        if strategy is None:
            return self._default, False
        return strategy, True


DIRECT_TAG_PROTOCOL = DirectTagSwitchProtocol()
BP2000_PRO_PROTOCOL = BP2000ProSwitchProtocol()

# Register each model-specific product key here. Unknown keys retain the
# established direct-tag protocol for compatibility with existing stations.
SWITCH_PROTOCOLS = SwitchProtocolRegistry(
    default=DIRECT_TAG_PROTOCOL,
    registrations={
        "p11wN7": DIRECT_TAG_PROTOCOL,
        "p11sSr": BP2000_PRO_PROTOCOL,
    },
)

"""Constants for the Oukitel Power Station integration."""

DOMAIN = "oukitel"
VERSION = "1.4.1"

CONF_REGION = "region"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_POLL_INTERVAL = "poll_interval"
CONF_CONNECTION_MODE = "connection_mode"
CONF_PRICE_SENSOR = "price_sensor"
CONF_FIXED_PRICE = "fixed_price"
DEFAULT_FIXED_PRICE = 0.15

MODE_AUTO = "auto"
MODE_LAN = "lan"
MODE_CLOUD = "cloud"

CONNECTION_MODES = {
    MODE_AUTO: "Automático (LAN preferente + Cloud)",
    MODE_LAN: "Solo LAN (Tiempo real directo)",
    MODE_CLOUD: "Solo Cloud (Nube / Polling)",
}

DEFAULT_REGION = "EU"
DEFAULT_POLL_INTERVAL = 10
DEFAULT_WAKE_INTERVAL = 25
DEFAULT_CONNECTION_MODE = MODE_AUTO

REGION_SERVERS = {
    "EU": {
        "name": "Europe (Verified)",
        "base_url": "https://iot-api.acceleronix.io",
        "user_domain": "E.SP.4294967410",
        "user_domain_secret": "3aRNUwWahjyANa7WfBK2wCCkxCexB6nXxKJwXxfePvzf",
        "appid": "277",
        "appversion": "3.7.5",
    },
    "US": {
        "name": "North America / USA [EXPERIMENTAL]",
        "base_url": "https://iot-api.quectelus.com",
        "user_domain": "E.SP.4294967410",
        "user_domain_secret": "3aRNUwWahjyANa7WfBK2wCCkxCexB6nXxKJwXxfePvzf",
        "appid": "277",
        "appversion": "3.7.5",
    },
    "CN": {
        "name": "China / Asia [EXPERIMENTAL]",
        "base_url": "https://iot-api.quectelcn.com",
        "user_domain": "E.SP.4294967410",
        "user_domain_secret": "3aRNUwWahjyANa7WfBK2wCCkxCexB6nXxKJwXxfePvzf",
        "appid": "277",
        "appversion": "3.7.5",
    },
}

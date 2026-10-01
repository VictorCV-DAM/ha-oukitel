"""Constants for the Oukitel Power Station integration."""

DOMAIN = "oukitel"

CONF_REGION = "region"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_POLL_INTERVAL = "poll_interval"

DEFAULT_REGION = "EU"
DEFAULT_POLL_INTERVAL = 10
DEFAULT_WAKE_INTERVAL = 25

REGION_SERVERS = {
    "EU": {
        "name": "Europe (Verified)",
        "base_url": "https://iot-api.acceleronix.io",
        "user_domain": "E.SP.4294967410",
        "user_domain_secret": "3aRNUwWahjyANa7WfBK2wCCkxCexB6nXxKJwXxfePvzf",
        "appid": "277",
        "appversion": "2.19.6",
    },
    "US": {
        "name": "North America / USA [EXPERIMENTAL]",
        "base_url": "https://iot-api.quectelus.com",
        "user_domain": "E.SP.4294967410",
        "user_domain_secret": "3aRNUwWahjyANa7WfBK2wCCkxCexB6nXxKJwXxfePvzf",
        "appid": "277",
        "appversion": "2.19.6",
    },
    "CN": {
        "name": "China / Asia [EXPERIMENTAL]",
        "base_url": "https://iot-api.quectelcn.com",
        "user_domain": "E.SP.4294967410",
        "user_domain_secret": "3aRNUwWahjyANa7WfBK2wCCkxCexB6nXxKJwXxfePvzf",
        "appid": "277",
        "appversion": "2.19.6",
    },
}

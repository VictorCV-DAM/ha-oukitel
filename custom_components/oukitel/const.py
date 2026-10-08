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
CONF_CURRENCY = "currency"
DEFAULT_CURRENCY = "€"
CURRENCY_OPTIONS = ["€", "$", "£", "CHF", "kr", "¥", "zł", "R$", "MX$"]

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

ENTITY_DESCRIPTIONS = {
    # Core Telemetry & Diagnostics
    "battery_percentage": "Nivel de carga restante de la batería en porcentaje.",
    "total_input_power": "Potencia total combinada entrante a la estación (red eléctrica AC + paneles solares/DC).",
    "total_output_power": "Potencia total simultánea consumida por todas las salidas activas (AC + DC + USB).",
    "ac_input": "Potencia de recarga recibida desde la red eléctrica o enchufe de pared de 230V.",
    "dc_input": "Potencia de recarga generada por paneles solares fotovoltaicos o entrada DC.",
    "temp": "Temperatura interna general del compartimento de celdas de la batería.",
    "inverter_temp": "Temperatura interna de los disipadores y electrónica de potencia del inversor AC.",
    "remaining_time": "Tiempo restante estimado de funcionamiento según la pantalla LCD oficial.",
    "remain_time": "Autonomía restante de descarga hasta agotar la batería con el consumo actual.",
    "remain_charging_time": "Tiempo restante estimado para completar la carga de la batería al 100%.",
    "ac_output_power": "Potencia útil consumida por los aparatos conectados a las tomas de corriente AC (230V).",
    "ac_output_voltage": "Voltaje medido en tiempo real en las tomas de corriente alterna de salida (230V).",
    "usb_a_power": "Potencia total suministrada a través de los puertos de carga USB-A.",
    "usb_c_qc_power": "Potencia suministrada por el puerto de carga rápida USB-C Quick Charge.",
    "typec1_power": "Potencia suministrada en tiempo real por el puerto Type-C 1 (carga rápida Power Delivery).",
    "typec2_power": "Potencia suministrada en tiempo real por el puerto Type-C 2.",
    "typec3_power": "Potencia suministrada en tiempo real por el puerto Type-C 3.",
    "typec4_power": "Potencia suministrada en tiempo real por el puerto Type-C 4.",
    "dc_output_power": "Potencia consumida por la toma de mechero de 12V y puertos DC.",
    "dc_output_voltage": "Voltaje continuo medido en la salida de 12V DC.",
    "dc_output_current": "Intensidad de corriente continua en amperios en la salida de 12V DC.",
    "wifi_signal": "Intensidad de la señal Wi-Fi recibida por la estación en dBm.",
    "BMS_Version": "Versión de firmware del sistema de gestión de batería (BMS).",
    "AC_Version": "Versión de firmware del controlador del inversor de corriente alterna.",
    "device_fault_status": "Estado operativo del hardware y protecciones activas (temperatura, sobrecarga, batería).",
    "connection_mode": "Canal de comunicación activo con Home Assistant: red local (LAN) o servidores Cloud.",

    # Inverter Diagnostics & Losses
    "inverter_idle_power": "Consumo parásito del inversor encendido en reposo sin carga conectada (18W).",
    "inverter_efficiency": "Eficiencia de conversión energética en tiempo real del inversor de corriente alterna.",
    "inverter_loss_power": "Pérdidas térmicas internas y disipación de energía del inversor en vatios.",

    # Battery Health Tracker
    "battery_cycles_count": "Ciclos completos de carga/descarga equivalentes acumulados (estándar IEC 62620).",
    "battery_state_of_health_estimated": "Estado de salud restante estimado de las celdas LiFePO4 (3.500 ciclos al 80%).",
    "days_since_last_full_charge": "Días transcurridos desde el último 100% (alerta de calibración y balanceo del BMS).",

    # Calculated Energy kWh
    "calc_ac_input_kwh": "Energía total acumulada importada de la red eléctrica para recarga.",
    "calc_dc_input_kwh": "Energía total acumulada generada por paneles solares fotovoltaicos.",
    "calc_total_output_kwh": "Energía total suministrada por la estación a todos los dispositivos conectados.",
    "calc_ac_output_kwh": "Energía total entregada a través de las tomas de corriente alterna de 230V.",
    "calc_battery_discharged_kwh": "Energía total extraída de las celdas de la batería durante la descarga.",
    "calc_daily_ac_input_kwh": "Energía importada de la red eléctrica en el día en curso.",

    # Calculated Financial
    "calc_daily_charging_cost_eur": "Coste económico acumulado de la recarga desde la red eléctrica hoy.",
    "calc_monthly_charging_cost_eur": "Coste económico acumulado de la recarga eléctrica durante este mes.",
    "calc_daily_savings_eur": "Ahorro económico generado hoy gracias al autoconsumo solar fotovoltaico.",
    "calc_monthly_savings_eur": "Ahorro económico mensual obtenido mediante captación de energía solar.",
    "calc_daily_net_savings_eur": "Balance económico neto del día (ahorro solar menos coste de recarga de red).",
    "calc_lifetime_savings_eur": "Ahorro económico histórico acumulado generado por energía solar.",
    "calc_lifetime_charging_cost_eur": "Coste total histórico acumulado de la recarga eléctrica.",

    # Binary Sensors
    "device_online": "Indica si la estación está conectada y comunicando activamente en red local o nube.",
    "on_battery": "Indica si la estación está funcionando con batería (sin suministro de red o solar).",

    # Switches & Controls
    "ac_output": "Interruptor para encender o apagar las tomas de corriente alterna de 230V.",
    "dc_12v_output": "Interruptor para encender o apagar la salida de mechero de 12V DC.",
    "usb_output": "Interruptor para encender o apagar los puertos de carga USB y Type-C.",
    "pause_integration": "Pausa la comunicación con la estación para permitir su reposo profundo.",
    "ac_charging_limit": "Ajuste del límite de potencia de recarga desde la red eléctrica (del 3% al 100%).",
    "output_frequency": "Frecuencia de salida de la corriente alterna (50 Hz o 60 Hz).",
    "output_voltage": "Tensión nominal de salida de la corriente alterna (200V - 240V).",
    "reload": "Reinicia la sesión y reconecta los protocolos de la estación de forma inmediata.",
}

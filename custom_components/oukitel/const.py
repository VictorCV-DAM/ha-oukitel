"""Constants for the Oukitel Power Station integration."""

DOMAIN = "oukitel"
VERSION = "1.5.5"

CONF_REGION = "region"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_POLL_INTERVAL = "poll_interval"
CONF_CONNECTION_MODE = "connection_mode"
CONF_HOST = "host"
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

ENTITY_DESCRIPTIONS_ES = {
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
    "bms_version": "Versión de firmware del sistema de gestión de batería (BMS).",
    "AC_Version": "Versión de firmware del controlador del inversor de corriente alterna.",
    "ac_version": "Versión de firmware del controlador del inversor de corriente alterna.",
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
    "ac_switch": "Interruptor para encender o apagar las tomas de corriente alterna de 230V.",
    "dc_12v_output": "Interruptor para encender o apagar la salida de mechero de 12V DC.",
    "dc_switch": "Interruptor para encender o apagar la salida de mechero de 12V DC.",
    "usb_output": "Interruptor para encender o apagar los puertos de carga USB y Type-C.",
    "usb_switch": "Interruptor para encender o apagar los puertos de carga USB y Type-C.",
    "pause_integration": "Pausa la comunicación con la estación para permitir su reposo profundo.",
    "ac_charging_limit": "Ajuste del límite de potencia de recarga desde la red eléctrica (del 3% al 100%).",
    "output_frequency": "Frecuencia de salida de la corriente alterna (50 Hz o 60 Hz).",
    "output_voltage": "Tensión nominal de salida de la corriente alterna (200V - 240V).",
    "reload": "Reinicia la sesión y reconecta los protocolos de la estación de forma inmediata.",

    # Predictive Autonomy & Smart Timestamps
    "empty_timestamp": "Hora exacta prevista en la que se agotará la batería (0%) calculada con filtro de media móvil de consumo.",
    "full_charge_timestamp": "Hora exacta prevista en la que la batería alcanzará el 100% de carga calculada con filtro de media móvil.",
    "smoothed_discharge_time": "Autonomía restante de descarga en minutos suavizada con filtro de media móvil de 15 minutos.",
}

ENTITY_DESCRIPTIONS_EN = {
    # Core Telemetry & Diagnostics
    "battery_percentage": "Remaining battery state of charge in percentage.",
    "total_input_power": "Total combined incoming charging power (AC electrical grid + solar/DC input).",
    "total_output_power": "Total simultaneous power consumed across all active outputs (AC + DC + USB).",
    "ac_input": "Charging power drawn from the AC electrical grid / wall socket.",
    "dc_input": "Solar photovoltaic or DC charging input power.",
    "temp": "Internal temperature of the battery cell compartment.",
    "inverter_temp": "Internal temperature of the AC inverter power electronics and heatsinks.",
    "remaining_time": "Estimated remaining operating time reported by the station's LCD display.",
    "remain_time": "Estimated remaining discharge autonomy until battery depletion at current load.",
    "remain_charging_time": "Estimated remaining time to reach 100% full charge.",
    "ac_output_power": "Active load power consumed by appliances connected to the 230V AC outlets.",
    "ac_output_voltage": "Real-time voltage measured at the alternating current AC output sockets.",
    "usb_a_power": "Total power delivered through the USB-A charging ports.",
    "usb_c_qc_power": "Power delivered through the Quick Charge USB-C port.",
    "typec1_power": "Real-time power delivered by Type-C port 1 (Power Delivery fast charge).",
    "typec2_power": "Real-time power delivered by Type-C port 2.",
    "typec3_power": "Real-time power delivered by Type-C port 3.",
    "typec4_power": "Real-time power delivered by Type-C port 4.",
    "dc_output_power": "Power consumed by the 12V cigarette lighter and DC barrel ports.",
    "dc_output_voltage": "Direct current voltage measured at the 12V DC output.",
    "dc_output_current": "Direct current intensity in amperes at the 12V DC output.",
    "wifi_signal": "Wi-Fi signal strength received by the power station in dBm.",
    "BMS_Version": "Firmware version of the Battery Management System (BMS).",
    "bms_version": "Firmware version of the Battery Management System (BMS).",
    "AC_Version": "Firmware version of the AC inverter controller.",
    "ac_version": "Firmware version of the AC inverter controller.",
    "device_fault_status": "Operating hardware status and active protections (thermal, overload, battery).",
    "connection_mode": "Active communication transport with Home Assistant: local network (LAN) or Cloud servers.",

    # Inverter Diagnostics & Losses
    "inverter_idle_power": "Parasitic tare consumption of the active AC inverter with no load connected (18W).",
    "inverter_efficiency": "Real-time energy conversion efficiency of the AC inverter.",
    "inverter_loss_power": "Internal thermal dissipation and power conversion losses of the inverter in Watts.",

    # Battery Health Tracker
    "battery_cycles_count": "Cumulative equivalent full charge/discharge cycles (IEC 62620 standard).",
    "battery_state_of_health_estimated": "Estimated remaining State of Health (SoH) of the LiFePO4 cells (3,500 cycles to 80%).",
    "days_since_last_full_charge": "Days elapsed since the last 100% full charge (BMS cell balancing & calibration alert).",

    # Calculated Energy kWh
    "calc_ac_input_kwh": "Total cumulative energy imported from the AC grid for charging.",
    "calc_dc_input_kwh": "Total cumulative energy generated by solar photovoltaic panels.",
    "calc_total_output_kwh": "Total energy delivered by the power station to all connected loads.",
    "calc_ac_output_kwh": "Total energy delivered through the 230V AC output sockets.",
    "calc_battery_discharged_kwh": "Total cumulative energy discharged from the battery cells.",
    "calc_daily_ac_input_kwh": "Energy imported from the electrical grid during the current day.",

    # Calculated Financial
    "calc_daily_charging_cost_eur": "Accumulated economic cost of grid charging today.",
    "calc_monthly_charging_cost_eur": "Accumulated economic cost of grid charging during this month.",
    "calc_daily_savings_eur": "Economic savings generated today from solar photovoltaic self-consumption.",
    "calc_monthly_savings_eur": "Monthly economic savings generated from solar energy harvesting.",
    "calc_daily_net_savings_eur": "Daily net financial balance (solar savings minus grid charging cost).",
    "calc_lifetime_savings_eur": "Historical lifetime savings generated by solar self-consumption.",
    "calc_lifetime_charging_cost_eur": "Historical lifetime cost of electrical grid charging.",

    # Binary Sensors
    "device_online": "Indicates whether the station is online and actively communicating via LAN or Cloud.",
    "on_battery": "Indicates whether the station is running on battery (no grid or solar input present).",

    # Switches & Controls
    "ac_output": "Switch to toggle the 230V AC output sockets on or off.",
    "ac_switch": "Switch to toggle the 230V AC output sockets on or off.",
    "dc_12v_output": "Switch to toggle the 12V DC car socket and barrel ports on or off.",
    "dc_switch": "Switch to toggle the 12V DC car socket and barrel ports on or off.",
    "usb_output": "Switch to toggle the USB and Type-C charging ports on or off.",
    "usb_switch": "Switch to toggle the USB and Type-C charging ports on or off.",
    "pause_integration": "Pauses communication with the station to allow deep sleep standby.",
    "ac_charging_limit": "Adjustment of the AC grid charging power limit (from 3% to 100%).",
    "output_frequency": "AC output frequency setting (50 Hz or 60 Hz).",
    "output_voltage": "Nominal AC output voltage setting (200V - 240V).",
    "reload": "Restarts the session and reconnects protocols immediately.",

    # Predictive Autonomy & Smart Timestamps
    "empty_timestamp": "Estimated exact timestamp when the battery will reach 0% based on smoothed moving average discharge load.",
    "full_charge_timestamp": "Estimated exact timestamp when the battery will reach 100% full charge based on smoothed incoming charging power.",
    "smoothed_discharge_time": "Remaining discharge autonomy in minutes calculated with 15-minute moving average (immune to appliance startup spikes).",
}

# Default backwards-compatible alias
ENTITY_DESCRIPTIONS = ENTITY_DESCRIPTIONS_ES


def get_entity_description(key: str, hass=None) -> str:
    """Retrieve entity functional description localized to the user's Home Assistant language."""
    if not key:
        return ""
    lang = "en"
    if hass and hasattr(hass, "config") and getattr(hass.config, "language", None):
        lang = str(hass.config.language).lower()
    primary = ENTITY_DESCRIPTIONS_ES if lang.startswith("es") else ENTITY_DESCRIPTIONS_EN
    fallback = ENTITY_DESCRIPTIONS_EN if lang.startswith("es") else ENTITY_DESCRIPTIONS_ES

    k_str = str(key)
    res = primary.get(k_str) or primary.get(k_str.lower())
    if not res:
        res = fallback.get(k_str) or fallback.get(k_str.lower())
    return res or ""


def get_battery_capacity_wh(client) -> float:
    """Determine nominal battery capacity in Watt-hours from client model/product name."""
    raw = (getattr(client, "product_name", None) or getattr(client, "device_name", "") or "").lower()
    if "5000" in raw:
        return 5120.0
    if "3000" in raw:
        return 3072.0
    if "1000" in raw or "1024" in raw:
        return 1024.0
    if "1200" in raw or "960" in raw:
        return 960.0
    if "500" in raw or "505" in raw:
        return 505.0
    return 2048.0


ENTITY_NAMES_ES = {
    # Core Telemetry & Diagnostics
    "battery_percentage": "Batería",
    "total_input_power": "Potencia total de entrada",
    "total_output_power": "Potencia total de salida",
    "ac_input": "Potencia de entrada AC",
    "dc_input": "Potencia solar de entrada DC",
    "temp": "Temperatura de la batería",
    "inverter_temp": "Temperatura del inversor",
    "remaining_time": "Tiempo restante",
    "remain_time": "Tiempo restante de descarga",
    "remain_charging_time": "Tiempo restante de carga",
    "ac_output_power": "Potencia de salida AC",
    "ac_output_voltage": "Voltaje de salida AC",
    "usb_a_power": "Potencia USB-A",
    "usb_c_qc_power": "Potencia USB-C QC",
    "typec1_power": "Potencia Type-C 1",
    "typec2_power": "Potencia Type-C 2",
    "typec3_power": "Potencia Type-C 3",
    "typec4_power": "Potencia Type-C 4",
    "dc_output_power": "Potencia de salida DC",
    "dc_output_voltage": "Voltaje de salida DC",
    "dc_output_current": "Corriente de salida DC",
    "wifi_signal": "Señal Wi-Fi",
    "bms_version": "Versión de BMS",
    "ac_version": "Versión de inversor",
    "device_fault_status": "Estado operativo del hardware",
    "connection_mode": "Modo de conexión",
    "inverter_idle_power": "Consumo en reposo del inversor",
    "inverter_efficiency": "Eficiencia del inversor",
    "inverter_loss_power": "Pérdida de potencia del inversor",
    "battery_cycles_count": "Ciclos equivalentes de batería",
    "battery_state_of_health_estimated": "Salud estimada de la batería (SoH)",
    "days_since_last_full_charge": "Días desde última carga completa",
    "empty_timestamp": "Hora estimada de batería agotada",
    "full_charge_timestamp": "Hora estimada de carga completa",
    "smoothed_discharge_time": "Autonomía de descarga suavizada",

    # Calculated Energy & Financial
    "calc_ac_input_kwh": "Energía importada de la red AC",
    "calc_dc_input_kwh": "Energía solar generada",
    "calc_total_output_kwh": "Energía total suministrada",
    "calc_ac_output_kwh": "Energía AC suministrada",
    "calc_battery_discharged_kwh": "Energía descargada de batería",
    "calc_daily_ac_input_kwh": "Energía diaria importada de la red AC",
    "calc_daily_charging_cost_eur": "Coste diario de carga",
    "calc_monthly_charging_cost_eur": "Coste mensual de carga",
    "calc_daily_savings_eur": "Ahorro solar diario",
    "calc_monthly_savings_eur": "Ahorro solar mensual",
    "calc_daily_net_savings_eur": "Balance neto diario",
    "calc_lifetime_savings_eur": "Ahorro solar acumulado",
    "calc_lifetime_charging_cost_eur": "Coste de carga acumulado",

    # Binary Sensors, Switches, Buttons, Numbers, Selects
    "on_battery": "Funcionando con batería",
    "device_online": "Dispositivo en línea",
    "ac_switch": "Salida AC",
    "dc_switch": "Salida DC 12V",
    "usb_switch": "Salida USB",
    "pause_integration": "Pausar integración",
    "reload": "Recargar conexión",
    "ac_charging_limit": "Límite de carga AC",
    "output_frequency": "Frecuencia de salida",
    "output_voltage": "Voltaje de salida",
}

ENTITY_NAMES_EN = {
    # Core Telemetry & Diagnostics
    "battery_percentage": "Battery",
    "total_input_power": "Total Input Power",
    "total_output_power": "Total Output Power",
    "ac_input": "AC Input Power",
    "dc_input": "DC Solar Input Power",
    "temp": "Battery Temperature",
    "inverter_temp": "Inverter Temperature",
    "remaining_time": "Remaining Time",
    "remain_time": "Remaining Discharge Time",
    "remain_charging_time": "Remaining Charge Time",
    "ac_output_power": "AC Output Power",
    "ac_output_voltage": "AC Output Voltage",
    "usb_a_power": "USB-A Power",
    "usb_c_qc_power": "USB-C QC Power",
    "typec1_power": "Type-C 1 Power",
    "typec2_power": "Type-C 2 Power",
    "typec3_power": "Type-C 3 Power",
    "typec4_power": "Type-C 4 Power",
    "dc_output_power": "DC Output Power",
    "dc_output_voltage": "DC Output Voltage",
    "dc_output_current": "DC Output Current",
    "wifi_signal": "WiFi Signal",
    "bms_version": "BMS Version",
    "ac_version": "Inverter Version",
    "device_fault_status": "Hardware Fault Status",
    "connection_mode": "Connection Mode",
    "inverter_idle_power": "Inverter Standby Consumption",
    "inverter_efficiency": "Inverter Efficiency",
    "inverter_loss_power": "Inverter Loss Power",
    "battery_cycles_count": "Battery Equivalent Cycles",
    "battery_state_of_health_estimated": "Estimated Battery Health (SoH)",
    "days_since_last_full_charge": "Days Since Last Full Charge",
    "empty_timestamp": "Predicted Empty Time",
    "full_charge_timestamp": "Predicted Full Charge Time",
    "smoothed_discharge_time": "Smoothed Discharge Time",

    # Calculated Energy & Financial
    "calc_ac_input_kwh": "AC Grid Import Energy",
    "calc_dc_input_kwh": "Solar Energy Generated",
    "calc_total_output_kwh": "Total Output Energy",
    "calc_ac_output_kwh": "AC Output Energy",
    "calc_battery_discharged_kwh": "Battery Energy Discharged",
    "calc_daily_ac_input_kwh": "Daily AC Grid Import Energy",
    "calc_daily_charging_cost_eur": "Daily Charging Cost",
    "calc_monthly_charging_cost_eur": "Monthly Charging Cost",
    "calc_daily_savings_eur": "Daily Solar Savings",
    "calc_monthly_savings_eur": "Monthly Solar Savings",
    "calc_daily_net_savings_eur": "Daily Net Balance",
    "calc_lifetime_savings_eur": "Lifetime Solar Savings",
    "calc_lifetime_charging_cost_eur": "Lifetime Charging Cost",

    # Binary Sensors, Switches, Buttons, Numbers, Selects
    "on_battery": "Operating on Battery",
    "device_online": "Device Online",
    "ac_switch": "AC Output",
    "dc_switch": "DC 12V Output",
    "usb_switch": "USB Output",
    "pause_integration": "Pause Integration",
    "reload": "Reload Connection",
    "ac_charging_limit": "AC Charging Limit",
    "output_frequency": "Output Frequency",
    "output_voltage": "Output Voltage",
}


def get_entity_name(key: str, default_name: str, hass=None) -> str:
    """Retrieve entity display name localized to the user's Home Assistant language."""
    if not key:
        return default_name
    lang = "en"
    if hass and hasattr(hass, "config") and getattr(hass.config, "language", None):
        lang = str(hass.config.language).lower()
    k_str = str(key).lower()
    if lang.startswith("es"):
        return ENTITY_NAMES_ES.get(k_str, default_name)
    return ENTITY_NAMES_EN.get(k_str, default_name)


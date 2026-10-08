/**
 * Oukitel Power Station Lovelace Cards (v3.4.2)
 *
 * 1. custom:oukitel-display-card - 100% authentic LCD screen simulation:
 *    - Removed off-center inner arc line inside the sphere for clean authentic look
 *    - Perfectly tuned minutes unit tag spacing (x=192, balanced clearance)
 *    - Expanded top margin (viewBox 900x310, inner LCD y=24..250)
 *    - Fan icon elevated (cx=334, cy=44) with generous clearance above arc bracket
 *    - Battery capsule lowered (y=134) in the sphere bottom opening
 *    - Perfect bilateral symmetry: 68px identical margins on both left and right edges
 *    - Exact time display: `${hrs}h ${mins}m` and `MM Mins`
 * 2. custom:oukitel-card - Complete control dashboard with sleek, discreet mini tactile switches,
 *    2-step safety confirmation, financial balance, and system diagnostics.
 *
 * Repository: https://github.com/VictorCV-DAM/ha-oukitel
 */

// Import modern high-tech LCD and UI fonts
const fontLink = document.createElement("link");
fontLink.rel = "stylesheet";
fontLink.href = "https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=Orbitron:wght@500;700;800;900&family=Rajdhani:wght@600;700;800&display=swap";
if (!document.head.querySelector("link[href*='Orbitron']")) {
  document.head.appendChild(fontLink);
}

// Universal Tooltip Descriptions for Oukitel Entities (Spanish)
const OUKITEL_DESCRIPTIONS_ES = {
  // Core Telemetry & Diagnostics
  battery_percentage: "Nivel de carga restante de la batería en porcentaje.",
  total_input_power: "Potencia total combinada entrante a la estación (red eléctrica AC + paneles solares/DC).",
  total_output_power: "Potencia total simultánea consumida por todas las salidas activas (AC + DC + USB).",
  ac_input: "Potencia de recarga recibida desde la red eléctrica o enchufe de pared de 230V.",
  dc_input: "Potencia de recarga generada por paneles solares fotovoltaicos o entrada DC.",
  temp: "Temperatura interna general del compartimento de celdas de la batería.",
  inverter_temp: "Temperatura interna de los disipadores y electrónica de potencia del inversor AC.",
  remaining_time: "Tiempo restante estimado de funcionamiento según la pantalla LCD oficial.",
  remain_time: "Autonomía restante de descarga hasta agotar la batería con el consumo actual.",
  remain_charging_time: "Tiempo restante estimado para completar la carga de la batería al 100%.",
  ac_output_power: "Potencia útil consumida por los aparatos conectados a las tomas de corriente AC (230V).",
  ac_output_voltage: "Voltaje medido en tiempo real en las tomas de corriente alterna de salida (230V).",
  usb_a_power: "Potencia total suministrada a través de los puertos de carga USB-A.",
  usb_c_qc_power: "Potencia suministrada por el puerto de carga rápida USB-C Quick Charge.",
  typec1_power: "Potencia suministrada en tiempo real por el puerto Type-C 1 (carga rápida Power Delivery).",
  typec2_power: "Potencia suministrada en tiempo real por el puerto Type-C 2.",
  typec3_power: "Potencia suministrada en tiempo real por el puerto Type-C 3.",
  typec4_power: "Potencia suministrada en tiempo real por el puerto Type-C 4.",
  dc_output_power: "Potencia consumida por la toma de mechero de 12V y puertos DC.",
  dc_output_voltage: "Voltaje continuo medido en la salida de 12V DC.",
  dc_output_current: "Intensidad de corriente continua en amperios en la salida de 12V DC.",
  wifi_signal: "Intensidad de la señal Wi-Fi recibida por la estación en dBm.",
  BMS_Version: "Versión de firmware del sistema de gestión de batería (BMS).",
  AC_Version: "Versión de firmware del controlador del inversor de corriente alterna.",
  device_fault_status: "Estado operativo del hardware y protecciones activas (temperatura, sobrecarga, batería).",
  connection_mode: "Canal de comunicación activo con Home Assistant: red local (LAN) o servidores Cloud.",

  // Inverter Diagnostics & Losses
  inverter_idle_power: "Consumo parásito del inversor encendido en reposo sin carga conectada (18W).",
  inverter_efficiency: "Eficiencia de conversión energética en tiempo real del inversor de corriente alterna.",
  inverter_loss_power: "Pérdidas térmicas internas y disipación de energía del inversor en vatios.",

  // Battery Health Tracker
  battery_cycles_count: "Ciclos completos de carga/descarga equivalentes acumulados (estándar IEC 62620).",
  battery_state_of_health_estimated: "Estado de salud restante estimado de las celdas LiFePO4 (3.500 ciclos al 80%).",
  days_since_last_full_charge: "Días transcurridos desde el último 100% (alerta de calibración y balanceo del BMS).",

  // Calculated Energy kWh
  calc_ac_input_kwh: "Energía total acumulada importada de la red eléctrica para recarga.",
  calc_dc_input_kwh: "Energía total acumulada generada por paneles solares fotovoltaicos.",
  calc_total_output_kwh: "Energía total suministrada por la estación a todos los dispositivos conectados.",
  calc_ac_output_kwh: "Energía total entregada a través de las tomas de corriente alterna de 230V.",
  calc_battery_discharged_kwh: "Energía total extraída de las celdas de la batería durante la descarga.",
  calc_daily_ac_input_kwh: "Energía importada de la red eléctrica en el día en curso.",

  // Calculated Financial
  calc_daily_charging_cost_eur: "Coste económico acumulado de la recarga desde la red eléctrica hoy.",
  calc_monthly_charging_cost_eur: "Coste económico acumulado de la recarga eléctrica durante este mes.",
  calc_daily_savings_eur: "Ahorro económico generado hoy gracias al autoconsumo solar fotovoltaico.",
  calc_monthly_savings_eur: "Ahorro económico mensual obtenido mediante captación de energía solar.",
  calc_daily_net_savings_eur: "Balance económico neto del día (ahorro solar menos coste de recarga de red).",
  calc_lifetime_savings_eur: "Ahorro económico histórico acumulado generado por energía solar.",
  calc_lifetime_charging_cost_eur: "Coste total histórico acumulado de la recarga eléctrica.",

  // Binary Sensors
  device_online: "Indica si la estación está conectada y comunicando activamente en red local o nube.",
  on_battery: "Indica si la estación está funcionando con batería (sin suministro de red o solar).",

  // Switches & Controls
  ac_output: "Interruptor para encender o apagar las tomas de corriente alterna de 230V.",
  ac_switch: "Interruptor para encender o apagar las tomas de corriente alterna de 230V.",
  dc_12v_output: "Interruptor para encender o apagar la salida de mechero de 12V DC.",
  dc_switch: "Interruptor para encender o apagar la salida de mechero de 12V DC.",
  usb_output: "Interruptor para encender o apagar los puertos de carga USB y Type-C.",
  usb_switch: "Interruptor para encender o apagar los puertos de carga USB y Type-C.",
  pause_integration: "Pausa la comunicación con la estación para permitir su reposo profundo.",
  ac_charging_limit: "Ajuste del límite de potencia de recarga desde la red eléctrica (del 3% al 100%).",
  output_frequency: "Frecuencia de salida de la corriente alterna (50 Hz o 60 Hz).",
  output_voltage: "Tensión nominal de salida de la corriente alterna (200V - 240V).",
  reload: "Reinicia la sesión y reconecta los protocolos de la estación de forma inmediata.",

  // Predictive Autonomy & Smart Timestamps
  empty_timestamp: "Hora exacta prevista en la que se agotará la batería (0%) calculada con filtro de media móvil de consumo.",
  full_charge_timestamp: "Hora exacta prevista en la que la batería alcanzará el 100% de carga calculada con filtro de media móvil.",
  smoothed_discharge_time: "Autonomía restante de descarga en minutos suavizada con filtro de media móvil de 15 minutos.",
  bms_version: "Versión de firmware del sistema de gestión de batería (BMS).",
  ac_version: "Versión de firmware del controlador del inversor de corriente alterna.",
};

// Universal Tooltip Descriptions for Oukitel Entities (English)
const OUKITEL_DESCRIPTIONS_EN = {
  // Core Telemetry & Diagnostics
  battery_percentage: "Remaining battery state of charge in percentage.",
  total_input_power: "Total combined incoming charging power (AC electrical grid + solar/DC input).",
  total_output_power: "Total simultaneous power consumed across all active outputs (AC + DC + USB).",
  ac_input: "Charging power drawn from the AC electrical grid / wall socket.",
  dc_input: "Solar photovoltaic or DC charging input power.",
  temp: "Internal temperature of the battery cell compartment.",
  inverter_temp: "Internal temperature of the AC inverter power electronics and heatsinks.",
  remaining_time: "Estimated remaining operating time reported by the station's LCD display.",
  remain_time: "Estimated remaining discharge autonomy until battery depletion at current load.",
  remain_charging_time: "Estimated remaining time to reach 100% full charge.",
  ac_output_power: "Active load power consumed by appliances connected to the 230V AC outlets.",
  ac_output_voltage: "Real-time voltage measured at the alternating current AC output sockets.",
  usb_a_power: "Total power delivered through the USB-A charging ports.",
  usb_c_qc_power: "Power delivered through the Quick Charge USB-C port.",
  typec1_power: "Real-time power delivered by Type-C port 1 (Power Delivery fast charge).",
  typec2_power: "Real-time power delivered by Type-C port 2.",
  typec3_power: "Real-time power delivered by Type-C port 3.",
  typec4_power: "Real-time power delivered by Type-C port 4.",
  dc_output_power: "Power consumed by the 12V cigarette lighter and DC barrel ports.",
  dc_output_voltage: "Direct current voltage measured at the 12V DC output.",
  dc_output_current: "Direct current intensity in amperes at the 12V DC output.",
  wifi_signal: "Wi-Fi signal strength received by the power station in dBm.",
  BMS_Version: "Firmware version of the Battery Management System (BMS).",
  AC_Version: "Firmware version of the AC inverter controller.",
  device_fault_status: "Operating hardware status and active protections (thermal, overload, battery).",
  connection_mode: "Active communication transport with Home Assistant: local network (LAN) or Cloud servers.",

  // Inverter Diagnostics & Losses
  inverter_idle_power: "Parasitic tare consumption of the active AC inverter with no load connected (18W).",
  inverter_efficiency: "Real-time energy conversion efficiency of the AC inverter.",
  inverter_loss_power: "Internal thermal dissipation and power conversion losses of the inverter in Watts.",

  // Battery Health Tracker
  battery_cycles_count: "Cumulative equivalent full charge/discharge cycles (IEC 62620 standard).",
  battery_state_of_health_estimated: "Estimated remaining State of Health (SoH) of the LiFePO4 cells (3,500 cycles to 80%).",
  days_since_last_full_charge: "Days elapsed since the last 100% full charge (BMS cell balancing & calibration alert).",

  // Calculated Energy kWh
  calc_ac_input_kwh: "Total cumulative energy imported from the AC grid for charging.",
  calc_dc_input_kwh: "Total cumulative energy generated by solar photovoltaic panels.",
  calc_total_output_kwh: "Total energy delivered by the power station to all connected loads.",
  calc_ac_output_kwh: "Total energy delivered through the 230V AC output sockets.",
  calc_battery_discharged_kwh: "Total cumulative energy discharged from the battery cells.",
  calc_daily_ac_input_kwh: "Energy imported from the electrical grid during the current day.",

  // Calculated Financial
  calc_daily_charging_cost_eur: "Accumulated economic cost of grid charging today.",
  calc_monthly_charging_cost_eur: "Accumulated economic cost of grid charging during this month.",
  calc_daily_savings_eur: "Economic savings generated today from solar photovoltaic self-consumption.",
  calc_monthly_savings_eur: "Monthly economic savings generated from solar energy harvesting.",
  calc_daily_net_savings_eur: "Daily net financial balance (solar savings minus grid charging cost).",
  calc_lifetime_savings_eur: "Historical lifetime savings generated by solar self-consumption.",
  calc_lifetime_charging_cost_eur: "Historical lifetime cost of electrical grid charging.",

  // Binary Sensors
  device_online: "Indicates whether the station is online and actively communicating via LAN or Cloud.",
  on_battery: "Indicates whether the station is running on battery (no grid or solar input present).",

  // Switches & Controls
  ac_output: "Switch to toggle the 230V AC output sockets on or off.",
  ac_switch: "Switch to toggle the 230V AC output sockets on or off.",
  dc_12v_output: "Switch to toggle the 12V DC car socket and barrel ports on or off.",
  dc_switch: "Switch to toggle the 12V DC car socket and barrel ports on or off.",
  usb_output: "Switch to toggle the USB and Type-C charging ports on or off.",
  usb_switch: "Switch to toggle the USB and Type-C charging ports on or off.",
  pause_integration: "Pauses communication with the station to allow deep sleep standby.",
  ac_charging_limit: "Adjustment of the AC grid charging power limit (from 3% to 100%).",
  output_frequency: "AC output frequency setting (50 Hz or 60 Hz).",
  output_voltage: "Nominal AC output voltage setting (200V - 240V).",
  reload: "Restarts the session and reconnects protocols immediately.",

  // Predictive Autonomy & Smart Timestamps
  empty_timestamp: "Estimated exact timestamp when the battery will reach 0% based on smoothed moving average discharge load.",
  full_charge_timestamp: "Estimated exact timestamp when the battery will reach 100% full charge based on smoothed incoming charging power.",
  smoothed_discharge_time: "Remaining discharge autonomy in minutes calculated with 15-minute moving average (immune to appliance startup spikes).",
  bms_version: "Firmware version of the Battery Management System (BMS).",
  ac_version: "Firmware version of the AC inverter controller.",
};

const OUKITEL_DESCRIPTIONS = OUKITEL_DESCRIPTIONS_ES;

function getOukitelDescription(entityOrText, hass) {
  if (!entityOrText || typeof entityOrText !== "string") return null;

  // 1. Direct state attributes description (already localized by HA backend)
  if (hass && hass.states && hass.states[entityOrText]) {
    const st = hass.states[entityOrText];
    if (st.attributes && st.attributes.description) {
      return st.attributes.description;
    }
  }

  // 2. Language detection
  const lang = (
    (hass && (hass.locale?.language || hass.language)) ||
    (navigator && navigator.language) ||
    "en"
  ).toLowerCase();
  const dict = lang.startsWith("es") ? OUKITEL_DESCRIPTIONS_ES : OUKITEL_DESCRIPTIONS_EN;

  const id = entityOrText.toLowerCase().replace(/[\s-]+/g, "_");

  // 3. Substring matching (supports entity ID, translation keys, and display names)
  if (id.includes("inverter_temp") || id.includes("inverter_temperature")) return dict.inverter_temp;
  if (id.includes("inverter_idle") || id.includes("standby_consumption") || id.includes("consumo_parásito") || id.includes("consumo_parasito")) return dict.inverter_idle_power;
  if (id.includes("inverter_eff") || id.includes("eficiencia")) return dict.inverter_efficiency;
  if (id.includes("inverter_loss") || id.includes("pérdidas_inversor") || id.includes("perdidas_inversor")) return dict.inverter_loss_power;
  if (id.includes("battery_cycles") || id.includes("cycles_count") || id.includes("ciclos")) return dict.battery_cycles_count;
  if (id.includes("battery_state_of_health") || id.includes("health_estimated") || id.includes("battery_health") || id.includes("salud_batería") || id.includes("salud_bateria")) return dict.battery_state_of_health_estimated;
  if (id.includes("days_since") || id.includes("last_full_charge") || id.includes("días_desde") || id.includes("dias_desde")) return dict.days_since_last_full_charge;

  if (id.includes("calc_ac_input_kwh") || id.includes("entrada_ac_acumulada")) return dict.calc_ac_input_kwh;
  if (id.includes("calc_dc_input_kwh") || id.includes("solar_dc_acumulada")) return dict.calc_dc_input_kwh;
  if (id.includes("calc_total_output_kwh") || id.includes("salida_total_acumulada")) return dict.calc_total_output_kwh;
  if (id.includes("calc_ac_output_kwh") || id.includes("salida_ac_acumulada")) return dict.calc_ac_output_kwh;
  if (id.includes("calc_battery_discharged_kwh") || id.includes("descarga_batería_acumulada") || id.includes("descarga_bateria_acumulada")) return dict.calc_battery_discharged_kwh;
  if (id.includes("calc_daily_ac_input_kwh") || id.includes("entrada_ac_diaria")) return dict.calc_daily_ac_input_kwh;

  if (id.includes("calc_daily_charging_cost") || id.includes("coste_diario_de_recarga")) return dict.calc_daily_charging_cost_eur;
  if (id.includes("calc_monthly_charging_cost") || id.includes("coste_mensual_de_recarga")) return dict.calc_monthly_charging_cost_eur;
  if (id.includes("calc_daily_savings") || id.includes("ahorro_solar_diario")) return dict.calc_daily_savings_eur;
  if (id.includes("calc_monthly_savings") || id.includes("ahorro_solar_mensual")) return dict.calc_monthly_savings_eur;
  if (id.includes("calc_daily_net_savings") || id.includes("balance_neto_diario")) return dict.calc_daily_net_savings_eur;
  if (id.includes("calc_lifetime_savings") || id.includes("ahorro_solar_histórico") || id.includes("ahorro_solar_historico")) return dict.calc_lifetime_savings_eur;
  if (id.includes("calc_lifetime_charging_cost") || id.includes("coste_de_recarga_histórico") || id.includes("coste_de_recarga_historico")) return dict.calc_lifetime_charging_cost_eur;

  if (id.includes("empty_timestamp") || id.includes("hora_prevista_batería_agotada") || id.includes("empty_time") || id.includes("predicted_empty")) return dict.empty_timestamp;
  if (id.includes("full_charge_timestamp") || id.includes("hora_prevista_carga_completa") || id.includes("full_charge_time") || id.includes("predicted_full_charge")) return dict.full_charge_timestamp;
  if (id.includes("smoothed_discharge") || id.includes("autonomía_suavizada") || id.includes("autonomia_suavizada")) return dict.smoothed_discharge_time;

  if (id.includes("total_input_power") || id.includes("potencia_total_entrada")) return dict.total_input_power;
  if (id.includes("total_output_power") || id.includes("potencia_total_salida")) return dict.total_output_power;
  if (id.includes("ac_input") || id.includes("potencia_entrada_ac")) return dict.ac_input;
  if (id.includes("dc_input") || id.includes("potencia_entrada_dc")) return dict.dc_input;
  if (id.includes("ac_output_power") || id.includes("potencia_salida_ac")) return dict.ac_output_power;
  if (id.includes("ac_output_voltage") || id.includes("voltaje_salida_ac")) return dict.ac_output_voltage;
  if (id.includes("usb_a_power") || id.includes("potencia_usb_a")) return dict.usb_a_power;
  if (id.includes("usb_c_qc_power") || id.includes("potencia_usb_c_qc")) return dict.usb_c_qc_power;
  if (id.includes("typec1_power") || id.includes("potencia_type_c_1")) return dict.typec1_power;
  if (id.includes("typec2_power") || id.includes("potencia_type_c_2")) return dict.typec2_power;
  if (id.includes("typec3_power") || id.includes("potencia_type_c_3")) return dict.typec3_power;
  if (id.includes("typec4_power") || id.includes("potencia_type_c_4")) return dict.typec4_power;
  if (id.includes("dc_output_power") || id.includes("potencia_salida_dc")) return dict.dc_output_power;
  if (id.includes("dc_output_voltage") || id.includes("voltaje_salida_dc")) return dict.dc_output_voltage;
  if (id.includes("dc_output_current") || id.includes("corriente_salida_dc")) return dict.dc_output_current;
  if (id.includes("wifi_signal") || id.includes("señal_wi_fi") || id.includes("senal_wi_fi") || id.includes("wifi")) return dict.wifi_signal;
  if (id.includes("bms_version") || id.includes("versión_de_bms") || id.includes("version_de_bms")) return dict.BMS_Version;
  if (id.includes("ac_version") || id.includes("inverter_version") || id.includes("versión_de_inversor") || id.includes("version_de_inversor")) return dict.AC_Version;
  if (id.includes("hardware_fault") || id.includes("device_fault") || id.includes("fault_status") || id.includes("estado_operativo_del_hardware")) return dict.device_fault_status;
  if (id.includes("connection_mode") || id.includes("modo_de_conexión") || id.includes("modo_de_conexion")) return dict.connection_mode;
  if (id.includes("remaining_time") || id.includes("tiempo_restante")) return dict.remaining_time;
  if (id.includes("remain_charging_time") || id.includes("tiempo_restante_de_carga")) return dict.remain_charging_time;
  if (id.includes("remain_time") || id.includes("tiempo_restante_de_descarga")) return dict.remain_time;
  if ((id.includes("temp") || id.includes("temperatura")) && !id.includes("inverter")) return dict.temp;
  if (id.includes("on_battery") || id.includes("alimentado_por_batería") || id.includes("alimentado_por_bateria")) return dict.on_battery;
  if (id.includes("device_online") || id.endsWith("_online") || id.includes("dispositivo_en_línea") || id.includes("dispositivo_en_linea")) return dict.device_online;
  if (id.includes("pause_integration") || id.includes("pausar_integración") || id.includes("pausar_integracion")) return dict.pause_integration;
  if (id.includes("ac_charging_limit") || id.includes("límite_de_carga_ac") || id.includes("limite_de_carga_ac")) return dict.ac_charging_limit;
  if (id.includes("frequency") || id.includes("frecuencia")) return dict.output_frequency;
  if ((id.includes("voltage") || id.includes("tensión") || id.includes("tension") || id.includes("voltaje")) && (id.includes("select") || id.includes("output_voltage"))) return dict.output_voltage;
  if (id.includes("reload") || id.includes("recargar")) return dict.reload;

  if (id.includes("ac_switch") || id.endsWith("_ac_output") || id.includes("salida_ac")) return dict.ac_output;
  if (id.includes("dc_switch") || id.includes("dc_12v_output") || id.includes("salida_dc")) return dict.dc_12v_output;
  if (id.includes("usb_switch") || id.includes("usb_output") || id.includes("salida_usb")) return dict.usb_output;

  if (id.includes("battery_percentage") || id.endsWith("_battery") || id.includes("batería") || id.includes("bateria")) return dict.battery_percentage;

  return null;
}

function setupOukitelTooltips() {
  if (window.__oukitel_tooltips_initialized) return;
  window.__oukitel_tooltips_initialized = true;

  function hookRowClass(cls) {
    if (!cls || !cls.prototype || cls.prototype.__oukitel_hooked) return;
    cls.prototype.__oukitel_hooked = true;
    const origUpdated = cls.prototype.updated;
    cls.prototype.updated = function (changedProps) {
      if (origUpdated) {
        origUpdated.call(this, changedProps);
      }
      try {
        const entityId = this._config?.entity || this.config?.entity;
        if (entityId) {
          const desc = getOukitelDescription(entityId, this.hass);
          if (desc) {
            const root = this.shadowRoot || this;
            const elements = root.querySelectorAll(".name, .info, .text-content, state-badge, ha-state-icon, div[title]");
            elements.forEach((el) => {
              el.title = desc;
            });
            this.title = desc;
          }
        }
      } catch (e) {}
    };
  }

  if (window.customElements) {
    if (customElements.get("hui-generic-entity-row")) {
      hookRowClass(customElements.get("hui-generic-entity-row"));
    }
    if (customElements.whenDefined) {
      customElements.whenDefined("hui-generic-entity-row").then(hookRowClass);
    }
  }

  // Global mouseover / pointerover listener
  document.addEventListener(
    "mouseover",
    (event) => {
      try {
        const path = event.composedPath ? event.composedPath() : [];
        let foundDesc = null;
        let targetRow = null;

        for (const el of path) {
          if (!el || !el.tagName) continue;

          // 1. Check entity attributes
          const entityId =
            (typeof el.entity === "string" ? el.entity : null) ||
            (typeof el._config?.entity === "string" ? el._config.entity : null) ||
            (typeof el.config?.entity === "string" ? el.config.entity : null) ||
            (typeof el.stateObj?.entity_id === "string" ? el.stateObj.entity_id : null) ||
            (typeof el._stateObj?.entity_id === "string" ? el._stateObj.entity_id : null) ||
            (el.getAttribute && (el.getAttribute("data-entity-id") || el.getAttribute("entity") || el.getAttribute("data-row-id")));

          const hass = el.hass || window.document.querySelector("home-assistant")?.hass;

          if (entityId && typeof entityId === "string") {
            const desc = getOukitelDescription(entityId, hass);
            if (desc) {
              foundDesc = desc;
              targetRow = el;
              break;
            }
          }

          // 2. Check links (device page entity tables: <a href="/config/entities/sensor.xyz">)
          if (el.href && typeof el.href === "string") {
            const m = el.href.match(/\/config\/entities\/([^/?#]+)/) || el.href.match(/entity_id=([^&#]+)/);
            if (m) {
              const desc = getOukitelDescription(decodeURIComponent(m[1]), hass);
              if (desc) {
                foundDesc = desc;
                targetRow = el;
                break;
              }
            }
          }

          // 3. Check existing title attribute or text content
          const txt = (el.title && typeof el.title === "string" ? el.title : "") || (el.innerText && el.innerText.length < 80 ? el.innerText : "");
          if (txt && (txt.toLowerCase().includes("oukitel") || txt.toLowerCase().includes("p2001") || txt.toLowerCase().includes("bms") || txt.toLowerCase().includes("inverter") || txt.toLowerCase().includes("hardware") || txt.toLowerCase().includes("operativo") || txt.toLowerCase().includes("fault") || txt.toLowerCase().includes("fallo"))) {
            const desc = getOukitelDescription(txt, hass);
            if (desc) {
              foundDesc = desc;
              targetRow = el;
              break;
            }
          }
        }

        if (foundDesc) {
          for (const subEl of path) {
            if (!subEl || !subEl.tagName) continue;
            subEl.title = foundDesc;
            if (subEl === targetRow) break;
          }
        }
      } catch (e) {}
    },
    true
  );
}

setupOukitelTooltips();

// Universal Auto-discovery helper for Oukitel entities (supports any entity name, model or custom rename)
function findOukitelEntities(hass, explicitConfig = {}) {
  const states = hass.states || {};
  const config = { ...explicitConfig };
  const allIds = Object.keys(states);

  // 1. Explicit device prefix override in card config (e.g. device: "p2001_plus_tt_ab76" or "mi_estacion")
  let explicitDevicePrefix = config.device
    ? String(config.device).trim().replace(/^sensor\./, "").replace(/_battery$/, "")
    : null;

  // 2. Battery discovery:
  let batteryId = config.battery;

  if (!batteryId || !states[batteryId]) {
    // Strategy A: If device prefix is specified in YAML
    if (explicitDevicePrefix) {
      const match = allIds.find(
        (id) => id.startsWith("sensor.") && id.includes(explicitDevicePrefix) && id.endsWith("_battery") && !id.includes("calculated")
      );
      if (match) batteryId = match;
    }

    // Strategy B: Check Home Assistant Entity Registry (hass.entities) for platform == "oukitel"
    if (!batteryId && hass.entities) {
      const oukitelEntities = Object.keys(hass.entities).filter(
        (id) => hass.entities[id] && hass.entities[id].platform === "oukitel"
      );
      batteryId = oukitelEntities.find(
        (id) => id.startsWith("sensor.") && id.endsWith("_battery") && !id.includes("calculated") && !id.includes("energy_")
      );
    }

    // Strategy C: Correlated cluster signature (unique to Oukitel: total_input_power + total_output_power)
    // Works EVEN IF the user named their battery "furgoneta" or "estacion_solar"
    if (!batteryId) {
      const powerEntity = allIds.find(
        (id) =>
          id.startsWith("sensor.") &&
          (id.endsWith("_total_input_power") || id.endsWith("_total_output_power")) &&
          !id.includes("calculated") &&
          !id.includes("energy_")
      );
      if (powerEntity) {
        const guessedPrefix = powerEntity
          .replace(/^sensor\./, "")
          .replace(/_total_input_power$/, "")
          .replace(/_total_output_power$/, "");
        const candBattery = `sensor.${guessedPrefix}_battery`;
        if (states[candBattery]) {
          batteryId = candBattery;
        } else {
          // Find any battery sharing this guessed prefix
          batteryId = allIds.find(
            (id) => id.startsWith("sensor.") && id.includes(guessedPrefix) && id.endsWith("_battery") && !id.includes("calculated")
          );
        }
      }
    }

    // Strategy D: Known Oukitel model identifiers (P2001 Plus, BP2000, BP3000, P5000, etc.)
    if (!batteryId) {
      batteryId = allIds.find(
        (id) =>
          id.startsWith("sensor.") &&
          (id.includes("p2001_plus_tt_") || id.includes("oukitel_tt_") || id.includes("p2001_plus_") || id.includes("bp3000_") || id.includes("bp2000_") || id.includes("p5000_") || id.includes("p1200_") || id.includes("p1000_")) &&
          id.endsWith("_battery") &&
          !id.includes("calculated") &&
          !id.includes("energy_")
      );
    }

    // Strategy E: Generic brand keyword in entity_id
    if (!batteryId) {
      batteryId = allIds.find(
        (id) =>
          id.startsWith("sensor.") &&
          (id.includes("oukitel") || id.includes("p2001") || id.includes("bp3000") || id.includes("bp2000") || id.includes("p5000") || id.includes("p1000")) &&
          id.endsWith("_battery") &&
          !id.includes("calculated") &&
          !id.includes("energy_")
      );
    }

    // Strategy F: Friendly name match (if user renamed entity in HA to "Oukitel ..." or "P2001 ...")
    if (!batteryId) {
      batteryId = allIds.find((id) => {
        if (!id.startsWith("sensor.") || !id.endsWith("_battery") || id.includes("calculated") || id.includes("energy_")) return false;
        const fn = (states[id]?.attributes?.friendly_name || "").toLowerCase();
        return fn.includes("oukitel") || fn.includes("p2001") || fn.includes("power station");
      });
    }

    // Strategy G: Fallback to any power station battery sensor
    if (!batteryId) {
      batteryId = allIds.find(
        (id) =>
          id.startsWith("sensor.") &&
          id.endsWith("_battery") &&
          !id.includes("calculated") &&
          !id.includes("energy_") &&
          !id.includes("phone") &&
          !id.includes("mobile") &&
          !id.includes("tablet")
      );
    }

    config.battery = batteryId;
  }

  // 3. Extract common device prefix for related entities
  let devicePrefix = explicitDevicePrefix;
  if (!devicePrefix && batteryId) {
    const raw = batteryId.replace(/^sensor\./, "").replace(/_battery$/, "");
    devicePrefix = raw.replace(/_p2001_plus$/, "").replace(/_oukitel$/, "");
  }

  if (devicePrefix || batteryId) {
    const findEntity = (domain, patterns, excludePatterns = []) => {
      // 1. Strict match: exact domain AND starts with domain.devicePrefix, EXCLUDING Riemann sums and calculated kWh
      if (devicePrefix) {
        let found = allIds.find((id) => {
          if (domain && !id.startsWith(`${domain}.`)) return false;
          if (!id.startsWith(`${domain}.${devicePrefix}`)) return false;
          if (id.includes("energy_") || id.includes("calculated") || id.endsWith("_kwh") || id.endsWith("_cost")) return false;
          if (excludePatterns.some((ex) => id.includes(ex))) return false;
          return patterns.some((p) => id.includes(p));
        });
        if (found) return found;

        // 2. Secondary match containing devicePrefix
        found = allIds.find((id) => {
          if (domain && !id.startsWith(`${domain}.`)) return false;
          if (!id.includes(devicePrefix)) return false;
          if (id.includes("energy_") || id.includes("calculated") || id.endsWith("_kwh") || id.endsWith("_cost")) return false;
          if (excludePatterns.some((ex) => id.includes(ex))) return false;
          return patterns.some((p) => id.includes(p));
        });
        if (found) return found;
      }

      // 3. Match from oukitel platform in entity registry
      if (hass.entities) {
        const found = Object.keys(hass.entities).find((id) => {
          if (domain && !id.startsWith(`${domain}.`)) return false;
          if (hass.entities[id]?.platform !== "oukitel") return false;
          if (id.includes("energy_") || id.includes("calculated") || id.endsWith("_kwh") || id.endsWith("_cost")) return false;
          if (excludePatterns.some((ex) => id.includes(ex))) return false;
          return patterns.some((p) => id.includes(p));
        });
        if (found) return found;
      }

      // 4. Generic fallback across all entities
      return allIds.find((id) => {
        if (domain && !id.startsWith(`${domain}.`)) return false;
        if (id.includes("energy_") || id.includes("calculated") || id.endsWith("_kwh") || id.endsWith("_cost")) return false;
        if (excludePatterns.some((ex) => id.includes(ex))) return false;
        return patterns.some((p) => id.includes(p));
      });
    };

    config.input_power = config.input_power || findEntity("sensor", ["total_input_power", "input_power"]);
    config.output_power = config.output_power || findEntity("sensor", ["total_output_power", "output_power"]);
    config.ac_input = config.ac_input || findEntity("sensor", ["ac_input_power", "ac_input"]);
    config.dc_input = config.dc_input || findEntity("sensor", ["dc_solar_input_power", "dc_input", "solar_input"]);
    config.ac_output_power = config.ac_output_power || findEntity("sensor", ["ac_output_power"]);
    config.ac_voltage = config.ac_voltage || findEntity("sensor", ["ac_output_voltage", "ac_voltage"]);

    // Remaining time
    config.remaining_charge = config.remaining_charge || findEntity("sensor", ["remaining_charge_time", "remain_charging_time"]);
    config.remaining_discharge = config.remaining_discharge || findEntity("sensor", ["remaining_discharge_time", "remain_time"]);
    config.remaining_time = config.remaining_time || findEntity("sensor", ["remaining_time"]);

    // Switches
    config.switch_ac = config.switch_ac || findEntity("switch", ["ac_output", "ac_switch", "toma_ac"]);
    config.switch_dc = config.switch_dc || findEntity("switch", ["dc_12v_output", "dc_output", "dc_switch", "salida_dc"]);
    config.switch_usb = config.switch_usb || findEntity("switch", ["usb_output", "usb_switch", "puertos_usb"]);

    // Diagnostics & Selects
    config.frequency = config.frequency || findEntity("select", ["output_frequency"]);
    config.inverter_temp = config.inverter_temp || findEntity("sensor", ["inverter_temperature", "inverter_temp"]);
    config.battery_temp = config.battery_temp || findEntity("sensor", ["p2001_plus_temperature", "battery_temperature", "temperature", "temp"], ["inverter"]);
    config.wifi_signal = config.wifi_signal || findEntity("sensor", ["wifi_signal"]);
    config.connection_mode = config.connection_mode || findEntity("sensor", ["connection_mode"]);
    config.fault_status = config.fault_status || findEntity("sensor", ["hardware_fault_status", "device_fault_status", "fault_status"]);

    // Financial (these DO use calculated)
    const findFinancial = (patterns) =>
      allIds.find(
        (id) =>
          id.startsWith("sensor.") &&
          (devicePrefix ? id.includes(devicePrefix) : true) &&
          patterns.some((p) => id.includes(p))
      );
    config.daily_cost = config.daily_cost || findFinancial(["daily_charging_cost", "daily_cost"]);
    config.daily_savings = config.daily_savings || findFinancial(["daily_savings"]);
    config.daily_net = config.daily_net || findFinancial(["daily_net_savings", "daily_net"]);
  }

  return config;
}

/* ==========================================================================
   1. OUKITEL DISPLAY CARD (100% Vector LCD Screen Replica)
   ========================================================================== */
class OukitelDisplayCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
    this._mapped = {};
  }

  connectedCallback() {
    if (!this._hasRendered) {
      this._render();
      this._hasRendered = true;
    }
    if (this._hass) {
      this._updateState();
    }
  }

  setConfig(config) {
    this._config = {
      show_bezel: true,
      ...config,
    };
    this._render();
    this._hasRendered = true;
    if (this._hass) {
      this._updateState();
    }
  }

  set hass(hass) {
    this._hass = hass;
    this._mapped = findOukitelEntities(hass, this._config);
    if (!this._hasRendered) {
      this._render();
      this._hasRendered = true;
    }
    this._updateState();
  }

  getCardSize() {
    return 4;
  }

  _render() {
    // Generate 11 authentic large annular curved blocks
    // Center: cx=450, cy=122, Outer radius rOut=88, Inner radius rIn=66
    // Span: 140° (bottom-left) to 40° (bottom-right) going clockwise = 260° sweep
    let annularBlocks = "";
    const totalBlocks = 11;
    const cx = 450;
    const cy = 122;
    const rIn = 66;
    const rOut = 88;
    const startBase = 140;
    const sweepTotal = 260;

    for (let i = 0; i < totalBlocks; i++) {
      const startDeg = startBase + i * (sweepTotal / totalBlocks) + 2;
      const endDeg = startDeg + (sweepTotal / totalBlocks) - 4;
      const sRad = (startDeg * Math.PI) / 180;
      const eRad = (endDeg * Math.PI) / 180;
      const x1 = (cx + rOut * Math.cos(sRad)).toFixed(1);
      const y1 = (cy + rOut * Math.sin(sRad)).toFixed(1);
      const x2 = (cx + rOut * Math.cos(eRad)).toFixed(1);
      const y2 = (cy + rOut * Math.sin(eRad)).toFixed(1);
      const x3 = (cx + rIn * Math.cos(eRad)).toFixed(1);
      const y3 = (cy + rIn * Math.sin(eRad)).toFixed(1);
      const x4 = (cx + rIn * Math.cos(sRad)).toFixed(1);
      const y4 = (cy + rIn * Math.sin(sRad)).toFixed(1);

      annularBlocks += `<path id="gauge-block-${i}" d="M ${x1} ${y1} A ${rOut} ${rOut} 0 0 1 ${x2} ${y2} L ${x3} ${y3} A ${rIn} ${rIn} 0 0 0 ${x4} ${y4} Z" fill="rgba(0, 229, 255, 0.08)" />\n`;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          width: 100%;
          user-select: none;
          box-sizing: border-box;
          font-family: 'Chakra Petch', 'Rajdhani', -apple-system, sans-serif;
        }

        .svg-container {
          width: 100%;
          height: auto;
          display: block;
          filter: drop-shadow(0 14px 32px rgba(0, 0, 0, 0.75));
        }

        @keyframes fanSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .fan-blade {
          transform-origin: 334px 44px;
        }
        .fan-spinning {
          animation: fanSpin 0.9s linear infinite;
        }
      </style>

      <svg class="svg-container" viewBox="0 0 900 310" preserveAspectRatio="xMidYMid meet" id="screen-svg">
        <defs>
          <filter id="lcd-cyan-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          <filter id="lcd-green-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          <linearGradient id="chassis-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#242830" />
            <stop offset="30%" stop-color="#181a20" />
            <stop offset="100%" stop-color="#0f1115" />
          </linearGradient>

          <linearGradient id="glass-reflection" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="rgba(255, 255, 255, 0.04)" />
            <stop offset="45%" stop-color="rgba(255, 255, 255, 0)" />
          </linearGradient>
        </defs>

        <!-- CHASSIS OUTER BEZEL (Airy top margin) -->
        <rect x="4" y="4" width="892" height="302" rx="20" fill="url(#chassis-grad)" stroke="#383c46" stroke-width="2" />

        <!-- INNER LCD SCREEN (Expanded: y=24..250 with 20px top bezel) -->
        <rect x="22" y="24" width="856" height="226" rx="14" fill="#04060a" stroke="#000000" stroke-width="2.5" />
        <rect x="22" y="24" width="856" height="226" rx="14" fill="url(#glass-reflection)" pointer-events="none" />

        <!-- ========================================================
             1. LEFT SECTION: REMAINING TIME & WARNINGS (Starts at x=90)
             ======================================================== -->
        <g id="grp-left">
          <!-- REMAINING Title (y=66) -->
          <text x="90" y="66" fill="#00e5ff" font-family="'Chakra Petch', sans-serif" font-size="14" font-weight="800" letter-spacing="2" filter="url(#lcd-cyan-glow)">REMAINING</text>

          <!-- Exact Digits (x=90, y=140) & Unit placed with balanced space -->
          <text id="txt-rem-digits" x="90" y="140" fill="#00e5ff" font-family="'Orbitron', monospace" font-size="52" font-weight="900" letter-spacing="2" filter="url(#lcd-cyan-glow)">--</text>
          <text id="txt-rem-unit" x="192" y="136" fill="#00e5ff" font-family="'Chakra Petch', sans-serif" font-size="17" font-weight="800" filter="url(#lcd-cyan-glow)">Mins</text>

          <!-- Warning / Protection Circles (y=182) -->
          <g id="ico-temp-warn" transform="translate(90, 182)" opacity="0.2">
            <circle cx="13" cy="13" r="12" fill="none" stroke="#00e5ff" stroke-width="1.8" />
            <path d="M 13 6 L 13 14 A 3 3 0 1 0 15 18 L 15 6 Z" fill="#00e5ff" />
          </g>

          <g id="ico-fault-warn" transform="translate(132, 182)" opacity="0.2">
            <circle cx="13" cy="13" r="12" fill="none" stroke="#ef4444" stroke-width="1.8" />
            <text x="13" y="18" text-anchor="middle" fill="#ef4444" font-family="'Orbitron', sans-serif" font-size="13" font-weight="900">!</text>
          </g>
        </g>

        <!-- ========================================================
             2. CENTER SECTION: AUTHENTIC BATTERY AREOLA (cx=450, cy=122)
             ======================================================== -->
        <g id="grp-center">
          <!-- Fan Icon elevated at top-left (cx=334, cy=44) -->
          <g id="fan-icon-grp" opacity="0.25">
            <g class="fan-blade" id="fan-blade-elem">
              <path d="M 334 44 C 334 37 340 34 344 37 C 341 41 338 43 334 44 Z" fill="#00e5ff" />
              <path d="M 334 44 C 341 44 344 50 341 54 C 337 51 335 48 334 44 Z" fill="#00e5ff" />
              <path d="M 334 44 C 334 51 328 54 324 51 C 327 47 330 45 334 44 Z" fill="#00e5ff" />
              <path d="M 334 44 C 327 44 324 38 327 34 C 331 37 333 40 334 44 Z" fill="#00e5ff" />
            </g>
            <circle cx="334" cy="44" r="3" fill="#00e5ff" />
          </g>

          <!-- Outer Parenthesis Bracket Arcs: ( [RING] ) -->
          <path d="M 344 74 A 106 106 0 0 0 344 170" fill="none" stroke="#00e5ff" stroke-width="2" filter="url(#lcd-cyan-glow)" />
          <path d="M 556 74 A 106 106 0 0 1 556 170" fill="none" stroke="#00e5ff" stroke-width="2" filter="url(#lcd-cyan-glow)" />

          <!-- 11 Large Annular Blocks -->
          <g id="annular-blocks-grp">
            ${annularBlocks}
          </g>

          <!-- Large Battery Percentage Digits (y=110) -->
          <text id="txt-batt-pct" x="442" y="110" text-anchor="middle" fill="#ffffff" font-family="'Orbitron', monospace" font-size="44" font-weight="900" filter="url(#lcd-cyan-glow)">--</text>
          <text x="482" y="98" fill="#ffffff" font-family="'Orbitron', sans-serif" font-size="17" font-weight="800" filter="url(#lcd-cyan-glow)">%</text>

          <!-- Green Battery Capsule (Lowered to bottom opening y=134) -->
          <rect x="422" y="134" width="56" height="22" rx="4" fill="none" stroke="#00e676" stroke-width="2" filter="url(#lcd-green-glow)" />
          <rect x="478" y="139" width="3" height="11" rx="1.5" fill="#00e676" filter="url(#lcd-green-glow)" />
          <!-- Inner Fill Rect -->
          <rect id="batt-fill-rect" x="425" y="137" width="50" height="16" rx="2" fill="#00e676" filter="url(#lcd-green-glow)" />
          <!-- Center Lightning Bolt -->
          <path id="batt-lightning" d="M 450 137 L 444 146 L 449 146 L 447 153 L 455 144 L 450 144 Z" fill="#ffffff" />

          <!-- Dynamic Status Mode Label (SUPERCHARGE / CHARGING / DISCHARGING / STANDBY, y=172) -->
          <text id="status-mode-txt" x="450" y="172" text-anchor="middle" fill="#00e676" font-family="'Chakra Petch', sans-serif" font-size="12" font-weight="900" letter-spacing="1.5" filter="url(#lcd-green-glow)">STANDBY</text>

          <!-- AC Wall Plug Icon (cy=206) -->
          <g id="plug-icon-grp" transform="translate(450, 206)" opacity="0.2">
            <circle cx="0" cy="0" r="10" fill="none" stroke="#00e676" stroke-width="1.8" filter="url(#lcd-green-glow)" />
            <path d="M -3 -4 L -3 -1 L 3 -1 L 3 -4 M -5 -1 L 5 -1 L 3 4 L -3 4 Z M 0 4 L 0 7" fill="none" stroke="#00e676" stroke-width="1.5" stroke-linecap="round" />
          </g>
        </g>

        <!-- ========================================================
             3. RIGHT SECTION: UPS, INPUT, OUTPUT, VOLTAGE & OUTPUT ICONS
             (Ends at x=810, perfectly symmetrical 68px margin from LCD edge)
             ======================================================== -->
        <g id="grp-right">
          <!-- UPS Badge (Placed at y=32 with ample clearance) -->
          <g id="ups-badge-grp" transform="translate(740, 32)" opacity="0.2">
            <rect x="0" y="0" width="46" height="17" rx="3.5" fill="rgba(0, 229, 255, 0.1)" stroke="#00e5ff" stroke-width="1.6" filter="url(#lcd-cyan-glow)" />
            <text x="23" y="12.5" text-anchor="middle" fill="#00e5ff" font-family="'Orbitron', sans-serif" font-size="10" font-weight="900" letter-spacing="1" filter="url(#lcd-cyan-glow)">UPS</text>
          </g>

          <!-- Upper Row: INPUT Watts (y=84) -->
          <text id="txt-in-watts" x="740" y="84" text-anchor="end" fill="#00e5ff" font-family="'Orbitron', monospace" font-size="34" font-weight="800" letter-spacing="2" filter="url(#lcd-cyan-glow)">0000</text>
          <text x="755" y="74" fill="#00e5ff" font-family="'Chakra Petch', sans-serif" font-size="13" font-weight="800" letter-spacing="1" filter="url(#lcd-cyan-glow)">INPUT</text>
          <text x="755" y="88" fill="#8ecae6" font-family="'Chakra Petch', sans-serif" font-size="10" font-weight="700">Watts</text>

          <!-- Middle Row: OUTPUT Watts (y=138) -->
          <text id="txt-out-watts" x="740" y="138" text-anchor="end" fill="#00e5ff" font-family="'Orbitron', monospace" font-size="34" font-weight="800" letter-spacing="2" filter="url(#lcd-cyan-glow)">0000</text>
          <text x="755" y="128" fill="#00e5ff" font-family="'Chakra Petch', sans-serif" font-size="13" font-weight="800" letter-spacing="1" filter="url(#lcd-cyan-glow)">OUTPUT</text>
          <text x="755" y="142" fill="#8ecae6" font-family="'Chakra Petch', sans-serif" font-size="10" font-weight="700">Watts</text>

          <!-- Lower Row A: VOLTAGE (y=178) -->
          <text id="txt-volt-val" x="740" y="178" text-anchor="end" fill="#00e5ff" font-family="'Orbitron', monospace" font-size="24" font-weight="800" letter-spacing="1" filter="url(#lcd-cyan-glow)">230</text>
          <text id="txt-volt-unit" x="755" y="176" fill="#00e5ff" font-family="'Chakra Petch', sans-serif" font-size="12" font-weight="800" filter="url(#lcd-cyan-glow)">V</text>

          <!-- Lower Row B: OUTPUT ICONS (Locked to exact baseline cy=214, spaced by 95px) -->
          <!-- 1. DC 12V Socket Icon (cx=590, cy=214) -->
          <g id="ico-dc-sock" transform="translate(590, 214)" opacity="0.2">
            <circle cx="0" cy="0" r="10" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
            <text x="0" y="3.5" text-anchor="middle" fill="#00e5ff" font-family="'Orbitron', sans-serif" font-size="8" font-weight="900" filter="url(#lcd-cyan-glow)">12V</text>
          </g>

          <!-- 2. USB Socket Icon (cx=685, cy=214) -->
          <g id="ico-usb-sock" transform="translate(685, 214)" opacity="0.2">
            <rect x="-11" y="-6.5" width="22" height="13" rx="3" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
            <rect x="-6" y="-3.5" width="12" height="7" rx="1.5" fill="#00e5ff" />
          </g>

          <!-- 3. AC Sine Wave Icon (cx=780, cy=214) -->
          <g id="ico-ac-wave" transform="translate(780, 214)" opacity="0.2">
            <circle cx="0" cy="0" r="10" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
            <path d="M -5 0 C -3 -4 -1 -4 0 0 C 1 4 3 4 5 0" fill="none" stroke="#00e5ff" stroke-width="1.8" stroke-linecap="round" />
          </g>
        </g>

        <!-- ========================================================
             4. BOTTOM CHASSIS FRAME: LOGO & POWER / IOT BUTTON
             ======================================================== -->
        <text x="450" y="284" text-anchor="middle" fill="#d1d5db" font-family="'Chakra Petch', -apple-system, sans-serif" font-size="20" font-weight="800" letter-spacing="8" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.8))">OUKITEL</text>

        <!-- POWER BUTTON & IOT LED -->
        <g id="power-btn-grp" transform="translate(800, 264)">
          <text x="-12" y="8" text-anchor="end" fill="#94a3b8" font-family="'Chakra Petch', sans-serif" font-size="8" font-weight="700" letter-spacing="0.8">POWER</text>
          <text x="-12" y="18" text-anchor="end" fill="#94a3b8" font-family="'Chakra Petch', sans-serif" font-size="8" font-weight="700" letter-spacing="0.8">IOT</text>

          <!-- IOT Status LED -->
          <circle id="iot-led-circle" cx="-5" cy="15" r="3" fill="#475569" />

          <!-- Power Button Outer Bezel -->
          <circle cx="16" cy="10" r="15" fill="#181a20" stroke="#334155" stroke-width="1.8" />
          <circle cx="16" cy="10" r="12" fill="#0f172a" />
          <path d="M 16 4 L 16 10 M 11.5 6.5 A 6 6 0 1 0 20.5 6.5" fill="none" stroke="#00e5ff" stroke-width="1.8" stroke-linecap="round" filter="url(#lcd-cyan-glow)" />
        </g>
      </svg>
    `;
  }

  _updateState() {
    if (!this._hass || !this.shadowRoot) return;

    const getVal = (key, fallback = 0) => {
      const id = this._mapped[key];
      if (!id || !this._hass.states[id]) return fallback;
      const val = parseFloat(this._hass.states[id].state);
      return isNaN(val) ? fallback : val;
    };

    const getStr = (key, fallback = "") => {
      const id = this._mapped[key];
      return id && this._hass.states[id] ? this._hass.states[id].state : fallback;
    };

    // 1. Data readings (Robust multi-sensor fallbacks)
    const batteryPct = Math.round(getVal("battery", 0));
    const inputW = Math.round(Math.max(getVal("input_power", 0), getVal("ac_input", 0) + getVal("dc_input", 0)));
    const outputW = Math.round(Math.max(getVal("output_power", 0), getVal("ac_output_power", 0)));
    const voltageV = Math.round(getVal("ac_voltage", 230));

    const isAcOn = getStr("switch_ac") === "on";
    const isDcOn = getStr("switch_dc") === "on";
    const isUsbOn = getStr("switch_usb") === "on";

    // Remaining time
    const remChg = getVal("remaining_charge", null);
    const remDis = getVal("remaining_discharge", null);
    const remTot = getVal("remaining_time", null);

    const isCharging = inputW > 5 || (remChg !== null && remChg > 0);
    const isDischarging = (outputW > 5 && !isCharging) || (remDis !== null && remDis > 0 && !isCharging);
    const isSupercharge = inputW > 900;
    const isAcConnected = getVal("ac_input", 0) > 10 || isCharging;

    let remMinutes = null;
    if (isCharging) {
      remMinutes = remChg !== null && remChg > 0 ? remChg : remTot;
    } else if (isDischarging) {
      remMinutes = remDis !== null && remDis > 0 ? remDis : remTot;
    } else {
      remMinutes = remTot;
    }

    // 2. LEFT: Remaining Time (Exact time: Xh Ym or MM Mins, generous auto-spacing)
    const txtRemDigits = this.shadowRoot.getElementById("txt-rem-digits");
    const txtRemUnit = this.shadowRoot.getElementById("txt-rem-unit");
    if (txtRemDigits && txtRemUnit) {
      let remNum = "--";
      let remUnit = "Mins";
      if (remMinutes !== null && remMinutes > 0) {
        if (remMinutes < 60) {
          remNum = String(Math.round(remMinutes)).padStart(2, "0");
          remUnit = "Mins";
          txtRemDigits.setAttribute("font-size", "52");
        } else {
          const hrs = Math.floor(remMinutes / 60);
          const mins = Math.round(remMinutes % 60);
          remNum = `${hrs}h ${String(mins).padStart(2, "0")}m`;
          remUnit = "";
          txtRemDigits.setAttribute("font-size", "42");
        }
      } else {
        txtRemDigits.setAttribute("font-size", "52");
      }
      txtRemDigits.textContent = remNum;
      txtRemUnit.textContent = remUnit;

      if (remUnit) {
        // Balanced clearance: 14px after digits (tight and clean, zero overlap)
        const digitsWidth = remNum.length * 44;
        txtRemUnit.setAttribute("x", `${90 + digitsWidth + 14}`);
      }
    }

    // Warnings / Temps
    const tempWarn = this.shadowRoot.getElementById("ico-temp-warn");
    if (tempWarn) {
      const invTemp = getVal("inverter_temp", 25);
      const battTemp = getVal("battery_temp", 25);
      tempWarn.style.opacity = invTemp > 60 || battTemp > 45 ? "1" : "0.2";
    }

    const faultWarn = this.shadowRoot.getElementById("ico-fault-warn");
    if (faultWarn) {
      const fault = getStr("fault_status", "Normal");
      const isFault = fault && fault.toLowerCase() !== "normal" && fault !== "0";
      faultWarn.style.opacity = isFault ? "1" : "0.2";
    }

    // 3. CENTER: 11 Large Annular Gauge Blocks
    const totalBlocks = 11;
    const activeBlocks = Math.round((Math.min(100, Math.max(0, batteryPct)) / 100) * totalBlocks);
    for (let i = 0; i < totalBlocks; i++) {
      const block = this.shadowRoot.getElementById(`gauge-block-${i}`);
      if (block) {
        if (i < activeBlocks) {
          block.setAttribute("fill", "#00e5ff");
          block.setAttribute("filter", "url(#lcd-cyan-glow)");
        } else {
          block.setAttribute("fill", "rgba(0, 229, 255, 0.08)");
          block.removeAttribute("filter");
        }
      }
    }

    const txtPct = this.shadowRoot.getElementById("txt-batt-pct");
    if (txtPct) txtPct.textContent = String(Math.min(100, Math.max(0, batteryPct)));

    const fillRect = this.shadowRoot.getElementById("batt-fill-rect");
    if (fillRect) {
      const width = Math.max(2, (Math.min(100, batteryPct) / 100) * 50);
      fillRect.setAttribute("width", `${width.toFixed(1)}`);
    }

    const lightning = this.shadowRoot.getElementById("batt-lightning");
    if (lightning) {
      lightning.style.display = isCharging ? "block" : "none";
    }

    const statusModeTxt = this.shadowRoot.getElementById("status-mode-txt");
    if (statusModeTxt) {
      if (isSupercharge) {
        statusModeTxt.textContent = "SUPERCHARGE";
        statusModeTxt.setAttribute("fill", "#00e676");
      } else if (isCharging) {
        statusModeTxt.textContent = "CHARGING";
        statusModeTxt.setAttribute("fill", "#00e676");
      } else if (isDischarging) {
        statusModeTxt.textContent = "DISCHARGING";
        statusModeTxt.setAttribute("fill", "#38bdf8");
      } else {
        statusModeTxt.textContent = "STANDBY";
        statusModeTxt.setAttribute("fill", "#64748b");
      }
    }

    // AC Plug Icon
    const plugIcon = this.shadowRoot.getElementById("plug-icon-grp");
    if (plugIcon) {
      plugIcon.style.opacity = isAcConnected ? "1" : "0.2";
    }

    // Fan Blade Animation (spins whenever charging, discharging, AC active, or active remaining time)
    const fanGrp = this.shadowRoot.getElementById("fan-icon-grp");
    const fanElem = this.shadowRoot.getElementById("fan-blade-elem");
    if (fanGrp && fanElem) {
      const isFanActive = isCharging || isDischarging || isAcOn || outputW > 0 || inputW > 0 || (remMinutes !== null && remMinutes > 0);
      fanGrp.style.opacity = isFanActive ? "1" : "0.25";
      if (isFanActive) {
        fanElem.classList.add("fan-spinning");
      } else {
        fanElem.classList.remove("fan-spinning");
      }
    }

    // 4. RIGHT: Watts, Voltage, Badges
    const upsBadge = this.shadowRoot.getElementById("ups-badge-grp");
    if (upsBadge) {
      upsBadge.style.opacity = isAcConnected && (isCharging || outputW > 0) ? "1" : "0.2";
    }

    const txtInWatts = this.shadowRoot.getElementById("txt-in-watts");
    if (txtInWatts) {
      txtInWatts.textContent = String(Math.min(9999, Math.max(0, inputW))).padStart(4, "0");
    }

    const txtOutWatts = this.shadowRoot.getElementById("txt-out-watts");
    if (txtOutWatts) {
      txtOutWatts.textContent = String(Math.min(9999, Math.max(0, outputW))).padStart(4, "0");
    }

    const txtVoltVal = this.shadowRoot.getElementById("txt-volt-val");
    if (txtVoltVal) {
      txtVoltVal.textContent = String(Math.min(999, Math.max(0, voltageV > 0 ? voltageV : 230)));
    }

    // Output Active Badges
    const icoAc = this.shadowRoot.getElementById("ico-ac-wave");
    if (icoAc) icoAc.style.opacity = isAcOn ? "1" : "0.2";

    const icoUsb = this.shadowRoot.getElementById("ico-usb-sock");
    if (icoUsb) icoUsb.style.opacity = isUsbOn ? "1" : "0.2";

    const icoDc = this.shadowRoot.getElementById("ico-dc-sock");
    if (icoDc) icoDc.style.opacity = isDcOn ? "1" : "0.2";

    // IOT LED
    const iotLed = this.shadowRoot.getElementById("iot-led-circle");
    if (iotLed) {
      const mode = getStr("connection_mode", "LAN");
      iotLed.setAttribute("fill", mode.includes("LAN") || mode.includes("Cloud") ? "#00e5ff" : "#475569");
    }
  }
}

/* ==========================================================================
   2. OUKITEL CARD (Full Control Card with Discreet Mini Tactile Switches)
   ========================================================================== */
class OukitelCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
    this._mapped = {};
    this._confirmTimers = { ac: null, dc: null, usb: null };
  }

  connectedCallback() {
    if (!this._hasRendered) {
      this._render();
      this._hasRendered = true;
    }
    if (this._hass) {
      this._updateState();
    }
  }

  setConfig(config) {
    this._config = {
      title: "Oukitel Power Station",
      show_screen: true,
      show_switches: true,
      show_finances: true,
      ...config,
    };
    this._render();
    this._hasRendered = true;
    if (this._hass) {
      this._updateState();
    }
  }

  set hass(hass) {
    const prevLang = this._currentLang;
    this._currentLang = (
      (hass && (hass.locale?.language || hass.language)) ||
      (navigator && navigator.language) ||
      "en"
    ).toLowerCase();
    this._hass = hass;
    this._mapped = findOukitelEntities(hass, this._config);
    const displayCard = this.shadowRoot.querySelector("#inner-display");
    if (displayCard) {
      if (!displayCard._configInitialized) {
        displayCard.setConfig({ ...this._config, show_bezel: true });
        displayCard._configInitialized = true;
      }
      displayCard.hass = hass;
    }
    if (!this._hasRendered || (prevLang && prevLang !== this._currentLang)) {
      this._render();
      this._hasRendered = true;
    }
    this._updateState();
  }

  getCardSize() {
    return 7;
  }

  _render() {
    const isEs = (this._currentLang || "en").startsWith("es");

    const t = isEs ? {
      outputControl: "Control de Salidas",
      acTooltip: "Interruptor para encender o apagar las tomas de corriente alterna de 230V.",
      dcTooltip: "Interruptor para encender o apagar la salida de mechero de 12V DC.",
      usbTooltip: "Interruptor para encender o apagar los puertos de carga USB y Type-C.",
      financesTitle: "Balance Energético y Económico (Hoy)",
      gridCost: "Gasto Red",
      gridCostTooltip: "Coste económico acumulado de la recarga desde la red eléctrica hoy.",
      solarSavings: "Ahorro Solar",
      solarSavingsTooltip: "Ahorro económico generado hoy gracias al autoconsumo solar fotovoltaico.",
      netBalance: "Balance Neto",
      netBalanceTooltip: "Balance económico neto del día (ahorro solar menos coste de recarga de red).",
      connTooltip: "Canal de comunicación activo con Home Assistant: red local (LAN) o servidores Cloud.",
      inverter: "Inversor",
      inverterTooltip: "Temperatura interna de los disipadores y electrónica de potencia del inversor AC.",
      battery: "Batería",
      batteryTooltip: "Temperatura interna general del compartimento de celdas de la batería.",
      status: "Estado",
      statusTooltip: "Estado operativo del hardware y protecciones activas (temperatura, sobrecarga, batería).",
      normal: "Normal",
    } : {
      outputControl: "Output Control",
      acTooltip: "Switch to toggle the 230V AC output sockets on or off.",
      dcTooltip: "Switch to toggle the 12V DC car socket and barrel ports on or off.",
      usbTooltip: "Switch to toggle the USB and Type-C charging ports on or off.",
      financesTitle: "Energy & Financial Balance (Today)",
      gridCost: "Grid Cost",
      gridCostTooltip: "Accumulated economic cost of grid charging today.",
      solarSavings: "Solar Savings",
      solarSavingsTooltip: "Economic savings generated today from solar photovoltaic self-consumption.",
      netBalance: "Net Balance",
      netBalanceTooltip: "Daily net financial balance (solar savings minus grid charging cost).",
      connTooltip: "Active communication transport with Home Assistant: local network (LAN) or Cloud servers.",
      inverter: "Inverter",
      inverterTooltip: "Internal temperature of the AC inverter power electronics and heatsinks.",
      battery: "Battery",
      batteryTooltip: "Internal temperature of the battery cell compartment.",
      status: "Status",
      statusTooltip: "Operating hardware status and active protections (thermal, overload, battery).",
      normal: "Normal",
    };

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: 'Rajdhani', 'Chakra Petch', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
          user-select: none;
          box-sizing: border-box;
        }

        ha-card {
          background: var(--ha-card-background, var(--card-background-color, #13151b));
          border-radius: var(--ha-card-border-radius, 18px);
          border: 1px solid var(--ha-card-border-color, rgba(255, 255, 255, 0.08));
          box-shadow: var(--ha-card-box-shadow, 0 8px 24px rgba(0, 0, 0, 0.5));
          overflow: hidden;
          padding: 12px;
        }

        .section-title {
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 1.2px;
          color: #94a3b8;
          text-transform: uppercase;
          margin: 10px 4px 6px 4px;
        }

        /* SLEEK, DISCREET MINI-SWITCHES GRID */
        .switches-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
          margin-top: 4px;
        }

        .switch-btn {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 10px;
          padding: 7px 10px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 6px;
          cursor: pointer;
          user-select: none;
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .switch-btn:hover {
          background: rgba(255, 255, 255, 0.06);
          border-color: rgba(255, 255, 255, 0.2);
        }
        .switch-btn:active {
          transform: scale(0.98);
        }

        /* Active Switch States */
        .switch-btn.active {
          background: rgba(0, 229, 255, 0.08);
          border-color: rgba(0, 229, 255, 0.5);
          box-shadow: 0 0 10px rgba(0, 229, 255, 0.25);
        }
        .switch-btn.active .btn-icon {
          fill: #00e5ff;
          filter: drop-shadow(0 0 4px #00e5ff);
        }
        .switch-btn.active .btn-state {
          color: #00e5ff;
          background: rgba(0, 229, 255, 0.15);
        }

        /* Warning Pulsing for 2-step confirmation */
        @keyframes confirmPulse {
          0% { box-shadow: 0 0 4px #ef4444; border-color: #ef4444; }
          50% { box-shadow: 0 0 14px #ef4444; border-color: #ff7878; }
          100% { box-shadow: 0 0 4px #ef4444; border-color: #ef4444; }
        }
        .switch-btn.confirm-warning {
          background: rgba(239, 68, 68, 0.15) !important;
          border-color: #ef4444 !important;
          animation: confirmPulse 1s infinite ease-in-out;
        }
        .switch-btn.confirm-warning .btn-state {
          color: #ef4444 !important;
          background: rgba(239, 68, 68, 0.25) !important;
          font-weight: 800;
        }

        .btn-left {
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .btn-icon {
          width: 17px;
          height: 17px;
          fill: #94a3b8;
          transition: fill 0.2s ease;
          flex-shrink: 0;
        }
        .btn-label {
          font-size: 11px;
          font-weight: 800;
          color: #f1f5f9;
          letter-spacing: 0.4px;
          white-space: nowrap;
        }
        .btn-state {
          font-size: 9px;
          font-weight: 800;
          letter-spacing: 0.6px;
          color: #64748b;
          text-transform: uppercase;
          padding: 2px 5px;
          border-radius: 4px;
          background: rgba(255, 255, 255, 0.04);
          white-space: nowrap;
        }

        /* FINANCIAL METRICS GRID */
        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
          margin-top: 4px;
        }
        .metric-card {
          background: rgba(255, 255, 255, 0.025);
          border: 1px solid rgba(255, 255, 255, 0.05);
          border-radius: 10px;
          padding: 8px 6px;
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
        }
        .metric-label {
          font-size: 10px;
          font-weight: 700;
          color: #94a3b8;
          text-transform: uppercase;
          letter-spacing: 0.6px;
          margin-bottom: 2px;
        }
        .metric-value {
          font-family: 'Orbitron', monospace;
          font-size: 15px;
          font-weight: 800;
        }
        .metric-value.cost { color: #f87171; }
        .metric-value.savings { color: #4ade80; }
        .metric-value.net { color: #38bdf8; }

        /* FOOTER DIAGNOSTICS */
        .footer-badges {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 4px 0px 4px;
          font-size: 10px;
          font-weight: 700;
          color: #64748b;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
          margin-top: 10px;
        }
        .badge-item {
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .badge-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: #00e5ff;
          box-shadow: 0 0 5px #00e5ff;
        }
      </style>

      <ha-card>
        <!-- SCREEN SIMULATION (Optional) -->
        ${this._config.show_screen ? '<oukitel-display-card id="inner-display" style="margin-bottom: 10px;"></oukitel-display-card>' : ''}

        <!-- DISCREET MINI TACTILE SWITCHES -->
        <div class="section-title">${t.outputControl}</div>
        <div class="switches-grid">
          <!-- 1. AC 230V SWITCH -->
          <div class="switch-btn" id="btn-sw-ac" title="${t.acTooltip}">
            <div class="btn-left">
              <svg class="btn-icon" viewBox="0 0 24 24">
                <path d="M7 2V11H10V22L17 10H14L17 2H7Z"/>
              </svg>
              <span class="btn-label">AC 230V</span>
            </div>
            <span class="btn-state" id="st-sw-ac">OFF</span>
          </div>

          <!-- 2. DC 12V SWITCH -->
          <div class="switch-btn" id="btn-sw-dc" title="${t.dcTooltip}">
            <div class="btn-left">
              <svg class="btn-icon" viewBox="0 0 24 24">
                <path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5H6.5C5.84 5 5.28 5.42 5.08 6.01L3 12V20C3 20.55 3.45 21 4 21H5C5.55 21 6 20.55 6 20V19H18V20C18 20.55 18.45 21 19 21H20C20.55 21 21 20.55 21 20V12L18.92 6.01M6.5 6.5H17.5L18.83 10.5H5.17L6.5 6.5M6.5 13C7.33 13 8 13.67 8 14.5S7.33 16 6.5 16 5 15.33 5 14.5 5.67 13 6.5 13M17.5 13C18.33 13 19 13.67 19 14.5S18.33 16 17.5 16 16 15.33 16 14.5 16.67 13 17.5 13Z"/>
              </svg>
              <span class="btn-label">DC 12V</span>
            </div>
            <span class="btn-state" id="st-sw-dc">OFF</span>
          </div>

          <!-- 3. USB SWITCH -->
          <div class="switch-btn" id="btn-sw-usb" title="${t.usbTooltip}">
            <div class="btn-left">
              <svg class="btn-icon" viewBox="0 0 24 24">
                <path d="M15 7V4H16V2H8V4H9V7H7V10H8V14C8 15.1 8.9 16 10 16H11V20H10V22H14V20H13V16H14C15.1 16 16 15.1 16 14V10H17V7H15M10 4H14V7H10V4Z"/>
              </svg>
              <span class="btn-label">USB</span>
            </div>
            <span class="btn-state" id="st-sw-usb">OFF</span>
          </div>
        </div>

        <!-- FINANCIAL & ENERGY SUMMARY -->
        <div class="section-title">${t.financesTitle}</div>
        <div class="metrics-grid">
          <div class="metric-card" title="${t.gridCostTooltip}">
            <span class="metric-label">${t.gridCost}</span>
            <span class="metric-value cost" id="val-daily-cost">0,00 €</span>
          </div>
          <div class="metric-card" title="${t.solarSavingsTooltip}">
            <span class="metric-label">${t.solarSavings}</span>
            <span class="metric-value savings" id="val-daily-savings">0,00 €</span>
          </div>
          <div class="metric-card" title="${t.netBalanceTooltip}">
            <span class="metric-label">${t.netBalance}</span>
            <span class="metric-value net" id="val-daily-net">0,00 €</span>
          </div>
        </div>

        <!-- FOOTER DIAGNOSTICS -->
        <div class="footer-badges">
          <div class="badge-item" title="${t.connTooltip}">
            <span class="badge-dot" id="dot-status"></span>
            <span id="txt-conn-mode">LAN (0ms)</span>
          </div>
          <div class="badge-item" title="${t.inverterTooltip}">
            <span>${t.inverter}: <strong id="txt-inv-temp" style="color: #e2e8f0;">--°C</strong></span>
          </div>
          <div class="badge-item" title="${t.batteryTooltip}">
            <span>${t.battery}: <strong id="txt-batt-temp" style="color: #e2e8f0;">--°C</strong></span>
          </div>
          <div class="badge-item" title="${t.statusTooltip}">
            <span>${t.status}: <strong id="txt-fault" style="color: #94a3b8;">${t.normal}</strong></span>
          </div>
        </div>
      </ha-card>
    `;

    this._attachEvents();
  }

  _attachEvents() {
    const bindSafeSwitch = (btnId, key, entityKey) => {
      const btn = this.shadowRoot.getElementById(btnId);
      if (btn) {
        btn.addEventListener("click", () => this._handleSafeSwitchClick(key, entityKey));
      }
    };

    bindSafeSwitch("btn-sw-ac", "ac", "switch_ac");
    bindSafeSwitch("btn-sw-dc", "dc", "switch_dc");
    bindSafeSwitch("btn-sw-usb", "usb", "switch_usb");
  }

  // Safety confirmation logic: Turning OFF an active output requires a 2nd confirmation click
  _handleSafeSwitchClick(switchKey, entityKey) {
    const entityId = this._mapped[entityKey];
    if (!entityId || !this._hass) return;

    const stateObj = this._hass.states[entityId];
    const isCurrentlyOn = stateObj && stateObj.state === "on";

    if (!isCurrentlyOn) {
      // Direct Turn ON (no danger)
      this._hass.callService("switch", "turn_on", { entity_id: entityId });
      return;
    }

    // Is currently ON -> check if already awaiting confirmation
    if (this._confirmTimers[switchKey]) {
      // 2nd Click confirmed! Execute Turn OFF
      clearTimeout(this._confirmTimers[switchKey].timeout);
      clearInterval(this._confirmTimers[switchKey].interval);
      this._confirmTimers[switchKey] = null;
      this._hass.callService("switch", "turn_off", { entity_id: entityId });
      this._updateSwitchButtonVisual(switchKey, false, "OFF", false);
      return;
    }

    // First click: arm 4-second safety warning countdown
    let remainingSec = 4;
    const btn = this.shadowRoot.getElementById(`btn-sw-${switchKey}`);
    const st = this.shadowRoot.getElementById(`st-sw-${switchKey}`);

    const renderWarning = () => {
      if (btn && st) {
        btn.classList.add("confirm-warning");
        st.textContent = `⚠️ ${remainingSec}s`;
      }
    };

    renderWarning();

    const interval = setInterval(() => {
      remainingSec--;
      if (remainingSec > 0) {
        renderWarning();
      }
    }, 1000);

    const timeout = setTimeout(() => {
      clearInterval(interval);
      this._confirmTimers[switchKey] = null;
      if (btn && st) {
        btn.classList.remove("confirm-warning");
        const stillOn = this._hass && this._hass.states[entityId] && this._hass.states[entityId].state === "on";
        st.textContent = stillOn ? "ON" : "OFF";
      }
    }, 4000);

    this._confirmTimers[switchKey] = { timeout, interval };
  }

  _updateSwitchButtonVisual(switchKey, isActive, labelText, isWarning = false) {
    const btn = this.shadowRoot.getElementById(`btn-sw-${switchKey}`);
    const st = this.shadowRoot.getElementById(`st-sw-${switchKey}`);
    if (!btn || !st) return;

    btn.classList.toggle("active", isActive);
    btn.classList.toggle("confirm-warning", isWarning);
    st.textContent = labelText;
  }

  _updateState() {
    if (!this._hass || !this.shadowRoot) return;

    const getState = (key) => {
      const id = this._mapped[key];
      return id && this._hass.states[id] ? this._hass.states[id].state : null;
    };

    const getUnit = (key, fallback = "€") => {
      const id = this._mapped[key];
      return id && this._hass.states[id] && this._hass.states[id].attributes
        ? this._hass.states[id].attributes.unit_of_measurement || fallback
        : fallback;
    };

    // Update switches (respecting pending safety confirmation timers)
    const updateSwitch = (switchKey, entityKey) => {
      if (this._confirmTimers[switchKey]) return;
      const s = getState(entityKey);
      const is_on = s === "on" || s === true;
      this._updateSwitchButtonVisual(switchKey, is_on, is_on ? "ON" : "OFF", false);
    };

    updateSwitch("ac", "switch_ac");
    updateSwitch("dc", "switch_dc");
    updateSwitch("usb", "switch_usb");

    // Financial Metrics
    const fmtMoney = (key) => {
      const s = getState(key);
      const unit = getUnit(key, "€");
      if (s === null || s === undefined || isNaN(parseFloat(s))) return `0,00 ${unit}`;
      return `${parseFloat(s).toFixed(2).replace(".", ",")} ${unit}`;
    };

    const costEl = this.shadowRoot.getElementById("val-daily-cost");
    const savingsEl = this.shadowRoot.getElementById("val-daily-savings");
    const netEl = this.shadowRoot.getElementById("val-daily-net");

    if (costEl) costEl.textContent = fmtMoney("daily_cost");
    if (savingsEl) savingsEl.textContent = fmtMoney("daily_savings");
    if (netEl) {
      const netVal = parseFloat(getState("daily_net") || 0);
      const unit = getUnit("daily_net", "€");
      const sign = netVal > 0 ? "+" : "";
      netEl.textContent = `${sign}${netVal.toFixed(2).replace(".", ",")} ${unit}`;
    }

    // Diagnostics
    const invTempEl = this.shadowRoot.getElementById("txt-inv-temp");
    if (invTempEl) {
      const t = getState("inverter_temp");
      invTempEl.textContent = t !== null && t !== undefined && !isNaN(parseFloat(t)) ? `${Math.round(parseFloat(t))}°C` : "--°C";
    }

    const battTempEl = this.shadowRoot.getElementById("txt-batt-temp");
    if (battTempEl) {
      const t = getState("battery_temp");
      battTempEl.textContent = t !== null && t !== undefined && !isNaN(parseFloat(t)) ? `${Math.round(parseFloat(t))}°C` : "--°C";
    }

    const isEs = (this._currentLang || "en").startsWith("es");
    const modeEl = this.shadowRoot.getElementById("txt-conn-mode");
    if (modeEl) {
      const m = getState("connection_mode");
      modeEl.textContent = m || (isEs ? "Automático" : "Automatic");
    }

    const faultEl = this.shadowRoot.getElementById("txt-fault");
    if (faultEl) {
      const f = getState("fault_status");
      const isNormal = !f || f.toLowerCase() === "normal" || f === "0";
      faultEl.textContent = isNormal ? "Normal" : f;
      faultEl.style.color = isNormal ? "#94a3b8" : "#f87171";
    }
  }
}

// Register both custom elements
if (!customElements.get("oukitel-display-card")) {
  customElements.define("oukitel-display-card", OukitelDisplayCard);
}
if (!customElements.get("oukitel-card")) {
  customElements.define("oukitel-card", OukitelCard);
}

// Window card declarations for Lovelace visual card picker
window.customCards = window.customCards || [];
const isEsPicker = ((navigator && navigator.language) || "en").toLowerCase().startsWith("es");
if (!window.customCards.some((c) => c.type === "oukitel-display-card")) {
  window.customCards.push({
    type: "oukitel-display-card",
    name: "Oukitel LCD Screen Display",
    description: isEsPicker
      ? "Réplica 100% fotorrealista en SVG de la pantalla LCD física de la estación Oukitel"
      : "100% photorealistic SVG replica of the physical Oukitel power station LCD display",
    preview: true,
  });
}
if (!window.customCards.some((c) => c.type === "oukitel-card")) {
  window.customCards.push({
    type: "oukitel-card",
    name: "Oukitel Control Card",
    description: isEsPicker
      ? "Tarjeta de control completo con interruptores táctiles AC/DC/USB, confirmación de seguridad y balance financiero"
      : "Complete control dashboard card with AC/DC/USB tactile switches, safety confirmation, and financial balance",
    preview: true,
  });
}

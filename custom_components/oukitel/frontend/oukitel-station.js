/**
 * Oukitel Power Station Lovelace Cards (v3.1.0)
 *
 * 1. custom:oukitel-display-card - 100% authentic LCD screen simulation:
 *    - 11 thick annular curved gauge blocks matching real physical battery photo
 *    - Parenthesis bracket arcs `( [RING] )`
 *    - Collision-free layout: Voltage on upper row, Output badges (12V, USB, AC) on lower row
 *    - Plug icon centered in the bottom horseshoe opening
 *    - Fan animation active when charging, discharging, or in use
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

// Auto-discovery helper for Oukitel entities with strict device-prefix matching
function findOukitelEntities(hass, explicitConfig = {}) {
  const states = hass.states;
  const config = { ...explicitConfig };
  const allIds = Object.keys(states);

  let batteryId = config.battery;
  if (!batteryId || !states[batteryId]) {
    // 1. Strict match on active integration entity (e.g. sensor.p2001_plus_..._battery)
    batteryId = allIds.find(
      (id) =>
        id.startsWith("sensor.") &&
        (id.includes("p2001_plus_tt_") || id.includes("oukitel_tt_") || id.includes("p2001_plus_") || id.includes("bp3000_")) &&
        id.endsWith("_battery") &&
        !id.includes("calculated") &&
        !id.includes("energy_")
    );
    // 2. Fallback
    if (!batteryId) {
      batteryId = allIds.find(
        (id) =>
          id.startsWith("sensor.") &&
          (id.includes("oukitel") || id.includes("p2001") || id.includes("bp3000") || id.includes("p1000")) &&
          id.endsWith("_battery") &&
          !id.includes("calculated") &&
          !id.includes("energy_")
      );
    }
    config.battery = batteryId;
  }

  if (batteryId) {
    const raw = batteryId.replace(/^sensor\./, "").replace(/_battery$/, "");
    const devicePrefix = raw.replace(/_p2001_plus$/, "").replace(/_oukitel$/, "");

    const findEntity = (domain, patterns) => {
      // 1. Strict match: exact domain AND starts with domain.devicePrefix, EXCLUDING Riemann sums and calculated kWh
      let found = allIds.find((id) => {
        if (domain && !id.startsWith(`${domain}.`)) return false;
        if (!id.startsWith(`${domain}.${devicePrefix}`)) return false;
        if (id.includes("energy_") || id.includes("calculated") || id.endsWith("_kwh") || id.endsWith("_cost")) return false;
        return patterns.some((p) => id.includes(p));
      });
      if (found) return found;

      // 2. Secondary match containing devicePrefix
      found = allIds.find((id) => {
        if (domain && !id.startsWith(`${domain}.`)) return false;
        if (!id.includes(devicePrefix)) return false;
        if (id.includes("energy_") || id.includes("calculated") || id.endsWith("_kwh") || id.endsWith("_cost")) return false;
        return patterns.some((p) => id.includes(p));
      });
      if (found) return found;

      // 3. Generic fallback
      return allIds.find((id) => {
        if (domain && !id.startsWith(`${domain}.`)) return false;
        if (!id.includes("p2001") && !id.includes("oukitel")) return false;
        if (id.includes("energy_") || id.includes("calculated") || id.endsWith("_kwh") || id.endsWith("_cost")) return false;
        return patterns.some((p) => id.includes(p));
      });
    };

    config.input_power = config.input_power || findEntity("sensor", ["total_input_power", "input_power"]);
    config.output_power = config.output_power || findEntity("sensor", ["total_output_power", "output_power"]);
    config.ac_input = config.ac_input || findEntity("sensor", ["ac_input_power", "ac_input"]);
    config.dc_input = config.dc_input || findEntity("sensor", ["dc_solar_input_power", "dc_input"]);
    config.ac_output_power = config.ac_output_power || findEntity("sensor", ["ac_output_power"]);
    config.ac_voltage = config.ac_voltage || findEntity("sensor", ["ac_output_voltage"]);

    // Remaining time
    config.remaining_charge = config.remaining_charge || findEntity("sensor", ["remaining_charge_time"]);
    config.remaining_discharge = config.remaining_discharge || findEntity("sensor", ["remaining_discharge_time"]);
    config.remaining_time = config.remaining_time || findEntity("sensor", ["remaining_time"]);

    // Switches
    config.switch_ac = config.switch_ac || findEntity("switch", ["ac_output", "ac_switch"]);
    config.switch_dc = config.switch_dc || findEntity("switch", ["dc_12v_output", "dc_output", "dc_switch"]);
    config.switch_usb = config.switch_usb || findEntity("switch", ["usb_output", "usb_switch"]);

    // Diagnostics & Selects
    config.frequency = config.frequency || findEntity("select", ["output_frequency"]);
    config.inverter_temp = config.inverter_temp || findEntity("sensor", ["inverter_temperature", "inverter_temp"]);
    config.battery_temp = config.battery_temp || findEntity("sensor", ["temperature"]);
    config.wifi_signal = config.wifi_signal || findEntity("sensor", ["wifi_signal"]);
    config.connection_mode = config.connection_mode || findEntity("sensor", ["connection_mode"]);
    config.fault_status = config.fault_status || findEntity("sensor", ["fault_status", "hardware_fault_status"]);

    // Financial (these DO use calculated)
    const findFinancial = (patterns) => allIds.find(id => id.startsWith("sensor.") && id.includes(devicePrefix) && patterns.some(p => id.includes(p)));
    config.daily_cost = config.daily_cost || findFinancial(["daily_charging_cost"]);
    config.daily_savings = config.daily_savings || findFinancial(["daily_savings"]);
    config.daily_net = config.daily_net || findFinancial(["daily_net_savings"]);
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
    // Generate 11 authentic thick annular curved blocks matching physical photo
    // Span: 140° (bottom-left) to 40° (bottom-right) going clockwise = 260° sweep
    let annularBlocks = "";
    const totalBlocks = 11;
    const cx = 440;
    const cy = 110;
    const rIn = 58;
    const rOut = 78;
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
          transform-origin: 345px 52px;
        }
        .fan-spinning {
          animation: fanSpin 0.9s linear infinite;
        }
      </style>

      <svg class="svg-container" viewBox="0 0 880 275" preserveAspectRatio="xMidYMid meet" id="screen-svg">
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

        <!-- CHASSIS OUTER BEZEL -->
        <rect x="3" y="3" width="874" height="269" rx="20" fill="url(#chassis-grad)" stroke="#383c46" stroke-width="2" />

        <!-- INNER LCD SCREEN -->
        <rect x="24" y="20" width="832" height="196" rx="14" fill="#04060a" stroke="#000000" stroke-width="2.5" />
        <rect x="24" y="20" width="832" height="196" rx="14" fill="url(#glass-reflection)" pointer-events="none" />

        <!-- ========================================================
             1. LEFT SECTION: REMAINING TIME, UNIT & WARNINGS
             ======================================================== -->
        <g id="grp-left">
          <!-- REMAINING Title -->
          <text x="68" y="58" fill="#00e5ff" font-family="'Chakra Petch', sans-serif" font-size="14" font-weight="800" letter-spacing="2" filter="url(#lcd-cyan-glow)">REMAINING</text>

          <!-- Large Digital Digits -->
          <text id="txt-rem-digits" x="68" y="130" fill="#00e5ff" font-family="'Orbitron', monospace" font-size="62" font-weight="900" letter-spacing="3" filter="url(#lcd-cyan-glow)">--</text>

          <!-- Unit Mins / Hours -->
          <text id="txt-rem-unit" x="180" y="126" fill="#00e5ff" font-family="'Chakra Petch', sans-serif" font-size="18" font-weight="800" filter="url(#lcd-cyan-glow)">Mins</text>

          <!-- Warning / Protection Circles -->
          <g id="ico-temp-warn" transform="translate(68, 162)" opacity="0.2">
            <circle cx="14" cy="14" r="13" fill="none" stroke="#00e5ff" stroke-width="1.8" />
            <path d="M 14 7 L 14 15 A 3 3 0 1 0 16 19 L 16 7 Z" fill="#00e5ff" />
          </g>

          <g id="ico-fault-warn" transform="translate(108, 162)" opacity="0.2">
            <circle cx="14" cy="14" r="13" fill="none" stroke="#ef4444" stroke-width="1.8" />
            <text x="14" y="19" text-anchor="middle" fill="#ef4444" font-family="'Orbitron', sans-serif" font-size="14" font-weight="900">!</text>
          </g>
        </g>

        <!-- ========================================================
             2. CENTER SECTION: AUTHENTIC 1:1 BATTERY GAUGE & STATUS
             ======================================================== -->
        <g id="grp-center">
          <!-- Fan Icon at top-left of the gauge (x=345, y=52) -->
          <g id="fan-icon-grp" opacity="0.25">
            <g class="fan-blade" id="fan-blade-elem">
              <path d="M 345 52 C 345 45 351 42 355 45 C 352 49 349 51 345 52 Z" fill="#00e5ff" />
              <path d="M 345 52 C 352 52 355 58 352 62 C 348 59 346 56 345 52 Z" fill="#00e5ff" />
              <path d="M 345 52 C 345 59 339 62 335 59 C 338 55 341 53 345 52 Z" fill="#00e5ff" />
              <path d="M 345 52 C 338 52 335 46 338 42 C 342 45 344 48 345 52 Z" fill="#00e5ff" />
            </g>
            <circle cx="345" cy="52" r="3" fill="#00e5ff" />
          </g>

          <!-- Outer Parenthesis Bracket Arcs: ( [RING] ) -->
          <path d="M 348 65 A 94 94 0 0 0 348 155" fill="none" stroke="#00e5ff" stroke-width="2" filter="url(#lcd-cyan-glow)" />
          <path d="M 532 65 A 94 94 0 0 1 532 155" fill="none" stroke="#00e5ff" stroke-width="2" filter="url(#lcd-cyan-glow)" />

          <!-- 11 Thick Annular Blocks -->
          <g id="annular-blocks-grp">
            ${annularBlocks}
          </g>

          <!-- Inner Guide Circle -->
          <circle cx="440" cy="110" r="54" fill="none" stroke="rgba(0, 229, 255, 0.3)" stroke-width="1.6" />

          <!-- Large Battery Percentage Digits -->
          <text id="txt-batt-pct" x="432" y="104" text-anchor="middle" fill="#ffffff" font-family="'Orbitron', monospace" font-size="40" font-weight="900" filter="url(#lcd-cyan-glow)">--</text>
          <text x="468" y="92" fill="#ffffff" font-family="'Orbitron', sans-serif" font-size="16" font-weight="800" filter="url(#lcd-cyan-glow)">%</text>

          <!-- Green Battery Capsule -->
          <rect x="414" y="116" width="52" height="20" rx="3.5" fill="none" stroke="#00e676" stroke-width="1.8" filter="url(#lcd-green-glow)" />
          <rect x="466" y="121" width="3" height="10" rx="1" fill="#00e676" filter="url(#lcd-green-glow)" />
          <!-- Inner Fill Rect -->
          <rect id="batt-fill-rect" x="416.5" y="118.5" width="47" height="15" rx="2" fill="#00e676" filter="url(#lcd-green-glow)" />
          <!-- Center Lightning Bolt -->
          <path id="batt-lightning" d="M 440 119 L 435 126 L 439 126 L 438 132 L 444 125 L 440 125 Z" fill="#ffffff" />

          <!-- Dynamic Status Mode Label (SUPERCHARGE / CHARGING / DISCHARGING / STANDBY) -->
          <text id="status-mode-txt" x="440" y="152" text-anchor="middle" fill="#00e676" font-family="'Chakra Petch', sans-serif" font-size="11" font-weight="900" letter-spacing="1.2" filter="url(#lcd-green-glow)">STANDBY</text>

          <!-- AC Wall Plug Icon (cleanly centered at bottom opening, y=186) -->
          <g id="plug-icon-grp" transform="translate(440, 186)" opacity="0.2">
            <circle cx="0" cy="0" r="10" fill="none" stroke="#00e676" stroke-width="1.8" filter="url(#lcd-green-glow)" />
            <path d="M -3 -4 L -3 -1 L 3 -1 L 3 -4 M -5 -1 L 5 -1 L 3 4 L -3 4 Z M 0 4 L 0 7" fill="none" stroke="#00e676" stroke-width="1.5" stroke-linecap="round" />
          </g>
        </g>

        <!-- ========================================================
             3. RIGHT SECTION: UPS, INPUT, OUTPUT, VOLTAGE & OUTPUT ICONS
             ======================================================== -->
        <g id="grp-right">
          <!-- UPS Badge (Top Right) -->
          <g id="ups-badge-grp" transform="translate(685, 30)" opacity="0.2">
            <rect x="0" y="0" width="48" height="18" rx="4" fill="rgba(0, 229, 255, 0.1)" stroke="#00e5ff" stroke-width="1.6" filter="url(#lcd-cyan-glow)" />
            <text x="24" y="13" text-anchor="middle" fill="#00e5ff" font-family="'Orbitron', sans-serif" font-size="11" font-weight="900" letter-spacing="1" filter="url(#lcd-cyan-glow)">UPS</text>
          </g>

          <!-- Upper Row: INPUT Watts -->
          <text id="txt-in-watts" x="715" y="78" text-anchor="end" fill="#00e5ff" font-family="'Orbitron', monospace" font-size="34" font-weight="800" letter-spacing="2" filter="url(#lcd-cyan-glow)">0000</text>
          <text x="728" y="68" fill="#00e5ff" font-family="'Chakra Petch', sans-serif" font-size="13" font-weight="800" letter-spacing="1" filter="url(#lcd-cyan-glow)">INPUT</text>
          <text x="728" y="82" fill="#8ecae6" font-family="'Chakra Petch', sans-serif" font-size="10" font-weight="700">Watts</text>

          <!-- Middle Row: OUTPUT Watts -->
          <text id="txt-out-watts" x="715" y="132" text-anchor="end" fill="#00e5ff" font-family="'Orbitron', monospace" font-size="34" font-weight="800" letter-spacing="2" filter="url(#lcd-cyan-glow)">0000</text>
          <text x="728" y="122" fill="#00e5ff" font-family="'Chakra Petch', sans-serif" font-size="13" font-weight="800" letter-spacing="1" filter="url(#lcd-cyan-glow)">OUTPUT</text>
          <text x="728" y="136" fill="#8ecae6" font-family="'Chakra Petch', sans-serif" font-size="10" font-weight="700">Watts</text>

          <!-- Lower Row A: VOLTAGE (y=168) - completely separated from icons -->
          <text id="txt-volt-val" x="715" y="168" text-anchor="end" fill="#00e5ff" font-family="'Orbitron', monospace" font-size="24" font-weight="800" letter-spacing="1" filter="url(#lcd-cyan-glow)">230</text>
          <text id="txt-volt-unit" x="728" y="166" fill="#00e5ff" font-family="'Chakra Petch', sans-serif" font-size="12" font-weight="800" filter="url(#lcd-cyan-glow)">V</text>

          <!-- Lower Row B: OUTPUT ACTIVE ICONS (y=195) - spacious, no overlap -->
          <!-- 1. DC 12V Socket Icon (left) -->
          <g id="ico-dc-sock" transform="translate(565, 192)" opacity="0.2">
            <circle cx="9" cy="9" r="9" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
            <text x="9" y="12.5" text-anchor="middle" fill="#00e5ff" font-family="'Orbitron', sans-serif" font-size="7.5" font-weight="900" filter="url(#lcd-cyan-glow)">12V</text>
          </g>

          <!-- 2. USB Socket Icon (center) -->
          <g id="ico-usb-sock" transform="translate(635, 187)" opacity="0.2">
            <rect x="0" y="0" width="22" height="13" rx="3" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
            <rect x="5" y="3" width="12" height="7" rx="1.5" fill="#00e5ff" />
          </g>

          <!-- 3. AC Sine Wave Icon (right, below voltage) -->
          <g id="ico-ac-wave" transform="translate(718, 192)" opacity="0.2">
            <circle cx="9" cy="9" r="9" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
            <path d="M 4 9 C 6 5 8 5 9 9 C 10 13 12 13 14 9" fill="none" stroke="#00e5ff" stroke-width="1.8" stroke-linecap="round" />
          </g>
        </g>

        <!-- ========================================================
             4. BOTTOM CHASSIS FRAME: LOGO & POWER / IOT BUTTON
             ======================================================== -->
        <text x="440" y="246" text-anchor="middle" fill="#d1d5db" font-family="'Chakra Petch', -apple-system, sans-serif" font-size="20" font-weight="800" letter-spacing="8" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.8))">OUKITEL</text>

        <!-- POWER BUTTON & IOT LED -->
        <g id="power-btn-grp" transform="translate(775, 226)">
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

    // 2. LEFT: Remaining Time
    const txtRemDigits = this.shadowRoot.getElementById("txt-rem-digits");
    const txtRemUnit = this.shadowRoot.getElementById("txt-rem-unit");
    if (txtRemDigits && txtRemUnit) {
      if (remMinutes !== null && remMinutes > 0) {
        if (remMinutes < 100) {
          txtRemDigits.textContent = String(Math.round(remMinutes)).padStart(2, "0");
          txtRemUnit.textContent = "Mins";
        } else {
          const hours = (remMinutes / 60).toFixed(1);
          txtRemDigits.textContent = hours;
          txtRemUnit.textContent = "Hours";
        }
      } else {
        txtRemDigits.textContent = "--";
        txtRemUnit.textContent = "Mins";
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

    // 3. CENTER: 11 Annular Gauge Blocks
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
      const width = Math.max(2, (Math.min(100, batteryPct) / 100) * 47);
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
    if (!this._hasRendered) {
      this._render();
      this._hasRendered = true;
    }
    this._updateState();
  }

  getCardSize() {
    return 7;
  }

  _render() {
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
        <div class="section-title">Control de Salidas</div>
        <div class="switches-grid">
          <!-- 1. AC 230V SWITCH -->
          <div class="switch-btn" id="btn-sw-ac">
            <div class="btn-left">
              <svg class="btn-icon" viewBox="0 0 24 24">
                <path d="M7 2V11H10V22L17 10H14L17 2H7Z"/>
              </svg>
              <span class="btn-label">AC 230V</span>
            </div>
            <span class="btn-state" id="st-sw-ac">OFF</span>
          </div>

          <!-- 2. DC 12V SWITCH -->
          <div class="switch-btn" id="btn-sw-dc">
            <div class="btn-left">
              <svg class="btn-icon" viewBox="0 0 24 24">
                <path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5H6.5C5.84 5 5.28 5.42 5.08 6.01L3 12V20C3 20.55 3.45 21 4 21H5C5.55 21 6 20.55 6 20V19H18V20C18 20.55 18.45 21 19 21H20C20.55 21 21 20.55 21 20V12L18.92 6.01M6.5 6.5H17.5L18.83 10.5H5.17L6.5 6.5M6.5 13C7.33 13 8 13.67 8 14.5S7.33 16 6.5 16 5 15.33 5 14.5 5.67 13 6.5 13M17.5 13C18.33 13 19 13.67 19 14.5S18.33 16 17.5 16 16 15.33 16 14.5 16.67 13 17.5 13Z"/>
              </svg>
              <span class="btn-label">DC 12V</span>
            </div>
            <span class="btn-state" id="st-sw-dc">OFF</span>
          </div>

          <!-- 3. USB SWITCH -->
          <div class="switch-btn" id="btn-sw-usb">
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
        <div class="section-title">Balance Energético y Económico (Hoy)</div>
        <div class="metrics-grid">
          <div class="metric-card">
            <span class="metric-label">Gasto Red</span>
            <span class="metric-value cost" id="val-daily-cost">0,00 €</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Ahorro Solar</span>
            <span class="metric-value savings" id="val-daily-savings">0,00 €</span>
          </div>
          <div class="metric-card">
            <span class="metric-label">Balance Neto</span>
            <span class="metric-value net" id="val-daily-net">0,00 €</span>
          </div>
        </div>

        <!-- FOOTER DIAGNOSTICS -->
        <div class="footer-badges">
          <div class="badge-item">
            <span class="badge-dot" id="dot-status"></span>
            <span id="txt-conn-mode">LAN (0ms)</span>
          </div>
          <div class="badge-item">
            <span>Inversor: <strong id="txt-inv-temp" style="color: #e2e8f0;">--°C</strong></span>
          </div>
          <div class="badge-item">
            <span>Batería: <strong id="txt-batt-temp" style="color: #e2e8f0;">--°C</strong></span>
          </div>
          <div class="badge-item">
            <span>Estado: <strong id="txt-fault" style="color: #94a3b8;">Normal</strong></span>
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

    const modeEl = this.shadowRoot.getElementById("txt-conn-mode");
    if (modeEl) {
      const m = getState("connection_mode");
      modeEl.textContent = m || "Automático";
    }

    const faultEl = this.shadowRoot.getElementById("txt-fault");
    if (faultEl) {
      const f = getState("fault_status");
      faultEl.textContent = f && f.toLowerCase() !== "normal" && f !== "0" ? f : "Normal";
      faultEl.style.color = faultEl.textContent === "Normal" ? "#94a3b8" : "#f87171";
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
if (!window.customCards.some((c) => c.type === "oukitel-display-card")) {
  window.customCards.push({
    type: "oukitel-display-card",
    name: "Oukitel LCD Screen Display",
    description: "Réplica 100% fotorealista en SVG de la pantalla LCD física de la estación Oukitel",
    preview: true,
  });
}
if (!window.customCards.some((c) => c.type === "oukitel-card")) {
  window.customCards.push({
    type: "oukitel-card",
    name: "Oukitel Control Card",
    description: "Tarjeta de control completo con interruptores táctiles AC/DC/USB, confirmación de seguridad y balance financiero",
    preview: true,
  });
}

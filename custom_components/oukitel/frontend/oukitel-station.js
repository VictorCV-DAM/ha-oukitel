/**
 * Oukitel Power Station Lovelace Cards (v2.0.0)
 * 1. custom:oukitel-display-card - 100% Photorealistic Vector LCD Screen Simulator.
 * 2. custom:oukitel-card - Complete tactile control dashboard with switches & metrics.
 * 
 * Developer: VictorCV-DAM (ha-oukitel)
 */

const CARD_VERSION = "2.0.0";

console.info(
  `%c OUKITEL POWER STATION %c v${CARD_VERSION} `,
  "color: #ffffff; background: #0284c7; font-weight: 700; border-radius: 3px 0 0 3px; padding: 2px 4px;",
  "color: #0284c7; background: #0f172a; font-weight: 700; border-radius: 0 3px 3px 0; padding: 2px 4px;"
);

// 7-Segment SVG Segment Map
const SEG_MAP = {
  "0": ["a", "b", "c", "d", "e", "f"],
  "1": ["b", "c"],
  "2": ["a", "b", "g", "e", "d"],
  "3": ["a", "b", "g", "c", "d"],
  "4": ["f", "g", "b", "c"],
  "5": ["a", "f", "g", "c", "d"],
  "6": ["a", "f", "e", "d", "c", "g"],
  "7": ["a", "b", "c"],
  "8": ["a", "b", "c", "d", "e", "f", "g"],
  "9": ["a", "b", "c", "d", "f", "g"],
  "-": ["g"],
  " ": [],
};

// Generates SVG for a true 7-segment LCD digit with inactive ghost segments
function render7Segment(char, x, y, scale = 1, skew = -5) {
  const activeSegs = SEG_MAP[char] || [];
  const litColor = "#00e5ff";
  const dimColor = "rgba(0, 229, 255, 0.05)";

  // Standard segment paths at width 28, height 50 with chamfered joints
  const segs = {
    a: "M 4 0.5 L 24 0.5 L 20.5 4.5 L 7.5 4.5 Z",
    b: "M 24.5 3.5 L 24.5 22.5 L 20.5 20 L 20.5 7.5 Z",
    c: "M 24.5 27.5 L 24.5 46.5 L 20.5 42.5 L 20.5 30 Z",
    d: "M 7.5 45.5 L 20.5 45.5 L 24 49.5 L 4 49.5 Z",
    e: "M 3.5 27.5 L 7.5 30 L 7.5 42.5 L 3.5 46.5 Z",
    f: "M 3.5 3.5 L 7.5 7.5 L 7.5 20 L 3.5 22.5 Z",
    g: "M 6 23.5 L 22 23.5 L 24 25 L 22 26.5 L 6 26.5 L 4 25 Z",
  };

  let paths = "";
  for (const [key, d] of Object.entries(segs)) {
    const isLit = activeSegs.includes(key);
    const fill = isLit ? litColor : dimColor;
    const filter = isLit ? 'filter="url(#lcd-cyan-glow)"' : "";
    paths += `<path d="${d}" fill="${fill}" ${filter} />`;
  }

  return `<g transform="translate(${x}, ${y}) scale(${scale}) skewX(${skew})">${paths}</g>`;
}

// Auto-discovery helper for Oukitel entities
function findOukitelEntities(hass, explicitConfig = {}) {
  const states = hass.states;
  const config = { ...explicitConfig };
  const allIds = Object.keys(states);

  let batteryId = config.battery;
  if (!batteryId || !states[batteryId]) {
    batteryId = allIds.find(
      (id) =>
        (id.includes("oukitel") || id.includes("p2001") || id.includes("p1000") || id.includes("bp3000")) &&
        id.endsWith("_battery") &&
        !id.includes("calculated")
    );
    if (!batteryId) {
      batteryId = allIds.find(
        (id) => states[id].attributes && states[id].attributes.device_class === "battery" && (id.includes("oukitel") || id.includes("p2001"))
      );
    }
    config.battery = batteryId;
  }

  if (batteryId) {
    const cleanId = batteryId.replace(/^sensor\./, "").replace(/_battery$/, "");
    const tokens = cleanId.split("_").filter((t) => t.length >= 4);

    const findEntity = (domain, patterns) => {
      return allIds.find((id) => {
        if (domain && !id.startsWith(`${domain}.`)) return false;
        const matchesToken = tokens.length === 0 || tokens.some((t) => id.includes(t));
        if (!matchesToken) return false;
        return patterns.some((p) => id.includes(p));
      });
    };

    config.input_power = config.input_power || findEntity("sensor", ["total_input_power", "input_power", "entrada_watts"]);
    config.output_power = config.output_power || findEntity("sensor", ["total_output_power", "output_power", "salida_watts"]);
    config.ac_input = config.ac_input || findEntity("sensor", ["ac_input_power", "ac_input", "entrada_ac"]);
    config.dc_input = config.dc_input || findEntity("sensor", ["dc_solar_input_power", "dc_input", "entrada_dc"]);
    config.ac_output_power = config.ac_output_power || findEntity("sensor", ["ac_output_power"]);

    // Remaining time sensors
    config.remaining_charge = config.remaining_charge || findEntity("sensor", ["remaining_charge_time", "remain_charging_time", "tiempo_restante_carga"]);
    config.remaining_discharge = config.remaining_discharge || findEntity("sensor", ["remaining_discharge_time", "remain_time", "tiempo_restante_descarga"]);
    config.remaining_time = config.remaining_time || findEntity("sensor", ["remaining_time", "station_lcd_remaining_time"]);

    // Switches
    config.switch_ac = config.switch_ac || findEntity("switch", ["ac_output", "ac_switch", "interruptor_ac"]);
    config.switch_dc = config.switch_dc || findEntity("switch", ["dc_12v_output", "dc_output", "dc_switch", "interruptor_dc"]);
    config.switch_usb = config.switch_usb || findEntity("switch", ["usb_output", "usb_switch", "interruptor_usb"]);

    // Metadata & sensors
    config.frequency = config.frequency || findEntity("select", ["output_frequency"]);
    config.inverter_temp = config.inverter_temp || findEntity("sensor", ["inverter_temperature", "inverter_temp"]);
    config.battery_temp = config.battery_temp || findEntity("sensor", ["_temperature", "temperatura_oukitel"]);
    config.connection_mode = config.connection_mode || findEntity("sensor", ["connection_mode"]);
    config.fault_status = config.fault_status || findEntity("sensor", ["hardware_fault_status", "fault_status"]);

    // Financial sensors
    config.daily_cost = config.daily_cost || allIds.find((id) => id.includes("daily_charging_cost"));
    config.daily_savings = config.daily_savings || allIds.find((id) => id.includes("daily_savings") || id.includes("daily_solar_savings"));
    config.daily_net = config.daily_net || allIds.find((id) => id.includes("daily_net_savings"));
  }

  return config;
}

/* ==========================================================================
   1. OUKITEL DISPLAY CARD (100% Vector Scalable Screen Simulation)
   ========================================================================== */
class OukitelDisplayCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
    this._mapped = {};
  }

  setConfig(config) {
    this._config = {
      show_bezel: true,
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._mapped = findOukitelEntities(hass, this._config);
    this._updateState();
  }

  getCardSize() {
    return 4;
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          width: 100%;
          user-select: none;
          box-sizing: border-box;
        }

        .svg-container {
          width: 100%;
          height: auto;
          display: block;
          aspect-ratio: 880 / 320;
          filter: drop-shadow(0 12px 28px rgba(0, 0, 0, 0.7));
        }

        .interactive-btn {
          cursor: pointer;
          transition: transform 0.15s ease, filter 0.2s ease;
        }
        .interactive-btn:hover {
          filter: brightness(1.25);
        }
        .interactive-btn:active {
          transform: scale(0.97);
          transform-origin: center;
        }

        @keyframes fanSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .fan-blade {
          transform-origin: 368px 72px;
        }
        .fan-spinning {
          animation: fanSpin 0.9s linear infinite;
        }
      </style>

      <svg class="svg-container" viewBox="0 0 880 320" preserveAspectRatio="xMidYMid meet" id="screen-svg">
        <defs>
          <!-- Glowing Filter for Cyan Segments -->
          <filter id="lcd-cyan-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="1.6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          <!-- Glowing Filter for Green Elements -->
          <filter id="lcd-green-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          <!-- Chassis Metallic Gradient -->
          <linearGradient id="chassis-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#2a2e36" />
            <stop offset="20%" stop-color="#1d2027" />
            <stop offset="100%" stop-color="#111317" />
          </linearGradient>

          <!-- Screen Glass Subtle Reflection -->
          <linearGradient id="glass-reflection" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="rgba(255, 255, 255, 0.04)" />
            <stop offset="35%" stop-color="rgba(255, 255, 255, 0)" />
          </linearGradient>
        </defs>

        <!-- CHASSIS OUTER BEZEL -->
        <rect x="2" y="2" width="876" height="316" rx="20" fill="url(#chassis-grad)" stroke="#373b45" stroke-width="2" />
        
        <!-- INNER LCD RECESS FRAME -->
        <rect x="26" y="20" width="828" height="230" rx="12" fill="#04070d" stroke="#12151b" stroke-width="2.5" />
        <rect x="26" y="20" width="828" height="230" rx="12" fill="url(#glass-reflection)" pointer-events="none" />

        <!-- ==========================================
             LEFT SECTION: REMAINING TIME (x: 50..340)
             ========================================== -->
        <g id="grp-left" class="interactive-btn">
          <text x="65" y="62" fill="#00e5ff" font-family="'SF Pro Display', -apple-system, sans-serif" font-size="13" font-weight="800" letter-spacing="2" filter="url(#lcd-cyan-glow)">REMAINING</text>
          
          <!-- 7-Segment Digits Container (Two Digits side by side) -->
          <g id="rem-digits-svg"></g>

          <!-- Mins / Hours label right next to big digits -->
          <text x="180" y="146" id="rem-unit-txt" fill="#00e5ff" font-family="'SF Pro Display', sans-serif" font-size="18" font-weight="800" filter="url(#lcd-cyan-glow)">Mins</text>

          <!-- Status Icons Underneath -->
          <g transform="translate(0, 4)">
            <!-- Left Icon: Circle with Thermometer -->
            <circle cx="86" cy="186" r="13" fill="none" stroke="#00e5ff" stroke-width="2" opacity="0.85" filter="url(#lcd-cyan-glow)" />
            <path d="M 86 179 L 86 189 M 84 189 A 3 3 0 1 0 88 189 Z" fill="#00e5ff" stroke="#00e5ff" stroke-width="1.2" />

            <!-- Right Icon: Circle with Target/Dot -->
            <circle cx="128" cy="186" r="13" fill="none" stroke="#00e5ff" stroke-width="2" opacity="0.85" filter="url(#lcd-cyan-glow)" />
            <circle cx="128" cy="186" r="5" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
            <circle cx="128" cy="186" r="2" fill="#00e5ff" />
          </g>
        </g>

        <!-- ==========================================
             CENTER SECTION: CIRCULAR BATTERY GAUGE (cx: 440)
             ========================================== -->
        <g id="grp-center" class="interactive-btn">
          <!-- Animated Fan Icon (Top-Left of Gauge) -->
          <g id="fan-group" class="fan-blade">
            <circle cx="368" cy="72" r="3" fill="#00e5ff" />
            <path d="M 368 72 C 374 66 376 59 373 57 C 370 55 366 62 368 72 Z" fill="#00e5ff" filter="url(#lcd-cyan-glow)" />
            <path d="M 368 72 C 374 78 381 80 383 77 C 385 74 378 70 368 72 Z" fill="#00e5ff" filter="url(#lcd-cyan-glow)" />
            <path d="M 368 72 C 362 78 360 85 363 87 C 366 89 370 82 368 72 Z" fill="#00e5ff" filter="url(#lcd-cyan-glow)" />
            <path d="M 368 72 C 362 66 355 64 353 67 C 351 70 358 74 368 72 Z" fill="#00e5ff" filter="url(#lcd-cyan-glow)" />
          </g>

          <!-- Outer Bracket Arcs ( ) -->
          <path d="M 360 85 A 82 82 0 0 0 360 185" fill="none" stroke="#00e5ff" stroke-width="2.2" opacity="0.55" filter="url(#lcd-cyan-glow)" />
          <path d="M 520 85 A 82 82 0 0 1 520 185" fill="none" stroke="#00e5ff" stroke-width="2.2" opacity="0.55" filter="url(#lcd-cyan-glow)" />

          <!-- Radial Ticks Container (28 Notches) -->
          <g id="gauge-ticks"></g>

          <!-- Center Percentage Digits (Two 7-segment digits + %) -->
          <g id="pct-digits-svg"></g>
          <text x="472" y="124" fill="#ffffff" font-family="'SF Pro Display', sans-serif" font-size="18" font-weight="900" filter="url(#lcd-cyan-glow)">%</text>

          <!-- Green Battery Icon -->
          <g transform="translate(412, 142)">
            <rect x="0" y="0" width="56" height="22" rx="4" fill="none" stroke="#00e676" stroke-width="2.2" filter="url(#lcd-green-glow)" />
            <path d="M 58 5.5 Q 61 5.5 61 11 Q 61 16.5 58 16.5 Z" fill="#00e676" filter="url(#lcd-green-glow)" />
            <!-- Dynamic Battery Fill Level -->
            <rect id="batt-fill-rect" x="3" y="3" width="36" height="16" rx="2" fill="#00e676" opacity="0.55" />
            <!-- Centered Lightning Bolt -->
            <path d="M 29 3 L 21 11 L 28 11 L 25 19 L 35 9 L 28 9 Z" fill="#ffffff" filter="drop-shadow(0 0 4px #00e676)" />
          </g>

          <!-- Status Text Under Battery (Supercharge / Charging / etc.) -->
          <text x="440" y="184" id="status-mode-txt" text-anchor="middle" fill="#00e676" font-family="'SF Pro Display', sans-serif" font-size="11" font-weight="900" letter-spacing="1.5" filter="url(#lcd-green-glow)">SUPERCHARGE</text>

          <!-- Green AC Plug Badge -->
          <g id="plug-badge-grp" transform="translate(430, 196)">
            <circle cx="10" cy="10" r="10" fill="none" stroke="#00e676" stroke-width="1.8" filter="url(#lcd-green-glow)" />
            <path d="M 7 5 L 7 8 M 13 5 L 13 8 M 6 8 L 14 8 L 14 12 C 14 14.5 12 16 10 16 C 8 16 6 14.5 6 12 Z M 10 16 L 10 19" fill="none" stroke="#00e676" stroke-width="1.6" stroke-linecap="round" />
          </g>
        </g>

        <!-- ==========================================
             RIGHT SECTION: INPUT / OUTPUT WATTS (x: 540..820)
             ========================================== -->
        <g id="grp-right" class="interactive-btn">
          <!-- TOP ROW: INPUT WATTS -->
          <g id="input-digits-svg"></g>
          <text x="688" y="78" fill="#00e5ff" font-family="'SF Pro Display', sans-serif" font-size="14" font-weight="900" letter-spacing="1.5" filter="url(#lcd-cyan-glow)">INPUT</text>
          <text x="688" y="94" fill="#8ecae6" font-family="'SF Pro Display', sans-serif" font-size="10" font-weight="700" letter-spacing="0.5">Watts</text>

          <!-- BOTTOM ROW: OUTPUT WATTS -->
          <g id="output-digits-svg"></g>
          <text x="688" y="144" id="txt-freq" fill="#00e5ff" font-family="'SF Pro Display', sans-serif" font-size="11" font-weight="800" filter="url(#lcd-cyan-glow)">50 Hz</text>
          <text x="688" y="160" fill="#00e5ff" font-family="'SF Pro Display', sans-serif" font-size="14" font-weight="900" letter-spacing="1.5" filter="url(#lcd-cyan-glow)">OUTPUT</text>
          <text x="688" y="176" fill="#8ecae6" font-family="'SF Pro Display', sans-serif" font-size="10" font-weight="700" letter-spacing="0.5">Watts</text>
        </g>

        <!-- ==========================================
             BEZEL FOOTER: BRAND & POWER BUTTON
             ========================================== -->
        <!-- OUKITEL Silver Logo Centered -->
        <text x="440" y="292" text-anchor="middle" fill="#d1d5db" font-family="'SF Pro Display', -apple-system, sans-serif" font-size="22" font-weight="900" letter-spacing="8" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.8))">OUKITEL</text>

        <!-- Power Button & IOT LED on Right -->
        <g id="power-button-grp" class="interactive-btn" transform="translate(735, 268)">
          <text x="14" y="14" fill="#94a3b8" font-family="'SF Pro Display', sans-serif" font-size="9" font-weight="800" letter-spacing="1">POWER</text>
          <circle cx="4" cy="25" r="3.5" id="iot-led-circle" fill="#00e5ff" filter="url(#lcd-cyan-glow)" />
          <text x="14" y="28" fill="#94a3b8" font-family="'SF Pro Display', sans-serif" font-size="9" font-weight="800" letter-spacing="1">IOT</text>

          <!-- Circular Button -->
          <circle cx="68" cy="20" r="18" fill="radial-gradient(circle, #2a2e36 0%, #15171c 100%)" stroke="#475569" stroke-width="2" />
          <circle cx="68" cy="20" r="13" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
          <path d="M 68 12 L 68 18 M 64 14 A 6 6 0 1 0 72 14" fill="none" stroke="#00e5ff" stroke-width="2" stroke-linecap="round" />
        </g>
      </svg>
    `;

    this._buildSvgRadialTicks();
    this._attachEvents();
  }

  _buildSvgRadialTicks() {
    const container = this.shadowRoot.getElementById("gauge-ticks");
    if (!container) return;

    const cx = 440;
    const cy = 135;
    const r = 74;
    const totalTicks = 28;
    const startAngle = 130;
    const endAngle = 410;
    const step = (endAngle - startAngle) / (totalTicks - 1);

    let html = "";
    for (let i = 0; i < totalTicks; i++) {
      const angleRad = (startAngle + i * step) * (Math.PI / 180);
      const x1 = cx + (r - 9) * Math.cos(angleRad);
      const y1 = cy + (r - 9) * Math.sin(angleRad);
      const x2 = cx + r * Math.cos(angleRad);
      const y2 = cy + r * Math.sin(angleRad);

      html += `
        <line id="tick-${i}" x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}"
              x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}"
              stroke="rgba(0, 229, 255, 0.12)" stroke-width="3.2" stroke-linecap="round" />
      `;
    }
    container.innerHTML = html;
  }

  _attachEvents() {
    const moreInfo = (key) => {
      const id = this._mapped[key] || this._mapped.battery;
      if (!id) return;
      this.dispatchEvent(
        new CustomEvent("hass-more-info", {
          detail: { entityId: id },
          bubbles: true,
          composed: true,
        })
      );
    };

    const pwrBtn = this.shadowRoot.getElementById("power-button-grp");
    if (pwrBtn) pwrBtn.addEventListener("click", () => moreInfo("battery"));

    const grpCenter = this.shadowRoot.getElementById("grp-center");
    if (grpCenter) grpCenter.addEventListener("click", () => moreInfo("battery"));

    const grpLeft = this.shadowRoot.getElementById("grp-left");
    if (grpLeft) grpLeft.addEventListener("click", () => moreInfo("remaining_time"));

    const grpRight = this.shadowRoot.getElementById("grp-right");
    if (grpRight) grpRight.addEventListener("click", () => moreInfo("input_power"));
  }

  _updateState() {
    if (!this._hass || !this.shadowRoot) return;

    const getNum = (key, fallback = 0) => {
      const id = this._mapped[key];
      if (id && this._hass.states[id]) {
        const v = parseFloat(this._hass.states[id].state);
        return isNaN(v) ? fallback : v;
      }
      return fallback;
    };

    const getStr = (key, fallback = "") => {
      const id = this._mapped[key];
      return id && this._hass.states[id] ? this._hass.states[id].state : fallback;
    };

    const batteryPct = Math.round(getNum("battery", 0));
    const inputW = Math.round(getNum("input_power", 0));
    const outputW = Math.round(getNum("output_power", 0));
    const acInW = Math.round(getNum("ac_input", 0));
    const freqStr = getStr("frequency", "50 Hz");

    // Smart Remaining Time: charge vs discharge vs generic with hardware or Wh calculation
    let remMinutes = 0;
    if (inputW > 15) {
      remMinutes = Math.round(getNum("remaining_charge", 0));
      if (remMinutes <= 0) remMinutes = Math.round(getNum("remaining_time", 0));
      // Fallback calculation if sensor reports 0
      if (remMinutes <= 0 && batteryPct < 100) {
        const netW = Math.max(10, inputW - outputW);
        const neededWh = ((100 - batteryPct) / 100) * 2048;
        remMinutes = Math.round((neededWh / netW) * 60);
      }
    } else if (outputW > 15) {
      remMinutes = Math.round(getNum("remaining_discharge", 0));
      if (remMinutes <= 0) remMinutes = Math.round(getNum("remaining_time", 0));
      // Fallback calculation if sensor reports 0
      if (remMinutes <= 0 && batteryPct > 0) {
        const netW = Math.max(10, outputW - inputW);
        const availWh = (batteryPct / 100) * 2048;
        remMinutes = Math.round((availWh / netW) * 60);
      }
    } else {
      remMinutes = Math.round(getNum("remaining_time", 0));
    }

    const isAcConnected = acInW > 10 || (inputW > 10 && acInW >= 0);
    const isCharging = inputW > 15;
    const isDischarging = outputW > 15 && !isCharging;
    const isSupercharge = inputW >= 800;
    const isFanActive = outputW > 250 || inputW > 450 || getNum("inverter_temp", 25) > 40;

    // 1. LEFT: 7-Segment Remaining Time (Side-by-side digits)
    const remSvgContainer = this.shadowRoot.getElementById("rem-digits-svg");
    const remUnitTxt = this.shadowRoot.getElementById("rem-unit-txt");
    if (remSvgContainer && remUnitTxt) {
      let remStr = "--";
      if (remMinutes > 0) {
        if (remMinutes >= 60) {
          const hrs = Math.floor(remMinutes / 60);
          remStr = String(Math.min(99, hrs)).padStart(2, "0");
          remUnitTxt.textContent = "Hours";
        } else {
          remStr = String(Math.min(99, remMinutes)).padStart(2, "0");
          remUnitTxt.textContent = "Mins";
        }
      } else {
        remStr = "--";
        remUnitTxt.textContent = "Mins";
      }

      // Render two digits side-by-side horizontally at scale 1.5
      remSvgContainer.innerHTML =
        render7Segment(remStr[0] || "-", 65, 78, 1.5) +
        render7Segment(remStr[1] || "-", 122, 78, 1.5);
    }

    // 2. CENTER: Radial Ticks & 7-Segment Battery Percentage
    const totalTicks = 28;
    const activeTicks = Math.round((Math.min(100, Math.max(0, batteryPct)) / 100) * totalTicks);
    for (let i = 0; i < totalTicks; i++) {
      const tick = this.shadowRoot.getElementById(`tick-${i}`);
      if (tick) {
        if (i < activeTicks) {
          tick.setAttribute("stroke", "#00e5ff");
          tick.setAttribute("filter", "url(#lcd-cyan-glow)");
        } else {
          tick.setAttribute("stroke", "rgba(0, 229, 255, 0.12)");
          tick.removeAttribute("filter");
        }
      }
    }

    // Center Percentage 7-Segment Digits
    const pctSvgContainer = this.shadowRoot.getElementById("pct-digits-svg");
    if (pctSvgContainer) {
      const pctStr = String(Math.min(100, Math.max(0, batteryPct))).padStart(2, " ");
      pctSvgContainer.innerHTML =
        render7Segment(pctStr[pctStr.length - 2] || " ", 402, 85, 0.95) +
        render7Segment(pctStr[pctStr.length - 1] || "0", 436, 85, 0.95);
    }

    // Battery Fill Rect
    const fillRect = this.shadowRoot.getElementById("batt-fill-rect");
    if (fillRect) {
      fillRect.setAttribute("width", `${Math.max(2, (batteryPct / 100) * 50)}`);
    }

    // Mode Text
    const modeTxt = this.shadowRoot.getElementById("status-mode-txt");
    if (modeTxt) {
      if (isSupercharge) {
        modeTxt.textContent = "SUPERCHARGE";
        modeTxt.setAttribute("fill", "#00e676");
      } else if (isCharging) {
        modeTxt.textContent = "CHARGING";
        modeTxt.setAttribute("fill", "#00e676");
      } else if (isDischarging) {
        modeTxt.textContent = "DISCHARGING";
        modeTxt.setAttribute("fill", "#38bdf8");
      } else {
        modeTxt.textContent = "STANDBY";
        modeTxt.setAttribute("fill", "#64748b");
      }
    }

    // Plug Badge Opacity
    const plugBadge = this.shadowRoot.getElementById("plug-badge-grp");
    if (plugBadge) {
      plugBadge.style.opacity = isAcConnected ? "1" : "0.15";
    }

    // Fan Spinning
    const fanGroup = this.shadowRoot.getElementById("fan-group");
    if (fanGroup) {
      fanGroup.classList.toggle("fan-spinning", isFanActive);
      fanGroup.style.opacity = isFanActive ? "1" : "0.2";
    }

    // 3. RIGHT: 7-Segment Input & Output Watts (scale 0.88, inset margins)
    const pad4 = (n) => String(Math.min(9999, Math.max(0, n))).padStart(4, "0");
    const inStr = pad4(inputW);
    const inContainer = this.shadowRoot.getElementById("input-digits-svg");
    if (inContainer) {
      inContainer.innerHTML =
        render7Segment(inStr[0], 550, 62, 0.88) +
        render7Segment(inStr[1], 584, 62, 0.88) +
        render7Segment(inStr[2], 618, 62, 0.88) +
        render7Segment(inStr[3], 652, 62, 0.88);
    }

    const outStr = pad4(outputW);
    const outContainer = this.shadowRoot.getElementById("output-digits-svg");
    if (outContainer) {
      outContainer.innerHTML =
        render7Segment(outStr[0], 550, 138, 0.88) +
        render7Segment(outStr[1], 584, 138, 0.88) +
        render7Segment(outStr[2], 618, 138, 0.88) +
        render7Segment(outStr[3], 652, 138, 0.88);
    }

    const freqTxt = this.shadowRoot.getElementById("txt-freq");
    if (freqTxt) {
      freqTxt.textContent = freqStr.includes("60") ? "60 Hz" : "50 Hz";
    }

    // IOT LED
    const iotLed = this.shadowRoot.getElementById("iot-led-circle");
    if (iotLed) {
      const mode = getStr("connection_mode", "LAN");
      iotLed.setAttribute("fill", mode.includes("LAN") || mode.includes("Cloud") ? "#00e5ff" : "#475569");
    }
  }
}

/* ==========================================================================
   2. OUKITEL CARD (Full Control Card)
   ========================================================================== */
class OukitelCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
    this._mapped = {};
  }

  setConfig(config) {
    this._config = {
      title: "Oukitel Power Station",
      show_screen: false,
      show_switches: true,
      show_finances: true,
      ...config,
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._mapped = findOukitelEntities(hass, this._config);
    const displayCard = this.shadowRoot.querySelector("#inner-display");
    if (displayCard) {
      if (!displayCard._configInitialized) {
        displayCard.setConfig({ ...this._config, show_bezel: false });
        displayCard._configInitialized = true;
      }
      displayCard.hass = hass;
    }
    this._updateState();
  }

  getCardSize() {
    return 6;
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        }
        ha-card {
          background: var(--ha-card-background, var(--card-background-color, #1a1c22));
          border-radius: var(--ha-card-border-radius, 16px);
          border: 1px solid var(--ha-card-border-color, rgba(255, 255, 255, 0.08));
          box-shadow: var(--ha-card-box-shadow, 0 4px 12px rgba(0, 0, 0, 0.4));
          overflow: hidden;
          padding: 12px;
        }
        .section-title {
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 1px;
          color: #94a3b8;
          text-transform: uppercase;
          margin: 14px 6px 8px 6px;
        }

        .switches-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 10px;
          margin-top: 6px;
        }
        .switch-btn {
          background: rgba(255, 255, 255, 0.04);
          border: 1.5px solid rgba(255, 255, 255, 0.08);
          border-radius: 14px;
          padding: 12px 10px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 6px;
          cursor: pointer;
          user-select: none;
          transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .switch-btn:hover {
          background: rgba(255, 255, 255, 0.08);
          border-color: rgba(255, 255, 255, 0.2);
          transform: translateY(-1px);
        }
        .switch-btn:active {
          transform: scale(0.97);
        }
        .switch-btn.active {
          background: rgba(34, 197, 94, 0.12);
          border-color: #22c55e;
          box-shadow: 0 0 14px rgba(34, 197, 94, 0.35);
        }
        .switch-btn.active.ac {
          background: rgba(0, 229, 255, 0.12);
          border-color: #00e5ff;
          box-shadow: 0 0 14px rgba(0, 229, 255, 0.35);
        }
        .btn-icon {
          width: 24px;
          height: 24px;
          fill: #94a3b8;
          transition: fill 0.2s ease, filter 0.2s ease;
        }
        .switch-btn.active .btn-icon {
          fill: #22c55e;
          filter: drop-shadow(0 0 6px #22c55e);
        }
        .switch-btn.active.ac .btn-icon {
          fill: #00e5ff;
          filter: drop-shadow(0 0 6px #00e5ff);
        }
        .btn-label {
          font-size: 13px;
          font-weight: 700;
          color: #e2e8f0;
        }
        .btn-sub {
          font-size: 11px;
          color: #94a3b8;
          font-weight: 500;
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px;
          margin-top: 6px;
        }
        .metric-box {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 12px;
          padding: 10px;
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
        }
        .metric-val {
          font-size: 16px;
          font-weight: 800;
          color: #f8fafc;
          margin-top: 2px;
        }
        .metric-val.green { color: #22c55e; }
        .metric-val.orange { color: #f59e0b; }
        .metric-val.cyan { color: #00e5ff; }
        .metric-lbl {
          font-size: 10px;
          color: #94a3b8;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-top: 4px;
        }
      </style>

      <ha-card>
        ${this._config.show_screen ? `<oukitel-display-card id="inner-display"></oukitel-display-card>` : ""}

        ${this._config.show_switches ? `
          <div class="section-title">Salidas de Energía</div>
          <div class="switches-grid">
            <!-- AC Switch -->
            <div class="switch-btn ac" id="btn-sw-ac">
              <svg class="btn-icon" viewBox="0 0 24 24">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 14h-2v-4h2v4zm0-6h-2V7h2v3z"/>
              </svg>
              <div class="btn-label">AC 230V</div>
              <div class="btn-sub" id="sub-ac">OFF</div>
            </div>

            <!-- DC 12V Switch -->
            <div class="switch-btn" id="btn-sw-dc">
              <svg class="btn-icon" viewBox="0 0 24 24">
                <path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z"/>
              </svg>
              <div class="btn-label">DC 12V</div>
              <div class="btn-sub" id="sub-dc">OFF</div>
            </div>

            <!-- USB Switch -->
            <div class="switch-btn" id="btn-sw-usb">
              <svg class="btn-icon" viewBox="0 0 24 24">
                <path d="M15 7v4h1v2h-3V5h2l-3-4-3 4h2v8H8v-2.07c.7-.37 1.2-1.08 1.2-1.93 0-1.21-.99-2.2-2.2-2.2-1.21 0-2.2.99-2.2 2.2 0 .85.5 1.56 1.2 1.93V13c0 1.11.89 2 2 2h3v3.05c-.71.37-1.2 1.1-1.2 1.95a2.2 2.2 0 0 0 4.4 0c0-.85-.49-1.58-1.2-1.95V15h3c1.11 0 2-.89 2-2v-2h1V7h-3z"/>
              </svg>
              <div class="btn-label">USB Port</div>
              <div class="btn-sub" id="sub-usb">OFF</div>
            </div>
          </div>
        ` : ""}

        ${this._config.show_finances ? `
          <div class="section-title">Métricas de Ahorro y Balance Diario</div>
          <div class="metrics-grid">
            <div class="metric-box">
              <div class="metric-val orange" id="val-daily-cost">0,00 €</div>
              <div class="metric-lbl">Coste Carga</div>
            </div>
            <div class="metric-box">
              <div class="metric-val green" id="val-daily-savings">0,00 €</div>
              <div class="metric-lbl">Ahorro Solar</div>
            </div>
            <div class="metric-box">
              <div class="metric-val cyan" id="val-daily-net">0,00 €</div>
              <div class="metric-lbl">Balance Neto</div>
            </div>
          </div>
        ` : ""}
      </ha-card>
    `;

    this._setupSwitches();
  }

  _setupSwitches() {
    const toggleSwitch = (key) => {
      const entityId = this._mapped[key];
      if (!entityId || !this._hass) return;
      this._hass.callService("switch", "toggle", { entity_id: entityId });
    };

    const btnAc = this.shadowRoot.getElementById("btn-sw-ac");
    if (btnAc) btnAc.addEventListener("click", () => toggleSwitch("switch_ac"));

    const btnDc = this.shadowRoot.getElementById("btn-sw-dc");
    if (btnDc) btnDc.addEventListener("click", () => toggleSwitch("switch_dc"));

    const btnUsb = this.shadowRoot.getElementById("btn-sw-usb");
    if (btnUsb) btnUsb.addEventListener("click", () => toggleSwitch("switch_usb"));
  }

  _updateState() {
    if (!this._hass || !this.shadowRoot) return;

    const isSwOn = (key) => {
      const id = this._mapped[key];
      return id && this._hass.states[id] && this._hass.states[id].state === "on";
    };

    const getMoneyStr = (key) => {
      const id = this._mapped[key];
      if (id && this._hass.states[id]) {
        const v = parseFloat(this._hass.states[id].state);
        if (!isNaN(v)) return v.toFixed(2).replace(".", ",") + " €";
      }
      return "0,00 €";
    };

    // Update Switch buttons state
    const updateBtn = (btnId, subId, isOn, labelOn = "ON") => {
      const btn = this.shadowRoot.getElementById(btnId);
      const sub = this.shadowRoot.getElementById(subId);
      if (btn && sub) {
        btn.classList.toggle("active", isOn);
        sub.textContent = isOn ? labelOn : "OFF";
      }
    };

    updateBtn("btn-sw-ac", "sub-ac", isSwOn("switch_ac"), "230V ACTIVO");
    updateBtn("btn-sw-dc", "sub-dc", isSwOn("switch_dc"), "12V ACTIVO");
    updateBtn("btn-sw-usb", "sub-usb", isSwOn("switch_usb"), "ACTIVO");

    // Update Financial metrics
    const costEl = this.shadowRoot.getElementById("val-daily-cost");
    if (costEl) costEl.textContent = getMoneyStr("daily_cost");

    const savEl = this.shadowRoot.getElementById("val-daily-savings");
    if (savEl) savEl.textContent = getMoneyStr("daily_savings");

    const netEl = this.shadowRoot.getElementById("val-daily-net");
    if (netEl) netEl.textContent = getMoneyStr("daily_net");
  }
}

// Register Custom Elements
if (!customElements.get("oukitel-display-card")) {
  customElements.define("oukitel-display-card", OukitelDisplayCard);
}
if (!customElements.get("oukitel-card")) {
  customElements.define("oukitel-card", OukitelCard);
}

// Window card declarations for Lovelace card picker
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "oukitel-display-card")) {
  window.customCards.push({
    type: "oukitel-display-card",
    name: "Oukitel LCD Screen Display",
    description: "Authentic vector simulation of the physical Oukitel LCD screen with 7-segment digits and glowing indicators.",
    preview: true,
  });
}
if (!window.customCards.some((c) => c.type === "oukitel-card")) {
  window.customCards.push({
    type: "oukitel-card",
    name: "Oukitel Station Control Card",
    description: "Complete control dashboard with tactile switches (AC 230V, DC 12V, USB) and financial savings balance.",
    preview: true,
  });
}

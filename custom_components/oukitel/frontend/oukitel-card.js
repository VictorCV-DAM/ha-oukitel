/**
 * Oukitel Power Station Lovelace Cards (v2.1.0)
 * 1. custom:oukitel-display-card - 100% Photorealistic Vector LCD Screen Simulator + Safety Tactile Control Dock.
 * 2. custom:oukitel-card - Complete control dashboard with switches & metrics.
 * 
 * Developer: VictorCV-DAM (ha-oukitel)
 */

const CARD_VERSION = "2.1.0";

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

// Generates static SVG markup for a 7-segment LCD digit with static element IDs
function make7SegmentMarkup(prefix, x, y, scale = 1, skew = -5) {
  return `
    <g id="${prefix}" transform="translate(${x}, ${y}) scale(${scale}) skewX(${skew})">
      <path id="${prefix}-a" d="M 4 0.5 L 24 0.5 L 20.5 4.5 L 7.5 4.5 Z" fill="rgba(0, 229, 255, 0.05)" />
      <path id="${prefix}-b" d="M 24.5 3.5 L 24.5 22.5 L 20.5 20 L 20.5 7.5 Z" fill="rgba(0, 229, 255, 0.05)" />
      <path id="${prefix}-c" d="M 24.5 27.5 L 24.5 46.5 L 20.5 42.5 L 20.5 30 Z" fill="rgba(0, 229, 255, 0.05)" />
      <path id="${prefix}-d" d="M 7.5 45.5 L 20.5 45.5 L 24 49.5 L 4 49.5 Z" fill="rgba(0, 229, 255, 0.05)" />
      <path id="${prefix}-e" d="M 3.5 27.5 L 7.5 30 L 7.5 42.5 L 3.5 46.5 Z" fill="rgba(0, 229, 255, 0.05)" />
      <path id="${prefix}-f" d="M 3.5 3.5 L 7.5 7.5 L 7.5 20 L 3.5 22.5 Z" fill="rgba(0, 229, 255, 0.05)" />
      <path id="${prefix}-g" d="M 6 23.5 L 22 23.5 L 24 25 L 22 26.5 L 6 26.5 L 4 25 Z" fill="rgba(0, 229, 255, 0.05)" />
    </g>
  `;
}

// Generates an annular curved block (thick arc segment)
function describeArcBlock(x, y, rIn, rOut, startAngle, endAngle) {
  const rad = Math.PI / 180;
  const sRad = (startAngle - 90) * rad;
  const eRad = (endAngle - 90) * rad;
  const x1 = x + rOut * Math.cos(sRad);
  const y1 = y + rOut * Math.sin(sRad);
  const x2 = x + rOut * Math.cos(eRad);
  const y2 = y + rOut * Math.sin(eRad);
  const x3 = x + rIn * Math.cos(eRad);
  const y3 = y + rIn * Math.sin(eRad);
  const x4 = x + rIn * Math.cos(sRad);
  const y4 = y + rIn * Math.sin(sRad);
  const large = (endAngle - startAngle) > 180 ? 1 : 0;
  return `M ${x1.toFixed(1)} ${y1.toFixed(1)} A ${rOut} ${rOut} 0 ${large} 1 ${x2.toFixed(1)} ${y2.toFixed(1)} L ${x3.toFixed(1)} ${y3.toFixed(1)} A ${rIn} ${rIn} 0 ${large} 0 ${x4.toFixed(1)} ${y4.toFixed(1)} Z`;
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
    config.ac_voltage = config.ac_voltage || findEntity("sensor", ["ac_output_voltage"]);

    // Remaining time sensors
    config.remaining_charge = config.remaining_charge || findEntity("sensor", ["remaining_charge_time", "remain_charging_time", "tiempo_restante_carga"]);
    config.remaining_discharge = config.remaining_discharge || findEntity("sensor", ["remaining_discharge_time", "remain_time", "tiempo_restante_descarga"]);
    config.remaining_time = config.remaining_time || findEntity("sensor", ["remaining_time", "station_lcd_remaining_time"]);

    // Switches
    config.switch_ac = config.switch_ac || findEntity("switch", ["ac_output", "ac_switch", "interruptor_ac"]);
    config.switch_dc = config.switch_dc || findEntity("switch", ["dc_12v_output", "dc_output", "dc_switch", "interruptor_dc"]);
    config.switch_usb = config.switch_usb || findEntity("switch", ["usb_output", "usb_switch", "interruptor_usb"]);

    // Metadata
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
   1. OUKITEL DISPLAY CARD (100% Vector Scalable Simulation + Control Dock)
   ========================================================================== */
class OukitelDisplayCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
    this._mapped = {};
    // Safety confirmation states: null or expiry timestamp
    this._confirmTimers = {
      ac: null,
      dc: null,
      usb: null,
    };
    this._intervalId = null;
  }

  connectedCallback() {
    // Timer to update countdown on buttons if confirmation active
    this._intervalId = setInterval(() => {
      this._checkConfirmTimeouts();
    }, 500);
  }

  disconnectedCallback() {
    if (this._intervalId) clearInterval(this._intervalId);
  }

  setConfig(config) {
    this._config = {
      show_bezel: true,
      show_controls: true,
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
    return 5;
  }

  _render() {
    // 18 Curved blocks around the gauge from 135 deg to 405 deg
    let gaugeBlocksSvg = "";
    const totalBlocks = 18;
    const startDeg = 135;
    const endDeg = 405;
    const step = (endDeg - startDeg) / totalBlocks;
    for (let i = 0; i < totalBlocks; i++) {
      const s = startDeg + i * step + 1.2;
      const e = startDeg + (i + 1) * step - 1.2;
      const d = describeArcBlock(440, 135, 65, 78, s, e);
      gaugeBlocksSvg += `<path id="gauge-block-${i}" d="${d}" fill="rgba(0, 229, 255, 0.08)" />`;
    }

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
          aspect-ratio: 880 / 385;
          filter: drop-shadow(0 14px 32px rgba(0, 0, 0, 0.75));
        }

        .interactive-btn {
          cursor: pointer;
          transition: transform 0.15s ease, filter 0.2s ease, fill 0.2s ease;
        }
        .interactive-btn:hover {
          filter: brightness(1.2);
        }
        .interactive-btn:active {
          transform: scale(0.98);
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

        @keyframes pulseWarning {
          0% { stroke-opacity: 0.9; stroke-width: 2.2; }
          50% { stroke-opacity: 0.3; stroke-width: 3.5; }
          100% { stroke-opacity: 0.9; stroke-width: 2.2; }
        }
        .confirm-pulsing {
          animation: pulseWarning 0.9s infinite ease-in-out;
        }
      </style>

      <svg class="svg-container" viewBox="0 0 880 385" preserveAspectRatio="xMidYMid meet" id="screen-svg">
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
            <stop offset="18%" stop-color="#1c1f26" />
            <stop offset="100%" stop-color="#111317" />
          </linearGradient>

          <!-- Control Button Active Gradient -->
          <linearGradient id="btn-active-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="rgba(0, 229, 255, 0.18)" />
            <stop offset="100%" stop-color="rgba(0, 229, 255, 0.05)" />
          </linearGradient>

          <!-- Screen Glass Reflection -->
          <linearGradient id="glass-reflection" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="rgba(255, 255, 255, 0.04)" />
            <stop offset="35%" stop-color="rgba(255, 255, 255, 0)" />
          </linearGradient>
        </defs>

        <!-- CHASSIS OUTER BEZEL -->
        <rect x="2" y="2" width="876" height="381" rx="22" fill="url(#chassis-grad)" stroke="#373b45" stroke-width="2" />
        
        <!-- INNER LCD RECESS FRAME -->
        <rect x="26" y="20" width="828" height="232" rx="12" fill="#04070d" stroke="#12151b" stroke-width="2.5" />
        <rect x="26" y="20" width="828" height="232" rx="12" fill="url(#glass-reflection)" pointer-events="none" />

        <!-- ==========================================
             LEFT SECTION: REMAINING TIME (x: 50..340)
             ========================================== -->
        <g id="grp-left" class="interactive-btn">
          <text x="65" y="58" fill="#00e5ff" font-family="'SF Pro Display', -apple-system, sans-serif" font-size="13" font-weight="800" letter-spacing="2" filter="url(#lcd-cyan-glow)">REMAINING</text>
          
          <!-- Static 7-Segment Digits Container (Two Digits side-by-side) -->
          ${make7SegmentMarkup("rem_d0", 65, 74, 1.55)}
          ${make7SegmentMarkup("rem_d1", 126, 74, 1.55)}

          <!-- Mins / Hours label right next to big digits -->
          <text x="188" y="142" id="rem-unit-txt" fill="#00e5ff" font-family="'SF Pro Display', sans-serif" font-size="18" font-weight="800" filter="url(#lcd-cyan-glow)">Mins</text>

          <!-- Status Icons Underneath -->
          <g transform="translate(0, 4)">
            <!-- Thermometer Icon -->
            <circle cx="88" cy="188" r="13" fill="none" stroke="#00e5ff" stroke-width="2" opacity="0.85" filter="url(#lcd-cyan-glow)" />
            <path d="M 88 181 L 88 191 M 86 191 A 3 3 0 1 0 90 191 Z" fill="#00e5ff" stroke="#00e5ff" stroke-width="1.2" />

            <!-- Target / Cog Icon -->
            <circle cx="132" cy="188" r="13" fill="none" stroke="#00e5ff" stroke-width="2" opacity="0.85" filter="url(#lcd-cyan-glow)" />
            <circle cx="132" cy="188" r="5" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
            <circle cx="132" cy="188" r="2" fill="#00e5ff" />
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
          <path d="M 358 85 A 86 86 0 0 0 358 185" fill="none" stroke="#00e5ff" stroke-width="2.2" opacity="0.55" filter="url(#lcd-cyan-glow)" />
          <path d="M 522 85 A 86 86 0 0 1 522 185" fill="none" stroke="#00e5ff" stroke-width="2.2" opacity="0.55" filter="url(#lcd-cyan-glow)" />

          <!-- Thick Segmented Arc Blocks (18 blocks) -->
          <g id="gauge-blocks-grp">${gaugeBlocksSvg}</g>

          <!-- Center Percentage Digits (Two 7-segment digits + %) -->
          ${make7SegmentMarkup("pct_d0", 402, 80, 1.05)}
          ${make7SegmentMarkup("pct_d1", 438, 80, 1.05)}
          <text x="474" y="120" fill="#ffffff" font-family="'SF Pro Display', sans-serif" font-size="18" font-weight="900" filter="url(#lcd-cyan-glow)">%</text>

          <!-- Green Battery Icon -->
          <g transform="translate(412, 138)">
            <rect x="0" y="0" width="56" height="22" rx="4" fill="none" stroke="#00e676" stroke-width="2.2" filter="url(#lcd-green-glow)" />
            <path d="M 58 5.5 Q 61 5.5 61 11 Q 61 16.5 58 16.5 Z" fill="#00e676" filter="url(#lcd-green-glow)" />
            <!-- Dynamic Battery Fill Level -->
            <rect id="batt-fill-rect" x="3" y="3" width="36" height="16" rx="2" fill="#00e676" opacity="0.6" />
            <!-- Centered Lightning Bolt -->
            <path d="M 29 3 L 21 11 L 28 11 L 25 19 L 35 9 L 28 9 Z" fill="#ffffff" filter="drop-shadow(0 0 4px #00e676)" />
          </g>

          <!-- Status Text Under Battery -->
          <text x="440" y="180" id="status-mode-txt" text-anchor="middle" fill="#00e676" font-family="'SF Pro Display', sans-serif" font-size="11" font-weight="900" letter-spacing="1.5" filter="url(#lcd-green-glow)">SUPERCHARGE</text>

          <!-- Green AC Plug Badge -->
          <g id="plug-badge-grp" transform="translate(430, 194)">
            <circle cx="10" cy="10" r="10" fill="none" stroke="#00e676" stroke-width="1.8" filter="url(#lcd-green-glow)" />
            <path d="M 7 5 L 7 8 M 13 5 L 13 8 M 6 8 L 14 8 L 14 12 C 14 14.5 12 16 10 16 C 8 16 6 14.5 6 12 Z M 10 16 L 10 19" fill="none" stroke="#00e676" stroke-width="1.6" stroke-linecap="round" />
          </g>
        </g>

        <!-- ==========================================
             RIGHT SECTION: POWER, VOLTAGE & ICONS
             ========================================== -->
        <g id="grp-right" class="interactive-btn">
          <!-- Top UPS Badge -->
          <g id="ups-badge-grp" transform="translate(616, 30)">
            <rect x="0" y="0" width="48" height="20" rx="4" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
            <text x="24" y="14" text-anchor="middle" fill="#00e5ff" font-family="'SF Pro Display', sans-serif" font-size="11" font-weight="900" letter-spacing="1" filter="url(#lcd-cyan-glow)">UPS</text>
          </g>

          <!-- ROW 1: INPUT WATTS (4 Digits) -->
          ${make7SegmentMarkup("in_d0", 554, 58, 1.05)}
          ${make7SegmentMarkup("in_d1", 592, 58, 1.05)}
          ${make7SegmentMarkup("in_d2", 630, 58, 1.05)}
          ${make7SegmentMarkup("in_d3", 668, 58, 1.05)}

          <!-- ROW 2: OUTPUT WATTS (4 Digits) -->
          ${make7SegmentMarkup("out_d0", 554, 124, 1.05)}
          ${make7SegmentMarkup("out_d1", 592, 124, 1.05)}
          ${make7SegmentMarkup("out_d2", 630, 124, 1.05)}
          ${make7SegmentMarkup("out_d3", 668, 124, 1.05)}

          <!-- ROW 3: VOLTAGE (3 Digits) & ICONS -->
          <!-- Small Voltage Digits (e.g. 232 V) -->
          ${make7SegmentMarkup("volt_d0", 636, 188, 0.62)}
          ${make7SegmentMarkup("volt_d1", 658, 188, 0.62)}
          ${make7SegmentMarkup("volt_d2", 680, 188, 0.62)}

          <!-- AC Symbol Circle below voltage -->
          <g id="ac-lcd-symbol" transform="translate(656, 218)">
            <circle cx="12" cy="12" r="12" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
            <!-- Sine Wave Curve -->
            <path d="M 6 12 C 8 8 10 8 12 12 C 14 16 16 16 18 12" fill="none" stroke="#00e5ff" stroke-width="2" stroke-linecap="round" filter="url(#lcd-cyan-glow)" />
          </g>

          <!-- USB Symbol to the left of AC -->
          <g id="usb-lcd-symbol" transform="translate(574, 222)">
            <rect x="0" y="0" width="34" height="17" rx="3.5" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
            <rect x="7" y="4" width="20" height="9" rx="1.5" fill="#00e5ff" filter="url(#lcd-cyan-glow)" />
          </g>

          <!-- DC 12V Symbol -->
          <g id="dc-lcd-symbol" transform="translate(520, 218)">
            <circle cx="12" cy="12" r="12" fill="none" stroke="#00e5ff" stroke-width="1.8" opacity="0.8" filter="url(#lcd-cyan-glow)" />
            <text x="12" y="16" text-anchor="middle" fill="#00e5ff" font-family="'SF Pro Display', sans-serif" font-size="9" font-weight="900" filter="url(#lcd-cyan-glow)">12V</text>
          </g>
        </g>

        <!-- ==========================================
             BEZEL FOOTER: BRAND & POWER BUTTON
             ========================================== -->
        <!-- OUKITEL Silver Logo Centered -->
        <text x="440" y="284" text-anchor="middle" fill="#d1d5db" font-family="'SF Pro Display', -apple-system, sans-serif" font-size="22" font-weight="900" letter-spacing="8" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.8))">OUKITEL</text>

        <!-- Power Button & IOT LED on Right -->
        <g id="power-button-grp" class="interactive-btn" transform="translate(735, 260)">
          <text x="14" y="14" fill="#94a3b8" font-family="'SF Pro Display', sans-serif" font-size="9" font-weight="800" letter-spacing="1">POWER</text>
          <circle cx="4" cy="25" r="3.5" id="iot-led-circle" fill="#00e5ff" filter="url(#lcd-cyan-glow)" />
          <text x="14" y="28" fill="#94a3b8" font-family="'SF Pro Display', sans-serif" font-size="9" font-weight="800" letter-spacing="1">IOT</text>

          <!-- Circular Button -->
          <circle cx="68" cy="20" r="18" fill="radial-gradient(circle, #2a2e36 0%, #15171c 100%)" stroke="#475569" stroke-width="2" />
          <circle cx="68" cy="20" r="13" fill="none" stroke="#00e5ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
          <path d="M 68 12 L 68 18 M 64 14 A 6 6 0 1 0 72 14" fill="none" stroke="#00e5ff" stroke-width="2" stroke-linecap="round" />
        </g>

        <!-- ==========================================
             EXTERIOR CONTROL DOCK: AC, DC, USB SWITCHES
             Safety 2-step confirmation: 1st click warns, 2nd click turns off
             ========================================== -->
        <line x1="30" y1="308" x2="850" y2="308" stroke="rgba(255, 255, 255, 0.08)" stroke-width="1.5" />

        <!-- 1. AC 230V CONTROL SWITCH -->
        <g id="btn-ctrl-ac" class="interactive-btn" transform="translate(55, 318)">
          <rect id="bg-ctrl-ac" x="0" y="0" width="240" height="50" rx="10" fill="rgba(255, 255, 255, 0.04)" stroke="#475569" stroke-width="1.8" />
          <!-- AC Wave Icon -->
          <circle cx="28" cy="25" r="14" fill="none" stroke="#94a3b8" stroke-width="1.8" id="ico-circle-ac" />
          <path d="M 21 25 C 23 21 25 21 28 25 C 31 29 33 29 35 25" fill="none" stroke="#94a3b8" stroke-width="2" stroke-linecap="round" id="ico-wave-ac" />
          <!-- Text -->
          <text x="52" y="24" fill="#f8fafc" font-family="'SF Pro Display', sans-serif" font-size="13" font-weight="800">SALIDA AC 230V</text>
          <text id="txt-sub-ac" x="52" y="38" fill="#94a3b8" font-family="'SF Pro Display', sans-serif" font-size="11" font-weight="600">APAGADO</text>
        </g>

        <!-- 2. DC 12V CONTROL SWITCH -->
        <g id="btn-ctrl-dc" class="interactive-btn" transform="translate(320, 318)">
          <rect id="bg-ctrl-dc" x="0" y="0" width="240" height="50" rx="10" fill="rgba(255, 255, 255, 0.04)" stroke="#475569" stroke-width="1.8" />
          <!-- DC Car Plug Icon -->
          <circle cx="28" cy="25" r="14" fill="none" stroke="#94a3b8" stroke-width="1.8" id="ico-circle-dc" />
          <text id="ico-txt-dc" x="28" y="29" text-anchor="middle" fill="#94a3b8" font-family="'SF Pro Display', sans-serif" font-size="10" font-weight="900">12V</text>
          <!-- Text -->
          <text x="52" y="24" fill="#f8fafc" font-family="'SF Pro Display', sans-serif" font-size="13" font-weight="800">SALIDA DC 12V</text>
          <text id="txt-sub-dc" x="52" y="38" fill="#94a3b8" font-family="'SF Pro Display', sans-serif" font-size="11" font-weight="600">APAGADO</text>
        </g>

        <!-- 3. USB CONTROL SWITCH -->
        <g id="btn-ctrl-usb" class="interactive-btn" transform="translate(585, 318)">
          <rect id="bg-ctrl-usb" x="0" y="0" width="240" height="50" rx="10" fill="rgba(255, 255, 255, 0.04)" stroke="#475569" stroke-width="1.8" />
          <!-- USB Port Icon -->
          <rect id="ico-rect-usb" x="14" y="17" width="28" height="16" rx="3.5" fill="none" stroke="#94a3b8" stroke-width="1.8" />
          <rect id="ico-pin-usb" x="20" y="21" width="16" height="8" rx="1.5" fill="#94a3b8" />
          <!-- Text -->
          <text x="52" y="24" fill="#f8fafc" font-family="'SF Pro Display', sans-serif" font-size="13" font-weight="800">PUERTOS USB</text>
          <text id="txt-sub-usb" x="52" y="38" fill="#94a3b8" font-family="'SF Pro Display', sans-serif" font-size="11" font-weight="600">APAGADO</text>
        </g>
      </svg>
    `;

    this._attachEvents();
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

    // Safe Switch Handlers (AC, DC, USB)
    const btnAc = this.shadowRoot.getElementById("btn-ctrl-ac");
    if (btnAc) btnAc.addEventListener("click", () => this._handleSafeSwitchClick("ac", "switch_ac"));

    const btnDc = this.shadowRoot.getElementById("btn-ctrl-dc");
    if (btnDc) btnDc.addEventListener("click", () => this._handleSafeSwitchClick("dc", "switch_dc"));

    const btnUsb = this.shadowRoot.getElementById("btn-ctrl-usb");
    if (btnUsb) btnUsb.addEventListener("click", () => this._handleSafeSwitchClick("usb", "switch_usb"));
  }

  // Safety confirmation logic: If ON, requires a 2nd confirmation click within 4s to turn off!
  _handleSafeSwitchClick(switchKey, entityKey) {
    const entityId = this._mapped[entityKey];
    if (!entityId || !this._hass) return;

    const stateObj = this._hass.states[entityId];
    const isCurrentlyOn = stateObj && stateObj.state === "on";

    if (!isCurrentlyOn) {
      // Turning ON does not cut active power, allow direct single-click
      this._confirmTimers[switchKey] = null;
      this._hass.callService("switch", "turn_on", { entity_id: entityId });
      this._updateSwitchButtonVisual(switchKey, true, "ENCENDIENDO...", false);
      return;
    }

    // Switch is ON: Check if confirmation is already pending
    const now = Date.now();
    const expiry = this._confirmTimers[switchKey];

    if (expiry && now < expiry) {
      // 2ND CONFIRMATION CLICK: Safely execute turn-off!
      this._confirmTimers[switchKey] = null;
      this._hass.callService("switch", "turn_off", { entity_id: entityId });
      this._updateSwitchButtonVisual(switchKey, false, "APAGANDO...", false);
    } else {
      // 1ST CLICK: Activate 4-second confirmation state!
      this._confirmTimers[switchKey] = now + 4000;
      this._updateSwitchButtonVisual(switchKey, true, "⚠️ ¿APAGAR? (PULSA DE NUEVO)", true);
    }
  }

  _checkConfirmTimeouts() {
    const now = Date.now();
    ["ac", "dc", "usb"].forEach((key) => {
      const expiry = this._confirmTimers[key];
      if (expiry) {
        if (now >= expiry) {
          // Timed out: safety cancel
          this._confirmTimers[key] = null;
          this._updateState();
        } else {
          // Still pending: update seconds remaining
          const secs = Math.ceil((expiry - now) / 1000);
          this._updateSwitchButtonVisual(key, true, `⚠️ ¿APAGAR? (${secs}s)`, true);
        }
      }
    });
  }

  _updateSwitchButtonVisual(key, isOn, subText, isWarning = false) {
    const bg = this.shadowRoot.getElementById(`bg-ctrl-${key}`);
    const sub = this.shadowRoot.getElementById(`txt-sub-${key}`);
    if (!bg || !sub) return;

    sub.textContent = subText;

    if (isWarning) {
      bg.setAttribute("fill", "rgba(239, 68, 68, 0.22)");
      bg.setAttribute("stroke", "#ef4444");
      bg.classList.add("confirm-pulsing");
      sub.setAttribute("fill", "#ef4444");
    } else if (isOn) {
      bg.setAttribute("fill", "url(#btn-active-grad)");
      bg.setAttribute("stroke", "#00e5ff");
      bg.classList.remove("confirm-pulsing");
      sub.setAttribute("fill", "#00e5ff");
    } else {
      bg.setAttribute("fill", "rgba(255, 255, 255, 0.04)");
      bg.setAttribute("stroke", "#475569");
      bg.classList.remove("confirm-pulsing");
      sub.setAttribute("fill", "#94a3b8");
    }

    // Update icons
    if (key === "ac") {
      const circ = this.shadowRoot.getElementById("ico-circle-ac");
      const wave = this.shadowRoot.getElementById("ico-wave-ac");
      const c = isWarning ? "#ef4444" : isOn ? "#00e5ff" : "#94a3b8";
      if (circ) circ.setAttribute("stroke", c);
      if (wave) wave.setAttribute("stroke", c);
    } else if (key === "dc") {
      const circ = this.shadowRoot.getElementById("ico-circle-dc");
      const txt = this.shadowRoot.getElementById("ico-txt-dc");
      const c = isWarning ? "#ef4444" : isOn ? "#00e5ff" : "#94a3b8";
      if (circ) circ.setAttribute("stroke", c);
      if (txt) txt.setAttribute("fill", c);
    } else if (key === "usb") {
      const rect = this.shadowRoot.getElementById("ico-rect-usb");
      const pin = this.shadowRoot.getElementById("ico-pin-usb");
      const c = isWarning ? "#ef4444" : isOn ? "#00e5ff" : "#94a3b8";
      if (rect) rect.setAttribute("stroke", c);
      if (pin) pin.setAttribute("fill", c);
    }
  }

  _set7SegmentDigit(prefix, char) {
    const active = SEG_MAP[char] || [];
    const litColor = "#00e5ff";
    const dimColor = "rgba(0, 229, 255, 0.05)";
    const segs = ["a", "b", "c", "d", "e", "f", "g"];
    for (let i = 0; i < 7; i++) {
      const s = segs[i];
      const el = this.shadowRoot.getElementById(`${prefix}-${s}`);
      if (el) {
        const isLit = active.includes(s);
        el.setAttribute("fill", isLit ? litColor : dimColor);
        if (isLit) {
          el.setAttribute("filter", "url(#lcd-cyan-glow)");
        } else {
          el.removeAttribute("filter");
        }
      }
    }
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

    const isSwOn = (key) => {
      const id = this._mapped[key];
      return id && this._hass.states[id] && this._hass.states[id].state === "on";
    };

    const batteryPct = Math.round(getNum("battery", 0));
    const inputW = Math.round(getNum("input_power", 0));
    const outputW = Math.round(getNum("output_power", 0));
    const acInW = Math.round(getNum("ac_input", 0));
    const acVolts = Math.round(getNum("ac_voltage", 230));

    // Smart Remaining Time calculation
    let remMinutes = 0;
    if (inputW > 15) {
      remMinutes = Math.round(getNum("remaining_charge", 0));
      if (remMinutes <= 0) remMinutes = Math.round(getNum("remaining_time", 0));
      if (remMinutes <= 0 && batteryPct < 100) {
        const netW = Math.max(10, inputW - outputW);
        const neededWh = ((100 - batteryPct) / 100) * 2048;
        remMinutes = Math.round((neededWh / netW) * 60);
      }
    } else if (outputW > 15) {
      remMinutes = Math.round(getNum("remaining_discharge", 0));
      if (remMinutes <= 0) remMinutes = Math.round(getNum("remaining_time", 0));
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

    const isAcOn = isSwOn("switch_ac");
    const isDcOn = isSwOn("switch_dc");
    const isUsbOn = isSwOn("switch_usb");

    // 1. LEFT: 7-Segment Remaining Time
    const remUnitTxt = this.shadowRoot.getElementById("rem-unit-txt");
    let remStr = "--";
    if (remMinutes > 0) {
      if (remMinutes >= 60) {
        const hrs = Math.floor(remMinutes / 60);
        remStr = String(Math.min(99, hrs)).padStart(2, "0");
        if (remUnitTxt) remUnitTxt.textContent = "Hours";
      } else {
        remStr = String(Math.min(99, remMinutes)).padStart(2, "0");
        if (remUnitTxt) remUnitTxt.textContent = "Mins";
      }
    } else {
      remStr = "--";
      if (remUnitTxt) remUnitTxt.textContent = "Mins";
    }

    this._set7SegmentDigit("rem_d0", remStr[0] || "-");
    this._set7SegmentDigit("rem_d1", remStr[1] || "-");

    // 2. CENTER: Curved Arc Blocks & Battery %
    const totalBlocks = 18;
    const activeBlocks = Math.round((Math.min(100, Math.max(0, batteryPct)) / 100) * totalBlocks);
    for (let i = 0; i < totalBlocks; i++) {
      const blk = this.shadowRoot.getElementById(`gauge-block-${i}`);
      if (blk) {
        if (i < activeBlocks) {
          blk.setAttribute("fill", "#00e5ff");
          blk.setAttribute("filter", "url(#lcd-cyan-glow)");
        } else {
          blk.setAttribute("fill", "rgba(0, 229, 255, 0.08)");
          blk.removeAttribute("filter");
        }
      }
    }

    // Battery % Digits
    const pctStr = String(Math.min(100, Math.max(0, batteryPct))).padStart(2, " ");
    this._set7SegmentDigit("pct_d0", pctStr[pctStr.length - 2] || " ");
    this._set7SegmentDigit("pct_d1", pctStr[pctStr.length - 1] || "0");

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

    // 3. RIGHT: UPS Badge, Input Watts, Output Watts & Voltage
    const upsBadge = this.shadowRoot.getElementById("ups-badge-grp");
    if (upsBadge) {
      // Lit when AC power is actively feeding through
      upsBadge.style.opacity = isAcConnected && (isCharging || outputW > 0) ? "1" : "0.15";
    }

    // Input Watts (4 Digits)
    const pad4 = (n) => String(Math.min(9999, Math.max(0, n))).padStart(4, "0");
    const inStr = pad4(inputW);
    this._set7SegmentDigit("in_d0", inStr[0]);
    this._set7SegmentDigit("in_d1", inStr[1]);
    this._set7SegmentDigit("in_d2", inStr[2]);
    this._set7SegmentDigit("in_d3", inStr[3]);

    // Output Watts (4 Digits)
    const outStr = pad4(outputW);
    this._set7SegmentDigit("out_d0", outStr[0]);
    this._set7SegmentDigit("out_d1", outStr[1]);
    this._set7SegmentDigit("out_d2", outStr[2]);
    this._set7SegmentDigit("out_d3", outStr[3]);

    // Voltage Digits (3 Digits)
    const pad3 = (n) => String(Math.min(999, Math.max(0, n))).padStart(3, "0");
    const voltStr = isAcOn ? pad3(acVolts > 0 ? acVolts : 230) : "000";
    this._set7SegmentDigit("volt_d0", voltStr[0]);
    this._set7SegmentDigit("volt_d1", voltStr[1]);
    this._set7SegmentDigit("volt_d2", voltStr[2]);

    // Right LCD Symbols: AC, USB, DC
    const acSymbol = this.shadowRoot.getElementById("ac-lcd-symbol");
    if (acSymbol) acSymbol.style.opacity = isAcOn ? "1" : "0.15";

    const usbSymbol = this.shadowRoot.getElementById("usb-lcd-symbol");
    if (usbSymbol) usbSymbol.style.opacity = isUsbOn ? "1" : "0.15";

    const dcSymbol = this.shadowRoot.getElementById("dc-lcd-symbol");
    if (dcSymbol) dcSymbol.style.opacity = isDcOn ? "1" : "0.15";

    // IoT LED
    const iotLed = this.shadowRoot.getElementById("iot-led-circle");
    if (iotLed) {
      const mode = getStr("connection_mode", "LAN");
      iotLed.setAttribute("fill", mode.includes("LAN") || mode.includes("Cloud") ? "#00e5ff" : "#475569");
    }

    // 4. EXTERIOR CONTROL DOCK BUTTONS (Respect pending safety confirmations)
    if (!this._confirmTimers.ac) {
      this._updateSwitchButtonVisual("ac", isAcOn, isAcOn ? "ACTIVO • 230V" : "APAGADO", false);
    }
    if (!this._confirmTimers.dc) {
      this._updateSwitchButtonVisual("dc", isDcOn, isDcOn ? "ACTIVO • 12V" : "APAGADO", false);
    }
    if (!this._confirmTimers.usb) {
      this._updateSwitchButtonVisual("usb", isUsbOn, isUsbOn ? "ACTIVO" : "APAGADO", false);
    }
  }
}

/* ==========================================================================
   2. OUKITEL CARD (Complete Control & Financial Metrics Card)
   ========================================================================== */
class OukitelCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._config = {};
    this._mapped = {};
    this._confirmTimers = { ac: null, dc: null, usb: null };
    this._intervalId = null;
  }

  connectedCallback() {
    this._intervalId = setInterval(() => {
      this._checkConfirmTimeouts();
    }, 500);
  }

  disconnectedCallback() {
    if (this._intervalId) clearInterval(this._intervalId);
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
          background: rgba(0, 229, 255, 0.12);
          border-color: #00e5ff;
          box-shadow: 0 0 14px rgba(0, 229, 255, 0.35);
        }
        .switch-btn.warning {
          background: rgba(239, 68, 68, 0.2) !important;
          border-color: #ef4444 !important;
          box-shadow: 0 0 14px rgba(239, 68, 68, 0.4) !important;
          animation: pulseBtn 0.9s infinite ease-in-out;
        }
        @keyframes pulseBtn {
          0% { transform: scale(1); }
          50% { transform: scale(0.98); }
          100% { transform: scale(1); }
        }
        .btn-icon {
          width: 24px;
          height: 24px;
          fill: #94a3b8;
          transition: fill 0.2s ease, filter 0.2s ease;
        }
        .switch-btn.active .btn-icon {
          fill: #00e5ff;
          filter: drop-shadow(0 0 6px #00e5ff);
        }
        .switch-btn.warning .btn-icon {
          fill: #ef4444;
          filter: drop-shadow(0 0 6px #ef4444);
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
          text-align: center;
        }
        .switch-btn.warning .btn-sub {
          color: #ef4444;
          font-weight: 700;
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
          <div class="section-title">Salidas de Energía (Confirmación Segura)</div>
          <div class="switches-grid">
            <!-- AC Switch -->
            <div class="switch-btn" id="btn-sw-ac">
              <svg class="btn-icon" viewBox="0 0 24 24">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 14h-2v-4h2v4zm0-6h-2V7h2v3z"/>
              </svg>
              <div class="btn-label">AC 230V</div>
              <div class="btn-sub" id="sub-ac">OFF</div>
            </div>

            <!-- DC 12V Switch -->
            <div class="switch-btn" id="btn-sw-dc">
              <svg class="btn-icon" viewBox="0 0 24 24">
                <path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55 1 .45 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z"/>
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
    const handleSafeClick = (key, entityKey) => {
      const entityId = this._mapped[entityKey];
      if (!entityId || !this._hass) return;

      const stateObj = this._hass.states[entityId];
      const isCurrentlyOn = stateObj && stateObj.state === "on";

      if (!isCurrentlyOn) {
        this._confirmTimers[key] = null;
        this._hass.callService("switch", "turn_on", { entity_id: entityId });
        return;
      }

      const now = Date.now();
      const expiry = this._confirmTimers[key];
      if (expiry && now < expiry) {
        this._confirmTimers[key] = null;
        this._hass.callService("switch", "turn_off", { entity_id: entityId });
      } else {
        this._confirmTimers[key] = now + 4000;
        this._updateState();
      }
    };

    const btnAc = this.shadowRoot.getElementById("btn-sw-ac");
    if (btnAc) btnAc.addEventListener("click", () => handleSafeClick("ac", "switch_ac"));

    const btnDc = this.shadowRoot.getElementById("btn-sw-dc");
    if (btnDc) btnDc.addEventListener("click", () => handleSafeClick("dc", "switch_dc"));

    const btnUsb = this.shadowRoot.getElementById("btn-sw-usb");
    if (btnUsb) btnUsb.addEventListener("click", () => handleSafeClick("usb", "switch_usb"));
  }

  _checkConfirmTimeouts() {
    const now = Date.now();
    let needsUpdate = false;
    ["ac", "dc", "usb"].forEach((key) => {
      if (this._confirmTimers[key]) {
        if (now >= this._confirmTimers[key]) {
          this._confirmTimers[key] = null;
          needsUpdate = true;
        } else {
          needsUpdate = true;
        }
      }
    });
    if (needsUpdate) this._updateState();
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

    const now = Date.now();
    const updateBtn = (btnId, subId, timerKey, isOn, labelOn = "ON") => {
      const btn = this.shadowRoot.getElementById(btnId);
      const sub = this.shadowRoot.getElementById(subId);
      if (!btn || !sub) return;

      const expiry = this._confirmTimers[timerKey];
      if (expiry && now < expiry) {
        const secs = Math.ceil((expiry - now) / 1000);
        btn.classList.add("warning");
        btn.classList.remove("active");
        sub.textContent = `⚠️ ¿APAGAR? (${secs}s)`;
      } else {
        btn.classList.remove("warning");
        btn.classList.toggle("active", isOn);
        sub.textContent = isOn ? labelOn : "OFF";
      }
    };

    updateBtn("btn-sw-ac", "sub-ac", "ac", isSwOn("switch_ac"), "230V ACTIVO");
    updateBtn("btn-sw-dc", "sub-dc", "dc", isSwOn("switch_dc"), "12V ACTIVO");
    updateBtn("btn-sw-usb", "sub-usb", "usb", isSwOn("switch_usb"), "ACTIVO");

    // Financials
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
    description: "Authentic vector simulation of the physical Oukitel LCD screen with tactile safety control dock.",
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

/**
 * Oukitel Power Station Lovelace Cards (v1.5.2)
 * 1. oukitel-display-card: 100% Authentic Vector SVG Simulation of the physical Oukitel LCD screen.
 * 2. oukitel-card: Full control card with tactile switches and financial metrics.
 * 
 * Developer: VictorCV-DAM (ha-oukitel)
 */

const CARD_VERSION = "1.5.2";

console.info(
  `%c OUKITEL POWER STATION DISPLAY %c v${CARD_VERSION} `,
  "color: #ffffff; background: #0284c7; font-weight: 700; border-radius: 3px 0 0 3px;",
  "color: #0284c7; background: #0f172a; font-weight: 700; border-radius: 0 3px 3px 0;"
);

// 7-Segment SVG Map
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
function render7Segment(char, x, y, scale = 1, skew = -6) {
  const activeSegs = SEG_MAP[char] || [];
  const litColor = "#2be4ff";
  const dimColor = "rgba(43, 228, 255, 0.07)";

  // Standard segment paths at width 28, height 50
  const segs = {
    a: "M 3 0 L 25 0 L 21 4.5 L 7 4.5 Z",
    b: "M 27 2.5 L 27 22 L 22.5 19.5 L 22.5 6 Z",
    c: "M 27 27.5 L 27 47 L 22.5 43.5 L 22.5 30 Z",
    d: "M 7 45.5 L 21 45.5 L 25 50 L 3 50 Z",
    e: "M 1 27.5 L 5.5 30 L 5.5 43.5 L 1 47 Z",
    f: "M 1 2.5 L 5.5 6 L 5.5 19.5 L 1 22 Z",
    g: "M 5 23 L 23 23 L 25 25 L 23 27 L 5 27 L 3 25 Z",
  };

  let paths = "";
  for (const [key, d] of Object.entries(segs)) {
    const isLit = activeSegs.includes(key);
    const fill = isLit ? litColor : dimColor;
    const filter = isLit ? 'filter="url(#lcd-cyan-glow)"' : "";
    paths += `<path d="${d}" fill="${fill}" ${filter} />`;
  }

  return `
    <g transform="translate(${x}, ${y}) scale(${scale}) skewX(${skew})">
      ${paths}
    </g>
  `;
}

// Auto-discovery helper
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

    config.input_power = config.input_power || findEntity("sensor", ["total_input_power", "input_power"]);
    config.output_power = config.output_power || findEntity("sensor", ["total_output_power", "output_power"]);
    config.ac_input = config.ac_input || findEntity("sensor", ["ac_input_power", "ac_input"]);
    config.dc_input = config.dc_input || findEntity("sensor", ["dc_solar_input_power", "dc_input"]);
    config.ac_output_power = config.ac_output_power || findEntity("sensor", ["ac_output_power"]);

    // Remaining time: prioritize charge/discharge specific, then generic
    config.remaining_charge = config.remaining_charge || findEntity("sensor", ["remaining_charge_time"]);
    config.remaining_discharge = config.remaining_discharge || findEntity("sensor", ["remaining_discharge_time"]);
    config.remaining_time = config.remaining_time || findEntity("sensor", ["remaining_time"]);

    config.switch_ac = config.switch_ac || findEntity("switch", ["ac_output", "ac_switch"]);
    config.switch_dc = config.switch_dc || findEntity("switch", ["dc_12v_output", "dc_output", "dc_switch"]);
    config.switch_usb = config.switch_usb || findEntity("switch", ["usb_output", "usb_switch"]);

    config.frequency = config.frequency || findEntity("select", ["output_frequency"]);
    config.inverter_temp = config.inverter_temp || findEntity("sensor", ["inverter_temperature", "inverter_temp"]);
    config.battery_temp = config.battery_temp || findEntity("sensor", ["_temperature", "temperature"]);
    config.connection_mode = config.connection_mode || findEntity("sensor", ["connection_mode"]);
    config.fault_status = config.fault_status || findEntity("sensor", ["hardware_fault_status", "fault_status"]);

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
          filter: drop-shadow(0 12px 28px rgba(0, 0, 0, 0.65));
        }

        .interactive-btn {
          cursor: pointer;
          transition: transform 0.15s ease, filter 0.2s ease;
        }
        .interactive-btn:hover {
          filter: brightness(1.2);
        }
        .interactive-btn:active {
          transform: scale(0.96);
          transform-origin: center;
        }

        @keyframes fanSpin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .fan-blade {
          transform-origin: 368px 78px;
        }
        .fan-spinning {
          animation: fanSpin 1s linear infinite;
        }
      </style>

      <svg class="svg-container" viewBox="0 0 880 330" preserveAspectRatio="xMidYMid meet" id="screen-svg">
        <defs>
          <!-- Glowing Filter for Cyan Segments -->
          <filter id="lcd-cyan-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          <!-- Glowing Filter for Green Elements -->
          <filter id="lcd-green-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          <!-- Chassis Metallic Gradient -->
          <linearGradient id="chassis-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#2c3038" />
            <stop offset="25%" stop-color="#1e2128" />
            <stop offset="100%" stop-color="#121418" />
          </linearGradient>

          <!-- Screen Glass Subtle Reflection -->
          <linearGradient id="glass-reflection" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="rgba(255, 255, 255, 0.05)" />
            <stop offset="40%" stop-color="rgba(255, 255, 255, 0)" />
          </linearGradient>
        </defs>

        <!-- CHASSIS OUTER BEZEL -->
        <rect x="2" y="2" width="876" height="326" rx="22" fill="url(#chassis-grad)" stroke="#383c46" stroke-width="2" />
        
        <!-- INNER LCD RECESS FRAME -->
        <rect x="26" y="22" width="828" height="236" rx="14" fill="#04060a" stroke="#000000" stroke-width="3" />
        <rect x="26" y="22" width="828" height="236" rx="14" fill="url(#glass-reflection)" pointer-events="none" />

        <!-- ==========================================
             LEFT SECTION: REMAINING TIME
             ========================================== -->
        <g id="grp-left" class="interactive-btn">
          <text x="68" y="68" fill="#2be4ff" font-family="'SF Pro Display', -apple-system, sans-serif" font-size="13" font-weight="800" letter-spacing="2" filter="url(#lcd-cyan-glow)">REMAINING</text>
          
          <!-- 7-Segment Digits Container (Two Digits) -->
          <g id="rem-digits-svg"></g>

          <!-- Mins / Hours label -->
          <text x="202" y="146" id="rem-unit-txt" fill="#2be4ff" font-family="'SF Pro Display', sans-serif" font-size="16" font-weight="800" filter="url(#lcd-cyan-glow)">Mins</text>

          <!-- Circular Status Icons Underneath -->
          <circle cx="86" cy="186" r="14" fill="none" stroke="#2be4ff" stroke-width="2" opacity="0.8" filter="url(#lcd-cyan-glow)" />
          <!-- Checkmark / Thermometer Icon inside -->
          <path d="M 80 186 L 84 190 L 92 182" fill="none" stroke="#2be4ff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />

          <circle cx="126" cy="186" r="14" fill="none" stroke="#2be4ff" stroke-width="2" opacity="0.8" filter="url(#lcd-cyan-glow)" />
          <!-- Lightning / Power Icon inside -->
          <path d="M 126 178 L 122 186 L 126 186 L 124 194 L 130 184 L 126 184 Z" fill="#2be4ff" />
        </g>

        <!-- ==========================================
             CENTER SECTION: CIRCULAR BATTERY GAUGE
             ========================================== -->
        <g id="grp-center" class="interactive-btn">
          <!-- Fan Icon (Top-Left of Gauge, animated) -->
          <g id="fan-group" class="fan-blade">
            <circle cx="368" cy="78" r="3" fill="#2be4ff" />
            <path d="M 368 78 C 374 72 376 65 373 63 C 370 61 366 68 368 78 Z" fill="#2be4ff" filter="url(#lcd-cyan-glow)" />
            <path d="M 368 78 C 374 84 381 86 383 83 C 385 80 378 76 368 78 Z" fill="#2be4ff" filter="url(#lcd-cyan-glow)" />
            <path d="M 368 78 C 362 84 360 91 363 93 C 366 95 370 88 368 78 Z" fill="#2be4ff" filter="url(#lcd-cyan-glow)" />
            <path d="M 368 78 C 362 72 355 70 353 73 C 351 76 358 80 368 78 Z" fill="#2be4ff" filter="url(#lcd-cyan-glow)" />
          </g>

          <!-- Outer Bracket Arcs ( ) -->
          <path d="M 358 88 A 82 82 0 0 0 358 192" fill="none" stroke="#2be4ff" stroke-width="2.2" opacity="0.6" filter="url(#lcd-cyan-glow)" />
          <path d="M 522 88 A 82 82 0 0 1 522 192" fill="none" stroke="#2be4ff" stroke-width="2.2" opacity="0.6" filter="url(#lcd-cyan-glow)" />

          <!-- Radial Ticks Container (28 Notches) -->
          <g id="gauge-ticks"></g>

          <!-- Center Percentage Digits (Two 7-segment digits + %) -->
          <g id="pct-digits-svg"></g>
          <text x="472" y="132" fill="#ffffff" font-family="'SF Pro Display', sans-serif" font-size="20" font-weight="900" filter="url(#lcd-cyan-glow)">%</text>

          <!-- Green Battery Icon -->
          <g transform="translate(410, 150)">
            <rect x="0" y="0" width="56" height="24" rx="4" fill="none" stroke="#22c55e" stroke-width="2.2" filter="url(#lcd-green-glow)" />
            <path d="M 58 6 Q 62 6 62 12 Q 62 18 58 18 Z" fill="#22c55e" filter="url(#lcd-green-glow)" />
            <!-- Dynamic Battery Fill Level -->
            <rect id="batt-fill-rect" x="3" y="3" width="40" height="18" rx="2" fill="#22c55e" opacity="0.5" />
            <!-- Centered Lightning Bolt -->
            <path d="M 29 4 L 21 13 L 28 13 L 25 20 L 35 10 L 28 10 Z" fill="#ffffff" filter="drop-shadow(0 0 4px #22c55e)" />
          </g>

          <!-- Status Text Under Battery (Supercharge / Charging / etc.) -->
          <text x="440" y="196" id="status-mode-txt" text-anchor="middle" fill="#22c55e" font-family="'SF Pro Display', sans-serif" font-size="11" font-weight="900" letter-spacing="1.5" filter="url(#lcd-green-glow)">SUPERCHARGE</text>

          <!-- Green AC Plug Badge -->
          <g id="plug-badge-grp" transform="translate(430, 206)">
            <circle cx="10" cy="10" r="10" fill="none" stroke="#22c55e" stroke-width="1.8" filter="url(#lcd-green-glow)" />
            <path d="M 7 5 L 7 8 M 13 5 L 13 8 M 6 8 L 14 8 L 14 12 C 14 14.5 12 16 10 16 C 8 16 6 14.5 6 12 Z M 10 16 L 10 19" fill="none" stroke="#22c55e" stroke-width="1.6" stroke-linecap="round" />
          </g>
        </g>

        <!-- ==========================================
             RIGHT SECTION: INPUT / OUTPUT WATTS
             ========================================== -->
        <g id="grp-right" class="interactive-btn">
          <!-- TOP ROW: INPUT WATTS -->
          <g id="input-digits-svg"></g>
          <text x="770" y="82" fill="#2be4ff" font-family="'SF Pro Display', sans-serif" font-size="14" font-weight="900" letter-spacing="1.5" filter="url(#lcd-cyan-glow)">INPUT</text>
          <text x="770" y="98" fill="#8ecae6" font-family="'SF Pro Display', sans-serif" font-size="10" font-weight="700" letter-spacing="0.5">Watts</text>

          <!-- BOTTOM ROW: OUTPUT WATTS -->
          <g id="output-digits-svg"></g>
          <text x="770" y="148" id="txt-freq" fill="#2be4ff" font-family="'SF Pro Display', sans-serif" font-size="11" font-weight="800" filter="url(#lcd-cyan-glow)">50 Hz</text>
          <text x="770" y="164" fill="#2be4ff" font-family="'SF Pro Display', sans-serif" font-size="14" font-weight="900" letter-spacing="1.5" filter="url(#lcd-cyan-glow)">OUTPUT</text>
          <text x="770" y="180" fill="#8ecae6" font-family="'SF Pro Display', sans-serif" font-size="10" font-weight="700" letter-spacing="0.5">Watts</text>
        </g>

        <!-- ==========================================
             BEZEL FOOTER: BRAND & POWER BUTTON
             ========================================== -->
        <!-- OUKITEL Silver Logo Centered -->
        <text x="440" y="300" text-anchor="middle" fill="#d1d5db" font-family="'SF Pro Display', -apple-system, sans-serif" font-size="22" font-weight="900" letter-spacing="8" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.8))">OUKITEL</text>

        <!-- Power Button & IOT LED on Right -->
        <g id="power-button-grp" class="interactive-btn" transform="translate(735, 276)">
          <text x="14" y="14" fill="#94a3b8" font-family="'SF Pro Display', sans-serif" font-size="9" font-weight="800" letter-spacing="1">POWER</text>
          <circle cx="4" cy="25" r="3.5" id="iot-led-circle" fill="#2be4ff" filter="url(#lcd-cyan-glow)" />
          <text x="14" y="28" fill="#94a3b8" font-family="'SF Pro Display', sans-serif" font-size="9" font-weight="800" letter-spacing="1">IOT</text>

          <!-- Circular Button -->
          <circle cx="68" cy="20" r="18" fill="radial-gradient(circle, #2a2e36 0%, #15171c 100%)" stroke="#475569" stroke-width="2" />
          <circle cx="68" cy="20" r="13" fill="none" stroke="#2be4ff" stroke-width="1.8" filter="url(#lcd-cyan-glow)" />
          <path d="M 68 12 L 68 18 M 64 14 A 6 6 0 1 0 72 14" fill="none" stroke="#2be4ff" stroke-width="2" stroke-linecap="round" />
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
    const cy = 142;
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
              stroke="rgba(43, 228, 255, 0.12)" stroke-width="3.2" stroke-linecap="round" />
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

    // Smart Remaining Time: charge vs discharge vs generic
    let remMinutes = 0;
    if (inputW > 15) {
      remMinutes = Math.round(getNum("remaining_charge", getNum("remaining_time", 0)));
    } else if (outputW > 15) {
      remMinutes = Math.round(getNum("remaining_discharge", getNum("remaining_time", 0)));
    } else {
      remMinutes = Math.round(getNum("remaining_time", 0));
    }

    const isAcConnected = acInW > 10 || (inputW > 10 && acInW >= 0);
    const isCharging = inputW > 15;
    const isDischarging = outputW > 15 && !isCharging;
    const isSupercharge = inputW >= 800;
    const isFanActive = outputW > 250 || inputW > 450 || getNum("inverter_temp", 25) > 40;

    // 1. LEFT: 7-Segment Remaining Time
    const remSvgContainer = this.shadowRoot.getElementById("rem-digits-svg");
    const remUnitTxt = this.shadowRoot.getElementById("rem-unit-txt");
    if (remSvgContainer && remUnitTxt) {
      let remStr = "--";
      if (remMinutes > 0) {
        if (remMinutes >= 60) {
          const hrs = Math.floor(remMinutes / 60);
          remStr = String(hrs).padStart(2, "0");
          remUnitTxt.textContent = "Hours";
        } else {
          remStr = String(remMinutes).padStart(2, "0");
          remUnitTxt.textContent = "Mins";
        }
      } else {
        remStr = "--";
        remUnitTxt.textContent = "Mins";
      }

      remSvgContainer.innerHTML =
        render7Segment(remStr[0] || "-", 72, 86, 1.25) +
        render7Segment(remStr[1] || "-", 120, 86, 1.25);
    }

    // 2. CENTER: Radial Ticks & 7-Segment Battery Percentage
    const totalTicks = 28;
    const activeTicks = Math.round((Math.min(100, Math.max(0, batteryPct)) / 100) * totalTicks);
    for (let i = 0; i < totalTicks; i++) {
      const tick = this.shadowRoot.getElementById(`tick-${i}`);
      if (tick) {
        if (i < activeTicks) {
          tick.setAttribute("stroke", "#2be4ff");
          tick.setAttribute("filter", "url(#lcd-cyan-glow)");
        } else {
          tick.setAttribute("stroke", "rgba(43, 228, 255, 0.12)");
          tick.removeAttribute("filter");
        }
      }
    }

    // Center Percentage 7-Segment Digits
    const pctSvgContainer = this.shadowRoot.getElementById("pct-digits-svg");
    if (pctSvgContainer) {
      const pctStr = String(Math.min(100, Math.max(0, batteryPct))).padStart(2, " ");
      pctSvgContainer.innerHTML =
        render7Segment(pctStr[pctStr.length - 2] || " ", 398, 92, 0.95) +
        render7Segment(pctStr[pctStr.length - 1] || "0", 432, 92, 0.95);
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
        modeTxt.setAttribute("fill", "#22c55e");
      } else if (isCharging) {
        modeTxt.textContent = "CHARGING";
        modeTxt.setAttribute("fill", "#22c55e");
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

    // 3. RIGHT: 7-Segment Input & Output Watts
    const pad4 = (n) => String(Math.min(9999, Math.max(0, n))).padStart(4, "0");
    const inStr = pad4(inputW);
    const inContainer = this.shadowRoot.getElementById("input-digits-svg");
    if (inContainer) {
      inContainer.innerHTML =
        render7Segment(inStr[0], 610, 60, 0.82) +
        render7Segment(inStr[1], 646, 60, 0.82) +
        render7Segment(inStr[2], 682, 60, 0.82) +
        render7Segment(inStr[3], 718, 60, 0.82);
    }

    const outStr = pad4(outputW);
    const outContainer = this.shadowRoot.getElementById("output-digits-svg");
    if (outContainer) {
      outContainer.innerHTML =
        render7Segment(outStr[0], 610, 142, 0.82) +
        render7Segment(outStr[1], 646, 142, 0.82) +
        render7Segment(outStr[2], 682, 142, 0.82) +
        render7Segment(outStr[3], 718, 142, 0.82);
    }

    const freqTxt = this.shadowRoot.getElementById("txt-freq");
    if (freqTxt) {
      freqTxt.textContent = freqStr.includes("60") ? "60 Hz" : "50 Hz";
    }

    // IOT LED
    const iotLed = this.shadowRoot.getElementById("iot-led-circle");
    if (iotLed) {
      const mode = getStr("connection_mode", "LAN");
      iotLed.setAttribute("fill", mode.includes("LAN") || mode.includes("Cloud") ? "#2be4ff" : "#475569");
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
          background: rgba(43, 228, 255, 0.12);
          border-color: #2be4ff;
          box-shadow: 0 0 14px rgba(43, 228, 255, 0.35);
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
          fill: #2be4ff;
          filter: drop-shadow(0 0 6px #2be4ff);
        }
        .btn-label {
          font-size: 12px;
          font-weight: 700;
          color: #e2e8f0;
        }
        .btn-state {
          font-size: 10px;
          font-weight: 700;
          letter-spacing: 0.8px;
          color: #64748b;
          text-transform: uppercase;
        }
        .switch-btn.active .btn-state {
          color: #22c55e;
        }
        .switch-btn.active.ac .btn-state {
          color: #2be4ff;
        }

        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 10px;
          margin-top: 6px;
        }
        .metric-card {
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 12px;
          padding: 10px 8px;
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
        }
        .metric-label {
          font-size: 10px;
          font-weight: 600;
          color: #94a3b8;
          margin-bottom: 2px;
        }
        .metric-value {
          font-size: 15px;
          font-weight: 800;
          color: #f8fafc;
        }
        .metric-value.cost { color: #f87171; }
        .metric-value.savings { color: #4ade80; }
        .metric-value.net { color: #38bdf8; }

        .footer-badges {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 6px 2px 6px;
          font-size: 10px;
          font-weight: 600;
          color: #64748b;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
          margin-top: 12px;
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
          background: #4ade80;
        }
      </style>

      <ha-card>
        <!-- SCREEN SIMULATION (Optional) -->
        ${this._config.show_screen ? '<oukitel-display-card id="inner-display" style="margin-bottom: 12px;"></oukitel-display-card>' : ''}

        <!-- TACTILE OUTPUT SWITCHES -->
        <div class="section-title">Control de Salidas</div>
        <div class="switches-grid">
          <div class="switch-btn ac" id="btn-sw-ac">
            <svg class="btn-icon" viewBox="0 0 24 24">
              <path d="M7 2V11H10V22L17 10H14L17 2H7Z"/>
            </svg>
            <span class="btn-label">Toma AC</span>
            <span class="btn-state" id="st-sw-ac">OFF</span>
          </div>

          <div class="switch-btn" id="btn-sw-dc">
            <svg class="btn-icon" viewBox="0 0 24 24">
              <path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5H6.5C5.84 5 5.28 5.42 5.08 6.01L3 12V20C3 20.55 3.45 21 4 21H5C5.55 21 6 20.55 6 20V19H18V20C18 20.55 18.45 21 19 21H20C20.55 21 21 20.55 21 20V12L18.92 6.01M6.5 6.5H17.5L18.83 10.5H5.17L6.5 6.5M6.5 13C7.33 13 8 13.67 8 14.5S7.33 16 6.5 16 5 15.33 5 14.5 5.67 13 6.5 13M17.5 13C18.33 13 19 13.67 19 14.5S18.33 16 17.5 16 16 15.33 16 14.5 16.67 13 17.5 13Z"/>
            </svg>
            <span class="btn-label">Salida DC</span>
            <span class="btn-state" id="st-sw-dc">OFF</span>
          </div>

          <div class="switch-btn" id="btn-sw-usb">
            <svg class="btn-icon" viewBox="0 0 24 24">
              <path d="M15 7V4H16V2H8V4H9V7H7V10H8V14C8 15.1 8.9 16 10 16H11V20H10V22H14V20H13V16H14C15.1 16 16 15.1 16 14V10H17V7H15M10 4H14V7H10V4Z"/>
            </svg>
            <span class="btn-label">Puertos USB</span>
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
            <span>Inversor: <strong id="txt-inv-temp">--°C</strong></span>
          </div>
          <div class="badge-item">
            <span>Batería: <strong id="txt-batt-temp">--°C</strong></span>
          </div>
          <div class="badge-item">
            <span>Estado: <strong id="txt-fault">OK</strong></span>
          </div>
        </div>
      </ha-card>
    `;

    this._attachEvents();
  }

  _attachEvents() {
    const hookToggle = (elemId, entityKey) => {
      const btn = this.shadowRoot.getElementById(elemId);
      if (btn) {
        btn.addEventListener("click", () => {
          const entityId = this._mapped[entityKey];
          if (entityId && this._hass) {
            btn.style.transform = "scale(0.95)";
            setTimeout(() => { btn.style.transform = ""; }, 150);
            this._hass.callService("switch", "toggle", { entity_id: entityId });
          }
        });
      }
    };

    hookToggle("btn-sw-ac", "switch_ac");
    hookToggle("btn-sw-dc", "switch_dc");
    hookToggle("btn-sw-usb", "switch_usb");
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

    // Update switches
    const updateSwitch = (btnId, stId, key) => {
      const btn = this.shadowRoot.getElementById(btnId);
      const st = this.shadowRoot.getElementById(stId);
      const s = getState(key);
      const is_on = s === "on" || s === true;
      if (btn) btn.classList.toggle("active", is_on);
      if (st) st.textContent = is_on ? "ACTIVO" : "APAGADO";
    };

    updateSwitch("btn-sw-ac", "st-sw-ac", "switch_ac");
    updateSwitch("btn-sw-dc", "st-sw-dc", "switch_dc");
    updateSwitch("btn-sw-usb", "st-sw-usb", "switch_usb");

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
      invTempEl.textContent = (t !== null && t !== undefined && !isNaN(parseFloat(t))) ? `${Math.round(parseFloat(t))}°C` : "--°C";
    }

    const battTempEl = this.shadowRoot.getElementById("txt-batt-temp");
    if (battTempEl) {
      const t = getState("battery_temp");
      battTempEl.textContent = (t !== null && t !== undefined && !isNaN(parseFloat(t))) ? `${Math.round(parseFloat(t))}°C` : "--°C";
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
customElements.define("oukitel-display-card", OukitelDisplayCard);
customElements.define("oukitel-card", OukitelCard);

// Register in Home Assistant customCards list for visual picker
window.customCards = window.customCards || [];
window.customCards.push({
  type: "oukitel-display-card",
  name: "Oukitel LCD Display Card",
  description: "Réplica 100% fotorealista en SVG de la pantalla LCD física de la estación Oukitel",
  preview: true,
  documentationURL: "https://github.com/VictorCV-DAM/ha-oukitel",
});
window.customCards.push({
  type: "oukitel-card",
  name: "Oukitel Control Card",
  description: "Tarjeta de control completo con interruptores táctiles AC/DC/USB y balance económico",
  preview: true,
  documentationURL: "https://github.com/VictorCV-DAM/ha-oukitel",
});

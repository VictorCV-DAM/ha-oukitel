<div align="center">
  <img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/icon.gif" width="140" height="140" alt="Oukitel Power Station Icon" />
  <h1>Oukitel Power Station Integration for Home Assistant</h1>

  [![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)
  [![GitHub Release](https://img.shields.io/github/v/release/VictorCV-DAM/ha-oukitel)](https://github.com/VictorCV-DAM/ha-oukitel/releases)
  [![License: Proprietary](https://img.shields.io/badge/License-Proprietary-red.svg)](LICENSE)
  [![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Donate-orange?logo=buy-me-a-coffee)](https://buymeacoffee.com/VictorCV)
  [![PayPal](https://img.shields.io/badge/PayPal-Donate-blue?logo=paypal)](https://paypal.me/victorcava)
  [![Ko-fi](https://img.shields.io/badge/Ko--fi-Donate-red?logo=ko-fi)](https://ko-fi.com/victorcv)
</div>

Custom integration for Home Assistant to monitor and control **Oukitel Power Stations** (P2001 Plus, P2001, P5000, BP2000, etc.). Connects via **local LAN** when the device is on the same network, with automatic fallback to Cloud API — no phone, emulator, or ADB required.

---

## 👨‍💻 Author & Intellectual Property

- **Author & Maintainer:** Víctor C. V. ([@VictorCV-DAM](https://github.com/VictorCV-DAM))
- **Email:** `victorcvtrabajo@gmail.com`
- **Copyright:** © 2024-2026 Víctor C. V. All rights reserved.
- **License:** [Proprietary — All Rights Reserved](LICENSE). Pending adoption of an OSI-approved license.

> [!NOTE]
> **Pending OSI-approved license:** Until an OSI-approved open-source license is adopted, this project can only be installed as a **Custom Repository** in HACS and cannot be submitted to the official HACS default store. Functionality is not affected.

---

## ✨ Features

- **Dual Connection Mode**: Automatically connects via **local LAN** (TCP, real-time push) when the station is on the same network. Falls back to **Cloud API** (polling) if LAN is unavailable — switching is transparent and requires no user action.
- **Connection Mode Indicator**: Diagnostic entity in the device card shows whether the active connection is `LAN` or `Cloud` at all times.
- **100% Standalone**: No smartphone, emulator, or ADB required.
- **Interactive Bidirectional Switches**: Toggle AC, DC 12V, and USB directly from Home Assistant UI and automations with optimistic latching.
- **Dynamic Energy Icons**: Automatic real-time animated battery status icons showing charging vs discharging states at 10% steps.
- **Real-Time Telemetry**: Battery %, input power (Total, AC, Solar DC), output power, temperature, estimated times, Wi-Fi signal.
- **Autonomous Keep-Alive**: Automatically prevents the power station firmware from entering sleep mode.
- **Multi-Region Support**:
  - `EU` (Europe - Verified)
  - `US` (North America - [EXPERIMENTAL])
  - `CN` (China/Asia - [EXPERIMENTAL])
- **UI Config Flow**: Native setup directly from Home Assistant Settings → Devices & Services.

---

## 📦 Installation via HACS

### 1-Click Installation:
Click the button below to add this repository directly to your HACS:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=VictorCV-DAM&repository=ha-oukitel&category=integration)

### Manual Installation:
1. Open **HACS** in your Home Assistant.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. Add this repository URL: `https://github.com/VictorCV-DAM/ha-oukitel` and category **Integration**.
4. Click **Download** and restart Home Assistant.
5. In Home Assistant, go to **Settings** -> **Devices & Services** -> **Add Integration** -> Search for **Oukitel Power Station**.
6. Enter your account email, password, and region.

---

## 📸 Screenshots & User Interface

<div align="center">
  <h3>⚡ Full Device Dashboard & Interactive Controls</h3>
  <img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/05_device_dashboard.png" alt="Oukitel Device Dashboard" width="90%" />
  <p><i>Live telemetry: real-time battery status, bidirectional switches (AC, 12V DC, USB), input/output power, diagnostics, and frequency/voltage controls.</i></p>
</div>

<br/>

<div align="center">
  <table width="100%">
    <tr>
      <td width="50%" align="center">
        <b>1. Native Brand Search & Setup</b><br/><br/>
        <img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/01_select_brand.png" alt="Search Oukitel Brand" width="95%"/><br/>
        <sub>Direct search in Home Assistant Add Integration flow.</sub>
      </td>
      <td width="50%" align="center">
        <b>2. Multi-Region Cloud Authentication</b><br/><br/>
        <img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/02_login_dialog.png" alt="Login & Region Dialog" width="95%"/><br/>
        <sub>Region selection (EU/US/CN), email, password, and polling frequency.</sub>
      </td>
    </tr>
    <tr>
      <td width="50%" align="center">
        <b>3. Automatic Station Discovery</b><br/><br/>
        <img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/03_device_discovered.png" alt="Device Discovered" width="95%"/><br/>
        <sub>Discovers your station model, serial number, and allows naming/area assignment.</sub>
      </td>
      <td width="50%" align="center">
        <b>4. Integration Card & Connected Entities</b><br/><br/>
        <img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/02_integration_card.png" alt="Integration Card" width="95%"/><br/>
        <sub>Overview of the custom integration showing device status and 18 entities.</sub>
      </td>
    </tr>
    <tr>
      <td width="50%" align="center">
        <b>5. Device Management Hub</b><br/><br/>
        <img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/03_hub_device.png" alt="Hub Device View" width="95%"/><br/>
        <sub>Hub entry point with direct access to options and diagnostics.</sub>
      </td>
      <td width="50%" align="center">
        <b>6. Dynamic Telemetry Frequency Options</b><br/><br/>
        <img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/04_options_frequency.png" alt="Options Frequency Dialog" width="95%"/><br/>
        <sub>Modify update polling interval (3-120s) on-the-fly without re-logging.</sub>
      </td>
    </tr>
  </table>
</div>

---

## 🌐 Connection Modes: Auto, LAN & Cloud

You can configure the active connection mode at any time directly in Home Assistant (**Settings** ➔ **Devices & Services** ➔ **Oukitel Power Station** ➔ **Configure ⚙️**):

1. **Automático (LAN preferente + Cloud)** *(Default)*: Automatically connects via local LAN (TCP port 6607, binary AES-128 push) when the station is on your home Wi-Fi network. If the station goes offline, drops Wi-Fi, or is outside the local network, it seamlessly falls back to Cloud API polling without missing data.
2. **Solo LAN (Tiempo real directo)**: Pure local communication with 0 cloud latency. Does not make requests to the cloud servers.
3. **Solo Cloud (Nube / Polling)**: Standard cloud polling via the official Acceleronix/Quectel servers (ideal when Home Assistant and the power station are on separate networks or behind isolated VLANs).

| Feature | **LAN Mode** | **Cloud Mode** |
|---|---|---|
| **Protocol** | TCP port 6607 (binary, AES-128 push) | Acceleronix REST API (JSON) |
| **Latency** | Real-time push (~1 s) | Polling interval (min. 3 s) |
| **Internet Required** | Only during first setup | Always |
| **Works Offline / Cloud Down** | ✅ Yes | ❌ No |
| **Works Outside Local Network** | ❌ (requires VPN) | ✅ Yes |

> [!TIP]
> The **Connection Mode** diagnostic sensor on the device page always reports whether the station is actively communicating via `LAN` or `Cloud`.

---

## 📊 Entities Provided

### Sensors (Telemetry & Diagnostics)
- `sensor.oukitel_battery`: Battery level (%) with dynamic charging icons
- `sensor.oukitel_total_input_power`: Total input (W)
- `sensor.oukitel_total_output_power`: Total output (W)
- `sensor.oukitel_ac_input_power`: AC charging input (W)
- `sensor.oukitel_dc_solar_input_power`: Solar DC input (W)
- `sensor.oukitel_temperature`: Station internal temperature (°C)
- `sensor.oukitel_remaining_discharge_time`: Estimated time remaining (min)
- `sensor.oukitel_remaining_charge_time`: Charge time remaining (min)
- `sensor.oukitel_wifi_signal`: Cloud Wi-Fi RSSI (dBm) · *Diagnostic*
- `sensor.oukitel_bms_version`: BMS firmware version · *Diagnostic*
- `sensor.oukitel_inverter_version`: Inverter firmware version · *Diagnostic*
- `sensor.oukitel_connection_mode`: Active connection — `LAN` or `Cloud` · *Diagnostic*

### Switches (Bidirectional Control)
- `switch.oukitel_ac_output`: Toggle 230V AC output
- `switch.oukitel_dc_12v_output`: Toggle 12V DC output
- `switch.oukitel_usb_output`: Toggle USB ports output

### Controls & Configuration (From the "Settings / Wheel" Screen)
- `number.oukitel_ac_charging_limit`: AC Upper Limit Charging Power slider (3% to 100%)
- `select.oukitel_output_frequency`: Output Frequency setting (`50Hz` / `60Hz`)
- `select.oukitel_output_voltage`: Output Voltage setting (`200V`, `208V`, `220V`, `230V`, `240V`)

---

## 🎨 Dashboard Cards & Custom Lovelace Examples

Here are curated Lovelace card examples to monitor your Oukitel Power Station with custom visuals:

### 1. Animated Battery Graphic (Picture Elements)

Displays the station's animated battery graphic with live percentage overlaid in the center:

<img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/card_picture_elements.png" width="300" alt="Picture Elements Battery Card" />

```yaml
type: picture-elements
image: /local/oukitel/icon.svg
elements:
  - type: state-label
    entity: sensor.p2001_plus_tt_ab76_p2001_plus_battery
    tap_action:
      action: more-info
    style:
      top: 75%
      left: 50%
      transform: translate(-50%, -50%)
      color: white
      font-size: 24px
      font-weight: bold
      text-shadow: 2px 2px 4px rgba(0,0,0,0.8)
```
*(Note: Replace `sensor.p2001_plus_tt_ab76_p2001_plus_battery` with your device's entity ID).*

---

### 2. Header & Battery Autonomy Ring (custom:button-card)

Top header bar and circular gauge showing battery level, remaining autonomy, solar input, and AC load:

<img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/card_battery_ring.png" width="300" alt="Oukitel Header and Battery Ring" />

```yaml
type: vertical-stack
cards:
  - type: custom:button-card
    name: OUKITEL P2001
    show_name: true
    show_state: false
    styles:
      card:
        - background: '#1a1a1a'
        - border-radius: 30px 30px 0px 0px
        - padding: 20px 10px 5px 10px
        - border: none
        - margin-bottom: -8px
      name:
        - font-size: 22px
        - font-weight: bold
        - color: rgba(255, 255, 255, 0.9)
        - text-transform: uppercase
        - letter-spacing: 1px
  - type: custom:button-card
    entity: sensor.p2001_plus_tt_ab76_p2001_plus_battery
    aspect_ratio: 1/1
    show_name: false
    show_state: false
    custom_fields:
      ring: |
        [[[
          const pct = states['sensor.p2001_plus_tt_ab76_p2001_plus_battery'].state;
          const modo = states['sensor.oukitel_estado_de_autonomia'].attributes.modo;
          const color = modo === 'carga' ? '#00d2ff' : (modo === 'descarga' ? '#f5576c' : '#2ecc71');
          
          /* Ajustes de grosor y radio */
          const radius = 42; 
          const circ = 2 * Math.PI * radius;
          const offset = circ * (1 - pct / 100);
          
          /* Lógica para 10 segmentos */
          const numSegmentos = 10;
          const gap = 3; 
          const segmentLength = (circ / numSegmentos) - gap;
          const divisiones = `${gap} ${segmentLength}`; 

          return `
            <svg viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="${radius}" fill="none" 
                stroke="rgba(255,255,255,0.05)" stroke-width="12" />
              
              <circle cx="50" cy="50" r="${radius}" fill="none" stroke="${color}" stroke-width="12" 
                stroke-dasharray="${circ}" 
                stroke-dashoffset="${offset}" 
                stroke-linecap="butt" transform="rotate(-90 50 50)" style="transition: all 1s ease-out;" />
                
              <circle cx="50" cy="50" r="${radius}" fill="none" stroke="#1a1a1a" stroke-width="14" 
                stroke-dasharray="${divisiones}" transform="rotate(-91.5 50 50)" />

              <text x="50" y="48" text-anchor="middle" font-size="6" fill="rgba(255,255,255,0.5)" font-weight="bold">BATERÍA</text>
              <text x="50" y="62" text-anchor="middle" font-size="14" fill="white" font-weight="bold">${pct}%</text>
            </svg>
          `;
        ]]]
      tiempo: |
        [[[
          const tiempo = states['sensor.oukitel_estado_de_autonomia'].attributes.tiempo_formateado;
          const modo = states['sensor.oukitel_estado_de_autonomia'].attributes.modo;
          const label = modo === 'carga' ? 'CARGA COMPLETA EN:' : 'AUTONOMÍA';
          return `
            <div style="text-align: center;">
              <div style="font-size: 10px; opacity: 0.6; font-weight: bold;">${label}</div>
              <div style="font-size: 24px; font-weight: 900; color: white; line-height: 1.1;">${tiempo}</div>
            </div>
          `;
        ]]]
      watts: |
        [[[
          const entrada = states['sensor.p2001_plus_tt_ab76_p2001_plus_total_input_power'].state;
          const consumo = states['sensor.p2001_plus_tt_ab76_p2001_plus_total_output_power'].state;
          return `
            <div style="display: flex; justify-content: space-around; width: 100%; font-size: 14px; font-weight: bold;">
              <span style="color: #4caf50;">↑ ${entrada}W</span>
              <span style="color: #f44336;">↓ ${consumo}W</span>
            </div>
          `;
        ]]]
    styles:
      card:
        - border-radius: 0px 0px 30px 30px
        - background: '#1a1a1a'
        - padding: 10%
        - border: none
      grid:
        - grid-template-areas: '"ring" "tiempo" "watts"'
        - grid-template-columns: 1fr
        - grid-template-rows: 1fr auto auto
      custom_fields:
        ring:
          - width: 85%
          - justify-self: center
        tiempo:
          - margin-top: 30px
          - margin-bottom: 10px
        watts:
          - margin-top: 5px
```

---

### 3. Glassmorphic Temperature Card with Dynamic Icon (custom:button-card)

Interactive temperature card with glassmorphism, dynamic color thresholds, and thermometer icons:

<img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/card_temperature.png" width="180" alt="Oukitel Glassmorphic Temperature Card" />

```yaml
type: custom:button-card
entity: sensor.p2001_plus_tt_ab76_p2001_plus_temperature
show_name: true
show_state: true
name: OUKITEL
icon: |
  [[[
    if (entity.state > 25) return 'mdi:thermometer-high';
    if (entity.state < 18) return 'mdi:thermometer-low';
    return 'mdi:thermometer';
  ]]]
styles:
  card:
    - height: 140px
    - width: 140px
    - border-radius: 20px
    - background: rgba(255, 255, 255, 0.1)
    - backdrop-filter: blur(10px)
    - border: 1px solid rgba(255, 255, 255, 0.2)
    - box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37)
    - padding: 10%
  grid:
    - grid-template-areas: '"i" "n" "s"'
    - grid-template-columns: 1fr
    - grid-template-rows: 1fr min-content min-content
  icon:
    - width: 45%
    - color: |
        [[[
          if (entity.state > 25) return '#ff5722';
          if (entity.state < 18) return '#00bcd4';
          return '#4caf50';
        ]]]
  name:
    - justify-self: start
    - font-weight: bold
    - font-size: 14px
    - color: white
    - margin-top: 10px
  state:
    - justify-self: start
    - font-size: 22px
    - font-weight: 900
    - color: white
state:
  - operator: default
    spin: false
```

---

### 4. Conditional Solar Production Gauge

Only displays when AC grid charging is idle, focusing on clean solar generation:

<img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/card_solar_gauge.png" width="300" alt="Solar Production Gauge" />

```yaml
type: conditional
conditions:
  - condition: state
    entity: switch.oukitel_ac_charging_plug
    state_not: 'on'
card:
  type: gauge
  entity: sensor.p2001_plus_tt_ab76_p2001_plus_dc_solar_input_power
  min: 0
  max: 450
  name: Solar Production
```
*(Note: Replace `switch.oukitel_ac_charging_plug` with your AC wall plug entity if you automate grid charging).*

---

### 5. Mushroom Summary Chip (Compact Tile)

Compact status banner displaying battery, live input, and active load:

<img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/card_mushroom.png" width="300" alt="Mushroom Card" />

```yaml
type: custom:mushroom-template-card
primary: Oukitel P2001 Plus
secondary: >-
  {{ states('sensor.p2001_plus_tt_ab76_p2001_plus_battery') }}% • {{
  states('sensor.p2001_plus_tt_ab76_p2001_plus_total_input_power') | default(0) }}W IN • {{
  states('sensor.p2001_plus_tt_ab76_p2001_plus_total_output_power') | default(0) }}W OUT
picture: /local/oukitel/icon.svg
```

---

## 🔗 Related Projects & Alternative Deployments

* 📦 **[oukitel-hassio-addons](https://github.com/VictorCV-DAM/oukitel-hassio-addons)**: Official Docker Add-on repository for Home Assistant OS (Supervisor).
* 🐍 **[oukitel-portable-bridge](https://github.com/VictorCV-DAM/oukitel-portable-bridge)**: Universal standalone Python MQTT bridge (runs on Linux, Windows, macOS, or Raspberry Pi independently of Home Assistant).

---

## ☕ Support & Donations

If this integration has saved you time, enhanced your home solar automation, or allowed you to avoid buying an extra hardware bridge, consider supporting ongoing maintenance and testing of new firmware:

- ☕ **Buy Me a Coffee:** [buymeacoffee.com/VictorCV](https://buymeacoffee.com/VictorCV)
- 🅿️ **PayPal:** [paypal.me/victorcava](https://paypal.me/victorcava)
- 🔴 **Ko-fi:** [ko-fi.com/victorcv](https://ko-fi.com/victorcv)
- 💖 **GitHub Sponsors:** [github.com/sponsors/VictorCV-DAM](https://github.com/sponsors/VictorCV-DAM)

Thank you for your support! ⭐

---

## ⚖️ Disclaimer

This project is an independent community development and is not affiliated with, supported by, or endorsed by Oukitel or Acceleronix/Quectel. All product names, trademarks, and registered trademarks belong to their respective owners.

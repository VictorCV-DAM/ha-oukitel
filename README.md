<div align="center">
  <img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/icon.png" width="140" height="140" alt="Oukitel Power Station Icon" />
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
  <img src="https://raw.githubusercontent.com/VictorCV-DAM/ha-oukitel/main/docs/images/05_device_dashboard.png" alt="Oukitel Device Dashboard" width="510" />
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

The integration automatically exposes over 25 entities across sensors, binary sensors, switches, numbers, selects, and buttons:

### 🔋 Core Telemetry & Energy
- `sensor.oukitel_battery`: Battery level (%) with dynamic real-time charging/discharging animated icons.
- `sensor.oukitel_total_input_power`: Total aggregate incoming power from AC grid and solar DC (W).
- `sensor.oukitel_total_output_power`: Total aggregate power consumed across all active outlets (W).
- `sensor.oukitel_ac_input_power`: AC grid wall charging power (W).
- `sensor.oukitel_dc_solar_input_power`: Solar array photovoltaic input power (W).
- `sensor.oukitel_temperature`: Internal heatsink & cell temperature (°C).
- `sensor.oukitel_inverter_temperature`: Inverter thermal monitoring with automatic sensor fallback (°C).

### ⏱️ Smart Physics-Based Autonomy & Remaining Times
Unlike native station firmware which can confuse charging and discharging when solar production is lower than household consumption, this integration implements a **real-time net power balance engine**:
- `sensor.oukitel_remaining_time`: Station LCD display equivalent time (minutes).
- `sensor.oukitel_remaining_discharge_time`: True battery autonomy countdown while net discharging (minutes). Automatically sets to `0` when net charging.
- `sensor.oukitel_remaining_charge_time`: Intelligent estimate to reach 100% full capacity while net charging (minutes). Automatically sets to `0` when net discharging or already at 100%. Bypasses the station's 99-hour (5,940m) display overflow cap with dynamic calculations.

### 🔌 Per-Port Individual Telemetry
- `sensor.oukitel_ac_output_power`: 230V Pure Sine Wave inverter output (W).
- `sensor.oukitel_ac_output_voltage`: Real-time inverter output voltage (V). Accurately reports active voltage (e.g. 230V) when inverted output is active, and 0V when off.
- `sensor.oukitel_type_c_1_power`: Fast-charge Type-C 1 port power (W).
- `sensor.oukitel_type_c_2_power`: Type-C 2 port power (W).
- `sensor.oukitel_type_c_3_power`: Type-C 3 port power (W).
- `sensor.oukitel_type_c_4_power`: Type-C 4 port power (W).
- `sensor.oukitel_usb_a_power`: Standard USB-A port power (W).
- `sensor.oukitel_usb_c_qc_power`: Quick Charge USB-C port power (W).
- `sensor.oukitel_dc_car_output_power`: 12V DC cigarette lighter socket power (W).
- `sensor.oukitel_dc_car_output_voltage`: 12V DC car socket voltage (V).
- `sensor.oukitel_dc_car_output_current`: 12V DC car socket current (A).

*(Note: All port power sensors default to `0 W` immediately upon startup, guaranteeing zero `Unknown` states even before individual sub-packets arrive).*

### 🛡️ Diagnostic & Health Sensors
- `sensor.oukitel_hardware_fault_status`: **Official Home Assistant ENUM sensor** with predefined, standardized states for direct use in automations.
- `sensor.oukitel_connection_mode`: Active transport layer (`LAN` or `Cloud`) · *Diagnostic*.
- `sensor.oukitel_wifi_signal`: Cloud Wi-Fi RSSI (dBm) · *Diagnostic*.
- `sensor.oukitel_bms_version`: BMS firmware version · *Diagnostic*.
- `sensor.oukitel_inverter_version`: Inverter firmware version · *Diagnostic*.

### 🔌 Binary Sensors & Quick Actions
- `binary_sensor.oukitel_battery_powered_inferred`: Detects whether the station is actively running on battery (net discharging or mains/solar input absent).
- `button.oukitel_reload`: Instantly reloads the integration session without restarting Home Assistant.

### 🎛️ Bidirectional Switches & Settings
- `switch.oukitel_ac_output`: Toggle 230V AC inverter output with optimistic latching.
- `switch.oukitel_dc_12v_output`: Toggle 12V DC car/barrel port output.
- `switch.oukitel_usb_output`: Toggle USB & Type-C power bank outputs.
- `switch.oukitel_pause_integration`: Master toggle to pause all polling, disconnect the LAN socket, and stop keep-alive/wake commands. Allows the station to enter deep sleep without Home Assistant waking it up. Fully actionable via automations (`switch.turn_on` / `switch.turn_off`).
- `number.oukitel_ac_charging_limit`: AC Upper Limit Charging Power slider (3% to 100%).
- `select.oukitel_output_frequency`: Output Frequency setting (`50Hz` / `60Hz`).
- `select.oukitel_output_voltage`: Output Voltage setting (`200V`, `208V`, `220V`, `230V`, `240V`).

---

## 🛡️ Hardware Fault Status & Native Automations

The `sensor.oukitel_hardware_fault_status` entity is implemented as a native **Home Assistant Enum Sensor** (`SensorDeviceClass.ENUM`). This means you do **not** have to guess what strings might occur: when configuring triggers in the Home Assistant Automation UI, all valid states appear directly in the dropdown menu:

| State in Dropdown | Trigger Condition | Recommended Automation Action |
|:---|:---|:---|
| **`Normal`** | System operating within all safety specifications. | Resume normal schedule / clear alert dashboard. |
| **`High Temperature Warning`** | Internal heatsink/battery temperature $\ge 55^\circ\text{C}$. | Trigger cooling fan or reduce AC charging rate. |
| **`Over-Temperature`** | Internal temperature exceeds critical limit $\ge 65^\circ\text{C}$. | Disconnect heavy loads or shut down AC inverter. |
| **`Under-Temperature`** | Temperature falls below $-10^\circ\text{C}$ (LiFePO4 charge lock). | Inhibit high-current charging until warm. |
| **`Low Battery Warning`** | Battery $\le 10\%$ while actively discharging. | Send mobile push notification, shed secondary loads. |
| **`Critical Low Battery`** | Battery reaches $0\%$ under load. | Emergency shutdown to protect battery cells. |
| **`Overload Protection`** | Total output exceeds rated continuous capacity ($> 2,400\,\text{W}$). | Automatically trip or notify before hardware breaker trips. |
| **`Hardware Fault`** | Critical BMS or inverter hardware error code emitted. | Emit priority siren / emergency notification. |

### Entity Attributes (`extra_state_attributes`)
- `fault_details`: Human-readable description of the exact trigger (e.g. *"Output power (2650W) exceeds rated 2400W"* or *"Temperature is critical: 67°C"*).
- `possible_states`: Complete array of all possible enum states.

### Example Automation: High Temperature Alert
```yaml
alias: "Oukitel: Thermal Protection Alert"
description: "Notify and turn off heavy loads if Oukitel station overheats"
trigger:
  - platform: state
    entity_id: sensor.p2001_plus_tt_ab76_hardware_fault_status
    to:
      - "High Temperature Warning"
      - "Over-Temperature"
action:
  - service: notify.persistent_notification
    data:
      title: "⚠️ Oukitel Thermal Warning"
      message: >-
        Station reported {{ trigger.to_state.state }}.
        Details: {{ state_attr(trigger.entity_id, 'fault_details') }}.
```

---

## 🔬 Reverse-Engineering & Architecture Methodology

How was this information discovered and implemented?

1. **Thing Specification Language (TSL) Reverse Engineering:**
   The exact data model for the P2001 Plus was extracted by querying the Quectel / Acceleronix IoT Cloud device model repository for `productKey: p11wN7`. This revealed all 21 official properties, including the complex structs:
   - Tag 6 (`ac_data`): subtag 1 (`ac_switch`), subtag 2 (`ac1_output`), subtag 3 (`ac1_output_voltage`).
   - Tag 7 (`usb_data`): subtag 1 (`usb_switch`), subtag 2 (`USB_QC1_output`), subtag 3 (`USB_QC2_output`).
   - Tag 8 (`typec_data`): subtags 2, 5, 6, 7 (dedicated wattage for Type-C ports 1 through 4).
   - Tag 9 (`dc_data`): subtag 1 (`dc_switch`), subtag 2 (`car1_output`), subtag 3 (`car1_output_voltage`), subtag 4 (`car1_output_current`).
   - Tag 28 (`ACvoltage_Switchover`): Enums for 100V, 110V, 120V, 220V, and 230V.

2. **Binary LAN Protocol (Port 6607):**
   The station exposes an unadvertised local TCP service on port 6607 using a custom framing protocol (SLIP-like destuffing with `0xEB 0x90` frame magic and XOR byte-stuffing). The payload is encrypted with AES-128-CBC using a device-specific `authKey` provisioned over Cloud binding, and the decrypted body uses a compact TTLV (Tag-Type-Length-Value) encoding. Our parser decodes both scalar tags and nested struct subtags in real time.

3. **Physics & Battery Management Engine:**
   Official station firmware has known display quirks:
   - When solar input is present (e.g. 337W) but household AC draw is larger (e.g. 342W), the firmware's internal flag often incorrectly treats the battery as charging. We solved this with a pure physics engine:
     $$\text{NetPower} = \max(\text{Total}_{\text{in}}, \text{AC}_{\text{in}} + \text{DC}_{\text{in}}) - \max(\text{Total}_{\text{out}}, \text{AC}_{\text{out}} + \text{DC}_{\text{out}})$$
   - When charging at low net wattage, the firmware's internal integer overflows its 99-hour display limit, getting stuck at 5,940 minutes (99 hours). We dynamically calculate real remaining time based on the 2,048 Wh LiFePO4 battery capacity.

4. **Home Assistant Native Standards:**
   Rather than treating fault alarms as arbitrary text, we mapped all physical and firmware thresholds to standard Home Assistant `SensorDeviceClass.ENUM` contracts so the HA UI natively presents all actionable choices directly to the user.

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

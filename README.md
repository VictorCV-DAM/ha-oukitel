# Oukitel Power Station Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/github/v/release/VictorCV-DAM/ha-oukitel)](https://github.com/VictorCV-DAM/ha-oukitel/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Custom integration for Home Assistant to monitor and control **Oukitel Power Stations** (P2001 Plus, P2001, P5000, BP2000, etc.) via Cloud API without phone, emulator, or ADB.

---

## 👨‍💻 Author & Intellectual Property

- **Author & Maintainer:** Víctor C. V. ([@VictorCV-DAM](https://github.com/VictorCV-DAM))
- **Email:** `victorcvtrabajo@gmail.com`
- **Copyright:** © 2024-2026 Víctor C. V. All rights reserved.
- **License:** Released under the [MIT License](LICENSE).

---

## ✨ Features

- **100% Standalone**: No smartphone, emulator, or ADB required.
- **Interactive Bidirectional Switches**: Toggle AC, DC 12V, and USB directly from Home Assistant UI and automations.
- **Real-Time Telemetry**: Battery %, input power (Total, AC, Solar DC), output power, temperature, estimated times, Wi-Fi signal.
- **Autonomous Keep-Alive**: Automatically prevents the power station firmware from entering sleep mode.
- **Multi-Region Support**:
  - `EU` (Europe - Verified)
  - `US` (North America - [EXPERIMENTAL])
  - `CN` (China/Asia - [EXPERIMENTAL])
- **UI Config Flow**: Native setup directly from Home Assistant Settings -> Devices & Services.

---

## 📦 Installation via HACS

1. Open **HACS** in your Home Assistant.
2. Click the three dots in the top right corner and select **Custom repositories**.
3. Add this repository URL: `https://github.com/VictorCV-DAM/ha-oukitel` and category **Integration**.
4. Click **Download** and restart Home Assistant.
5. In Home Assistant, go to **Settings** -> **Devices & Services** -> **Add Integration** -> Search for **Oukitel Power Station**.
6. Enter your account email, password, and region.

---

## 📊 Entities Provided

### Sensors
- `sensor.oukitel_battery`: Battery level (%)
- `sensor.oukitel_total_input_power`: Total input (W)
- `sensor.oukitel_total_output_power`: Total output (W)
- `sensor.oukitel_ac_input_power`: AC charging input (W)
- `sensor.oukitel_dc_solar_input_power`: Solar DC input (W)
- `sensor.oukitel_temperature`: Station internal temperature (°C)
- `sensor.oukitel_remaining_discharge_time`: Estimated time remaining (min)
- `sensor.oukitel_remaining_charge_time`: Charge time remaining (min)
- `sensor.oukitel_ac_charging_limit`: Configured charge limit (%)
- `sensor.oukitel_wifi_signal`: Cloud Wi-Fi RSSI (dBm)

### Switches (Bidirectional Control)
- `switch.oukitel_ac_output`: Toggle 230V AC output
- `switch.oukitel_dc_12v_output`: Toggle 12V DC output
- `switch.oukitel_usb_output`: Toggle USB ports output

---

## ⚖️ Disclaimer

This project is an independent community development and is not affiliated with, supported by, or endorsed by Oukitel or Acceleronix/Quectel. All product names, trademarks, and registered trademarks belong to their respective owners.

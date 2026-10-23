# Zero-cloud task log

This document is the exhaustive record of the work implemented on
`feature/zero-cloud-broker`. It is intentionally more detailed than the
branch README.

## 1. Scope and environment

| Item | Value |
|---|---|
| Station | Oukitel P2001 Plus |
| Product key | `p11wN7` |
| Device key | `ecb5…` (redacted) |
| Vendor app | Wonderfree 3.7.5 (XAPK) |
| Home Assistant | 2024.1+ |
| Bluetooth access | ESPHome Bluetooth proxy + IoT pusher |
| Network capture | AdGuard DNS rewrite, local ports |
| TLS test server | Node.js 22 |
| APK analysis | jadx 1.5.6 |
| Logging | `diag_logger.py` → `oukitel_diag.log` |

The branch started from `main` v1.5.7. The snapshot commit `3b429eb` contains
the state of the BLE test work described here.

## 2. Design goals

1. Provision the station over BLE without the vendor app.
2. Point it at a local MQTT broker on port `8886`.
3. Use the LAN protocol on `6607` with the cloud-issued `authKey`.
4. Capture enough diagnostics to understand why the station stops streaming.
5. Keep every experiment reproducible.

The work deliberately did **not** include blind fuzzing of the provisioning
characteristic.

## 3. BLE provisioning (`ble_provision.py`)

### 3.1 Device discovery

- Scans connectable BLE advertisements.
- Accepts names starting with `QUEC_BLE` or containing `OUKITEL`, `P2001`,
  `BP2000`, `P5000`, `P1200`, `P800`, `CN505`.
- Parses Quectel manufacturer data to extract `productKey` and `deviceKey`.
- Exposes the available adapter/proxy sources and allows selecting one.
- Falls back to `auto` if the selected source cannot see the station.

### 3.2 `0x7010` frame

- Command: `28688` (`0x7010`).
- Packet id: `1000`.
- Characteristic: `9c40` (`00009c40-0000-1000-8000-00805f9b34fb`).
- No bonding, no pairing PIN.
- TTLV body:
  - tag 1: SSID (string)
  - tag 2: Wi-Fi password (string)
  - tag 11: provisioning timeout in seconds (number; confirmed by the APK builder)
  - tag 12: MCC (number)
  - tag 13: endpoint URL (string)
- The builder parses `mqtt://host:8886`, `mqtts://host:8883`, `host:port` and
  bare hosts.

### 3.3 No-endpoint mode

If the endpoint is `""`, `"none"` or `"lan"`, the frame contains only tags 1
and 2. The station joins Wi-Fi and exposes the LAN server on `6607` without a
cloud/broker endpoint.

### 3.4 Response handling

- Waits for `0x7011` (`28689`) and `0x7014` (`28692`).
- `listen_for` defaults to 180 s.
- Decodes `0x7011` TTLV fields 4, 5, 7, 8, 9.
- Decodes `0x7014` progress codes and logs them.
- Sends `0x7066` acks when the station requests cloud login/bind.
- Sends periodic `0x7014` success acks every 10 s while listening.
- Keeps the BLE client referenced in `hass.data` to prevent garbage collection.

### 3.5 Keepalive

- `_ble_keepalive_loop` writes an empty `0x7066` frame every 10 s.
- It was tested and did **not** extend the BLE window.
- The loop stops when the client disconnects.

### 3.6 Instrumentation

Events include:

- `BLE_POINT_STATION_CONNECTING`
- `BLE_GATT_TABLE`
- `BLE_NOTIFY_RAW`
- `BLE_NOTIFY_PACKET`
- `BLE_PROVISION_0x7010_SENT`
- `BLE_STATION_PROGRESS`
- `BLE_REPLYING_0x7066`
- `BLE_REPLYING_0x7066_BIND`
- `BLE_GATT_WRITE_0x7066`
- `BLE_GATT_WRITE_0x7014`
- `BLE_PROACTIVE_ACKS_BUILD`
- `BLE_SUCCESS_ACK_RESENT`
- `BLE_STATION_DISCONNECTED_NATURALLY`
- `BLE_STATION_NATURAL_DISCONNECT_IN_LOOP`
- `BLE_WAIT_END`
- `BLE_KEEPALIVE_TICK`
- `BLE_KEEPALIVE_ERR`

### 3.7 Errors and UX

- Translates authorization/`133` errors into a pairing-window message.
- Retries writes without response if the with-response write fails.
- Returns a human-readable success/failure message to the config flow.

## 4. Fake cloud (`cloud_bridge.py`)

### 4.1 Broker

- Asyncio TCP server on `0.0.0.0:8886`.
- MQTT 3.1.1 subset: `CONNECT`, `CONNACK`, `SUBSCRIBE`, `SUBACK`, `PUBLISH`,
  `PUBACK`, `PINGREQ`, `PINGRESP`, `DISCONNECT`.
- QoS 0 and QoS 1.
- `PASSIVE_CAPTURE = False` by default.

### 4.2 Topics

| Direction | Topic |
|---|---|
| Device → broker | `q/2/d/<pk><dk>/bus` |
| Broker → device | `q/1/d/<pk><dk>/+` |

The implementation also handles the `sys` and `bus_`/`sys_` variants used by
the app.

### 4.3 Protocol behaviour

- Answers the pairing status request with status `0`.
- Answers the cloud login request with a success ack.
- Sends `0x7014` progress and `0x7066` bind/login acks.
- Publishes telemetry to the device channel.
- Seeds state from the cloud API when credentials are available.

### 4.4 Dual-channel

- The bridge can run concurrently with the LAN session.
- QoS 1 is used for downlink commands.
- The coordinator coordinates bridge and LAN state to avoid duplicate entities.

### 4.5 Instrumentation

- `BRIDGE_START`, `BRIDGE_CONNECT`, `BRIDGE_SUBSCRIBE`, `BRIDGE_PUBLISH`.
- `BRIDGE_FRAME`, `BRIDGE_MQTT_PUBLISH`.
- `BRIDGE_PASSIVE_CAPTURE_SUBSCRIBE`.
- `BRIDGE_ABSENCE`, `BRIDGE_SILENCE`.

## 5. LAN protocol (`local_session.py`, `coordinator.py`)

### 5.1 Handshake

1. TCP connect to `6607`.
2. `CMD_HELLO`.
3. `CMD_NONCE` → 16-byte nonce, used as AES IV.
4. `CMD_LOGIN` with a token derived from the `authKey`.
5. `CMD_LOGIN_OK`; `result=0` means success.

### 5.2 Crypto

- AES-128-CBC.
- Key derived from the base64 `authKey` (decoded to 16 bytes).
- IV = the nonce bytes returned by the station.
- Payload TTLV, same encoder/decoder as BLE.

### 5.3 Commands

| Command | Purpose |
|---|---|
| 16 | Hello |
| 17 | Read tags |
| 19 | Write tag |
| 20 | Telemetry |
| 21 | Telemetry/notification |
| 35 | Heartbeat/keepalive |
| 36 | Write ACK / bind |
| 38 | Heartbeat/keepalive |

### 5.4 Tags

The coordinator maps tags to entities: battery, input/output power, AC/DC/USB
power, temperatures, AC/BMS versions, switches, frequency/voltage selectors,
and diagnostics.

### 5.5 Reconnection

- Reconnect delay grows from 10 s to 30 s.
- The coordinator re-arms LAN after a silence/absence period.
- `zero_cloud` mode keeps the LAN session alive while the bridge is active.

### 5.6 LAN diagnostics

- `LAN_CONNECT_START`, `LAN_HANDSHAKE_DONE`, `LAN_CONNECTED_OK`.
- `LAN_RX_RAW_FRAME`, `LAN_UNKNOWN_FRAME`.
- `LAN_BIND_FRAME` for `0x7036`.
- `COORD_LAN_CONNECT_OK`, `COORD_LAN_CONNECT_FAIL`.

## 6. Cloud API and `authKey`

### 6.1 Login

- Endpoint: `/v2/enduser/enduserapi/emailPwdLogin`.
- AES-encrypted password + SHA-256 signature with the domain secret.
- Returns an access token.

### 6.2 Device list

- Endpoint: `/v2/binding/enduserapi/userDeviceList`.
- Returns `deviceKey`, `productKey`, `authKey`, `bindingCode`, online status and
  signal strength.

### 6.3 `authKey`

- Used by LAN `6607`.
- Changes after a factory reset or rebind.
- The integration caches it in `config_entry.data`.

### 6.4 OTA

- EU host: `https://iot-api.quecteleu.com/v2/quecota`.
- `getBatchDeviceUpgradePlan` → `data: []` for this device.
- `haveUpgradePlanDeviceList` requires a `fid`.
- `getBatchUpgradeDetails` accepts the device list but returns empty.

## 7. TLS-PSK of the module

- The station connects to the vendor cloud with TLS-PSK only.
- ClientHello:
  - TLS 1.2
  - no SNI
  - no certificate suites
  - `0x008d`, `0x00ae`, `0x008c`, `0x00ff` (SCSV)
- A local Node.js PSK server was used to test 18 candidates:
  - `authKey` base64, hex, ASCII
  - `bindingCode`
  - `deviceKey`
  - `productKey`
  - domain secret
  - MD5/SHA-256/HMAC combinations
- All handshakes failed with `ossl_cipher_generic_stream_update`.
- The PSK is not present in the APK, the cloud API or the OTA image.

## 8. App reverse engineering

- Wonderfree 3.7.5 decompiled with jadx.
- `0x7066` payload is `emptyList()` from the Kotlin `CollectionsKt` facade.
- The app explicitly ignores `cmd == 28692` (`0x7014`).
- `0xFFFE` is generated by the module after the cloud bind, not by the app.
- `0x7055`/28757 requires a reset certificate obtained from the cloud.

## 9. Diagnostics and tooling

- `diag_logger.py`: JSON lines with timestamp, event and payload.
- Flight recorder for BLE, MQTT, LAN and coordinator.
- GATT table dump on connect.
- Hex logs for BLE notifications and MQTT frames.
- TLS probe listener on port `18883` (`TLS_PROBE`, `TLS_PROBE_LISTENING`).
- Test services:
  - `oukitel.ble_disconnect`
  - `oukitel.bridge_send`
- `reload_trigger.py` for hot reload during development.
- `services.yaml` with service definitions.

## 10. Home Assistant integration

- `zero_cloud` connection mode.
- Config/options flow for endpoint, Wi-Fi and BLE MAC.
- Entities for telemetry, switches, numbers, selects and diagnostics.
- `manifest.json` base v1.5.7.
- Bluetooth proxy support and IoT pusher automation.

## 11. Code map

| File | Entry points |
|---|---|
| `ble_provision.py` | `async_discover_oukitel_ble`, `point_station`, `_ble_keepalive_loop` |
| `cloud_bridge.py` | `CloudBridge`, broker handlers |
| `local_session.py` | `LocalSession.connect`, `read_loop`, `request_read` |
| `local_frame.py` | `build_frame`, `FrameAssembler`, `ttlv_encode`, `ttlv_decode` |
| `coordinator.py` | `async_setup_lan`, `_start_lan_session`, `_lan_read_loop` |
| `config_flow.py` | `async_step_bluetooth_confirm`, `async_step_ble_provision` |
| `diag_logger.py` | `diag_log` |
| `__init__.py` | setup, services, TLS probe |

## 12. Not done

- No UART/JTAG access.
- No hardware BLE sniffer.
- No blind fuzzing of `9c40`.
- No permanent cloud-free bind.
- No PSK extraction.
- No firmware download.

# Test log

All tests were performed on a P2001 Plus (`p11wN7`, `ecb5…`) with Home
Assistant, an ESPHome Bluetooth proxy, the IoT pusher and a local broker on
port `8886`. No UART/JTAG or hardware BLE sniffer was available.

## 1. Environment

| Item | Value |
|---|---|
| Station | Oukitel P2001 Plus |
| Wi-Fi | 2.4 GHz, WPA2/WPA3 transition |
| Home Assistant | LAN, `192.168.1.219:8123` |
| Broker | `mqtt://192.168.1.219:8886` |
| BLE proxy | ESPHome Bluetooth proxy on the roof |
| IoT control | ESP32 pusher (`button.pulsador_oukitel_pulsar`) |
| App | Wonderfree 3.7.5 |
| Log | `oukitel_diag.log` |

## 2. Test matrix

### T01 — Local broker with the correct Wi-Fi password

**Steps**

1. Open the BLE pairing window with the IoT button.
2. Send `0x7010` with the current SSID/password, MCC 214 and
   `mqtt://192.168.1.219:8886`.
3. Observe the broker log and the integration entities.

**Observed**

- The station joined Wi-Fi.
- TCP connection to `8886`.
- MQTT `CONNECT`, `SUBSCRIBE` to `q/1/d/<qd>/+`.
- Telemetry on `q/2/d/<qd>/bus`.
- Battery, input and output entities updated.

**Evidence**

`BRIDGE_CONNECT`, `BRIDGE_SUBSCRIBE`, `BRIDGE_MQTT_PUBLISH`,
`COORD_ON_TELEMETRY`.

### T02 — Stale Wi-Fi password

**Steps**

Repeat T01 with the previous password.

**Observed**

- The station did not join.
- It stayed at `0x7014` code 49.

**Conclusion**

The stale password was the real blocker. MCC was not the cause in this test.

### T03 — MCC 460 instead of 214

**Steps**

Repeat T01 after a factory reset with MCC 460.

**Observed**

- The station did not join.
- The test was not isolated from the password state.

**Conclusion**

MCC 460 vs 214 is **unproven**; it was not the confirmed blocker.

### T04 — BLE window and telemetry volume

**Steps**

Keep BLE connected and listen for 180 s.

**Observed**

- Telemetry during the whole window.
- 1,849 MQTT frames in one run.
- Battery, input, output and temperatures updated.

**Evidence**

`BLE_WAIT_END` with `elapsed=180.0`, `connected=true`.

### T05 — GATT keepalive

**Steps**

Start a 10 s keepalive write after the 180 s listener.

**Observed**

- `BLE_KEEPALIVE_TICK` at +10 s and +20 s.
- Module disconnected at +21 s.

**Conclusion**

The keepalive does not extend the BLE window.

### T06 — BLE disconnect with active telemetry

**Steps**

Disconnect BLE while telemetry is flowing.

**Observed**

- The MCU cut the UART stream in 8–9 s.
- The Wi-Fi icon started blinking.

### T07 — HA restart with BLE connected

**Steps**

Restart Home Assistant during a BLE session.

**Observed**

- The BLE client was lost.
- The station reconnected to the broker but did not publish.

### T08 — LAN `6607` with the new `authKey`

**Steps**

1. Fetch the `authKey` from `userDeviceList`.
2. Connect to `192.168.1.15:6607`.
3. Complete HELLO/NONCE/LOGIN.

**Observed**

- `result=0`.
- Telemetry frames (cmd 20) received.
- Entities updated.

### T09 — WAN cut with LAN active

**Steps**

Cut the fiber/WAN while LAN telemetry is flowing.

**Observed**

- Telemetry stopped within seconds.
- The Wi-Fi icon blinked.

**Conclusion**

LAN is gated by the cloud session, not an independent local path.

### T10 — `0x7010` on an already-bound station

**Steps**

Send `0x7010` while the station is bound/online.

**Observed**

- The module acknowledged but kept its old endpoint.
- No local connection.

### T11 — `0x7055` without reset certificate

**Steps**

Send `0x7055`/28757 without the cloud-issued reset certificate.

**Observed**

- The module ignored the frame.
- No endpoint change.

### T12 — Factory reset

**Steps**

Use Wonderfree “restore factory values”, then send `0x7010`.

**Observed**

- The device became virgin.
- `0x7010` was accepted again.
- The local broker worked.

### T13 — `0x7066` / `0x7014` 65534

**Steps**

Send `0x7066` acks and `0x7014` 65534 over BLE/MQTT.

**Observed**

- No change in bind state.
- No fixed Wi-Fi icon.

### T14 — TLS ClientHello

**Steps**

Capture the module's ClientHello toward the vendor cloud.

**Observed**

- TLS 1.2, PSK-only suites, no SNI, no certificates.

### T15 — TLS-PSK candidates

**Steps**

Run a local Node.js TLS-PSK server and try 18 derived keys.

**Observed**

- Every handshake failed at
  `ossl_cipher_generic_stream_update:cipher operation failed`.

### T16 — OTA plan

**Steps**

Query `getBatchDeviceUpgradePlan` on the EU OTA host.

**Observed**

- HTTP 200 with `data: []`.
- No firmware plan for the device.

### T17 — GATT enumeration

**Steps**

Dump all services/characteristics after connecting.

**Observed**

- `0x1800`, `0x1801`, `0x180A` and `9c40`.
- No DFU/UART/OTA service.

### T18 — LAN tag scan

**Steps**

Send a read request for tags 1–300 and log the responses.

**Observed**

- Only normal telemetry; no hidden tags or module version.

### T19 — Reset + no-endpoint provisioning

**Steps**

Factory reset, provision with endpoint `none`.

**Observed**

- LAN `6607` opened.
- Login succeeded with the new `authKey`.
- No telemetry while the cloud was offline.

### T20 — Rebind and cloud status

**Steps**

Rebind in Wonderfree, then query the cloud device list.

**Observed**

- The account listed the device.
- The module stayed at `0x7014` 49 when the local bind was incomplete.

## 3. Evidence summary

| Metric | Value |
|---|---|
| MQTT frames in 180 s | 1,849 |
| BLE close after `0x7010` | ~200 s |
| Keepalive ticks | +10 s, +20 s |
| Disconnect after keepalive | +21 s |
| UART cut after BLE close | 8–9 s |
| LAN login result | 0 |
| TLS candidates | 18 |
| TLS successes | 0 |
| OTA plan entries | 0 |

## 4. Not tested

- UART/JTAG to the Quectel module.
- Hardware BLE sniffer.
- Different firmware versions.
- A second P2001 Plus unit.
- Blind fuzzing of `9c40`.

## 5. Reproduction notes

- Use a local MQTT broker on port `8886` and the `zero_cloud` mode.
- Keep the BLE client alive while observing telemetry.
- Do not reuse a stale Wi-Fi password; always enter the current one.
- After a factory reset, use the current password and a known MCC.
- Use `oukitel_diag.log` to correlate `BLE_*`, `BRIDGE_*`, `LAN_*` and
  `COORD_*` events.

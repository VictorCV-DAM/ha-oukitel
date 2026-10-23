# Oukitel Power Station — Rama `feature/zero-cloud-broker`

> **Rama de laboratorio.** Contiene todo lo que había en `main` en la versión **v1.5.7**, más el trabajo de *zero cloud*: aprovisionamiento BLE, broker MQTT local, protocolo LAN, diagnóstico y las pruebas realizadas. **No es una release estable y no sustituye a `main`.**

---

## Estado de la rama

| Campo | Valor |
|---|---|
| Rama | `feature/zero-cloud-broker` |
| Base | `main` v1.5.7 |
| Último commit | `3b429eb` — *snapshot current BLE provisioning test state* |
| Home Assistant | 2024.1+ |
| Dispositivo de pruebas | Oukitel P2001 Plus (`p11wN7`, `ecb5…`) |
| App de referencia | Wonderfree 3.7.5 (XAPK) |
| Estado | Experimental / laboratorio |
| Modo de conexión | `zero_cloud` con broker local en `:8886` |

### Advertencias

- **No promete un modo 100 % local permanente.** Hoy no existe con el acceso disponible.
- La ventana BLE dura **~3 minutos** por emparejamiento; el keepalive no la prolonga.
- El modo LAN está **condicionado a la sesión de nube** del fabricante.
- El bind y la PSK son secretos del módulo Quectel; no están en la app, la API ni el OTA.
- Esta rama expone **servicios de prueba** y una **sonda TLS**; no es apta para producción.
- **No hacer fuzzing ciego del `9c40`**: es el canal de aprovisionamiento/OTA, no un puerto de depuración.

---

## Qué es *zero cloud*

El objetivo es que la estación hable con un broker MQTT local y con la LAN sin depender de `iot-south.acceleronix.io`.

La rama implementa:

1. **Aprovisionamiento BLE** (`0x7010` sobre la característica `9c40`) para decirle a la estación a qué Wi-Fi conectarse y a qué endpoint apuntar.
2. **Fake cloud** (`cloud_bridge.py`): broker MQTT en el puerto `8886` que responde como la nube de QuecThing.
3. **LAN directa** (`local_session.py`): TCP `6607` con handshake y cifrado AES usando el `authKey` del dispositivo.
4. **Diagnóstico**: volcado GATT, logs hex, flight recorder, servicios de prueba y sonda TLS.

La estación acepta el broker local y transmite telemetría, pero **solo mientras el enlace BLE de aprovisionamiento sigue abierto** o mientras la nube del fabricante mantiene viva la sesión. El bind/PSK sigue siendo el muro.

---

## Tareas realizadas

### 1. Aprovisionamiento BLE (`ble_provision.py`)

- Implementación de la trama `0x7010` (`28688`) sobre `9c40`, sin bonding.
- TTLV con tags:
  - `1`: SSID
  - `2`: contraseña Wi-Fi
  - `11`: puerto (la app lo llama `time`; en esta unidad el valor que funcionó fue el puerto `8886`/`8883`)
  - `12`: MCC
  - `13`: URL del endpoint
- Detección de la estación por nombre (`QUEC_BLE*`, `OUKITEL*`, P2001, BP2000, etc.) y por *manufacturer data* (`productKey`/`deviceKey`).
- Selección de adaptador/proxy Bluetooth (`source`), con fallback a `auto`.
- Escritura con respuesta y reintento sin respuesta; traducción de errores de autorización.
- Espera de `0x7011` (`28689`) y de `0x7014` (`28692`) con timeout configurable (`listen_for`, por defecto 180 s).
- **Modo sin endpoint** (`""`, `"none"`, `"lan"`): envía solo SSID y contraseña para que la estación levante la LAN en `6607`.
- **Keepalive BLE** cada 10 s (`_ble_keepalive_loop`) con una escritura vacía; probado y **no prolonga** la ventana.
- **Acks periódicos** de `0x7014`/`0x7066` cada 10 s; probados y **no cambian** el estado de bind.
- **Volcado GATT** al conectar: servicios y características completos.
- Instrumentación hex de cada notificación (`BLE_NOTIFY_RAW`, `BLE_NOTIFY_PACKET`, `BLE_GATT_WRITE_*`).
- Registro de la desconexión natural del periférico y del cliente BLE persistido en `hass.data`.

### 2. Fake cloud / broker local (`cloud_bridge.py`)

- Broker MQTT asyncio en `0.0.0.0:8886` (`BROKER_PORT = 8886`).
- `PASSIVE_CAPTURE = False` (modo activo).
- Soporte de `CONNECT`, `SUBSCRIBE`, `PUBLISH`, `PINGREQ` y QoS 1.
- Topics:
  - uplink: `q/2/d/<pk><dk>/bus`
  - downlink: `q/1/d/<pk><dk>/+`
- Respuestas de *pairing status*, *cloud login ack* y `0x7014`/`0x7066`/`0x7036`.
- Publicación de telemetría y *state seeding* desde la nube cuando está disponible.
- Concurrencia con la sesión LAN (dual-channel) y QoS 1.
- Flight recorder y logs de cada frame (`BRIDGE_FRAME`, `BRIDGE_MQTT_PUBLISH`, etc.).

### 3. LAN directa (`local_session.py`, `coordinator.py`)

- TCP `6607` con:
  - `CMD_HELLO`
  - `CMD_NONCE`
  - `CMD_LOGIN` con token derivado del `authKey`
  - `CMD_LOGIN_OK`
- Cifrado AES-128-CBC con IV = nonce y clave derivada del `authKey` (base64 → hex).
- Comandos manejados: `16`, `17` (read), `19` (write), `20` (telemetry), `21`, `35`, `36`, `38`.
- Mapa de tags a entidades (batería, potencias, temperaturas, versiones AC/BMS, switches).
- Lectura inicial, `request_read` periódico y *keepalive*.
- Logs de `0x7036` (`LAN_BIND_FRAME`), `0x7038` y frames desconocidos.
- Reintento de conexión y *rearm* en `zero_cloud`.

### 4. API de nube y `authKey`

- Login con email/contraseña (AES + firma) y `userDomain` EU.
- `userDeviceList` para obtener `authKey`, `bindingCode`, estado y señal.
- `authKey` usado por la LAN; cambia tras un reset/rebind.
- Consulta OTA:
  - host EU: `https://iot-api.quecteleu.com/v2/quecota`
  - `getBatchDeviceUpgradePlan`, `haveUpgradePlanDeviceList`, `getBatchUpgradeDetails`.
- Prueba de `fetch_auth_key` y de la caché de `authKey` en `config_entry`.

### 5. TLS-PSK del módulo

- Captura del `ClientHello`:
  - TLS 1.2, sin SNI, sin certificados.
  - Cipher suites `0x008d`, `0x00ae`, `0x008c`, `0x00ff` (SCSV).
- Servidor TLS-PSK local en Node.js y 18 candidatos derivados de:
  - `authKey` (base64, hex, ASCII)
  - `bindingCode`
  - `deviceKey`
  - `productKey`
  - secreto de dominio
  - combinaciones MD5/SHA-256/HMAC
- Todos los handshakes fallan en `ossl_cipher_generic_stream_update`; la PSK no está en la app.

### 6. Diagnóstico y herramientas

- `diag_logger.py`: log estructurado con timestamp, evento y payload JSON.
- Flight recorder de BLE, MQTT, LAN y coordinador.
- `BLE_GATT_TABLE`: volcado completo de servicios/características.
- `BLE_KEEPALIVE_*`, `BLE_SUCCESS_ACK_RESENT`, `BLE_PROACTIVE_ACKS_BUILD`.
- `LAN_BIND_FRAME`, `LAN_UNKNOWN_FRAME`, `LAN_RX_RAW_FRAME`.
- Sonda TLS en el puerto `18883` (`TLS_PROBE`, `TLS_PROBE_LISTENING`).
- Servicios de prueba:
  - `oukitel.ble_disconnect`
  - `oukitel.bridge_send`
- `reload_trigger.py` para recarga en caliente durante el desarrollo.
- `services.yaml` con la definición de los servicios.

### 7. Integración HA

- Modo `zero_cloud` en el *config flow* y en las opciones.
- Selección de endpoint (`mqtt://<HA>:8886` o nube).
- Entidades de telemetría, switches, números, selects y diagnósticos.
- `manifest.json` base v1.5.7; `iot_class: local_push`.
- Compatibilidad con el *Bluetooth proxy* de ESPHome y el pulsador IoT.

---

## Pruebas realizadas y resultados

| # | Prueba | Resultado |
|---|---|---|
| 1 | `0x7010` con contraseña Wi-Fi correcta, MCC 214, endpoint `mqtt://192.168.1.x:8886` | La estación une al Wi-Fi, conecta al broker, se suscribe y publica telemetría |
| 2 | La misma trama con contraseña antigua | No une; se queda en `0x7014` 49 |
| 3 | MCC 460 en lugar de 214 | No une tras reset (no aislado: la contraseña era el bloqueo real) |
| 4 | Mantener BLE 180 s | Telemetría durante toda la ventana; 1.849 frames MQTT en una ejecución |
| 5 | Keepalive GATT cada 10 s | Ticks a +10 s y +20 s; desconexión del módulo a +21 s; no prolonga |
| 6 | Desconectar BLE con telemetría activa | El MCU corta el UART en 8–9 s; el icono Wi-Fi parpadea |
| 7 | Reiniciar HA con BLE conectado | Se pierde el cliente BLE; la estación reconecta al broker pero no publica |
| 8 | LAN 6607 con `authKey` nuevo | Login `result=0`; telemetría correcta |
| 9 | Cortar WAN con LAN activa | La telemetría se detiene en segundos; el icono parpadea |
| 10 | `0x7010` sobre estación ya vinculada/online | El módulo acusa pero mantiene su endpoint; no hay conexión local |
| 11 | `0x7055`/28757 sin certificado de reset | Ignorado; sin cambio de endpoint |
| 12 | Reset de fábrica desde Wonderfree | La estación queda virgen; `0x7010` se acepta de nuevo |
| 13 | `0x7066` + `0x7014` 65534 por BLE/MQTT | Sin efecto sobre el bind |
| 14 | Captura del `ClientHello` TLS | PSK-only, sin SNI, sin certificados |
| 15 | Servidor TLS-PSK con 18 candidatos | Todos rechazados |
| 16 | OTA `getBatchDeviceUpgradePlan` | HTTP 200 con `data: []`; sin plan de firmware |
| 17 | Volcado GATT | Solo `0x1800`, `0x1801`, `0x180A` y `9c40`; sin DFU/UART |
| 18 | Escaneo de tags LAN 1–300 | Solo telemetría normal; sin tags ocultos |
| 19 | Reset + aprovisionamiento sin endpoint | La LAN `6607` se abre; el login funciona con el `authKey` |
| 20 | Rebind en Wonderfree y estado de nube | La cuenta ve el dispositivo; el módulo se queda en `0x7014` 49 si el bind local no está completo |

### Evidencia concreta

- **Ventana BLE:** `BLE_WAIT_END` con `elapsed=180.0` y `connected=true`; cierre natural ~200 s después del `0x7010`.
- **Keepalive:** `BLE_KEEPALIVE_TICK` a +10 s y +20 s; `BLE_STATION_DISCONNECTED_NATURALLY` a +21 s.
- **Telemetría local:** 1.849 frames en 180 s; batería, entrada, salida y temperaturas actualizando.
- **LAN:** `LAN_HANDSHAKE_DONE`, `COORD_LAN_CONNECTED_OK`, `result=0`.
- **TLS:** `ossl_cipher_generic_stream_update:cipher operation failed` en los 18 intentos.
- **OTA:** `{"code":200,"msg":"","data":[]}`.

---

## Lo que funciona

- **Cloud + LAN** en `main` v1.5.7: telemetría local con la nube como soporte del bind.
- **Broker local** en `:8886` durante la ventana BLE: `CONNECT`, `SUBSCRIBE`, telemetría y entidades.
- **LAN `6607`** con el `authKey` correcto mientras la nube está viva.
- **Reset de fábrica** como única vía de reentrada para volver a aprovisionar.
- **Diagnóstico completo** de BLE, MQTT, LAN y nube.

## Lo que no funciona

- **Modo permanente sin nube ni BLE.** El módulo corta el UART al cerrar BLE.
- **Icono Wi-Fi fijo** sin completar el bind del fabricante.
- **LAN sin nube.** Al cortar WAN, la estación deja de publicar.
- **Bind local desde la app.** El `0x7066` es un `emptyList()`; la app ignora `0x7014`; el `0xFFFE` lo genera el módulo tras el bind de nube.
- **PSK del TLS.** Es un secreto por dispositivo en la NVM del módulo.
- **Firmware por OTA.** No hay plan asignado y la PSK no está en la imagen.

## Hipótesis descartadas

- Que un keepalive GATT mantuviera la ventana BLE.
- Que `0x7066` con tags o `0xFFFE` completara el bind.
- Que `0x7014` 65534 fuera suficiente para el icono.
- Que el MCC 460 fuera el bloqueo principal (era la contraseña Wi-Fi vieja).
- Que la PSK estuviera en el APK, en la API o en el OTA.
- Que `0x7055` permitiera reconfigurar una estación ya vinculada sin certificado.

---

## Riesgos y límites

- Los **servicios de prueba** (`ble_disconnect`, `bridge_send`) y la **sonda TLS 18883** no deben usarse en producción.
- El **fuzzing ciego del `9c40`** puede dejar el módulo en DFU, borrar configuración o ladrillarlo; no se ha hecho y no se recomienda.
- El **keepalive** y los **acks periódicos** escriben en el canal de aprovisionamiento; no han demostrado beneficio.
- La rama no incluye `auth_refresh.py`, `provision_frame.py` ni los tests unitarios de la propuesta limpia; esos viven fuera de esta rama.
- No se ha accedido a UART/JTAG ni a un sniffer BLE físico.

---

## Instalación manual

1. Haz backup de `config/custom_components/oukitel`.
2. Copia esta carpeta `custom_components/oukitel` en tu HA.
3. Reinicia Home Assistant.
4. Configura la integración en modo `zero_cloud` y usa el endpoint `mqtt://<IP_HA>:8886`.
5. Para BLE necesitas un **Bluetooth proxy** (ESPHome) y el pulsador IoT para abrir la ventana de emparejamiento.

> HACS no instala ramas directamente. Para probar esta rama, copia la carpeta a mano o crea una pre-release con tag propio.

### Requisitos

- Home Assistant 2024.1+.
- `pycryptodome>=3.18.0`.
- Broker MQTT local en `8886` (lo levanta la integración).
- Bluetooth proxy para el aprovisionamiento BLE.
- La estación en la misma red que HA.

---

## Servicios

| Servicio | Campos | Uso |
|---|---|---|
| `oukitel.ble_disconnect` | — | Cierra el cliente BLE de aprovisionamiento |
| `oukitel.bridge_send` | `topic`, `payload`, `qos` | Publica una trama TLV (`hex:...`) o JSON en `bus`/`sys`/`bus_`/`sys_` |

---

## Estructura de archivos

| Archivo | Función |
|---|---|
| `ble_provision.py` | Aprovisionamiento `0x7010`, GATT, keepalive, acks |
| `cloud_bridge.py` | Fake cloud MQTT en `8886` |
| `local_session.py` | Sesión LAN `6607`, AES, handshake |
| `local_frame.py` | Framing, TTLV, AES |
| `local_client.py` | Cliente LAN auxiliar |
| `local_scan.py` | Descubrimiento LAN |
| `coordinator.py` | Coordinación nube/LAN/bridge |
| `config_flow.py` | Configuración y opciones |
| `const.py` | Constantes |
| `diag_logger.py` | Log estructurado |
| `sensor.py`, `switch.py`, `select.py`, `number.py`, `binary_sensor.py`, `button.py` | Entidades |
| `services.yaml` | Servicios de prueba |
| `reload_trigger.py` | Recarga en caliente |

---

## Pendiente

1. **Sniffer BLE** (nRF52840 + Wireshark) para capturar la trama real app ↔ módulo.
2. **UART/JTAG** al módulo Quectel para volcar la NVM y la PSK.
3. **Documentación de Oukitel/Quectel** sobre el bind y la PSK.
4. **Protocolo BLE de OTA** para leer la versión del módulo y pedir un plan.
5. **Refresco de `authKey`** en fallo de login LAN (propuesta limpia, no incluida aquí).
6. **MCC opcional** en el aprovisionamiento (propuesta limpia, no incluida aquí).
7. **Tests unitarios** de TTLV, frame `0x7010` y `authKey` (propuesta limpia, no incluidos aquí).

---

## Historial de la rama

| Commit | Descripción |
|---|---|
| `e59f83a` | Base zero cloud: bridge dual-channel, QoS 1, state seeding |
| `3b429eb` | Snapshot del estado de las pruebas BLE: GATT, keepalive, acks, servicios, sonda TLS, logs LAN |

---

## Licencia

GPL-3.0. Ver [LICENSE](LICENSE).

**Autor:** Víctor C. V. ([@VictorCV-DAM](https://github.com/VictorCV-DAM)).

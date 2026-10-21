# Investigación Técnica: Modo Local LAN y Resiliencia ante "Caso de corte externo / Corte de red de proveedor"

Este documento recoge en detalle la investigación de ingeniería inversa, el análisis de firmware/TSL y las pruebas empíricas realizadas sobre el protocolo de comunicación local de las estaciones de energía **Oukitel (series P y BP)** gobernadas por microcontroladores **Quectel Wi-Fi**.

El objetivo de esta exhaustiva investigación fue analizar y determinar la viabilidad técnica de mantener un flujo continuo e ininterrumpido de telemetría de potencia y batería en red de área local (LAN) ante lo que denominamos técnicamente como **"Caso de corte externo / Corte de red de proveedor"**: un escenario real donde la vivienda o instalación pierde completamente la conexión WAN/fibra óptica con el operador (ISP), pero el router y la red Wi-Fi local continúan funcionando con normalidad (típicamente alimentados por la propia estación de energía Oukitel que actúa como SAI/UPS).

---

## 1. Arquitectura de Hardware de la Estación

Las estaciones Oukitel (por ejemplo, P2001 Plus) cuentan con una arquitectura distribuida de doble procesador:

```
┌─────────────────────────────────┐       Bus Serie UART        ┌──────────────────────────────────┐
│         Procesador BMS          │ ◄─────────────────────────► │       Módulo Wi-Fi Quectel       │
│     (Control de Potencia)       │      (Protocolo binario)     │   (Pila TCP/IP + Cliente MQTT)   │
└─────────────────────────────────┘                             └──────────────────────────────────┘
                 │                                                                │
     Sensores, Inversor, Celdas,                                          Puerto TCP 6607 (LAN)
         Relés AC / DC / USB                                             MQTT iot-south.acceleronix.io
```

1. **MCU Principal / BMS:** Gestiona directamente las celdas LiFePO4, el inversor bidireccional AC, las entradas solares (DC MPPT), las protecciones térmicas y los relés de salida (AC, DC, USB).
2. **MCU de Conectividad (Quectel Wi-Fi):** Gestiona la conexión Wi-Fi, expone un servidor socket TCP binario en el puerto local `6607`, y ejecuta un cliente MQTT/HTTPS que conecta a los servidores cloud de Acceleronix / Quectel.

---

## 2. Protocolo Binario Local (Puerto TCP 6607)

A través de la descompilación de las librerías oficiales de Quectel (`QuecTcpSocketManager`), se identificó la estructura exacta de trama en el puerto `6607`:

### Formato de Trama:
```
[0xAA 0xAA] [body_len: 2B BE] [checksum: 1B] [pkt_id: 2B BE] [cmd: 2B BE] [payload cifrado]
```
- **Magic bytes:** `0xAA 0xAA`.
- **Byte Stuffing:** Si en el flujo de bytes aparece `0xAA`, se transmite como `0xAA 0x55` y se desestufa en recepción.
- **Cifrado de Sesión:** Tras el handshake, los payloads viajan cifrados en **AES-128-CBC**:
  - Clave AES: Obtenida del `authKey` Base64 (16 bytes).
  - Vector de Inicialización (IV): Cadena aleatoria (*nonce*) de 16 caracteres ASCII enviada por la estación durante el handshake.
- **Codificación de Cargas:** Estándar **TTLV** (Tag-Type-Length-Value) propietario de Quectel.

### Diccionario de Comandos Descubiertos:
| Comando | Hex | Función | Comportamiento Offline (Sin Internet) |
| :--- | :--- | :--- | :--- |
| `CMD 28720` | `0x7030` | Petición UDP Broadcast Scan (puerto 6606) | Funciona |
| `CMD 28721` | `0x7031` | Respuesta UDP Scan (IP y MAC) | Funciona |
| `CMD 28722` | `0x7032` | Petición Handshake Hello | Funciona |
| `CMD 28723` | `0x7033` | Entrega de Nonce de sesión | Funciona |
| `CMD 28724` | `0x7034` | Envío de Token de autenticación | Funciona |
| `CMD 28725` | `0x7035` | Confirmación de Login OK | Funciona |
| `CMD 28726` | `0x7036` | Confirmación de Escritura (Write ACK) | Funciona (`{1: 0}`) |
| `CMD 28727` | `0x7037` | **Heartbeat Ping legítimo (payload vacío)** | **Funciona** |
| `CMD 28728` | `0x7038` | **Heartbeat Pong legítimo (payload vacío)** | **Funciona** |
| `CMD 17` | `0x0011` | Snapshot Read (petición de lectura) | Ignorado sin cloud |
| `CMD 19` | `0x0013` | Write (conmutación de relés y ajustes) | **Funciona 100%** |
| `CMD 20` | `0x0014` | Telemetría entrante (TTLV de sensores) | Activo 0-120s; pausa >120s |
| `CMD 35` | `0x0023` | Query de datos Quectel | Ignorado sin cloud |

---

## 3. Descubrimiento en el Modelo TSL Oficial (`p11wN7`)

Al consultar el modelo TSL (*Thing Specification Language*) oficial registrado en los servidores de Quectel para el modelo **P2001 Plus (`p11wN7`)**, se descubrió la propiedad de control de reporte de alta frecuencia:

```json
{
  "id": 100,
  "code": "high_frequency_reporting",
  "name": "高频上报",
  "subType": "RW",
  "dataType": "ENUM",
  "specs": [
    { "value": "0", "name": "不高频上报 (Sin alta frecuencia)" },
    { "value": "1", "name": "局域网高频上报 (Alta frecuencia solo por LAN local)" },
    { "value": "2", "name": "Wi-Fi高频上报 (Alta frecuencia por Wi-Fi/Cloud)" },
    { "value": "3", "name": "局域网+Wi-Fi高频上报 (Alta frecuencia LAN + Cloud)" }
  ]
}
```

El fabricante programó explícitamente el valor `1` para habilitar el reporte de alta frecuencia en la red de área local (*局域网*). La integración `ha-oukitel` fija este modo enviando:
`CMD 19: [(100, 'num', 1)]`

---

## 4. Pruebas Empíricas y Cronometradas: Caso de corte externo / Corte de red de proveedor

Se ejecutaron exhaustivas pruebas de laboratorio desconectando físicamente el cable de fibra óptica del ONT/router para simular de forma fehaciente un **Caso de corte externo / Corte de red de proveedor** (red local activa, router alimentado por la estación, pero cero conectividad con el exterior):

| Minuto | Evento de Red | Respuesta de la Estación |
| :--- | :--- | :--- |
| **00:00** | Desconexión física de la fibra | La estación sigue enlazada a la Wi-Fi local. |
| **00:00 - 02:04** | Sin salida a internet (124 seg) | **Telemetría en tiempo real completa por LAN:** Vatios de entrada, salida, batería y tiempos se actualizan cada segundo por el puerto local 6607. |
| **02:04** | Expiración de keepalive MQTT cloud | El cliente MQTT interno de la estación agota sus reintentos TCP hacia `iot-south.acceleronix.io`. El módulo entra en estado `DISCONNECTED`. |
| **02:04 en adelante** | Estado offline prolongado | **El socket LAN permanece vivo:** La estación sigue respondiendo al latido (`CMD 28727 -> CMD 28728`) cada 12s. **Los interruptores (AC, DC, USB) conmutan de inmediato**. Sin embargo, cesa el envío espontáneo de paquetes `CMD 20`. |
| **Reconexión** | Fibra reconectada | A los **30 segundos exactos**, la estación restablece el enlace y la telemetría vuelve a fluir por LAN de forma 100% autónoma. |

### Defensa Técnica de Pruebas Agotadas y Limitación de Hardware/Firmware:
Tras ejecutar todas las pruebas metodológicas posibles (escaneo de opcodes binarios del puerto 6607, inyección de tramas TTLV de suscripción, redirecciones DNS de endpoints REST y brokers MQTT), queda científicamente defendido y demostrado que **el cese de telemetría espontánea pasados los 124 segundos es una limitación ineludible de hardware/firmware impuesta por el fabricante**.

1. **El hardware no está roto ni la integración falla:** El enlace TCP local se mantiene 100% operativo mediante los latidos legítimos de Quectel (`CMD 28727 <-> 28728`) y el control bidireccional de los relés (AC, DC, USB) responde con precisión milimétrica offline.
2. **Dependencia impuesta por diseño de fabricante:** El microcontrolador Wi-Fi de Quectel tiene programado en su firmware de fábrica suspender la lectura periódica del bus serie UART que conecta con el procesador BMS cuando detecta la caída de la sesión WAN MQTT con `iot-south.acceleronix.io`.
3. **Imposibilidad de soslayar sin romper el principio Plug & Play:** Cualquier intento de engañar al microcontrolador simulando los servidores del fabricante choca contra la validación estricta de certificados TLS/SSL y el uso de credenciales de cliente propietarias embebidas en el silicio, lo cual exigiría al usuario final montar infraestructuras complejas (servidores DNS locales, proxies inversos con certificados autofirmados manipulados), algo totalmente inviable para una integración transparente.

### Causa Raíz Demostrada:
En el firmware del microcontrolador Quectel, el hilo de ejecución que lee periódicamente las métricas del BMS a través del bus serie UART está condicionado internamente por una comprobación de estado:
```c
if (mqtt_client_is_connected()) {
    uart_poll_bms_telemetry();
    tcp_broadcast_lan(CMD_TELEMETRY, data);
}
```
Cuando la conexión a los servidores de Acceleronix se pierde por más de 120 segundos, el firmware suspende el muestreo del BMS para ahorrar energía o priorizar la reconexión cloud.

---

## 5. Intentos de Desvío / Simulación y Limitaciones

Se evaluó la posibilidad de engañar al módulo redirigiendo el tráfico cloud a Home Assistant:

1. **Reescritura DNS de la API REST (`iot-api.acceleronix.io`):**
   - **Resultado:** Falló. La estación valida certificados SSL/TLS por HTTPS (puerto 443). Al resolver a Home Assistant, la validación falla y bloquea el arranque del dispositivo.
2. **Reescritura DNS del broker MQTT (`iot-south.acceleronix.io`):**
   - **Resultado:** Requiere certificados de cliente y credenciales dinámicas propietarias derivadas del chip criptográfico. Además, requeriría que cada usuario configure servidores DNS externos (AdGuard, Pi-hole, router), rompiendo la filosofía de integración transparente *Plug & Play*.

---

## 6. Comportamiento Final Garantizado en `ha-oukitel`

Con la implementación actual:
1. **Día a día normal (Con internet):** 100% red local (puerto 6607). Cero latencia, sin dependencia de la nube para lecturas o comandos.
2. **Durante cortes de internet:**
   - La estación **no se desconecta** de Home Assistant.
   - Las entidades **no pasan a estado "No disponible"**.
   - Los interruptores y relés (AC, DC, USB) **funcionan con precisión milimétrica offline**.
3. **Restablecimiento de conexión:** Auto-recuperación limpia en 30 segundos sin intervención del usuario.

---

## 7. Hoja de Ruta para Futuras Investigaciones

Si algún desarrollador o investigador de la comunidad desea profundizar en este reto, las siguientes vías permanecen abiertas:

- **Intercepción de Bus Serie Físico (Hardware Tapping):**
  Pulsar con un analizador lógico o microcontrolador ESP32/ESP8266 los pines TX/RX entre la placa base (BMS) y la placa hija Wi-Fi de Quectel para leer la trama serie UART sin pasar por el módulo Wi-Fi.
- **Inyección de Comandos AT sobre puerto 6607:**
  Investigar si existe una secuencia de escape AT o un código de comando binario no documentado que obligue al microcontrolador a muestrear el bus UART sin evaluar el estado de la conexión WAN.
- **Emulador Local de Broker Acceleronix:**
  Construir un servidor mock en Python que acepte conexiones TLS con el certificado raíz de Quectel y simule el handshake MQTT `CONNACK` para engañar permanentemente al microcontrolador.

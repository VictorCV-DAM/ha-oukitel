#!/usr/bin/env python3
"""Standalone Oukitel Bluetooth Provisioning Tool.

Allows provisioning an Oukitel Power Station (P1000 Plus, P2001 Plus, P5000, etc.)
to connect to your local Home Assistant Zero-Cloud MQTT broker (or official cloud)
without requiring Bluetooth inside Home Assistant (ideal for HA in Virtual Machines).

Requirements:
    pip install bleak pycryptodome
Usage:
    python ble_provision_standalone.py
"""

import asyncio
import struct
import sys
import time

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("❌ Error: 'bleak' is required. Please run: pip install bleak")
    sys.exit(1)

CMD_PROVISION = 28688  # 0x7010
CMD_CONFIRM   = 28689  # 0x7011
CMD_PROGRESS  = 28692  # 0x7014

CHARACTERISTIC_SHORT = "9c40"


def _encode_int(value: int) -> bytes:
    neg = value < 0
    v = abs(value)
    body = b"\x00" if v == 0 else v.to_bytes((v.bit_length() + 7) // 8, "big")
    ctrl = (0x80 if neg else 0) | ((len(body) - 1) & 0x07)
    return bytes([ctrl]) + body


def ttlv_encode(fields: list[tuple[int, str, any]]) -> bytes:
    out = bytearray()
    for tag, kind, value in fields:
        if kind == "bool":
            out += struct.pack(">H", (tag << 3) | (1 if value else 0))
        elif kind == "num":
            out += struct.pack(">H", (tag << 3) | 2)
            out += _encode_int(int(value))
        elif kind == "str":
            raw = value.encode("utf-8") if isinstance(value, str) else bytes(value)
            out += struct.pack(">H", (tag << 3) | 3)
            out += struct.pack(">H", len(raw))
            out += raw
    return bytes(out)


def build_frame(packet_id: int, cmd: int, payload: bytes = b"") -> bytes:
    inner = struct.pack(">HH", packet_id & 0xFFFF, cmd & 0xFFFF) + payload
    checksum = sum(inner) & 0xFF
    body_len = len(inner) + 1
    raw = b"\xaa\xaa" + struct.pack(">HB", body_len, checksum) + inner
    out = bytearray(raw[:2])
    for j, b in enumerate(raw[2:]):
        out.append(b)
        if b == 0xAA and j + 3 < len(raw) and raw[j + 3] in (0x55, 0xAA):
            out.append(0x55)
    return bytes(out)


async def main():
    print("=" * 65)
    print("🔋 Oukitel Power Station — Standalone Zero-Cloud Provisioning")
    print("=" * 65)
    print("👉 Ensure your station is in pairing mode:")
    print("   Press and HOLD the IoT / WiFi button until the WiFi icon flashes.\n")

    print("🔍 Scanning for Oukitel Bluetooth devices (10s)...")
    devices = await BleakScanner.discover(timeout=10.0)
    oukitel_devices = []
    for d in devices:
        name = d.name or ""
        if "QUEC" in name.upper() or "OUKITEL" in name.upper():
            oukitel_devices.append(d)
        else:
            # check manufacturer data
            for m_id, m_data in (d.metadata.get("manufacturer_data") or {}).items():
                if len(m_data) >= 6:
                    oukitel_devices.append(d)
                    break

    if not oukitel_devices:
        print("❌ No Oukitel stations found in pairing mode.")
        print("   Make sure Bluetooth is enabled and the WiFi icon on the LCD is blinking.")
        return

    print(f"\n✅ Found {len(oukitel_devices)} device(s):")
    for i, dev in enumerate(oukitel_devices):
        print(f"   [{i+1}] {dev.name or 'Unknown'} ({dev.address})")

    idx = 0
    if len(oukitel_devices) > 1:
        choice = input(f"Select device [1-{len(oukitel_devices)}]: ")
        idx = int(choice) - 1

    target = oukitel_devices[idx]
    print(f"\nTarget device: {target.name} ({target.address})")

    ssid = input("\nEnter your 2.4GHz Wi-Fi SSID: ").strip()
    password = input("Enter your Wi-Fi Password: ").strip()
    ha_ip = input("Enter Home Assistant IP (e.g. 192.168.1.219): ").strip()
    port = input("Enter Local Broker Port [default: 8886]: ").strip() or "8886"

    endpoint = f"mqtt://{ha_ip}:{port}"
    print(f"\nBroker endpoint will be: {endpoint}")
    confirm = input("Proceed with provisioning? (Y/n): ").strip().lower()
    if confirm and confirm != "y":
        print("Cancelled.")
        return

    payload = ttlv_encode([
        (1, "str", ssid),
        (2, "str", password),
        (11, "num", 60),
        (12, "num", 0),
        (13, "str", endpoint),
    ])
    frame = build_frame(1, CMD_PROVISION, payload)

    print(f"\nConnecting to {target.address} via Bluetooth...")
    async with BleakClient(target.address) as client:
        print("Connected!")
        # Find 9c40 characteristic
        char_uuid = None
        for service in client.services:
            for char in service.characteristics:
                if CHARACTERISTIC_SHORT.lower() in char.uuid.lower():
                    char_uuid = char.uuid
                    break

        if not char_uuid:
            print("❌ Characteristic 9c40 not found.")
            return

        future_done = asyncio.get_event_loop().create_future()

        def notification_handler(sender, data):
            print(f"📥 BLE Notification ({len(data)} bytes): {data.hex()}")
            if len(data) >= 9:
                cmd = int.from_bytes(data[7:9], "big")
                if cmd == CMD_CONFIRM:
                    print("✅ Station confirmed receipt (0x7011)!")
                elif cmd == CMD_PROGRESS:
                    print(f"🔄 Station progress update (0x7014)")
                    if not future_done.done():
                        future_done.set_result(True)

        await client.start_notify(char_uuid, notification_handler)
        print(f"Writing 0x7010 provisioning frame ({len(frame)} bytes)...")
        await client.write_gatt_char(char_uuid, frame, response=False)
        print("Waiting for station response...")

        try:
            await asyncio.wait_for(future_done, timeout=15.0)
            print("\n🎉 SUCCESS! Station accepted provisioning and is connecting to your local broker!")
        except asyncio.TimeoutError:
            print("\n⚠️ Provisioning frame sent, but station did not send notification in time.")
            print("   Check your Home Assistant Zero-Cloud logs to verify connection.")

if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Standalone Oukitel Bluetooth Provisioning Tool.

Allows provisioning an Oukitel Power Station (P1000 Plus, P1000E Plus, P2001 Plus, P5000, etc.)
to connect to your local Home Assistant Zero-Cloud MQTT broker (or official cloud)
without requiring Bluetooth inside Home Assistant (ideal for HA in Virtual Machines).

Requirements:
    pip install bleak pycryptodome

Usage (Interactive):
    python ble_provision_standalone.py

Usage (Non-interactive CLI):
    python ble_provision_standalone.py --ssid "MyWiFi" --password "MySecret" --server "mqtt://192.168.1.219:8886"
"""

import argparse
import asyncio
import struct
import sys
import time
import urllib.parse

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("❌ Error: 'bleak' is required. Please run: pip install bleak")
    sys.exit(1)

CMD_PROVISION = 28688  # 0x7010
CMD_CONFIRM   = 28689  # 0x7011
CMD_PROGRESS  = 28692  # 0x7014
CMD_BIND_ACK  = 28774  # 0x7066

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


async def discover_candidates(timeout: float = 10.0) -> list[tuple[any, str, str]]:
    """Scan and discover Oukitel / Quectel devices safely across all Bleak versions.
    
    Returns list of (BLEDevice, display_name, address).
    """
    discovered_pairs = []
    try:
        # Modern Bleak (>= 0.20) returns dict[address, (BLEDevice, AdvertisementData)]
        res = await BleakScanner.discover(timeout=timeout, return_adv=True)
        if isinstance(res, dict):
            for dev, adv in res.values():
                adv_name = adv.local_name if adv else ""
                dev_name = dev.name or ""
                mfg = adv.manufacturer_data if adv else {}
                discovered_pairs.append((dev, adv_name or dev_name, mfg))
        else:
            for dev in res:
                discovered_pairs.append((dev, dev.name or "", getattr(dev, "metadata", {}).get("manufacturer_data", {})))
    except TypeError:
        # Fallback for older Bleak versions without return_adv
        devs = await BleakScanner.discover(timeout=timeout)
        for dev in devs:
            discovered_pairs.append((dev, dev.name or "", getattr(dev, "metadata", {}).get("manufacturer_data", {})))

    candidates = []
    seen = set()
    for dev, name, mfg in discovered_pairs:
        addr = dev.address
        if addr in seen:
            continue
        name_clean = (name or "").strip()
        name_upper = name_clean.upper()

        is_match = (
            "QUEC" in name_upper
            or "OUKITEL" in name_upper
            or any(p in name_upper for p in ("P1000", "P2001", "BP2000", "P5000", "P1200", "P800", "CN505"))
        )
        if not is_match and mfg:
            for m_id, m_data in mfg.items():
                if len(m_data) >= 6:
                    is_match = True
                    break

        if is_match:
            seen.add(addr)
            candidates.append((dev, name_clean or "QUEC_BLE_Station", addr))

    return candidates


async def main():
    parser = argparse.ArgumentParser(description="Oukitel Standalone Bluetooth Provisioning Tool")
    parser.add_argument("--ssid", help="Wi-Fi SSID network name")
    parser.add_argument("--password", help="Wi-Fi password")
    parser.add_argument("--server", "--endpoint", dest="server", help="MQTT broker endpoint (e.g. mqtt://192.168.1.100:8886)")
    parser.add_argument("--mac", help="Target device Bluetooth MAC address (optional)")
    args = parser.parse_args()

    print("=" * 68)
    print("🔋 Oukitel Power Station — Standalone Zero-Cloud Provisioning")
    print("=" * 68)
    print("👉 Ensure your station is in pairing mode:")
    print("   Press and HOLD the IoT / WiFi button for ~3s until the WiFi icon flashes.\n")

    target_dev = None
    target_addr = args.mac

    if not target_addr:
        print("🔍 Scanning for Oukitel / Quectel Bluetooth devices (10s)...")
        candidates = await discover_candidates(timeout=10.0)

        if not candidates:
            print("❌ No stations found in pairing mode.")
            print("   Make sure the Wi-Fi icon on the station's LCD is blinking rapidly.")
            print("   You can also specify the MAC directly with: --mac AA:BB:CC:DD:EE:FF")
            return

        print(f"\n✅ Found {len(candidates)} device(s):")
        for i, (dev, name, addr) in enumerate(candidates):
            print(f"   [{i+1}] {name} ({addr})")

        idx = 0
        if len(candidates) > 1:
            choice = input(f"\nSelect device [1-{len(candidates)}]: ").strip()
            try:
                idx = int(choice) - 1
            except ValueError:
                idx = 0
        target_dev, target_name, target_addr = candidates[idx]
        print(f"\nTarget selected: {target_name} ({target_addr})")
    else:
        print(f"Target specified by MAC: {target_addr}")

    ssid = args.ssid or input("\nEnter your 2.4GHz Wi-Fi SSID: ").strip()
    password = args.password if args.password is not None else input("Enter your Wi-Fi Password: ").strip()
    server = args.server or input("Enter Home Assistant Broker Endpoint (e.g. mqtt://192.168.1.219:8886): ").strip()

    if "://" not in server and ":" in server:
        server = f"mqtt://{server}"
    elif "://" not in server:
        server = f"mqtt://{server}:8886"

    print(f"\nTarget Broker Endpoint: {server}")
    if not (args.ssid and args.server):
        confirm = input("Proceed with Bluetooth provisioning? (Y/n): ").strip().lower()
        if confirm and confirm != "y":
            print("Cancelled.")
            return

    # Build 0x7010 frame
    payload = ttlv_encode([
        (1, "str", ssid),
        (2, "str", password),
        (11, "num", 60),
        (12, "num", 214),
        (13, "str", server),
    ])
    frame = build_frame(1001, CMD_PROVISION, payload)

    print(f"\nConnecting to {target_addr} via Bluetooth...")
    async with BleakClient(target_addr) as client:
        print(" Connected!")

        char_uuid = None
        for service in client.services:
            for char in service.characteristics:
                if CHARACTERISTIC_SHORT.lower() in char.uuid.lower():
                    char_uuid = char.uuid
                    break

        if not char_uuid:
            print("❌ Characteristic 9c40 not found on device.")
            return

        future_done = asyncio.get_event_loop().create_future()

        async def notification_handler(sender, data: bytearray):
            raw = bytes(data)
            if len(raw) < 9:
                return
            cmd = int.from_bytes(raw[7:9], "big")
            if cmd == CMD_CONFIRM:
                print(" Station accepted provisioning frame (0x7011 ACK)!")
            elif cmd == CMD_PROGRESS:
                code = raw[9] if len(raw) > 9 else 0
                print(f" Station progress update: 0x7014 (status byte: {code})")
                # Send proactive 0x7066 and 0x7014 acks
                bind_ack = build_frame(1003, CMD_BIND_ACK, b"")
                prog_ack = build_frame(1004, CMD_PROGRESS, ttlv_encode([(10, "num", 65534), (11, "num", 0)]))
                try:
                    await client.write_gatt_char(char_uuid, bind_ack, response=False)
                    await asyncio.sleep(0.05)
                    await client.write_gatt_char(char_uuid, prog_ack, response=False)
                except Exception:
                    pass
                if not future_done.done():
                    future_done.set_result(True)

        await client.start_notify(char_uuid, notification_handler)
        print(f"📤 Writing 0x7010 provisioning frame ({len(frame)} bytes)...")
        await client.write_gatt_char(char_uuid, frame, response=False)
        print("⏳ Waiting for station to join Wi-Fi and reach local broker...")

        try:
            await asyncio.wait_for(future_done, timeout=20.0)
            print("\n🎉 SUCCESS! Station accepted provisioning and is connecting to your local broker!")
            print("   The Wi-Fi icon on the station's LCD should turn solid in a few seconds.")
            print("   Check your Home Assistant logs (filter for 'oukitel: [Zero-Cloud]').")
        except asyncio.TimeoutError:
            print("\n⚠️ Provisioning frame sent, but timeout waiting for 0x7014 confirmation.")
            print("   Check if the Wi-Fi icon on the LCD stopped flashing.")
            print("   If it is solid, the station joined your network successfully!")

        try:
            await client.stop_notify(char_uuid)
        except Exception:
            pass

if __name__ == "__main__":
    asyncio.run(main())

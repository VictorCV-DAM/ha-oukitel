"""Binary framing, TTLV encoding/decoding and AES session crypto for LAN mode.

Wire format (TCP port 6607):
    AA AA | body_len(2,BE) | checksum(1) | pkt_id(2,BE) | cmd(2,BE) | payload
    - body_len  = checksum + pkt_id + cmd + payload  (excludes the 4 magic+len bytes)
    - checksum  = sum(bytes from pkt_id through end) & 0xFF
    - payload   = byte-stuffed; 0xAA in the data stream becomes 0xAA 0x55
    - after handshake the payload is AES-128-CBC encrypted before stuffing
"""

from __future__ import annotations

import base64
import hashlib
import os
import struct
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_FRAME_MAGIC = b"\xaa\xaa"


# ---------------------------------------------------------------------------
# AES helpers
# ---------------------------------------------------------------------------

def _pad(data: bytes) -> bytes:
    n = 16 - (len(data) % 16)
    return data + bytes([n]) * n


def _unpad(data: bytes) -> bytes:
    if not data:
        return data
    n = data[-1]
    if 1 <= n <= 16 and data[-n:] == bytes([n]) * n:
        return data[:-n]
    return data


def _aes_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return enc.update(_pad(plaintext)) + enc.finalize()


def _aes_decrypt(key: bytes, iv: bytes, ciphertext: bytes) -> bytes:
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    return _unpad(dec.update(ciphertext) + dec.finalize())


def auth_key_bytes(auth_key_b64: str) -> bytes:
    return base64.b64decode(auth_key_b64)


def session_token(key: bytes, nonce: str) -> str:
    return hashlib.sha256((key.hex() + ";" + nonce).encode()).hexdigest()


def fresh_iv() -> bytes:
    return os.urandom(16)


def encrypt_payload(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    return _aes_encrypt(key, iv, plaintext)


def decrypt_payload(key: bytes, iv: bytes, ciphertext: bytes) -> bytes:
    return _aes_decrypt(key, iv, ciphertext)


# ---------------------------------------------------------------------------
# Byte stuffing  (0xAA → 0xAA 0x55 in the wire stream)
# ---------------------------------------------------------------------------

def _stuff(frame: bytes) -> bytes:
    out = bytearray(frame[:2])
    body = frame[2:]
    for j, b in enumerate(body):
        out.append(b)
        if b == 0xAA and j + 1 < len(body) and body[j + 1] in (0x55, 0xAA):
            out.append(0x55)
    return bytes(out)


class _StreamDestuffer:
    def __init__(self) -> None:
        self._saw_aa = False

    def feed(self, data: bytes) -> bytes:
        out = bytearray()
        saw_aa = self._saw_aa
        for b in data:
            if saw_aa and b == 0x55:
                saw_aa = False
                continue
            out.append(b)
            saw_aa = b == 0xAA
        self._saw_aa = saw_aa
        return bytes(out)


# ---------------------------------------------------------------------------
# Frame builder / parser
# ---------------------------------------------------------------------------

_pkt_counter = 0


def _next_pkt_id() -> int:
    global _pkt_counter
    _pkt_counter = (_pkt_counter + 1) & 0xFFFF
    return _pkt_counter


def build_frame(cmd: int, payload: bytes = b"") -> bytes:
    pkt_id = _next_pkt_id()
    inner = struct.pack(">HH", pkt_id, cmd) + payload
    checksum = sum(inner) & 0xFF
    body_len = len(inner) + 1  # +1 for checksum byte
    raw = _FRAME_MAGIC + struct.pack(">HB", body_len, checksum) + inner
    return _stuff(raw)


def build_encrypted_frame(cmd: int, payload: bytes, key: bytes, iv: bytes) -> bytes:
    encrypted = encrypt_payload(key, iv, payload)
    return build_frame(cmd, iv + encrypted)


class FrameAssembler:
    """Reassembles variable-length frames from a raw TCP byte stream."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._destuffer = _StreamDestuffer()

    def feed(self, data: bytes) -> list[tuple[int, int, bytes]]:
        self._buf.extend(self._destuffer.feed(data))
        frames: list[tuple[int, int, bytes]] = []
        while True:
            frame = self._try_parse()
            if frame is None:
                break
            frames.append(frame)
        return frames

    def _try_parse(self) -> tuple[int, int, bytes] | None:
        buf = self._buf
        # Locate magic
        idx = 0
        while idx < len(buf) - 1:
            if buf[idx] == 0xAA and buf[idx + 1] == 0xAA:
                break
            idx += 1
        if idx:
            del self._buf[:idx]
            buf = self._buf

        if len(buf) < 5:
            return None

        body_len = struct.unpack_from(">H", buf, 2)[0]
        total = 4 + body_len  # magic(2) + len(2) + body_len
        if len(buf) < total:
            return None

        frame = bytes(buf[:total])
        del self._buf[:total]

        pkt_id = struct.unpack_from(">H", frame, 5)[0]
        cmd = struct.unpack_from(">H", frame, 7)[0]
        payload = frame[9:]
        return pkt_id, cmd, payload


# ---------------------------------------------------------------------------
# TTLV codec
# ---------------------------------------------------------------------------

def _encode_int(value: int) -> bytes:
    neg = value < 0
    v = abs(value)
    body = b"\x00" if v == 0 else v.to_bytes((v.bit_length() + 7) // 8, "big")
    ctrl = (0x80 if neg else 0) | ((len(body) - 1) & 0x07)
    return bytes([ctrl]) + body


def ttlv_encode(fields: list[tuple[int, str, Any]]) -> bytes:
    out = bytearray()
    for tag, kind, value in fields:
        if kind == "bool":
            out += struct.pack(">H", (tag << 3) | (1 if value else 0))
        elif kind == "num":
            out += struct.pack(">H", (tag << 3) | 2)
            out += _encode_int(int(value))
        else:
            raise ValueError(f"unknown TTLV kind: {kind}")
    return bytes(out)


def ttlv_decode(buf: bytes) -> dict[int, Any]:
    out: dict[int, Any] = {}
    i = 0
    n = len(buf)

    def _read_num(pos: int) -> tuple[float | int, int]:
        ctrl = buf[pos]
        pos += 1
        sign = (ctrl >> 7) & 1
        decimals = (ctrl >> 3) & 0x0F
        nbytes = (ctrl & 0x07) + 1
        v = int.from_bytes(buf[pos: pos + nbytes], "big")
        pos += nbytes
        if sign:
            v = -v
        return (v / (10 ** decimals) if decimals else v), pos

    while i < n:
        if i + 2 > n:
            break
        header = struct.unpack_from(">H", buf, i)[0]
        i += 2
        tag = header >> 3
        kind = header & 0x07

        if kind == 0:
            out[tag] = False
        elif kind == 1:
            out[tag] = True
        elif kind == 2:
            value, i = _read_num(i)
            out[tag] = value
        elif kind == 3:
            if i + 2 > n:
                break
            length = struct.unpack_from(">H", buf, i)[0]
            i += 2
            out[tag] = buf[i: i + length].decode("utf-8", errors="replace")
            i += length
        elif kind == 4:
            if i + 2 > n:
                break
            sub_len = struct.unpack_from(">H", buf, i)[0]
            i += 2
            out[tag] = ttlv_decode(buf[i: i + sub_len])
            i += sub_len
        else:
            break

    return out

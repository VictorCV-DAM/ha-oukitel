"""Binary framing, TTLV encoding/decoding and AES session crypto for LAN mode.

Wire format (TCP port 6607):
    AA AA | body_len(2,BE) | checksum(1) | pkt_id(2,BE) | cmd(2,BE) | payload
    - body_len  = checksum + pkt_id + cmd + payload  (excludes the 4 magic+len bytes)
    - checksum  = sum(bytes from pkt_id through end) & 0xFF
    - payload   = byte-stuffed; 0xAA in the data stream becomes 0xAA 0x55
    - after handshake the payload is AES-128-CBC encrypted (fixed IV = nonce bytes)
"""

from __future__ import annotations

import base64
import hashlib
import logging
import struct
from typing import Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

_FRAME_MAGIC = b"\xaa\xaa"
_LOGGER = logging.getLogger(__name__)


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


def aes_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return enc.update(_pad(plaintext)) + enc.finalize()


def aes_decrypt(key: bytes, iv: bytes, ciphertext: bytes) -> bytes:
    dec = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    return _unpad(dec.update(ciphertext) + dec.finalize())


def auth_key_bytes(auth_key_b64: str) -> bytes:
    return base64.b64decode(auth_key_b64)


def session_token(key: bytes, nonce: str) -> str:
    return hashlib.sha256((key.hex() + ";" + nonce).encode()).hexdigest()


# ---------------------------------------------------------------------------
# Byte stuffing  (0xAA -> 0xAA 0x55 in the wire stream)
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

def build_frame(packet_id: int, cmd: int, payload: bytes = b"") -> bytes:
    inner = struct.pack(">HH", packet_id & 0xFFFF, cmd & 0xFFFF) + payload
    checksum = sum(inner) & 0xFF
    body_len = len(inner) + 1
    raw = _FRAME_MAGIC + struct.pack(">HB", body_len, checksum) + inner
    return _stuff(raw)


class FrameAssembler:
    """Reassembles variable-length frames from a raw TCP byte stream."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self._destuffer = _StreamDestuffer()

    def feed(self, data: bytes) -> list[tuple[int, int, bytes]]:
        self._buf.extend(self._destuffer.feed(data))
        frames: list[tuple[int, int, bytes]] = []
        while True:
            k = self._buf.find(_FRAME_MAGIC)
            if k < 0:
                if len(self._buf) > 1:
                    del self._buf[:-1]
                break
            if k > 0:
                del self._buf[:k]
            if len(self._buf) < 9:
                break
            body_len = struct.unpack_from(">H", self._buf, 2)[0]
            total = 4 + body_len
            if len(self._buf) < total:
                break
            frame = bytes(self._buf[:total])
            del self._buf[:total]
            body = frame[5:]
            if (sum(body) & 0xFF) != frame[4]:
                _LOGGER.debug("oukitel: checksum mismatch — dropping frame")
                continue
            pid = struct.unpack_from(">H", frame, 5)[0]
            cmd = struct.unpack_from(">H", frame, 7)[0]
            frames.append((pid, cmd, frame[9:]))
        return frames


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
        elif kind == "struct":
            out += struct.pack(">HH", (tag << 3) | 4, len(value))
            out += ttlv_encode(value)
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
        h = struct.unpack_from(">H", buf, i)[0]
        i += 2
        tag, typ = (h >> 3) & 0x1FFF, h & 7
        if typ in (0, 1):
            out[tag] = typ == 1
        elif typ == 2:
            out[tag], i = _read_num(i)
        elif typ in (3, 5):
            if i + 2 > n:
                break
            ln = struct.unpack_from(">H", buf, i)[0]
            i += 2
            val = buf[i: i + ln]
            i += ln
            try:
                out[tag] = val.decode("ascii") if val.isascii() else val
            except Exception:
                out[tag] = val
        elif typ == 4:
            if i + 2 > n:
                break
            count = struct.unpack_from(">H", buf, i)[0]
            i += 2
            sub: dict[int, Any] = {}
            for _ in range(count):
                if i + 2 > n:
                    break
                h2 = struct.unpack_from(">H", buf, i)[0]
                i += 2
                t2, ty2 = (h2 >> 3) & 0x1FFF, h2 & 7
                if ty2 in (0, 1):
                    sub[t2] = ty2 == 1
                elif ty2 == 2:
                    sub[t2], i = _read_num(i)
                elif ty2 in (3, 5):
                    ln = struct.unpack_from(">H", buf, i)[0]
                    i += 2
                    sub[t2] = buf[i: i + ln]
                    i += ln
            out[tag] = sub
        else:
            break

    return out

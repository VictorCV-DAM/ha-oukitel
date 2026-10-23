import struct
import sys
import unittest
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "oukitel"
sys.path.append(str(COMPONENT))

from local_frame import ttlv_decode, ttlv_encode  # noqa: E402


class TtlvStringTests(unittest.TestCase):
    def test_roundtrip_ascii(self):
        raw = ttlv_encode([(1, "str", "abc")])
        self.assertEqual(ttlv_decode(raw), {1: "abc"})

    def test_roundtrip_empty(self):
        raw = ttlv_encode([(7, "str", "")])
        self.assertEqual(ttlv_decode(raw), {7: ""})

    def test_roundtrip_utf8(self):
        raw = ttlv_encode([(2, "str", "ñ€")])
        self.assertEqual(ttlv_decode(raw), {2: "ñ€"})

    def test_mixed_fields(self):
        raw = ttlv_encode(
            [
                (1, "str", "OUKITEL"),
                (2, "str", "secret"),
                (11, "num", 8886),
                (13, "str", "mqtt://host:8886"),
                (12, "num", 214),
            ]
        )
        self.assertEqual(
            ttlv_decode(raw),
            {1: "OUKITEL", 2: "secret", 11: 8886, 13: "mqtt://host:8886", 12: 214},
        )

    def test_nested_struct_with_string(self):
        raw = ttlv_encode([(1, "struct", [(2, "str", "x")])])
        self.assertEqual(ttlv_decode(raw), {1: {2: "x"}})

    def test_bool_and_num_unchanged(self):
        raw = ttlv_encode([(1, "bool", True), (2, "num", -5)])
        self.assertEqual(ttlv_decode(raw), {1: True, 2: -5})

    def test_type5_ascii_behaviour_is_preserved(self):
        raw = struct.pack(">HH", (5 << 3) | 5, 2) + b"AB"
        self.assertEqual(ttlv_decode(raw), {5: "AB"})

    def test_type5_binary_stays_bytes(self):
        raw = struct.pack(">HH", (5 << 3) | 5, 2) + b"\xff\x00"
        self.assertEqual(ttlv_decode(raw), {5: b"\xff\x00"})


if __name__ == "__main__":
    unittest.main()


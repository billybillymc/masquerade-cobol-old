"""Tests for CobolCraft uuid — UUID-ToString and UUID-FromString.

COBOL source: test-codebases/cobolcraft/src/encoding/uuid.cob

UUID-ToString: 16-byte big-endian binary → 36-char string  (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
UUID-FromString: 36-char string → 16-byte big-endian binary
"""
import pytest
from cc_uuid import uuid_to_string, uuid_from_string

NIL_BYTES  = b'\x00' * 16
NIL_STR    = '00000000-0000-0000-0000-000000000000'

MAX_BYTES  = b'\xff' * 16
MAX_STR    = 'ffffffff-ffff-ffff-ffff-ffffffffffff'

KNOWN_BYTES = bytes([
    0x55, 0x0e, 0x84, 0x00,
    0xe2, 0x9b,
    0x41, 0xd4,
    0xa7, 0x16,
    0x44, 0x66, 0x55, 0x44, 0x00, 0x00,
])
KNOWN_STR = '550e8400-e29b-41d4-a716-446655440000'


class TestUUIDToString:
    def test_nil_uuid(self):
        assert uuid_to_string(NIL_BYTES) == NIL_STR

    def test_max_uuid(self):
        assert uuid_to_string(MAX_BYTES) == MAX_STR

    def test_known_uuid(self):
        assert uuid_to_string(KNOWN_BYTES) == KNOWN_STR

    def test_output_length_is_36(self):
        assert len(uuid_to_string(NIL_BYTES)) == 36

    def test_dashes_at_correct_positions(self):
        result = uuid_to_string(NIL_BYTES)
        assert result[8] == '-'
        assert result[13] == '-'
        assert result[18] == '-'
        assert result[23] == '-'

    def test_all_hex_lowercase(self):
        result = uuid_to_string(MAX_BYTES)
        hex_chars = result.replace('-', '')
        assert hex_chars == hex_chars.lower()
        assert all(c in '0123456789abcdef' for c in hex_chars)


class TestUUIDFromString:
    def test_nil_uuid(self):
        assert uuid_from_string(NIL_STR) == NIL_BYTES

    def test_max_uuid(self):
        assert uuid_from_string(MAX_STR) == MAX_BYTES

    def test_known_uuid(self):
        assert uuid_from_string(KNOWN_STR) == KNOWN_BYTES

    def test_output_length_is_16(self):
        assert len(uuid_from_string(NIL_STR)) == 16


class TestRoundTrip:
    def test_bytes_roundtrip(self):
        assert uuid_from_string(uuid_to_string(KNOWN_BYTES)) == KNOWN_BYTES

    def test_string_roundtrip(self):
        assert uuid_to_string(uuid_from_string(KNOWN_STR)) == KNOWN_STR

    def test_all_byte_values(self):
        data = bytes(range(16))
        assert uuid_from_string(uuid_to_string(data)) == data

"""Tests for UTWOSCMP — one's complement byte utility.

COBOL source: test-codebases/bankdemo/sources/cobol/core/UTWOSCMP.cbl
Logic: for each byte i in input[0:len], output[i] = 255 - input[i]  (bitwise NOT)
"""
import pytest
from utwoscmp import twos_cmp


def test_single_byte_zero_becomes_255():
    result = twos_cmp(b"\x00")
    assert result == b"\xff"


def test_single_byte_255_becomes_zero():
    result = twos_cmp(b"\xff")
    assert result == b"\x00"


def test_single_byte_midpoint():
    result = twos_cmp(b"\x0f")
    assert result == b"\xf0"


def test_multi_byte_all_zero():
    result = twos_cmp(b"\x00\x00\x00")
    assert result == b"\xff\xff\xff"


def test_multi_byte_mixed():
    result = twos_cmp(b"\x01\x7f\x80\xfe")
    assert result == b"\xfe\x80\x7f\x01"


def test_round_trip_is_identity():
    original = b"\xde\xad\xbe\xef"
    assert twos_cmp(twos_cmp(original)) == original


def test_empty_input_returns_empty():
    assert twos_cmp(b"") == b""


def test_max_length_256():
    data = bytes(range(256))
    result = twos_cmp(data)
    assert len(result) == 256
    assert all(result[i] == 255 - data[i] for i in range(256))


def test_ascii_text_inverted():
    # 'A' = 0x41 → 0xbe
    result = twos_cmp(b"A")
    assert result == bytes([255 - ord("A")])

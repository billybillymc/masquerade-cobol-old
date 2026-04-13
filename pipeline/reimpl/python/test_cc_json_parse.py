"""Tests for CobolCraft json-parse.

COBOL source: test-codebases/cobolcraft/src/encoding/json-parse.cob

Each parser function takes (input_str, offset) and returns (flag, new_offset, value?).
flag=0 means success, flag=1 means parse error.
offset is 1-based (matching COBOL BINARY-LONG convention).
"""
import pytest
from cc_json_parse import (
    parse_object_start, parse_object_end,
    parse_array_start, parse_array_end,
    parse_comma, parse_string, parse_object_key,
    parse_null, parse_boolean, parse_integer, parse_float,
    parse_skip_value, parse_find_value,
)


# ── Object delimiters ──────────────────────────────────────────────────────────

def test_object_start_success():
    flag, off = parse_object_start('{"a":1}', 1)
    assert flag == 0 and off == 2

def test_object_start_with_leading_space():
    flag, off = parse_object_start('  {"a":1}', 1)
    assert flag == 0 and off == 4

def test_object_start_fail():
    flag, off = parse_object_start('[1,2]', 1)
    assert flag == 1

def test_object_end_success():
    flag, off = parse_object_end('}', 1)
    assert flag == 0 and off == 2

def test_object_end_fail():
    flag, off = parse_object_end(']', 1)
    assert flag == 1


# ── Array delimiters ───────────────────────────────────────────────────────────

def test_array_start_success():
    flag, off = parse_array_start('[1,2]', 1)
    assert flag == 0 and off == 2

def test_array_end_success():
    flag, off = parse_array_end(']', 1)
    assert flag == 0 and off == 2

def test_array_end_fail():
    flag, off = parse_array_end('}', 1)
    assert flag == 1


# ── Comma ─────────────────────────────────────────────────────────────────────

def test_comma_success():
    flag, off = parse_comma(',next', 1)
    assert flag == 0 and off == 2

def test_comma_with_space():
    flag, off = parse_comma('  , next', 1)
    assert flag == 0 and off == 4

def test_comma_fail():
    flag, off = parse_comma('next', 1)
    assert flag == 1


# ── String ────────────────────────────────────────────────────────────────────

def test_string_simple():
    flag, off, val = parse_string('"hello"', 1)
    assert flag == 0 and val == 'hello'

def test_string_empty():
    flag, off, val = parse_string('""', 1)
    assert flag == 0 and val == ''

def test_string_escape_quote():
    flag, off, val = parse_string(r'"say \"hi\""', 1)
    assert flag == 0 and val == 'say "hi"'

def test_string_escape_newline():
    flag, off, val = parse_string('"line1\\nline2"', 1)
    assert flag == 0 and val == 'line1\nline2'

def test_string_escape_tab():
    flag, off, val = parse_string('"a\\tb"', 1)
    assert flag == 0 and val == 'a\tb'

def test_string_no_opening_quote_fails():
    flag, off, val = parse_string('hello', 1)
    assert flag == 1

def test_string_unterminated_fails():
    flag, off, val = parse_string('"hello', 1)
    assert flag == 1


# ── Object key ────────────────────────────────────────────────────────────────

def test_object_key_success():
    flag, off, key = parse_object_key('"name": "value"', 1)
    assert flag == 0 and key == 'name'

def test_object_key_no_colon_fails():
    flag, off, key = parse_object_key('"name" "value"', 1)
    assert flag == 1


# ── Null ──────────────────────────────────────────────────────────────────────

def test_null_success():
    flag, off = parse_null('null,', 1)
    assert flag == 0 and off == 5

def test_null_fail():
    flag, off = parse_null('true', 1)
    assert flag == 1


# ── Boolean ───────────────────────────────────────────────────────────────────

def test_boolean_true():
    flag, off, val = parse_boolean('true', 1)
    assert flag == 0 and val == 1

def test_boolean_false():
    flag, off, val = parse_boolean('false', 1)
    assert flag == 0 and val == 0

def test_boolean_fail():
    flag, off, val = parse_boolean('null', 1)
    assert flag == 1


# ── Integer ───────────────────────────────────────────────────────────────────

def test_integer_positive():
    flag, off, val = parse_integer('42', 1)
    assert flag == 0 and val == 42

def test_integer_negative():
    flag, off, val = parse_integer('-7', 1)
    assert flag == 0 and val == -7

def test_integer_zero():
    flag, off, val = parse_integer('0', 1)
    assert flag == 0 and val == 0

def test_integer_stops_at_non_digit():
    flag, off, val = parse_integer('123,', 1)
    assert flag == 0 and val == 123 and off == 4

def test_integer_no_digits_fails():
    flag, off, val = parse_integer('abc', 1)
    assert flag == 1


# ── Float ─────────────────────────────────────────────────────────────────────

def test_float_simple():
    flag, off, val = parse_float('3.14', 1)
    assert flag == 0
    assert abs(val - 3.14) < 1e-9

def test_float_negative():
    flag, off, val = parse_float('-2.5', 1)
    assert flag == 0 and val == pytest.approx(-2.5)

def test_float_integer_only():
    flag, off, val = parse_float('42', 1)
    assert flag == 0 and val == pytest.approx(42.0)

def test_float_with_exponent():
    flag, off, val = parse_float('1.5e2', 1)
    assert flag == 0 and val == pytest.approx(150.0)

def test_float_with_negative_exponent():
    flag, off, val = parse_float('1.5e-2', 1)
    assert flag == 0 and val == pytest.approx(0.015)


# ── SkipValue ─────────────────────────────────────────────────────────────────

def test_skip_string():
    flag, off = parse_skip_value('"hello", next', 1)
    assert flag == 0 and off == 8

def test_skip_integer():
    flag, off = parse_skip_value('42,', 1)
    assert flag == 0 and off == 3

def test_skip_null():
    flag, off = parse_skip_value('null,', 1)
    assert flag == 0 and off == 5

def test_skip_true():
    flag, off = parse_skip_value('true,', 1)
    assert flag == 0 and off == 5

def test_skip_false():
    flag, off = parse_skip_value('false,', 1)
    assert flag == 0 and off == 6

def test_skip_empty_array():
    flag, off = parse_skip_value('[]', 1)
    assert flag == 0 and off == 3

def test_skip_nested_object():
    flag, off = parse_skip_value('{"a":1}', 1)
    assert flag == 0 and off == 8


# ── FindValue ─────────────────────────────────────────────────────────────────

def test_find_value_found():
    src = '"name": "Alice", "age": 30'
    flag, off = parse_find_value(src, 1, 'age')
    assert flag == 0
    _, _, val = parse_integer(src, off)
    assert val == 30

def test_find_value_first_key():
    src = '"x": 1, "y": 2'
    flag, off = parse_find_value(src, 1, 'x')
    assert flag == 0
    _, _, val = parse_integer(src, off)
    assert val == 1

def test_find_value_not_found():
    src = '"a": 1, "b": 2'
    flag, off = parse_find_value(src, 1, 'z')
    assert flag == 1

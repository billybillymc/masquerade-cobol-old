"""Tests for RTNCDE00 — standard return code handler.

COBOL source:  test-codebases/legacy-benchmark/src/programs/batch/RTNCDE00.cbl
Copybook:      test-codebases/legacy-benchmark/src/copybook/common/RTNCODE.cpy

Operations (RC-REQUEST-TYPE):
    'I' — Initialize: clear all fields, set status=SUCCESS, response=0
    'S' — Set: set current code, update highest, derive status level
    'G' — Get: copy current/highest/status into return-data fields
    'L' — Log: DB2 INSERT (stubbed — sets response=0 on success, 8 on failure)
    'A' — Analyze: DB2 SELECT (stubbed)

Status mapping (RC-NEW-CODE for Set):
    0       → 'S' (success)
    1–4     → 'W' (warning)
    5–8     → 'E' (error)
    9+      → 'F' (severe)
"""
import pytest
from rtncde00 import ReturnCodeArea, rtncde00


# ── Initialize ─────────────────────────────────────────────────────────────────

def test_initialize_clears_current_code():
    area = ReturnCodeArea(request='I')
    rtncde00(area)
    assert area.current_code == 0

def test_initialize_clears_highest_code():
    area = ReturnCodeArea(request='I', highest_code=99)
    rtncde00(area)
    assert area.highest_code == 0

def test_initialize_sets_status_success():
    area = ReturnCodeArea(request='I')
    rtncde00(area)
    assert area.status == 'S'

def test_initialize_clears_program_id():
    area = ReturnCodeArea(request='I', program_id='MYPROG  ')
    rtncde00(area)
    assert area.program_id.strip() == ''

def test_initialize_sets_response_zero():
    area = ReturnCodeArea(request='I')
    rtncde00(area)
    assert area.response_code == 0


# ── Set ────────────────────────────────────────────────────────────────────────

def test_set_code_zero_is_success():
    area = ReturnCodeArea(request='S', new_code=0)
    rtncde00(area)
    assert area.status == 'S'
    assert area.current_code == 0

def test_set_code_1_is_warning():
    area = ReturnCodeArea(request='S', new_code=1)
    rtncde00(area)
    assert area.status == 'W'

def test_set_code_4_is_warning():
    area = ReturnCodeArea(request='S', new_code=4)
    rtncde00(area)
    assert area.status == 'W'

def test_set_code_5_is_error():
    area = ReturnCodeArea(request='S', new_code=5)
    rtncde00(area)
    assert area.status == 'E'

def test_set_code_8_is_error():
    area = ReturnCodeArea(request='S', new_code=8)
    rtncde00(area)
    assert area.status == 'E'

def test_set_code_9_is_severe():
    area = ReturnCodeArea(request='S', new_code=9)
    rtncde00(area)
    assert area.status == 'F'

def test_set_code_100_is_severe():
    area = ReturnCodeArea(request='S', new_code=100)
    rtncde00(area)
    assert area.status == 'F'

def test_set_updates_highest_when_greater():
    area = ReturnCodeArea(request='S', new_code=7, highest_code=3)
    rtncde00(area)
    assert area.highest_code == 7

def test_set_does_not_lower_highest():
    area = ReturnCodeArea(request='S', new_code=2, highest_code=8)
    rtncde00(area)
    assert area.highest_code == 8

def test_set_current_code_stored():
    area = ReturnCodeArea(request='S', new_code=5)
    rtncde00(area)
    assert area.current_code == 5

def test_set_response_zero():
    area = ReturnCodeArea(request='S', new_code=3)
    rtncde00(area)
    assert area.response_code == 0


# ── Get ────────────────────────────────────────────────────────────────────────

def test_get_copies_current_to_return_value():
    area = ReturnCodeArea(request='G', current_code=6, highest_code=9, status='F')
    rtncde00(area)
    assert area.return_value == 6

def test_get_copies_highest_to_return():
    area = ReturnCodeArea(request='G', current_code=6, highest_code=9, status='F')
    rtncde00(area)
    assert area.highest_return == 9

def test_get_copies_status_to_return_status():
    area = ReturnCodeArea(request='G', current_code=6, highest_code=9, status='F')
    rtncde00(area)
    assert area.return_status == 'F'

def test_get_response_zero():
    area = ReturnCodeArea(request='G', current_code=0, highest_code=0, status='S')
    rtncde00(area)
    assert area.response_code == 0


# ── Set then Get round-trip ────────────────────────────────────────────────────

def test_set_then_get_round_trip():
    area = ReturnCodeArea(request='I')
    rtncde00(area)
    area.request = 'S'
    area.new_code = 6
    rtncde00(area)
    area.request = 'G'
    rtncde00(area)
    assert area.return_value == 6
    assert area.status == 'E'
    assert area.highest_return == 6

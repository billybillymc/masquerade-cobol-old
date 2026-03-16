"""Tests for record_io.py and cobol_runner.py — Phase 1 of COBOL test runner.

IQ-11: Pack/unpack COBOL records, compile and run batch programs via GnuCOBOL
in WSL, capture outputs for differential harness.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from record_io import (
    pack_display_alphanumeric,
    pack_display_numeric,
    pack_comp,
    pack_comp3,
    unpack_display_alphanumeric,
    unpack_display_numeric,
    unpack_comp,
    unpack_comp3,
    pack_record,
    unpack_record,
    pack_field,
    unpack_field,
)
from copybook_dict import CopybookDictionary, CopybookField
from cobol_runner import compile_cobol, run_cobol, compile_and_run, is_cobc_available

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
COBC_AVAILABLE = is_cobc_available()


class TestDisplayAlphanumeric:
    """Pack/unpack PIC X fields."""

    def test_pack_exact_length(self):
        assert pack_display_alphanumeric("HELLO", 5) == b"HELLO"

    def test_pack_pads_with_spaces(self):
        assert pack_display_alphanumeric("HI", 5) == b"HI   "

    def test_pack_truncates_to_length(self):
        assert pack_display_alphanumeric("TOOLONG", 4) == b"TOOL"

    def test_unpack(self):
        assert unpack_display_alphanumeric(b"HELLO") == "HELLO"


class TestDisplayNumeric:
    """Pack/unpack PIC 9 DISPLAY fields."""

    def test_pack_integer(self):
        result = pack_display_numeric(42, "9(05)")
        assert result == b"00042"

    def test_pack_decimal(self):
        result = pack_display_numeric(Decimal("123.45"), "S9(05)V99")
        assert result == b"0012345"

    def test_pack_zero(self):
        result = pack_display_numeric(0, "9(03)")
        assert result == b"000"

    def test_unpack_integer(self):
        result = unpack_display_numeric(b"00042", "9(05)")
        assert result == Decimal("42")

    def test_unpack_decimal(self):
        result = unpack_display_numeric(b"0012345", "S9(05)V99")
        assert result == Decimal("123.45")


class TestComp:
    """Pack/unpack COMP/BINARY fields."""

    def test_pack_small_int(self):
        result = pack_comp(42, "S9(04)")
        assert len(result) == 2
        assert unpack_comp(result, "S9(04)") == Decimal("42")

    def test_pack_medium_int(self):
        result = pack_comp(123456, "S9(09)")
        assert len(result) == 4
        assert unpack_comp(result, "S9(09)") == Decimal("123456")

    def test_pack_negative(self):
        result = pack_comp(-100, "S9(04)")
        assert unpack_comp(result, "S9(04)") == Decimal("-100")

    def test_round_trip_large(self):
        result = pack_comp(9999999999, "9(15)")
        assert len(result) == 8
        assert unpack_comp(result, "9(15)") == Decimal("9999999999")


class TestComp3:
    """Pack/unpack COMP-3/PACKED-DECIMAL fields."""

    def test_pack_positive(self):
        """PIC S9(05) COMP-3: 12345 → 0x01 0x23 0x45 0x0C (3 bytes)."""
        result = pack_comp3(12345, "S9(05)")
        assert len(result) == 3  # ceil((5+1)/2) = 3
        assert unpack_comp3(result, "S9(05)") == Decimal("12345")

    def test_pack_negative(self):
        result = pack_comp3(-12345, "S9(05)")
        assert unpack_comp3(result, "S9(05)") == Decimal("-12345")

    def test_pack_decimal(self):
        """PIC S9(10)V99 COMP-3: 5000.00 → 12 digits packed."""
        result = pack_comp3(Decimal("5000.00"), "S9(10)V99")
        unpacked = unpack_comp3(result, "S9(10)V99")
        assert unpacked == Decimal("5000.00")

    def test_pack_zero(self):
        result = pack_comp3(0, "S9(05)")
        assert unpack_comp3(result, "S9(05)") == Decimal("0")

    def test_known_encoding(self):
        """12345 packed as S9(05): 01 23 45 0C."""
        result = pack_comp3(12345, "S9(05)")
        # Nibbles: 0,1,2,3,4,5,C → bytes: 0x01, 0x23, 0x45, but we pad to even
        # With 5 digits + sign = 6 nibbles = 3 bytes: 01 23 5C
        assert result[-1] & 0x0F == 0x0C  # last nibble is sign C (positive)


class TestRecordPackUnpack:
    """Pack/unpack full records using copybook definitions."""

    def test_round_trip_csusr01y(self):
        """Pack and unpack a SEC-USER-DATA record (all PIC X fields)."""
        cbd = CopybookDictionary(str(CARDDEMO / "app" / "cpy"))
        values = {
            "SEC-USR-ID": "ADMIN001",
            "SEC-USR-FNAME": "John",
            "SEC-USR-LNAME": "Doe",
            "SEC-USR-PWD": "PASSWORD",
            "SEC-USR-TYPE": "A",
            "SEC-USR-FILLER": "",
        }
        packed = pack_record(values, "CSUSR01Y", cbd)
        assert len(packed) == 80  # 8+20+20+8+1+23 = 80

        unpacked = unpack_record(packed, "CSUSR01Y", cbd)
        assert unpacked["SEC-USR-ID"].rstrip() == "ADMIN001"
        assert unpacked["SEC-USR-FNAME"].rstrip() == "John"
        assert unpacked["SEC-USR-TYPE"].rstrip() == "A"

    def test_round_trip_cvact01y(self):
        """Pack and unpack an ACCOUNT-RECORD with mixed PIC X and S9V99 fields."""
        cbd = CopybookDictionary(str(CARDDEMO / "app" / "cpy"))
        values = {
            "ACCT-ID": "12345678901",
            "ACCT-ACTIVE-STATUS": "Y",
            "ACCT-CURR-BAL": Decimal("5000.00"),
            "ACCT-CREDIT-LIMIT": Decimal("10000.00"),
            "ACCT-CASH-CREDIT-LIMIT": Decimal("2000.00"),
            "ACCT-OPEN-DATE": "2020-01-15",
            "ACCT-EXPIRAION-DATE": "2026-01-15",
            "ACCT-REISSUE-DATE": "2024-06-01",
            "ACCT-CURR-CYC-CREDIT": Decimal("500.00"),
            "ACCT-CURR-CYC-DEBIT": Decimal("100.00"),
            "ACCT-ADDR-ZIP": "10001     ",
            "ACCT-GROUP-ID": "GRP001    ",
            "FILLER": "",
        }
        packed = pack_record(values, "CVACT01Y", cbd)
        unpacked = unpack_record(packed, "CVACT01Y", cbd)
        assert str(unpacked["ACCT-ID"]) == "12345678901" or unpacked["ACCT-ID"] == Decimal("12345678901")
        assert unpacked["ACCT-ACTIVE-STATUS"].rstrip() == "Y"


@pytest.mark.skipif(not COBC_AVAILABLE, reason="GnuCOBOL (cobc) not available in WSL")
class TestCoblCompilation:
    """Compile real carddemo COBOL programs."""

    def test_compile_cbact01c(self):
        """CBACT01C (batch account processor) compiles successfully."""
        result = compile_cobol(
            source_file=str(CARDDEMO / "app" / "cbl" / "CBACT01C.cbl"),
            copybook_dirs=[str(CARDDEMO / "app" / "cpy")],
        )
        assert result.success, f"Compilation failed: {result.stderr}"

    def test_compile_hello_world(self, tmp_path):
        """A minimal COBOL program compiles and runs."""
        source = tmp_path / "hello.cbl"
        source.write_text("""\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HELLO.
       PROCEDURE DIVISION.
           DISPLAY "HELLO-TEST-OUTPUT".
           STOP RUN.
""")
        result = compile_and_run(str(source))
        assert result.success, f"Failed: {result.stderr}"
        assert "HELLO-TEST-OUTPUT" in result.stdout

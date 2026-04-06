"""Tests for copybook_dict.py — field parsing, type detection, size calculation."""
import sys
from pathlib import Path
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from copybook_dict import parse_copybook, apply_replacing, CopybookField, CopybookDictionary


def _write_cpy(tmp_dir, name, content):
    p = Path(tmp_dir) / f"{name}.cpy"
    p.write_text(content, encoding="utf-8")
    return p


class TestFieldTypeParsing:
    def test_alphanumeric_field(self):
        f = CopybookField("WS-NAME", 5, "X(20)", None, None, None)
        assert f.field_type == "alphanumeric"
        assert f.size_bytes == 20

    def test_numeric_field(self):
        f = CopybookField("WS-COUNT", 5, "9(05)", None, None, None)
        assert f.field_type == "numeric"
        assert f.size_bytes == 5

    def test_decimal_field(self):
        f = CopybookField("WS-AMT", 5, "S9(10)V99", None, None, None)
        assert f.field_type == "decimal"
        assert f.size_bytes == 12

    def test_packed_decimal_comp3(self):
        f = CopybookField("WS-AMT", 5, "S9(10)V99", "COMP-3", None, None)
        assert f.size_bytes == 7  # (12 + 2) / 2

    def test_binary_comp(self):
        f = CopybookField("WS-IDX", 5, "9(04)", "COMP", None, None)
        assert f.size_bytes == 2

    def test_binary_comp_large(self):
        f = CopybookField("WS-BIG", 5, "9(09)", "COMP", None, None)
        assert f.size_bytes == 4

    def test_group_field(self):
        f = CopybookField("WS-GROUP", 1, None, None, None, None)
        assert f.field_type == "group"
        assert f.size_bytes == 0

    def test_condition_field(self):
        f = CopybookField("WS-VALID", 88, None, None, None, None)
        assert f.field_type == "condition"


class TestCopybookParsing:
    def test_parses_standard_copybook(self, tmp_path):
        _write_cpy(tmp_path, "TESTCPY", """
      * Test copybook
           05  WS-RECORD-KEY.
               10  WS-KEY-TYPE          PIC X(02).
                   88  WS-KEY-ALPHA     VALUE 'AL'.
                   88  WS-KEY-NUMERIC   VALUE 'NU'.
               10  WS-KEY-VALUE         PIC X(20).
           05  WS-AMOUNT                PIC S9(10)V99 COMP-3.
""")
        rec = parse_copybook(tmp_path / "TESTCPY.cpy")
        assert rec.name == "TESTCPY"
        assert rec.field_count >= 4
        assert rec.condition_count == 2

    def test_handles_redefines(self, tmp_path):
        _write_cpy(tmp_path, "REDEFCPY", """
           05  WS-DATE-FIELD           PIC X(08).
           05  WS-DATE-PARTS REDEFINES WS-DATE-FIELD.
               10  WS-YEAR             PIC X(04).
               10  WS-MONTH            PIC X(02).
               10  WS-DAY              PIC X(02).
""")
        rec = parse_copybook(tmp_path / "REDEFCPY.cpy")
        redef_fields = [f for f in rec.fields if f.redefines]
        assert len(redef_fields) == 1
        assert redef_fields[0].redefines == "WS-DATE-FIELD"

    def test_handles_occurs(self, tmp_path):
        _write_cpy(tmp_path, "OCCCPY", """
           05  WS-TABLE.
               10  WS-ENTRY OCCURS 10.
                   15  WS-ENTRY-NAME   PIC X(30).
                   15  WS-ENTRY-AMT    PIC 9(07)V99.
""")
        rec = parse_copybook(tmp_path / "OCCCPY.cpy")
        occ_fields = [f for f in rec.fields if f.occurs]
        assert len(occ_fields) >= 1
        assert occ_fields[0].occurs == 10


class TestCopybookDictionary:
    def test_search_and_lookup(self, tmp_path):
        _write_cpy(tmp_path, "CUST01", """
           05  CUST-NAME               PIC X(40).
           05  CUST-ID                 PIC 9(10).
           05  CUST-STATUS             PIC X(01).
""")
        _write_cpy(tmp_path, "ACCT01", """
           05  ACCT-ID                 PIC 9(10).
           05  ACCT-BALANCE            PIC S9(10)V99 COMP-3.
""")
        cbd = CopybookDictionary(str(tmp_path))
        assert cbd.summary()["total_copybooks"] == 2

        results = cbd.lookup_field("CUST-NAME")
        assert len(results) == 1
        assert results[0]["copybook"] == "CUST01"

        search = cbd.search_fields("ACCT")
        assert len(search) >= 2

        detail = cbd.copybook_detail("CUST01")
        assert detail is not None
        assert detail["field_count"] == 3


# Copybook using :PREF: placeholder — the idiomatic COBOL pattern for prefix substitution.
# COPY MYCPY REPLACING ==:PREF:== BY ==WS-ACCT== makes :PREF:-NAME -> WS-ACCT-NAME.
_SHARED_CPY = """
       05  :PREF:-NAME            PIC X(40).
       05  :PREF:-ID              PIC 9(10).
       05  :PREF:-STATUS          PIC X(01).
"""

# Copybook using full token names for exact-match substitution.
_EXACT_CPY = """
       05  WS-CUST-NAME           PIC X(40).
       05  WS-CUST-ID             PIC 9(10).
       05  WS-CUST-STATUS         PIC X(01).
"""


class TestApplyReplacing:
    def test_placeholder_prefix_substitution(self):
        # :PREF: is not a valid COBOL identifier so it acts as a safe placeholder.
        result = apply_replacing(_SHARED_CPY, [(":PREF:", "WS-ACCT")])
        assert "WS-ACCT-NAME" in result
        assert "WS-ACCT-ID" in result
        assert "WS-ACCT-STATUS" in result
        assert ":PREF:" not in result

    def test_exact_token_substitution(self):
        # Replacing a complete field name token leaves unrelated fields untouched.
        result = apply_replacing(_EXACT_CPY, [
            ("WS-CUST-NAME", "WS-ACCT-NAME"),
            ("WS-CUST-ID", "WS-ACCT-ID"),
            ("WS-CUST-STATUS", "WS-ACCT-STATUS"),
        ])
        assert "WS-ACCT-NAME" in result
        assert "WS-ACCT-ID" in result
        assert "WS-CUST-NAME" not in result

    def test_no_partial_match(self):
        # WS-CUST does NOT match inside WS-CUSTOMER-ID — they are different tokens.
        src = "       05  WS-CUSTOMER-ID  PIC 9(10).\n"
        result = apply_replacing(src, [("WS-CUST", "WS-ACCT")])
        assert "WS-CUSTOMER-ID" in result

    def test_multiple_pairs(self):
        result = apply_replacing(_EXACT_CPY, [
            ("WS-CUST-NAME", "WS-EMPLOYEE-NAME"),
            ("WS-CUST-ID", "WS-EMPLOYEE-ID"),
        ])
        assert "WS-EMPLOYEE-NAME" in result
        assert "WS-EMPLOYEE-ID" in result

    def test_empty_replacements(self):
        result = apply_replacing(_EXACT_CPY, [])
        assert result == _EXACT_CPY

    def test_case_insensitive(self):
        result = apply_replacing(_EXACT_CPY, [("ws-cust-name", "WS-ACCT-NAME")])
        assert "WS-ACCT-NAME" in result


class TestResolveWithReplacing:
    def test_resolve_applies_substitution(self, tmp_path):
        _write_cpy(tmp_path, "CUSTCPY", _SHARED_CPY)
        cbd = CopybookDictionary(str(tmp_path))

        rec = cbd.resolve_with_replacing("CUSTCPY", [(":PREF:", "WS-ACCT")])
        assert rec is not None
        names = [f.name for f in rec.fields]
        assert "WS-ACCT-NAME" in names
        assert "WS-ACCT-ID" in names
        assert not any(":PREF:" in n for n in names)

    def test_resolve_no_replacing_returns_original(self, tmp_path):
        _write_cpy(tmp_path, "CUSTCPY", _EXACT_CPY)
        cbd = CopybookDictionary(str(tmp_path))

        rec = cbd.resolve_with_replacing("CUSTCPY", [])
        assert rec is not None
        names = [f.name for f in rec.fields]
        assert "WS-CUST-NAME" in names

    def test_resolve_unknown_copybook_returns_none(self, tmp_path):
        cbd = CopybookDictionary(str(tmp_path))
        assert cbd.resolve_with_replacing("NONEXISTENT", [("A", "B")]) is None

"""Tests for COPY REPLACING clause parsing in cobol_parser.py."""
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cobol_parser import _parse_replacing_pairs, parse_cobol_file


class TestParseReplacingPairs:
    def test_pseudo_text_single_pair(self):
        text = "REPLACING ==WS-OLD== BY ==WS-NEW=="
        pairs = _parse_replacing_pairs(text)
        assert pairs == [("WS-OLD", "WS-NEW")]

    def test_pseudo_text_multiple_pairs(self):
        text = "REPLACING ==WS-CUST== BY ==WS-ACCT== ==WS-CUST-ID== BY ==WS-ACCT-ID=="
        pairs = _parse_replacing_pairs(text)
        assert ("WS-CUST", "WS-ACCT") in pairs
        assert ("WS-CUST-ID", "WS-ACCT-ID") in pairs

    def test_quoted_old_bare_new(self):
        # legacy single-quote syntax that existed before
        text = "REPLACING 'WS-OLD' BY WS-NEW"
        pairs = _parse_replacing_pairs(text)
        assert pairs == [("WS-OLD", "WS-NEW")]

    def test_no_replacing_keyword_returns_empty(self):
        text = "==WS-OLD== BY ==WS-NEW=="
        pairs = _parse_replacing_pairs(text)
        assert pairs == []

    def test_empty_string_returns_empty(self):
        assert _parse_replacing_pairs("") == []

    def test_strips_trailing_period_from_new(self):
        text = "REPLACING ==WS-OLD== BY ==WS-NEW==."
        pairs = _parse_replacing_pairs(text)
        assert pairs == [("WS-OLD", "WS-NEW")]

    def test_case_insensitive_replacing_keyword(self):
        text = "replacing ==WS-OLD== by ==WS-NEW=="
        pairs = _parse_replacing_pairs(text)
        assert pairs == [("WS-OLD", "WS-NEW")]


class TestCopyReplacingEndToEnd:
    def test_copy_replacing_stored_on_copy_statement(self, tmp_path):
        src = tmp_path / "TESTPROG.cbl"
        src.write_text(
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. TESTPROG.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       COPY CUSTCPY REPLACING ==WS-CUST== BY ==WS-ACCT==.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           STOP RUN.\n",
            encoding="utf-8",
        )
        prog = parse_cobol_file(src)
        assert len(prog.copy_statements) == 1
        cs = prog.copy_statements[0]
        assert cs.copybook_name.upper() == "CUSTCPY"
        assert ("WS-CUST", "WS-ACCT") in cs.replacing

    def test_copy_replacing_multiple_pairs_stored(self, tmp_path):
        src = tmp_path / "TESTPROG.cbl"
        src.write_text(
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. TESTPROG.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       COPY CUSTCPY REPLACING ==WS-CUST== BY ==WS-ACCT==\n"
            "                              ==WS-CUST-ID== BY ==WS-ACCT-ID==.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           STOP RUN.\n",
            encoding="utf-8",
        )
        prog = parse_cobol_file(src)
        cs = prog.copy_statements[0]
        assert ("WS-CUST", "WS-ACCT") in cs.replacing
        assert ("WS-CUST-ID", "WS-ACCT-ID") in cs.replacing

    def test_copy_without_replacing_has_empty_list(self, tmp_path):
        src = tmp_path / "TESTPROG.cbl"
        src.write_text(
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. TESTPROG.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       COPY CUSTCPY.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           STOP RUN.\n",
            encoding="utf-8",
        )
        prog = parse_cobol_file(src)
        assert prog.copy_statements[0].replacing == []

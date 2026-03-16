"""Tests for symbol_table.py — hierarchical field resolution and scope tracking.

IQ-10: Builds a proper symbol table that resolves qualified COBOL field
references (FIELD OF GROUP) and tracks REDEFINES unions and section scope.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from symbol_table import (
    SymbolTable,
    SymbolNode,
    AmbiguousReferenceError,
    build_symbol_table,
)
from copybook_dict import CopybookDictionary

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"


class TestSymbolTableConstruction:
    """Build symbol table from copybook fields."""

    def test_builds_from_copybook(self):
        """Symbol table built from CSUSR01Y has the 01-level record and children."""
        cbd = CopybookDictionary(str(CARDDEMO / "app" / "cpy"))
        st = build_symbol_table(["CSUSR01Y"], cbd)
        assert st.root_count() >= 1
        # SEC-USER-DATA is the 01-level record
        node = st.find("SEC-USER-DATA")
        assert node is not None
        assert node.level == 1

    def test_children_accessible(self):
        """Fields under SEC-USER-DATA are children of the 01-level node."""
        cbd = CopybookDictionary(str(CARDDEMO / "app" / "cpy"))
        st = build_symbol_table(["CSUSR01Y"], cbd)
        node = st.find("SEC-USR-ID")
        assert node is not None
        assert node.parent is not None
        assert node.parent.name == "SEC-USER-DATA"

    def test_nested_groups_from_cocom01y(self):
        """COCOM01Y has 01 → 05 → 10 hierarchy. All levels accessible."""
        cbd = CopybookDictionary(str(CARDDEMO / "app" / "cpy"))
        st = build_symbol_table(["COCOM01Y"], cbd)
        # CDEMO-FROM-TRANID is level 10, under CDEMO-GENERAL-INFO (05), under CARDDEMO-COMMAREA (01)
        node = st.find("CDEMO-FROM-TRANID")
        assert node is not None
        assert node.parent.name == "CDEMO-GENERAL-INFO"
        assert node.parent.parent.name == "CARDDEMO-COMMAREA"


class TestQualifiedResolution:
    """Resolve qualified references: FIELD OF GROUP."""

    def test_qualified_resolves_uniquely(self):
        """CUST-ADDR-COUNTRY-CD exists in both CUSTREC and CVCUS01Y.
        Qualified resolution with parent record name picks the right one."""
        cbd = CopybookDictionary(str(CARDDEMO / "app" / "cpy"))
        st = build_symbol_table(["CUSTREC", "CVCUS01Y"], cbd)
        # Both have CUST-ADDR-COUNTRY-CD — ambiguous unqualified
        all_matches = st.find_all("CUST-ADDR-COUNTRY-CD")
        assert len(all_matches) == 2
        # Qualified with parent record name resolves uniquely
        node = st.resolve("CUST-ADDR-COUNTRY-CD", qualifier="CUSTOMER-RECORD")
        assert node is not None
        assert node.name == "CUST-ADDR-COUNTRY-CD"
        assert node.copybook_origin == "CUSTREC"

    def test_unqualified_unique_resolves(self):
        """SEC-USR-ID only exists in one copybook — unqualified resolves fine."""
        cbd = CopybookDictionary(str(CARDDEMO / "app" / "cpy"))
        st = build_symbol_table(["CSUSR01Y"], cbd)
        node = st.resolve("SEC-USR-ID")
        assert node is not None
        assert node.name == "SEC-USR-ID"

    def test_ambiguous_unqualified_raises(self):
        """CUST-ADDR-COUNTRY-CD in both CUSTREC and CVCUS01Y — ambiguous."""
        cbd = CopybookDictionary(str(CARDDEMO / "app" / "cpy"))
        st = build_symbol_table(["CUSTREC", "CVCUS01Y"], cbd)
        all_matches = st.find_all("CUST-ADDR-COUNTRY-CD")
        assert len(all_matches) == 2
        with pytest.raises(AmbiguousReferenceError):
            st.resolve("CUST-ADDR-COUNTRY-CD")


class TestRedefines:
    """REDEFINES entries share memory offset."""

    def test_redefines_tracked(self, tmp_path):
        """REDEFINES field points to the target field."""
        # Build from a synthetic copybook with REDEFINES
        cpy_dir = tmp_path / "cpy"
        cpy_dir.mkdir()
        (cpy_dir / "TREDEF.cpy").write_text("""
           01  TEST-REC.
               05  WS-DATE-FIELD           PIC X(08).
               05  WS-DATE-PARTS REDEFINES WS-DATE-FIELD.
                   10  WS-YEAR             PIC X(04).
                   10  WS-MONTH            PIC X(02).
                   10  WS-DAY              PIC X(02).
        """, encoding="utf-8")
        cbd = CopybookDictionary(str(cpy_dir))
        st = build_symbol_table(["TREDEF"], cbd)
        node = st.find("WS-DATE-PARTS")
        assert node is not None
        assert node.redefines_target == "WS-DATE-FIELD"

    def test_redefines_children_accessible(self, tmp_path):
        """Children of a REDEFINES group are accessible."""
        cpy_dir = tmp_path / "cpy"
        cpy_dir.mkdir()
        (cpy_dir / "TREDEF.cpy").write_text("""
           01  TEST-REC.
               05  WS-DATE-FIELD           PIC X(08).
               05  WS-DATE-PARTS REDEFINES WS-DATE-FIELD.
                   10  WS-YEAR             PIC X(04).
                   10  WS-MONTH            PIC X(02).
                   10  WS-DAY              PIC X(02).
        """, encoding="utf-8")
        cbd = CopybookDictionary(str(cpy_dir))
        st = build_symbol_table(["TREDEF"], cbd)
        year = st.find("WS-YEAR")
        assert year is not None
        assert year.parent.name == "WS-DATE-PARTS"


class TestScopeTracking:
    """Section scope tags on symbol nodes."""

    def test_copybook_origin_tracked(self):
        """Symbols track which copybook they came from."""
        cbd = CopybookDictionary(str(CARDDEMO / "app" / "cpy"))
        st = build_symbol_table(["CSUSR01Y"], cbd)
        node = st.find("SEC-USR-ID")
        assert node is not None
        assert node.copybook_origin == "CSUSR01Y"

    def test_linkage_section_flagged(self):
        """Symbols can be tagged with a section (WORKING-STORAGE, LINKAGE, etc.)."""
        cbd = CopybookDictionary(str(CARDDEMO / "app" / "cpy"))
        st = build_symbol_table(["CSUSR01Y"], cbd, section="LINKAGE")
        node = st.find("SEC-USR-ID")
        assert node is not None
        assert node.section == "LINKAGE"

    def test_default_section_is_working_storage(self):
        """Default section when not specified is WORKING-STORAGE."""
        cbd = CopybookDictionary(str(CARDDEMO / "app" / "cpy"))
        st = build_symbol_table(["CSUSR01Y"], cbd)
        node = st.find("SEC-USR-ID")
        assert node.section == "WORKING-STORAGE"

    def test_qualified_path(self):
        """fully_qualified_name returns the full path: FIELD.GROUP.RECORD."""
        cbd = CopybookDictionary(str(CARDDEMO / "app" / "cpy"))
        st = build_symbol_table(["COCOM01Y"], cbd)
        node = st.find("CDEMO-FROM-TRANID")
        fqn = node.fully_qualified_name()
        assert "CDEMO-FROM-TRANID" in fqn
        assert "CDEMO-GENERAL-INFO" in fqn
        assert "CARDDEMO-COMMAREA" in fqn

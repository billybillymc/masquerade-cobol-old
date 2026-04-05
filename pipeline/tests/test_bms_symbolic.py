"""Tests for bms_symbolic.py — BMS symbolic map generation.

IQ-11 Phase 2: Generate COBOL copybooks from BMS definitions so CICS
programs can compile with GnuCOBOL without the IBM DFHCSDUP utility.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bms_symbolic import (
    generate_symbolic_map,
    generate_symbolic_maps_for_mapset,
    generate_all_symbolic_maps,
)
from bms_parser import parse_bms_file
import shlex

from cobol_runner import is_cobc_available, _to_wsl_path, _build_cmd
from cics_stub import preprocess_cics

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
COBC_AVAILABLE = is_cobc_available()


class TestSymbolicMapGeneration:
    """Generate COBOL symbolic maps from BMS definitions."""

    def test_cosgn0a_produces_input_map(self):
        """COSGN0A generates COSGN0AI with L/F/I fields."""
        mapset = parse_bms_file(CARDDEMO / "app" / "bms" / "COSGN00.bms")
        source = generate_symbolic_map(mapset.maps[0])
        assert "COSGN0AI" in source
        assert "USERIDI" in source
        assert "PASSWDI" in source
        assert "USERIDL" in source
        assert "PASSWDL" in source
        assert "ERRMSGI" in source

    def test_cosgn0a_produces_output_map(self):
        """COSGN0A generates COSGN0AO with A/O fields."""
        mapset = parse_bms_file(CARDDEMO / "app" / "bms" / "COSGN00.bms")
        source = generate_symbolic_map(mapset.maps[0])
        assert "COSGN0AO" in source
        assert "ERRMSGO" in source
        assert "TITLE01O" in source
        assert "TRNNAMEO" in source
        assert "PGMNAMEO" in source
        assert "APPLIDO" in source
        assert "SYSIDO" in source
        assert "CURDATEO" in source
        assert "CURTIMEO" in source

    def test_output_redefines_input(self):
        """COSGN0AO REDEFINES COSGN0AI."""
        mapset = parse_bms_file(CARDDEMO / "app" / "bms" / "COSGN00.bms")
        source = generate_symbolic_map(mapset.maps[0])
        assert "REDEFINES COSGN0AI" in source

    def test_field_lengths_match_bms(self):
        """Generated PIC lengths match BMS LENGTH values."""
        mapset = parse_bms_file(CARDDEMO / "app" / "bms" / "COSGN00.bms")
        source = generate_symbolic_map(mapset.maps[0])
        # USERID has LENGTH=8, ERRMSG has LENGTH=78
        assert "PIC X(08)" in source  # USERID
        assert "PIC X(78)" in source  # ERRMSG

    def test_generates_all_carddemo_mapsets(self):
        """generate_all_symbolic_maps produces copybooks for all BMS files."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            files = generate_all_symbolic_maps(
                str(CARDDEMO / "app" / "bms"), tmp,
            )
            assert len(files) >= 10  # carddemo has 21 BMS files
            # COSGN00.cpy should exist
            assert any("COSGN00" in f for f in files)


@pytest.mark.skipif(not COBC_AVAILABLE, reason="GnuCOBOL not available in WSL")
class TestCicsCompilationWithSymbolicMaps:
    """Stubbed CICS source + symbolic maps compile with GnuCOBOL."""

    def test_cosgn00c_compiles_with_symbolic_maps(self, tmp_path):
        """COSGN00C after CICS stubbing + symbolic map generation compiles."""
        import subprocess

        # Step 1: Generate symbolic maps for all BMS files
        sym_dir = tmp_path / "symbolic"
        generate_all_symbolic_maps(str(CARDDEMO / "app" / "bms"), str(sym_dir))

        # Step 2: Preprocess CICS
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))

        # Step 3: Inject file status declarations for generated datasets
        source = result.source
        # Add USRSEC-FILE-STATUS to WORKING-STORAGE
        ws_inject = ""
        for ds in result.datasets:
            ws_inject += f"       01  {ds.file_alias}-STATUS         PIC XX.\n"
        if ws_inject:
            import re
            ws_m = re.search(
                r'(^\s*WORKING-STORAGE\s+SECTION\.)',
                source, re.MULTILINE | re.IGNORECASE,
            )
            if ws_m:
                pos = ws_m.end()
                source = source[:pos] + "\n" + ws_inject + source[pos:]

        # Step 4: Write stubbed source
        stubbed = tmp_path / "COSGN00C_STUB.cbl"
        stubbed.write_text(source, encoding="utf-8")

        # Step 5: Compile with copybook dirs including symbolic maps
        cpy_dir = _to_wsl_path(str(CARDDEMO / "app" / "cpy"))
        sym_wsl = _to_wsl_path(str(sym_dir))
        src_wsl = _to_wsl_path(str(stubbed))

        cmd = _build_cmd(["cobc", "-x", "-std=ibm", "-I", cpy_dir, "-I", sym_wsl, "-o", "/tmp/cosgn00c_stub", src_wsl])
        compile_result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
            capture_output=True, text=True, timeout=60,
        )

        errors = [l for l in compile_result.stderr.splitlines()
                  if "error:" in l.lower()]

        assert compile_result.returncode == 0, \
            f"Compilation failed ({len(errors)} errors):\n" + \
            "\n".join(errors[:20])

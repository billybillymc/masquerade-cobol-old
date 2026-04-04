"""Tests for cics_stub.py — CICS preprocessor for standalone execution.

IQ-11 Phase 2: Rewrites EXEC CICS into plain COBOL that GnuCOBOL can compile.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cics_stub import preprocess_cics, StubResult
from cobol_runner import is_cobc_available

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
COBC_AVAILABLE = is_cobc_available()


class TestCicsPreprocessing:
    """EXEC CICS commands are replaced with plain COBOL."""

    def test_read_stubbed(self):
        """EXEC CICS READ → indexed file READ with INVALID KEY."""
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
        assert "EXEC CICS READ" not in result.source
        # Should have READ ... KEY IS ... INVALID KEY
        assert "READ" in result.source
        assert "INVALID KEY" in result.source

    def test_xctl_stubbed(self):
        """EXEC CICS XCTL → DISPLAY + STOP RUN."""
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
        assert "EXEC CICS XCTL" not in result.source
        assert "XCTL-TO:" in result.source
        assert "COADM01C" in result.source
        assert "COMEN01C" in result.source

    def test_return_stubbed(self):
        """EXEC CICS RETURN → STOP RUN."""
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
        assert "EXEC CICS RETURN" not in result.source
        assert "STOP RUN" in result.source

    def test_send_map_stubbed(self):
        """EXEC CICS SEND MAP → DISPLAY."""
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
        assert "EXEC CICS SEND" not in result.source
        assert "SEND-MAP:" in result.source

    def test_receive_map_stubbed(self):
        """EXEC CICS RECEIVE MAP → READ from screen input file."""
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
        assert "EXEC CICS RECEIVE" not in result.source
        assert "RECEIVE-MAP:" in result.source

    def test_assign_stubbed(self):
        """EXEC CICS ASSIGN → MOVE mock values."""
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
        assert "EXEC CICS ASSIGN" not in result.source
        assert "TESTAPPL" in result.source  # mock APPLID

    def test_no_exec_cics_remains(self):
        """After preprocessing, no EXEC CICS blocks should remain."""
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
        assert "EXEC CICS" not in result.source.upper()

    def test_datasets_discovered(self):
        """Preprocessing discovers CICS datasets used."""
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
        dataset_names = [d.name for d in result.datasets]
        assert any("USRSEC" in n.upper() for n in dataset_names)

    def test_xctl_targets_captured(self):
        """XCTL program targets are captured."""
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
        assert "COADM01C" in result.xctl_targets
        assert "COMEN01C" in result.xctl_targets

    def test_dfhaid_mocked(self):
        """COPY DFHAID is replaced with mock definitions."""
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
        assert "COPY DFHAID" not in result.source.upper()
        assert "DFHENTER" in result.source
        assert "DFHPF3" in result.source

    def test_eibcalen_available(self):
        """EIBCALEN is defined (from mock DFHEIBLK)."""
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
        assert "EIBCALEN" in result.source
        assert "DFHEIBLK" in result.source

    def test_needs_screen_io_detected(self):
        """COSGN00C uses SEND/RECEIVE MAP → needs_screen_io is True."""
        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))
        assert result.needs_screen_io is True


@pytest.mark.skipif(not COBC_AVAILABLE, reason="GnuCOBOL not available in WSL")
class TestStubCompilation:
    """Stubbed source compiles with GnuCOBOL."""

    def test_stubbed_cosgn00c_compiles(self, tmp_path):
        """COSGN00C after preprocessing + symbolic maps compiles with GnuCOBOL."""
        import re
        import shlex
        import subprocess
        from cobol_runner import _to_wsl_path, _build_cmd
        from bms_symbolic import generate_all_symbolic_maps

        # Generate symbolic maps
        sym_dir = tmp_path / "symbolic"
        generate_all_symbolic_maps(str(CARDDEMO / "app" / "bms"), str(sym_dir))

        result = preprocess_cics(str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl"))

        # Inject file status declarations
        source = result.source
        ws_inject = ""
        for ds in result.datasets:
            ws_inject += f"       01  {ds.file_alias}-STATUS         PIC XX.\n"
        if ws_inject:
            ws_m = re.search(
                r'(^\s*WORKING-STORAGE\s+SECTION\.)',
                source, re.MULTILINE | re.IGNORECASE,
            )
            if ws_m:
                pos = ws_m.end()
                source = source[:pos] + "\n" + ws_inject + source[pos:]

        stubbed = tmp_path / "COSGN00C_STUB.cbl"
        stubbed.write_text(source, encoding="utf-8")

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
            f"Compilation failed ({len(errors)} errors):\n" + "\n".join(errors[:20])

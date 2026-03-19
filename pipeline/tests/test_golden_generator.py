"""Tests for golden_generator.py — end-to-end COBOL golden vector generation.

IQ-11: Seeds input data, compiles+runs COBOL via GnuCOBOL in WSL, captures
DISPLAY output as golden vectors, and verifies via differential harness.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cobol_runner import is_cobc_available, _to_wsl_path
from golden_generator import (
    GoldenRunConfig,
    parse_display_output,
    generate_golden_vectors,
)
from differential_harness import run_vectors, DiffVector

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
STUBS = Path(__file__).resolve().parent.parent / "stubs"
COBC_AVAILABLE = is_cobc_available()


class TestDisplayParsing:
    """Parse COBOL DISPLAY output into field-value dicts."""

    def test_parses_field_value_pairs(self):
        stdout = """\
ACCT-ID                 :12345678901
ACCT-ACTIVE-STATUS      :Y
ACCT-CURR-BAL           :000000500000+
-------------------------------------------------
"""
        records = parse_display_output(stdout, "CBACT01C")
        assert len(records) == 1
        assert records[0]["ACCT-ID"] == "12345678901"
        assert records[0]["ACCT-ACTIVE-STATUS"] == "Y"
        assert records[0]["ACCT-CURR-BAL"] == "000000500000+"

    def test_parses_multiple_records(self):
        stdout = """\
ACCT-ID                 :11111111111
-------------------------------------------------
ACCT-ID                 :22222222222
-------------------------------------------------
"""
        records = parse_display_output(stdout, "TEST")
        assert len(records) == 2
        assert records[0]["ACCT-ID"] == "11111111111"
        assert records[1]["ACCT-ID"] == "22222222222"

    def test_ignores_non_field_lines(self):
        stdout = """\
START OF EXECUTION OF PROGRAM CBACT01C
ACCT-ID                 :12345678901
-------------------------------------------------
END OF EXECUTION OF PROGRAM CBACT01C
"""
        records = parse_display_output(stdout, "CBACT01C")
        assert len(records) == 1
        assert "ACCT-ID" in records[0]


@pytest.mark.skipif(not COBC_AVAILABLE, reason="GnuCOBOL (cobc) not available in WSL")
class TestEndToEndGoldenGeneration:
    """Full pipeline: seed → compile → run → capture → verify."""

    def _seed_input_file(self, work_dir: str):
        """Create indexed input file via a seed COBOL program."""
        seed_src = Path(__file__).resolve().parent.parent / "tests" / "seedcbact01c.cbl"
        seed_src.write_text("""\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SEEDFILE.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCTFILE ASSIGN TO ACCTFILE
                  ORGANIZATION IS INDEXED
                  ACCESS MODE IS SEQUENTIAL
                  RECORD KEY IS FD-ACCT-ID
                  FILE STATUS IS WS-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD  ACCTFILE.
       01  FD-ACCTFILE-REC.
           05 FD-ACCT-ID                        PIC 9(11).
           05 FD-ACCT-DATA                      PIC X(289).
       WORKING-STORAGE SECTION.
       COPY CVACT01Y.
       01  WS-STATUS                PIC XX.
       PROCEDURE DIVISION.
           OPEN OUTPUT ACCTFILE.
           INITIALIZE ACCOUNT-RECORD.
           MOVE 12345678901       TO ACCT-ID.
           MOVE 'Y'              TO ACCT-ACTIVE-STATUS.
           MOVE 5000.00          TO ACCT-CURR-BAL.
           MOVE 10000.00         TO ACCT-CREDIT-LIMIT.
           MOVE 2000.00          TO ACCT-CASH-CREDIT-LIMIT.
           MOVE '2020-01-15'     TO ACCT-OPEN-DATE.
           MOVE '2026-01-15'     TO ACCT-EXPIRAION-DATE.
           MOVE '2024-06-01'     TO ACCT-REISSUE-DATE.
           MOVE 500.00           TO ACCT-CURR-CYC-CREDIT.
           MOVE 0.00             TO ACCT-CURR-CYC-DEBIT.
           MOVE '10001     '     TO ACCT-ADDR-ZIP.
           MOVE 'GRP001    '     TO ACCT-GROUP-ID.
           MOVE ACCOUNT-RECORD   TO FD-ACCTFILE-REC.
           WRITE FD-ACCTFILE-REC.
           CLOSE ACCTFILE.
           DISPLAY 'SEED DONE'.
           STOP RUN.
""", encoding="utf-8")

        cpy_dir = _to_wsl_path(str(CARDDEMO / "app" / "cpy"))
        src_wsl = _to_wsl_path(str(seed_src))
        acct_file = f"{work_dir}/acct_input.dat"

        cmd = f'cobc -x -std=ibm -I {cpy_dir} -o {work_dir}/seedfile {src_wsl} && export ACCTFILE="{acct_file}" && {work_dir}/seedfile'
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c",
             f"mkdir -p {work_dir} && {cmd}"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"Seed failed: {result.stderr}"
        return acct_file

    def test_cbact01c_golden_vectors(self):
        """Generate golden vectors from CBACT01C and verify via differential harness."""
        work_dir = "/tmp/golden_cbact01c"
        acct_file = self._seed_input_file(work_dir)

        config = GoldenRunConfig(
            program="CBACT01C",
            source_file=str(CARDDEMO / "app" / "cbl" / "CBACT01C.cbl"),
            copybook_dirs=[str(CARDDEMO / "app" / "cpy")],
            stub_files=[str(STUBS / "COBDATFT.cbl")],
            input_records=[
                {
                    "ACCT-ID": "12345678901",
                    "ACCT-ACTIVE-STATUS": "Y",
                    "ACCT-CURR-BAL": "5000.00",
                },
            ],
            file_assignments={
                "ACCTFILE": acct_file,
                "OUTFILE": f"{work_dir}/out_acct.dat",
                "ARRYFILE": f"{work_dir}/out_array.dat",
                "VBRCFILE": f"{work_dir}/out_vbrc.dat",
            },
            output_file_names=["OUTFILE", "ARRYFILE", "VBRCFILE"],
        )

        vectors = generate_golden_vectors(config, work_dir=work_dir)
        assert len(vectors) >= 1, "Should produce at least one golden vector"

        # The vector should have the account fields from DISPLAY output
        v = vectors[0]
        assert v.program == "CBACT01C"
        assert v.expected_outputs.get("ACCT-ID") == "12345678901"
        assert "ACCT-CURR-BAL" in v.expected_outputs

        # Now simulate: if reimplementation produces same outputs → 100% confidence
        for vec in vectors:
            vec.actual_outputs = dict(vec.expected_outputs)  # perfect match

        report = run_vectors(vectors)
        assert report.confidence_score == 100.0
        assert report.failed == 0

    def test_golden_vectors_saved_and_loaded(self, tmp_path):
        """Golden vectors can be saved and reloaded."""
        work_dir = "/tmp/golden_cbact01c_save"
        acct_file = self._seed_input_file(work_dir)

        config = GoldenRunConfig(
            program="CBACT01C",
            source_file=str(CARDDEMO / "app" / "cbl" / "CBACT01C.cbl"),
            copybook_dirs=[str(CARDDEMO / "app" / "cpy")],
            stub_files=[str(STUBS / "COBDATFT.cbl")],
            input_records=[{"ACCT-ID": "12345678901"}],
            file_assignments={
                "ACCTFILE": acct_file,
                "OUTFILE": f"{work_dir}/out.dat",
                "ARRYFILE": f"{work_dir}/arr.dat",
                "VBRCFILE": f"{work_dir}/vbr.dat",
            },
            output_file_names=["OUTFILE", "ARRYFILE", "VBRCFILE"],
        )

        vectors = generate_golden_vectors(config, work_dir=work_dir)

        from differential_harness import save_golden_vectors, load_golden_vectors
        save_golden_vectors(vectors, "CBACT01C", str(tmp_path))
        loaded = load_golden_vectors("CBACT01C", str(tmp_path))
        assert len(loaded) == len(vectors)
        assert loaded[0].expected_outputs == vectors[0].expected_outputs

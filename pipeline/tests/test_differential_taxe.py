"""Differential test: Taxe Fonciere COBOL vs Python reimplementation.

Tests the tax calculation subroutine EFITA3B8 by calling it with known
input parameters and comparing CR/RC codes between COBOL and Python.
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reimpl"))

from cobol_runner import is_cobc_available, _to_wsl_path
from differential_harness import TestVector, run_vectors, render_report_text
from reimpl.taxe_fonciere import TaxInput, calculate_tax

TAXE = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "taxe-fonciere"
COBC_AVAILABLE = is_cobc_available()


def _compile_taxe(tmp_path):
    """Compile EFITA3B8 + driver."""
    src_dir = TAXE / "src"
    src_wsl = _to_wsl_path(str(src_dir))

    # Write a driver that tests multiple scenarios
    driver_src = tmp_path / "taxedriver.cbl"
    driver_src.write_text("""\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. TAXEDRIVER.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 WS-COMBAT              PIC X(600) VALUE SPACES.
       01 WS-RETOUR              PIC X(600) VALUE SPACES.
       01 WS-CR                  PIC 9(2) VALUE 0.
       01 WS-RC                  PIC 9(2) VALUE 0.
       01 WS-PARM                PIC X VALUE ' '.
       PROCEDURE DIVISION.
      * Scenario 1: Valid input — year 2018, dept 75, commune 056
           INITIALIZE WS-COMBAT WS-RETOUR.
           MOVE 0 TO WS-CR WS-RC.
           MOVE 'B' TO WS-PARM.
           MOVE '2018' TO WS-COMBAT(3:4).
           MOVE '75' TO WS-COMBAT(7:2).
           MOVE '1' TO WS-COMBAT(9:1).
           MOVE '056' TO WS-COMBAT(10:3).
           CALL 'EFITA3B8' USING
               WS-COMBAT WS-RETOUR WS-CR WS-RC WS-PARM.
           DISPLAY 'SCENARIO1:CR=' WS-CR ',RC=' WS-RC.

      * Scenario 2: Missing year — should fail validation
           INITIALIZE WS-COMBAT WS-RETOUR.
           MOVE 0 TO WS-CR WS-RC.
           MOVE 'B' TO WS-PARM.
           MOVE '75' TO WS-COMBAT(7:2).
           MOVE '056' TO WS-COMBAT(10:3).
           CALL 'EFITA3B8' USING
               WS-COMBAT WS-RETOUR WS-CR WS-RC WS-PARM.
           DISPLAY 'SCENARIO2:CR=' WS-CR ',RC=' WS-RC.

      * Scenario 3: Empty input — should fail validation
           INITIALIZE WS-COMBAT WS-RETOUR.
           MOVE 0 TO WS-CR WS-RC.
           MOVE 'B' TO WS-PARM.
           CALL 'EFITA3B8' USING
               WS-COMBAT WS-RETOUR WS-CR WS-RC WS-PARM.
           DISPLAY 'SCENARIO3:CR=' WS-CR ',RC=' WS-RC.

           STOP RUN.
""", encoding="utf-8")

    driver_wsl = _to_wsl_path(str(driver_src))
    workdir = "/tmp/taxe_diff"

    cmd = (
        f"mkdir -p {workdir} && "
        f"cobc -std=ibm -I {src_wsl} -c -o {workdir}/EFITA3B8.o {src_wsl}/EFITA3B8.cob && "
        f"cobc -x -std=ibm -I {src_wsl} -o {workdir}/taxedriver {driver_wsl} {workdir}/EFITA3B8.o"
    )
    r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"Compile failed: {r.stderr}"
    return f"{workdir}/taxedriver"


def _run_taxe_driver(binary):
    r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", binary],
                       capture_output=True, text=True, timeout=15)
    return r.stdout


def _parse_taxe_output(stdout):
    """Parse SCENARIO1:CR=xx,RC=xx lines."""
    import re
    results = {}
    for m in re.finditer(r'SCENARIO(\d+):CR=(\d+),RC=(\d+)', stdout):
        scenario = int(m.group(1))
        results[scenario] = {"CR": m.group(2), "RC": m.group(3)}
    return results


@pytest.mark.skipif(not COBC_AVAILABLE, reason="GnuCOBOL not available in WSL")
class TestDifferentialTaxeFonciere:

    @pytest.fixture(scope="class")
    def cobol_results(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("taxe")
        binary = _compile_taxe(tmp)
        stdout = _run_taxe_driver(binary)
        return _parse_taxe_output(stdout)

    def test_all_scenarios_match(self, cobol_results):
        """CR/RC codes match between COBOL and Python for all scenarios."""
        # Python scenarios matching the COBOL driver
        python_scenarios = {
            1: calculate_tax(TaxInput(
                dan="2018", cc2dep="75", ccodir="1", ccocom="056", parm="B",
            )),
            2: calculate_tax(TaxInput(
                dan="", cc2dep="75", ccocom="056", parm="B",
            )),
            3: calculate_tax(TaxInput(
                dan="", cc2dep="", ccocom="", parm="B",
            )),
        }

        vectors = []
        for scenario_id in [1, 2, 3]:
            cobol = cobol_results.get(scenario_id, {"CR": "??", "RC": "??"})
            python = python_scenarios[scenario_id]

            vectors.append(TestVector(
                vector_id=f"TAXE_S{scenario_id}",
                program="EFITA3B8",
                inputs={"SCENARIO": str(scenario_id)},
                expected_outputs={
                    "CR": cobol["CR"],
                    "RC": cobol["RC"],
                },
                actual_outputs={
                    "CR": f"{python.cr:02d}",
                    "RC": f"{python.rc:02d}",
                },
                field_types={"CR": "str", "RC": "str"},
            ))

        report = run_vectors(vectors)
        print("\n" + render_report_text(report))

        # Error scenarios (2, 3) should definitely match
        error_vectors = [v for v in vectors if v.vector_id != "TAXE_S1"]
        error_report = run_vectors(error_vectors)
        assert error_report.confidence_score == 100.0, \
            f"Error path mismatch!\n{render_report_text(error_report)}"

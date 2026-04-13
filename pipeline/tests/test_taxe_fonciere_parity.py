"""Cross-language parity tests for EFITA3B8 — French property tax (Taxe Fonciere).

Seventh Java reimplementation, fourth codebase. Heavy arithmetic: 8
cotisation calculations using COBOL ROUNDED (HALF_UP to integer), 6 OM zone
evaluations via EVALUATE on 2-char zone codes, 3 fee brackets (3%, 8%, 9%)
with assiette/non-valeur split and a rebalancing rule.
"""

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vector_runner import JavaRunner, PythonRunner, RunRequest

RUNNER_JAR = (
    Path(__file__).resolve().parent.parent
    / "reimpl" / "java" / "runner" / "target" / "masquerade-runner.jar"
)
JAVA_BIN = "C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot/bin/java.exe"

def _java_available():
    return RUNNER_JAR.exists() and Path(JAVA_BIN).exists()

def _jr():
    return JavaRunner(jar_path=RUNNER_JAR, java_bin=JAVA_BIN)

SCENARIOS = ["HAPPY_BASIC", "WITH_OM", "BAD_CCOBNB", "BAD_YEAR"]


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestTaxeFonciereParity:

    def setup_method(self):
        self.py = PythonRunner()
        self.jv = _jr()

    def test_all_scenarios_byte_identical(self):
        mismatches = []
        for s in SCENARIOS:
            req = RunRequest(program="TAXE_FONCIERE", vector_id=s, inputs={"SCENARIO": s})
            pr = self.py.run(req)
            jr = self.jv.run(req)
            assert pr.ok, f"{s}: Python errored: {pr.errors}"
            assert jr.ok, f"{s}: Java errored: {jr.errors}"
            if pr.outputs != jr.outputs:
                lines = [f"{s}:"]
                for k in sorted(set(pr.outputs) | set(jr.outputs)):
                    pv, jv = pr.outputs.get(k, "?"), jr.outputs.get(k, "?")
                    if pv != jv:
                        lines.append(f"  {k}: py={pv!r} java={jv!r}")
                mismatches.append("\n".join(lines))
        assert not mismatches, "\n\n".join(mismatches)

    def test_happy_basic_arithmetic(self):
        """Verify hand-computed cotisations: base * rate / 100, ROUNDED."""
        jr = self.jv.run(RunRequest(
            program="TAXE_FONCIERE", vector_id="HB",
            inputs={"SCENARIO": "HAPPY_BASIC"},
        ))
        o = jr.outputs
        # 10000 * 18.99 / 100 = 1899
        assert o["MCTCOM"] == "1899"
        # 10000 * 12.50 / 100 = 1250
        assert o["MCTDEP"] == "1250"
        # 5000 * 2.00 / 100 = 100
        assert o["MCTSYN"] == "100"
        # frais 3%: assiette = round(3399 * 0.01) = 34
        assert o["MFA300"] == "34"
        # total du = cotisations + frais
        assert o["TCTDU"] == "3772"

    def test_with_om_zones(self):
        """OM zones P(10%), RA(7.5%), RB(5%) add to TCTOM=1900."""
        jr = self.jv.run(RunRequest(
            program="TAXE_FONCIERE", vector_id="OM",
            inputs={"SCENARIO": "WITH_OM"},
        ))
        # 10000*10/100=1000, 8000*7.5/100=600, 6000*5/100=300 → 1900
        assert jr.outputs["TCTOM"] == "1900"
        assert jr.outputs["TCTDU"] == "5824"

    def test_bad_ccobnb_rejects(self):
        jr = self.jv.run(RunRequest(
            program="TAXE_FONCIERE", vector_id="BC",
            inputs={"SCENARIO": "BAD_CCOBNB"},
        ))
        assert jr.outputs["CR"] == "12"
        assert jr.outputs["RC"] == "1"
        assert jr.outputs["MCTCOM"] == "0"

    def test_bad_year_rejects(self):
        jr = self.jv.run(RunRequest(
            program="TAXE_FONCIERE", vector_id="BY",
            inputs={"SCENARIO": "BAD_YEAR"},
        ))
        assert jr.outputs["CR"] == "12"
        assert jr.outputs["RC"] == "2"


class TestPythonSideWorks:
    def test_python_happy(self):
        r = PythonRunner().run(RunRequest(
            program="TAXE_FONCIERE", vector_id="V1",
            inputs={"SCENARIO": "HAPPY_BASIC"},
        ))
        assert r.ok
        assert r.outputs["MCTCOM"] == "1899"
        assert r.outputs["TCTDU"] == "3772"

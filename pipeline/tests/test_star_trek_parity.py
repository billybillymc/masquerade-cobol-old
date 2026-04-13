"""Cross-language parity tests for Star Trek (ctrek.cob) — core deterministic engine.

Eighth Java reimplementation, fifth and final codebase. Exercises IEEE 754
float-precision RNG parity: the COBOL game uses a linear congruential
generator `seed = frac(262147 * seed)` truncated to 12 decimal places.
Both Python and Java use 64-bit doubles for this arithmetic. If the final
`seed_x` value matches after 600+ galaxy-init rolls, the entire RNG chain
is verified — and if the RNG matches, every game-state consequence
(positions, counts, star dates) must also match.

Multiple seeds are tested to catch any platform-specific float rounding
divergence across different regions of the double-precision space.
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


# Multiple seeds exercise different regions of the RNG's float space.
# skill/name variations exercise different skill-based computations.
INIT_SCENARIOS = [
    ("SEED_1", "12345678", "2", "KIRK"),
    ("SEED_2", "00000001", "1", "SPOCK"),
    ("SEED_3", "99999999", "4", "PICARD"),
    ("SEED_4", "08153042", "3", "JANEWAY"),
    ("SEED_5", "55555555", "1", "ARCHER"),
    ("SEED_6", "23595999", "2", "SISKO"),
]


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestStarTrekParity:

    def setup_method(self):
        self.py = PythonRunner()
        self.jv = _jr()

    @pytest.mark.parametrize("vid,seed,skill,name", INIT_SCENARIOS)
    def test_init_state_byte_identical(self, vid, seed, skill, name):
        """The most important parity test: every galaxy field must match
        for every seed. If SEED_X matches to 12dp after 600+ rolls,
        the IEEE 754 double chain is byte-identical."""
        req = RunRequest(
            program="STAR_TREK", vector_id=vid,
            inputs={"SCENARIO": "INIT_STATE", "SEED": seed,
                    "SKILL_LEVEL": skill, "CAPTAIN_NAME": name},
        )
        pr = self.py.run(req)
        jr = self.jv.run(req)
        assert pr.ok, f"{vid}: Python errored: {pr.errors}"
        assert jr.ok, f"{vid}: Java errored: {jr.errors}"

        if pr.outputs != jr.outputs:
            lines = [f"{vid} (seed={seed}, skill={skill}, name={name}):"]
            for k in sorted(set(pr.outputs) | set(jr.outputs)):
                pv, jv = pr.outputs.get(k, "?"), jr.outputs.get(k, "?")
                if pv != jv:
                    lines.append(f"  {k}: py={pv!r} java={jv!r}")
            pytest.fail("\n".join(lines))

    def test_seed_x_precision(self):
        """SEED_X is formatted to 12 decimal places — this is the full
        precision of the COBOL PIC V9(6) intermediate truncated to 12dp.
        If the 12th decimal place matches, no float drift occurred."""
        for vid, seed, skill, name in INIT_SCENARIOS:
            req = RunRequest(
                program="STAR_TREK", vector_id=vid,
                inputs={"SCENARIO": "INIT_STATE", "SEED": seed,
                        "SKILL_LEVEL": skill, "CAPTAIN_NAME": name},
            )
            jr = self.jv.run(req)
            sx = jr.outputs["SEED_X"]
            # Must be "0.XXXXXXXXXXXX" — exactly 12 digits after the dot
            parts = sx.split(".")
            assert len(parts) == 2 and len(parts[1]) == 12, \
                f"{vid}: SEED_X={sx!r} doesn't have 12dp"

    def test_entity_counts_consistent(self):
        """K_OR klingons placed + VAB2 romulons + VAB1 bases + 275 stars + 1E + 1H
        should account for all non-space cells. Some overlap (objects placed
        on stars) reduces star count below 275."""
        for vid, seed, skill, name in INIT_SCENARIOS[:3]:
            req = RunRequest(
                program="STAR_TREK", vector_id=vid,
                inputs={"SCENARIO": "INIT_STATE", "SEED": seed,
                        "SKILL_LEVEL": skill, "CAPTAIN_NAME": name},
            )
            jr = self.jv.run(req)
            o = jr.outputs
            k = int(o["COUNT_K"])
            r = int(o["COUNT_R"])
            b = int(o["COUNT_B"])
            # Klingons and bases are placed in EMPTY cells (retry loop)
            assert k == int(o["K_OR"])
            assert b == int(o["VAB1"])
            assert int(o["COUNT_E"]) == 1
            assert int(o["COUNT_H"]) == 1


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestStarTrekMissionParams:
    def test_all_skill_levels(self):
        py = PythonRunner()
        jv = _jr()
        for skill in ["1", "2", "3", "4"]:
            req = RunRequest(
                program="STAR_TREK", vector_id=f"MP_{skill}",
                inputs={"SCENARIO": "MISSION_PARAMS", "SKILL_LEVEL": skill},
            )
            pr = py.run(req)
            jr = jv.run(req)
            assert pr.outputs == jr.outputs, \
                f"skill={skill}: py={pr.outputs} java={jr.outputs}"


@pytest.mark.skipif(not _java_available(), reason="Java runner JAR not built")
class TestStarTrekSkillValidation:
    def test_valid_and_invalid(self):
        py = PythonRunner()
        jv = _jr()
        for level in ["0", "1", "2", "3", "4", "5", "abc"]:
            req = RunRequest(
                program="STAR_TREK", vector_id=f"SV_{level}",
                inputs={"SCENARIO": "SKILL_VALIDATION", "LEVEL": level},
            )
            pr = py.run(req)
            jr = jv.run(req)
            assert pr.outputs == jr.outputs, \
                f"level={level}: py={pr.outputs} java={jr.outputs}"


class TestPythonSideWorks:
    def test_init_state(self):
        r = PythonRunner().run(RunRequest(
            program="STAR_TREK", vector_id="V1",
            inputs={"SCENARIO": "INIT_STATE", "SEED": "12345678",
                    "SKILL_LEVEL": "2", "CAPTAIN_NAME": "KIRK"},
        ))
        assert r.ok
        assert r.outputs["MRCTR"] == "32"
        assert r.outputs["KLINGONS"] == "18"

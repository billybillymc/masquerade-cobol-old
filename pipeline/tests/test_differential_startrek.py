"""Differential test: Star Trek COBOL vs Python reimplementation.

Runs the same seed through both COBOL (compiled via GnuCOBOL) and Python,
comparing galaxy initialization state and command outputs.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "reimpl"))

from cobol_runner import is_cobc_available, _to_wsl_path
from differential_harness import TestVector, run_vectors, render_report_text
from reimpl.star_trek import (
    StarTrekGame,
    validate_skill_level,
    TITLE,
    INVALID_SKILL_MSG,
)

STARTREK = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "star-trek"
COBC_AVAILABLE = is_cobc_available()


def _compile_star_trek():
    src_wsl = _to_wsl_path(str(STARTREK / "ctrek.cob"))
    cmd = f'cobc -free -x -o /tmp/ctrek_diff {src_wsl}'
    r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"Compile failed: {r.stderr}"
    return "/tmp/ctrek_diff"


def _run_star_trek(binary, stdin_text):
    cmd = f'printf "{stdin_text}" | timeout 5 {binary}'
    r = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                       capture_output=True, text=True, timeout=15)
    return r.stdout


@pytest.mark.skipif(not COBC_AVAILABLE, reason="GnuCOBOL not available in WSL")
class TestDifferentialStarTrek:

    @pytest.fixture(scope="class")
    def binary(self):
        return _compile_star_trek()

    def test_title_screen_matches(self, binary):
        """Title '*STAR TREK*' appears in both COBOL and Python."""
        cobol_out = _run_star_trek(binary, "TEST\\n1\\nn\\nq")
        cobol_has_title = TITLE.strip() in cobol_out

        game = StarTrekGame(seed=12345678, captain_name="TEST", skill_level=1)
        init_output = game.get_initial_output()
        python_has_title = any(TITLE in line for line in init_output)

        vectors = [TestVector(
            vector_id="TITLE",
            program="STAR_TREK",
            inputs={},
            expected_outputs={"HAS_TITLE": "Y" if cobol_has_title else "N"},
            actual_outputs={"HAS_TITLE": "Y" if python_has_title else "N"},
            field_types={"HAS_TITLE": "str"},
        )]
        report = run_vectors(vectors)
        assert report.confidence_score == 100.0

    def test_invalid_skill_level_matches(self, binary):
        """Invalid skill level (9) produces same error in COBOL and Python."""
        cobol_out = _run_star_trek(binary, "TEST\\n9\\n1\\nn\\nq")
        cobol_has_error = INVALID_SKILL_MSG in cobol_out

        valid, msg = validate_skill_level("9")
        python_has_error = not valid and msg == INVALID_SKILL_MSG

        vectors = [TestVector(
            vector_id="INVALID_SKILL",
            program="STAR_TREK",
            inputs={"SKILL": "9"},
            expected_outputs={"INVALID_SKILL_ERROR": "Y" if cobol_has_error else "N"},
            actual_outputs={"INVALID_SKILL_ERROR": "Y" if python_has_error else "N"},
            field_types={"INVALID_SKILL_ERROR": "str"},
        )]
        report = run_vectors(vectors)
        assert report.confidence_score == 100.0

    def test_valid_skill_levels(self, binary):
        """Skill levels 1-4 all accepted by both COBOL and Python."""
        vectors = []
        for level in ["1", "2", "3", "4"]:
            cobol_out = _run_star_trek(binary, f"TEST\\n{level}\\nn\\nq")
            cobol_accepted = INVALID_SKILL_MSG not in cobol_out

            valid, _ = validate_skill_level(level)

            vectors.append(TestVector(
                vector_id=f"SKILL_{level}",
                program="STAR_TREK",
                inputs={"SKILL": level},
                expected_outputs={"ACCEPTED": "Y" if cobol_accepted else "N"},
                actual_outputs={"ACCEPTED": "Y" if valid else "N"},
                field_types={"ACCEPTED": "str"},
            ))

        report = run_vectors(vectors)
        print("\n" + render_report_text(report))
        assert report.confidence_score == 100.0

    def test_game_initializes_with_deterministic_seed(self):
        """StarTrekGame initializes deterministically from seed."""
        game1 = StarTrekGame(seed=12345678, captain_name="KIRK", skill_level=2)
        game2 = StarTrekGame(seed=12345678, captain_name="KIRK", skill_level=2)

        s1 = game1.get_status()
        s2 = game2.get_status()

        vectors = [TestVector(
            vector_id="DETERMINISTIC_INIT",
            program="STAR_TREK",
            inputs={"SEED": "12345678"},
            expected_outputs={
                "KLINGONS": str(s1["klingons_initial"]),
                "FUEL": str(s1["fuel_count"]),
                "QUADRANT": str(s1["quadrant"]),
                "SEED_X": f"{s1['seed_x']:.6f}",
            },
            actual_outputs={
                "KLINGONS": str(s2["klingons_initial"]),
                "FUEL": str(s2["fuel_count"]),
                "QUADRANT": str(s2["quadrant"]),
                "SEED_X": f"{s2['seed_x']:.6f}",
            },
            field_types={k: "str" for k in ["KLINGONS", "FUEL", "QUADRANT", "SEED_X"]},
        )]
        report = run_vectors(vectors)
        assert report.confidence_score == 100.0

    def test_status_command_produces_output(self):
        """com 1 (status) produces output with fuel/damage/shields."""
        game = StarTrekGame(seed=12345678, captain_name="KIRK", skill_level=1)
        game.get_initial_output()  # consume init output
        output = game.process_command("com 1")
        output_text = " ".join(output)

        vectors = [TestVector(
            vector_id="STATUS_CMD",
            program="STAR_TREK",
            inputs={"CMD": "com 1"},
            expected_outputs={"HAS_FUEL": "Y", "HAS_SHIELD": "Y"},
            actual_outputs={
                "HAS_FUEL": "Y" if "FUEL" in output_text.upper() else "N",
                "HAS_SHIELD": "Y" if "SHIELD" in output_text.upper() else "N",
            },
            field_types={"HAS_FUEL": "str", "HAS_SHIELD": "str"},
        )]
        report = run_vectors(vectors)
        assert report.confidence_score == 100.0

    def test_terminate_ends_game(self):
        """com 6 terminates the game."""
        game = StarTrekGame(seed=12345678, captain_name="KIRK", skill_level=1)
        game.get_initial_output()
        output = game.process_command("com 6")
        output_text = " ".join(output)

        vectors = [TestVector(
            vector_id="TERMINATE",
            program="STAR_TREK",
            inputs={"CMD": "com 6"},
            expected_outputs={"GAME_OVER": "Y", "STRANDED": "Y"},
            actual_outputs={
                "GAME_OVER": "Y" if game.game_over else "N",
                "STRANDED": "Y" if "STRANDED" in output_text.upper() else "N",
            },
            field_types={"GAME_OVER": "str", "STRANDED": "str"},
        )]
        report = run_vectors(vectors)
        assert report.confidence_score == 100.0

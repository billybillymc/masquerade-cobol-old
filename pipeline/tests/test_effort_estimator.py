"""Tests for effort_estimator.py — migration effort estimation."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from effort_estimator import estimate_program, estimate_estate


def _make_readiness(program="TESTPGM", code_lines=200, has_cics=False,
                    isolation=80, simplicity=80, dep_clarity=90, testability=80, composite=82):
    return {
        "program": program,
        "composite": composite,
        "isolation": isolation,
        "simplicity": simplicity,
        "dependency_clarity": dep_clarity,
        "testability": testability,
        "details": {
            "code_lines": code_lines,
            "total_lines": code_lines + 50,
            "paragraph_count": 5,
            "callers": 0,
            "callees": 0,
            "copybooks": 2,
            "shared_peers": 0,
            "has_cics": has_cics,
            "unresolved_copybooks": [],
            "unresolved_calls": [],
        },
    }


class TestProgramEstimate:
    def test_simple_batch_low_effort(self):
        r = _make_readiness(code_lines=100, has_cics=False, composite=85, simplicity=90)
        est = estimate_program(r)
        assert est.category == "Batch"
        assert est.effort_days < 2
        assert est.risk_level == "LOW"

    def test_large_cics_high_effort(self):
        r = _make_readiness(code_lines=1200, has_cics=True, composite=25,
                           isolation=20, simplicity=20, dep_clarity=40, testability=30)
        est = estimate_program(r)
        assert est.category == "CICS Online"
        assert est.effort_days > 10
        assert est.risk_level == "HIGH"

    def test_coupling_increases_effort(self):
        simple = _make_readiness(code_lines=300, isolation=90)
        coupled = _make_readiness(code_lines=300, isolation=20, composite=40)
        est_simple = estimate_program(simple)
        est_coupled = estimate_program(coupled)
        assert est_coupled.effort_days > est_simple.effort_days

    def test_minimum_effort(self):
        r = _make_readiness(code_lines=10, composite=95, simplicity=95)
        est = estimate_program(r)
        assert est.effort_days >= 0.5

    def test_cics_has_higher_rate_than_batch(self):
        batch = _make_readiness(code_lines=500, has_cics=False, simplicity=60)
        cics = _make_readiness(code_lines=500, has_cics=True, simplicity=40, composite=50)
        assert estimate_program(cics).effort_days > estimate_program(batch).effort_days


class TestEstateEstimate:
    def test_estate_summary(self):
        rankings = [
            _make_readiness("PGM1", code_lines=100, composite=85),
            _make_readiness("PGM2", code_lines=500, has_cics=True, composite=40,
                           isolation=30, simplicity=40, dep_clarity=60, testability=50),
            _make_readiness("PGM3", code_lines=200, composite=70),
        ]
        result = estimate_estate(rankings)
        assert result["summary"]["total_programs"] == 3
        assert result["summary"]["total_effort_days"] > 0
        assert len(result["waves"]) == 3

    def test_quick_wins_identified(self):
        rankings = [
            _make_readiness("EASY1", code_lines=80, composite=90, simplicity=95),
            _make_readiness("EASY2", code_lines=120, composite=85, simplicity=90),
            _make_readiness("HARD1", code_lines=1000, has_cics=True, composite=20,
                           isolation=10, simplicity=15, dep_clarity=30, testability=20),
        ]
        result = estimate_estate(rankings)
        assert len(result["quick_wins"]) >= 1
        assert "EASY1" in result["quick_wins"]

    def test_wave_planning(self):
        rankings = [
            _make_readiness("QUICK", code_lines=50, composite=90, simplicity=95),
            _make_readiness("MEDIUM", code_lines=400, composite=55, isolation=50),
            _make_readiness("COMPLEX", code_lines=1500, has_cics=True, composite=15,
                           isolation=5, simplicity=10, dep_clarity=20, testability=15),
        ]
        result = estimate_estate(rankings)
        wave_names = [w["name"] for w in result["waves"]]
        assert "Wave 1: Quick Wins" in wave_names
        assert "Wave 2: Core Migration" in wave_names
        assert "Wave 3: Complex Programs" in wave_names

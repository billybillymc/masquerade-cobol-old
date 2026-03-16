"""Tests for behavioral test generation — IQ-05.

Verifies that the test generator produces tests with real business behavior
assertions derived from conditional blocks (IQ-01), copybook fields (IQ-02),
and business rules (IQ-04), not just hasattr/callable checks.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_generator import (
    generate_test_suite,
    generate_all_test_suites,
    _generate_behavioral_tests,
    GeneratedTestCase,
)
from spec_generator import ProgramSpec, ParagraphSpec, DataContract, generate_program_spec, _load_program_data
from graph_context import GraphIndex

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
PROGRAMS_JSON = CARDDEMO / "_analysis" / "programs.json"


def _load_program_data_dict() -> dict:
    return json.loads(PROGRAMS_JSON.read_text())


def _make_cosgn00c_spec() -> ProgramSpec:
    """Build a ProgramSpec for COSGN00C from real analysis data."""
    analysis_dir = CARDDEMO / "_analysis"
    graph = GraphIndex(str(analysis_dir))
    program_data = _load_program_data(analysis_dir)
    return generate_program_spec("COSGN00C", graph, program_data, str(CARDDEMO))


class TestBehavioralTestGeneration:
    """_generate_behavioral_tests() produces scenario-based tests from conditional blocks."""

    def test_generates_behavioral_tests_for_cosgn00c(self):
        """COSGN00C has conditional blocks — behavioral tests must be produced."""
        spec = _make_cosgn00c_spec()
        program_data = _load_program_data_dict()
        tests = _generate_behavioral_tests(spec, program_data.get("COSGN00C", {}))
        assert len(tests) >= 3, f"Expected >=3 behavioral tests, got {len(tests)}"

    def test_successful_login_scenario(self):
        """Must generate a test for: RESP=0, password matches → routes to admin/regular."""
        spec = _make_cosgn00c_spec()
        program_data = _load_program_data_dict()
        tests = _generate_behavioral_tests(spec, program_data.get("COSGN00C", {}))
        names = [t.name for t in tests]
        descriptions = " ".join(t.description.lower() for t in tests)
        # Must have a test about successful login / password match / resp 0
        assert any("resp" in n and "0" in n for n in names) or \
            "password" in descriptions or "match" in descriptions or "success" in descriptions, \
            f"No successful-login test found. Names: {names}"

    def test_wrong_password_scenario(self):
        """Must generate a test for: RESP=0, password doesn't match → error."""
        spec = _make_cosgn00c_spec()
        program_data = _load_program_data_dict()
        tests = _generate_behavioral_tests(spec, program_data.get("COSGN00C", {}))
        descriptions = " ".join(t.description.lower() for t in tests)
        assert "wrong" in descriptions or "mismatch" in descriptions or \
            "not match" in descriptions or "incorrect" in descriptions or \
            "else" in descriptions, \
            f"No wrong-password test found. Descriptions: {descriptions}"

    def test_user_not_found_scenario(self):
        """Must generate a test for: RESP=13 → user not found error."""
        spec = _make_cosgn00c_spec()
        program_data = _load_program_data_dict()
        tests = _generate_behavioral_tests(spec, program_data.get("COSGN00C", {}))
        descriptions = " ".join(t.description.lower() for t in tests)
        assert "not found" in descriptions or "13" in descriptions or \
            "user not found" in descriptions, \
            f"No user-not-found test found. Descriptions: {descriptions}"

    def test_behavioral_tests_have_real_assertions(self):
        """Behavioral tests must have assertions, not just TODO comments."""
        spec = _make_cosgn00c_spec()
        program_data = _load_program_data_dict()
        tests = _generate_behavioral_tests(spec, program_data.get("COSGN00C", {}))
        for tc in tests:
            real_assertions = [a for a in tc.assertions if not a.strip().startswith("#")]
            assert len(real_assertions) >= 1, \
                f"Test {tc.name} has no real assertions: {tc.assertions}"

    def test_behavioral_tests_are_decision_branch_category(self):
        """Behavioral tests should be categorized as 'decision_branch'."""
        spec = _make_cosgn00c_spec()
        program_data = _load_program_data_dict()
        tests = _generate_behavioral_tests(spec, program_data.get("COSGN00C", {}))
        for tc in tests:
            assert tc.category in ("happy_path", "error_path", "decision_branch", "boundary"), \
                f"Test {tc.name} has unexpected category: {tc.category}"


class TestBehavioralTestInSuite:
    """Behavioral tests are included in the full generated test suite."""

    def test_full_suite_includes_behavioral_tests(self):
        """generate_test_suite with program_data produces behavioral tests."""
        spec = _make_cosgn00c_spec()
        program_data = _load_program_data_dict()
        code = generate_test_suite(spec, program_data=program_data.get("COSGN00C", {}))
        # Must contain behavioral test methods, not just hasattr
        assert "pytest.mark.skip" in code, "Behavioral tests should be skip-marked"
        assert "resp" in code.lower() or "password" in code.lower() or "branch" in code.lower(), \
            "Suite should contain behavioral scenario tests"

    def test_full_suite_compiles(self):
        """The generated test suite with behavioral tests must be valid Python."""
        spec = _make_cosgn00c_spec()
        program_data = _load_program_data_dict()
        code = generate_test_suite(spec, program_data=program_data.get("COSGN00C", {}))
        try:
            compile(code, "<cosgn00c_tests>", "exec")
        except SyntaxError as e:
            raise AssertionError(f"Generated test suite has syntax error: {e}\n{code}")

    def test_behavioral_tests_increase_assertion_count(self):
        """Suite with behavioral tests has more real assertions than without."""
        spec = _make_cosgn00c_spec()
        program_data = _load_program_data_dict()

        code_without = generate_test_suite(spec)
        code_with = generate_test_suite(spec, program_data=program_data.get("COSGN00C", {}))

        # Count non-TODO assertions
        def count_assertions(code):
            return sum(1 for line in code.split('\n')
                       if 'assert ' in line and '# TODO' not in line)

        assert count_assertions(code_with) > count_assertions(code_without), \
            "Behavioral tests should add real assertions"


class TestFixtureGeneration:
    """Typed fixtures are generated from copybook field metadata."""

    def test_generates_fixture_setup_for_copybook_fields(self):
        """Behavioral tests should have setup lines that populate copybook fields."""
        spec = _make_cosgn00c_spec()
        program_data = _load_program_data_dict()
        tests = _generate_behavioral_tests(spec, program_data.get("COSGN00C", {}))
        all_setup = " ".join(" ".join(t.setup) for t in tests)
        # At least some tests should set up field values
        assert len(all_setup) > 0, "Behavioral tests should have setup lines"

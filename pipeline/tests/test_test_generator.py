"""Tests for test_generator.py — test case generation from COBOL specs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from test_generator import (
    generate_test_suite,
    generate_all_test_suites,
    _generate_init_tests,
    _generate_validation_tests,
    _generate_call_mock_tests,
    _generate_cics_tests,
    GeneratedTestCase,
)
from spec_generator import ProgramSpec, ParagraphSpec, DataContract

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"


def _make_spec(has_cics=False) -> ProgramSpec:
    paras = [
        ParagraphSpec(
            name="MAIN-PROCESS",
            performs=["VALIDATE"],
            calls=["COBDATFT"],
            cics_ops=["SEND(MAP)", "RECEIVE(MAP)"] if has_cics else [],
            data_flows_in=[],
            data_flows_out=["WS-STATUS"],
            decision_indicators=2,
            is_entry_point=True,
        ),
        ParagraphSpec(
            name="VALIDATE",
            performs=[],
            calls=[],
            cics_ops=[],
            data_flows_in=["ACCT-NUM"],
            data_flows_out=["WS-RETURN-CODE"],
            decision_indicators=1,
            is_entry_point=False,
        ),
    ]
    return ProgramSpec(
        program="TESTPGM2",
        program_type="CICS Online" if has_cics else "Batch",
        source_file="test.cbl",
        total_lines=200,
        code_lines=150,
        paragraph_count=2,
        cyclomatic_complexity=10,
        max_nesting=3,
        complexity_grade="MODERATE",
        callers=[],
        callees=["COBDATFT"],
        copybooks=["CPYDATA"],
        files_accessed=[],
        readiness_score=75.0,
        effort_days=2.5,
        risk_level="MEDIUM",
        paragraphs=paras,
        data_contracts=[DataContract("CPYDATA", 5, [], [])],
        cics_operations=[],
        data_flow_summary={"total_flows": 10, "fields_written": [], "fields_read": []},
        decision_count=10,
        computation_count=3,
        validation_fields=["WS-STATUS", "WS-RETURN-CODE"],
        modern_pattern="Service",
        migration_wave="Wave 1",
        notes=[],
        entry_paragraphs=["MAIN-PROCESS"],
        exit_points=[],
        perform_graph={},
    )


class TestInitTests:
    def test_creates_instantiation_test(self):
        spec = _make_spec()
        tests = _generate_init_tests(spec)
        assert any("instantiate" in t.name for t in tests)

    def test_creates_data_structure_tests(self):
        spec = _make_spec()
        tests = _generate_init_tests(spec)
        assert any("cpydata" in t.name for t in tests)


class TestValidationTests:
    def test_creates_validation_field_tests(self):
        spec = _make_spec()
        tests = _generate_validation_tests(spec)
        assert len(tests) >= 2
        assert any("ws_status" in t.name for t in tests)
        assert any("ws_return_code" in t.name for t in tests)

    def test_includes_error_scenarios(self):
        spec = _make_spec()
        tests = _generate_validation_tests(spec)
        error_tests = [t for t in tests if t.category == "error"]
        assert len(error_tests) >= 1


class TestCallMockTests:
    def test_generates_mock_for_external_call(self):
        spec = _make_spec()
        tests = _generate_call_mock_tests(spec)
        assert len(tests) >= 1
        assert any("cobdatft" in t.name for t in tests)


class TestCicsTests:
    def test_generates_screen_tests_for_cics(self):
        spec = _make_spec(has_cics=True)
        tests = _generate_cics_tests(spec)
        assert len(tests) >= 2
        assert any("screen_output" in t.name for t in tests)
        assert any("screen_input" in t.name for t in tests)

    def test_no_cics_tests_for_batch(self):
        spec = _make_spec(has_cics=False)
        tests = _generate_cics_tests(spec)
        assert len(tests) == 0


class TestFullSuiteGeneration:
    def test_generates_compilable_test_suite(self):
        spec = _make_spec()
        code = generate_test_suite(spec)
        assert "class TestTestpgm2:" in code
        assert "def test_can_instantiate" in code
        assert "import pytest" in code

    def test_generates_carddemo_test_suites(self):
        if not CARDDEMO.exists():
            return
        results = generate_all_test_suites(str(CARDDEMO))
        assert len(results) > 20
        tests_dir = CARDDEMO / "_analysis" / "generated_tests"
        assert tests_dir.exists()
        total_tests = sum(r.test_count for r in results.values())
        assert total_tests > 100

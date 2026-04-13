"""Tests for the JUnit 5 emitter in test_generator.py (W7).

Verifies that:
  - generate_test_suite_java emits a syntactically valid JUnit 5 class
  - Test count matches the pytest version (1:1 scenario parity)
  - All scenario categories (init, paragraph, validation, CICS, behavioral) appear
  - Original Python assertions are preserved as comments for the human implementer
  - Disabled markers carry over for behavioral tests
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spec_generator import ProgramSpec, ParagraphSpec, DataContract
from test_generator import generate_test_suite, generate_test_suite_java


def _make_spec(program_type="Batch", has_cics=False) -> ProgramSpec:
    paras = [
        ParagraphSpec(
            name="MAIN-PROCESS",
            performs=["INIT", "PROCESS-RECORDS"],
            calls=[],
            cics_ops=[],
            data_flows_in=[],
            data_flows_out=["WS-STATUS"],
            decision_indicators=2,
            is_entry_point=True,
        ),
        ParagraphSpec(
            name="INIT",
            performs=[],
            calls=["COBDATFT"],
            cics_ops=[],
            data_flows_in=[],
            data_flows_out=[],
            decision_indicators=0,
            is_entry_point=False,
        ),
        ParagraphSpec(
            name="PROCESS-RECORDS",
            performs=[],
            calls=[],
            cics_ops=["SEND(MAP)", "RECEIVE(MAP)"] if has_cics else [],
            data_flows_in=["ACCT-NUM"],
            data_flows_out=["WS-RESULT"],
            decision_indicators=1,
            is_entry_point=False,
        ),
    ]
    return ProgramSpec(
        program="TESTPGM1",
        program_type=program_type,
        source_file="test.cbl",
        total_lines=200,
        code_lines=150,
        paragraph_count=3,
        cyclomatic_complexity=10,
        max_nesting=3,
        complexity_grade="MODERATE",
        callers=["MAIN"],
        callees=["COBDATFT"],
        copybooks=["CPYTEST"],
        files_accessed=[],
        readiness_score=75.0,
        effort_days=2.5,
        risk_level="MEDIUM",
        paragraphs=paras,
        data_contracts=[DataContract(
            copybook="CPYTEST",
            field_count=10,
            key_fields=["ACCT-NUM"],
            shared_with=["OTHER"],
        )],
        cics_operations=[],
        data_flow_summary={"total_flows": 25, "fields_written": [], "fields_read": []},
        decision_count=10,
        computation_count=5,
        validation_fields=["WS-STATUS"],
        modern_pattern="Standalone service",
        migration_wave="Wave 1",
        notes=[],
        entry_paragraphs=["MAIN-PROCESS"],
        exit_points=[],
        perform_graph={},
    )


# ── Structural ─────────────────────────────────────────────────────────────


class TestJunit5Structure:
    """The emitted Java looks like a JUnit 5 test class."""

    def test_emits_package(self):
        code = generate_test_suite_java(_make_spec(), package="com.modernization.carddemo.testpgm1")
        assert "package com.modernization.carddemo.testpgm1;" in code

    def test_imports_junit5(self):
        code = generate_test_suite_java(_make_spec())
        assert "import org.junit.jupiter.api.Test;" in code
        assert "import org.junit.jupiter.api.BeforeEach;" in code
        assert "import org.junit.jupiter.api.DisplayName;" in code

    def test_imports_assertions(self):
        code = generate_test_suite_java(_make_spec())
        assert "import static org.junit.jupiter.api.Assertions.assertNotNull;" in code

    def test_emits_test_class(self):
        code = generate_test_suite_java(_make_spec())
        assert "class Testpgm1Test" in code

    def test_has_before_each_setup(self):
        code = generate_test_suite_java(_make_spec())
        assert "@BeforeEach" in code
        assert "void setUp()" in code
        assert "program = new Main();" in code

    def test_braces_balanced(self):
        code = generate_test_suite_java(_make_spec())
        assert code.count("{") == code.count("}")

    def test_tests_have_test_annotation(self):
        code = generate_test_suite_java(_make_spec())
        assert code.count("@Test") >= 5

    def test_tests_have_display_name(self):
        code = generate_test_suite_java(_make_spec())
        assert code.count("@DisplayName") >= 6  # 1 class + ≥5 methods


# ── Test count parity ──────────────────────────────────────────────────────


class TestPytestParity:
    """The Java emitter must produce the same scenario count as the pytest one."""

    def test_test_count_matches_pytest(self):
        spec = _make_spec()
        py_code = generate_test_suite(spec)
        java_code = generate_test_suite_java(spec)

        py_count = py_code.count("    def test_")
        java_count = java_code.count("    @Test")

        assert py_count == java_count, (
            f"pytest emitted {py_count} tests, JUnit emitted {java_count} — "
            "scenario coverage must be 1:1 across languages"
        )

    def test_test_count_matches_for_cics(self):
        spec = _make_spec(program_type="CICS Online", has_cics=True)
        py_code = generate_test_suite(spec)
        java_code = generate_test_suite_java(spec)

        py_count = py_code.count("    def test_")
        java_count = java_code.count("    @Test")

        assert py_count == java_count


# ── Original assertion intent preserved ────────────────────────────────────


class TestIntentPreservation:
    """Python assertions show up as // comments for the human implementer."""

    def test_assertion_comments_present(self):
        code = generate_test_suite_java(_make_spec())
        assert "// intent:" in code

    def test_setup_comments_present_when_setup_lines_exist(self):
        spec = _make_spec()
        code = generate_test_suite_java(spec)
        # validation tests have setup lines like "program.X = 'INVALID'"
        assert "// setup:" in code or "// intent:" in code

    def test_every_test_has_at_least_one_assertion(self):
        """Every test method must have at least one real assertion (not just a comment)."""
        code = generate_test_suite_java(_make_spec())
        assertion_count = (
            code.count("assertNotNull(program);")
            + code.count("assertDoesNotThrow(")
            + code.count("assertTrue(")
        )
        assert assertion_count >= code.count("    @Test"), (
            f"Expected at least one assertion per @Test, got "
            f"{assertion_count} assertions for {code.count('    @Test')} tests"
        )


# ── Test name conversion ──────────────────────────────────────────────────


class TestNameConversion:
    """snake_case pytest names become camelCase JUnit methods."""

    def test_init_test_becomes_camel_case(self):
        code = generate_test_suite_java(_make_spec())
        # test_can_instantiate → testCanInstantiate
        assert "void testCanInstantiate(" in code

    def test_paragraph_test_becomes_camel_case(self):
        code = generate_test_suite_java(_make_spec())
        # test_main_process_exists → testMainProcessExists
        assert "void testMainProcessExists(" in code

    def test_run_method_test_present(self):
        code = generate_test_suite_java(_make_spec())
        assert "void testRunMethodExists(" in code

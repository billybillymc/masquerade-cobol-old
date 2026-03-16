"""Tests for multi-language skeleton generation — IQ-08.

Verifies that the same ProgramSpec produces valid skeletons in Python, Java,
and C# via a language-neutral IR with pluggable renderers.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skeleton_ir import (
    IRModule,
    IRClass,
    IRField,
    IRMethod,
    spec_to_ir,
    PythonRenderer,
    JavaRenderer,
    CSharpRenderer,
)
from spec_generator import ProgramSpec, ParagraphSpec, DataContract


def _make_spec(program_type="Batch", has_cics=False) -> ProgramSpec:
    """Reusable test spec with paragraphs, calls, copybooks."""
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


class TestSkeletonIR:
    """spec_to_ir produces a language-neutral intermediate representation."""

    def test_ir_has_main_class(self):
        ir = spec_to_ir(_make_spec())
        assert ir.main_class == "Testpgm1"

    def test_ir_has_methods_for_paragraphs(self):
        ir = spec_to_ir(_make_spec())
        method_names = [m.name for m in ir.methods]
        assert "main_process" in method_names
        assert "init" in method_names
        assert "process_records" in method_names

    def test_ir_has_dataclass_for_copybook(self):
        ir = spec_to_ir(_make_spec())
        class_names = [c.name for c in ir.dataclasses]
        assert "Cpytest" in class_names

    def test_ir_has_service_stubs(self):
        ir = spec_to_ir(_make_spec())
        stub_names = [c.name for c in ir.service_stubs]
        assert "CobdatftService" in stub_names

    def test_ir_has_entry_points(self):
        ir = spec_to_ir(_make_spec())
        assert "main_process" in ir.entry_points

    def test_ir_preserves_program_type(self):
        ir = spec_to_ir(_make_spec(program_type="CICS Online"))
        assert ir.program_type == "CICS Online"


class TestPythonRenderer:
    """Python renderer produces valid Python from the IR."""

    def test_produces_valid_python(self):
        ir = spec_to_ir(_make_spec())
        code = PythonRenderer().render(ir)
        compile(code, "<python_skeleton>", "exec")

    def test_has_class_and_methods(self):
        ir = spec_to_ir(_make_spec())
        code = PythonRenderer().render(ir)
        assert "class Testpgm1:" in code
        assert "def main_process(self)" in code
        assert "def init(self)" in code

    def test_has_dataclass_decorator(self):
        ir = spec_to_ir(_make_spec())
        code = PythonRenderer().render(ir)
        assert "@dataclass" in code
        assert "class Cpytest:" in code

    def test_has_entry_point(self):
        ir = spec_to_ir(_make_spec())
        code = PythonRenderer().render(ir)
        assert "def run(self)" in code
        assert '__name__ == "__main__"' in code


class TestJavaRenderer:
    """Java renderer produces structurally valid Java from the IR."""

    def test_has_class_declaration(self):
        ir = spec_to_ir(_make_spec())
        code = JavaRenderer().render(ir)
        assert "public class Testpgm1" in code

    def test_has_methods(self):
        ir = spec_to_ir(_make_spec())
        code = JavaRenderer().render(ir)
        assert "public void mainProcess()" in code
        assert "public void init()" in code

    def test_has_data_class(self):
        ir = spec_to_ir(_make_spec())
        code = JavaRenderer().render(ir)
        assert "class Cpytest" in code

    def test_has_main_method(self):
        ir = spec_to_ir(_make_spec())
        code = JavaRenderer().render(ir)
        assert "public static void main(" in code

    def test_braces_are_balanced(self):
        ir = spec_to_ir(_make_spec())
        code = JavaRenderer().render(ir)
        assert code.count("{") == code.count("}"), \
            f"Unbalanced braces: {code.count('{')} open, {code.count('}')} close"

    def test_no_python_keywords(self):
        ir = spec_to_ir(_make_spec())
        code = JavaRenderer().render(ir)
        assert "def " not in code
        assert "self." not in code
        assert "@dataclass" not in code

    def test_cics_has_spring_annotation(self):
        ir = spec_to_ir(_make_spec(program_type="CICS Online", has_cics=True))
        code = JavaRenderer().render(ir)
        assert "@RestController" in code or "@Controller" in code or "Spring" in code


class TestCSharpRenderer:
    """C# renderer produces structurally valid C# from the IR."""

    def test_has_class_declaration(self):
        ir = spec_to_ir(_make_spec())
        code = CSharpRenderer().render(ir)
        assert "class Testpgm1" in code

    def test_has_namespace(self):
        ir = spec_to_ir(_make_spec())
        code = CSharpRenderer().render(ir)
        assert "namespace" in code

    def test_has_methods(self):
        ir = spec_to_ir(_make_spec())
        code = CSharpRenderer().render(ir)
        assert "void MainProcess()" in code or "MainProcess()" in code

    def test_has_data_class(self):
        ir = spec_to_ir(_make_spec())
        code = CSharpRenderer().render(ir)
        assert "Cpytest" in code

    def test_braces_are_balanced(self):
        ir = spec_to_ir(_make_spec())
        code = CSharpRenderer().render(ir)
        assert code.count("{") == code.count("}"), \
            f"Unbalanced braces: {code.count('{')} open, {code.count('}')} close"

    def test_no_python_keywords(self):
        ir = spec_to_ir(_make_spec())
        code = CSharpRenderer().render(ir)
        assert "def " not in code
        assert "self." not in code
        assert "@dataclass" not in code

    def test_cics_has_api_controller(self):
        ir = spec_to_ir(_make_spec(program_type="CICS Online", has_cics=True))
        code = CSharpRenderer().render(ir)
        assert "[ApiController]" in code or "Controller" in code


class TestAllRenderersParity:
    """All renderers preserve the same structural elements."""

    def test_all_renderers_have_paragraph_methods(self):
        """Every renderer must produce methods for all paragraphs."""
        ir = spec_to_ir(_make_spec())
        for renderer_cls in (PythonRenderer, JavaRenderer, CSharpRenderer):
            code = renderer_cls().render(ir)
            lang = renderer_cls.__name__
            # All renderers must have some form of main_process and init
            code_lower = code.lower()
            assert "main" in code_lower and "process" in code_lower, \
                f"{lang} missing main_process method"
            assert "init" in code_lower, f"{lang} missing init method"

    def test_all_renderers_have_copybook_type(self):
        """Every renderer must produce a type for the copybook."""
        ir = spec_to_ir(_make_spec())
        for renderer_cls in (PythonRenderer, JavaRenderer, CSharpRenderer):
            code = renderer_cls().render(ir)
            lang = renderer_cls.__name__
            assert "Cpytest" in code, f"{lang} missing Cpytest data class"

    def test_all_renderers_have_service_stub(self):
        """Every renderer must produce a stub for external calls."""
        ir = spec_to_ir(_make_spec())
        for renderer_cls in (PythonRenderer, JavaRenderer, CSharpRenderer):
            code = renderer_cls().render(ir)
            lang = renderer_cls.__name__
            assert "Cobdatft" in code, f"{lang} missing CobdatftService stub"

"""Tests for the Java code generation orchestrator (W8).

Verifies the orchestration and CLI without requiring a real COBOL codebase
analysis directory. Uses a synthetic spec injected via monkeypatching.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from java_codegen import (
    JavaCodegenResult,
    generate_java_for_program,
    main as java_codegen_main,
)
from spec_generator import ProgramSpec, ParagraphSpec, DataContract


def _make_spec(program_id: str = "COSGN00C", program_type: str = "CICS Online") -> ProgramSpec:
    return ProgramSpec(
        program=program_id,
        program_type=program_type,
        source_file=f"{program_id}.cbl",
        total_lines=200,
        code_lines=150,
        paragraph_count=2,
        cyclomatic_complexity=8,
        max_nesting=2,
        complexity_grade="MODERATE",
        callers=[],
        callees=["COBDATFT"],
        copybooks=["CSUSR01Y"],
        files_accessed=[],
        readiness_score=80.0,
        effort_days=2.0,
        risk_level="LOW",
        paragraphs=[
            ParagraphSpec(
                name="MAIN-PARA",
                performs=["INIT-PARA"],
                calls=[],
                cics_ops=["SEND(MAP)"],
                data_flows_in=[],
                data_flows_out=["WS-MESSAGE"],
                decision_indicators=1,
                is_entry_point=True,
            ),
            ParagraphSpec(
                name="INIT-PARA",
                performs=[],
                calls=["COBDATFT"],
                cics_ops=[],
                data_flows_in=[],
                data_flows_out=[],
                decision_indicators=0,
                is_entry_point=False,
            ),
        ],
        data_contracts=[DataContract(
            copybook="CSUSR01Y",
            field_count=5,
            key_fields=["SEC-USR-ID"],
            shared_with=[],
        )],
        cics_operations=[],
        data_flow_summary={"total_flows": 10, "fields_written": [], "fields_read": []},
        decision_count=5,
        computation_count=2,
        validation_fields=[],
        modern_pattern="REST endpoint",
        migration_wave="Wave 1",
        notes=[],
        entry_paragraphs=["MAIN-PARA"],
        exit_points=[],
        perform_graph={},
    )


# ── Single program ─────────────────────────────────────────────────────────


class TestSingleProgramCodegen:
    """generate_java_for_program writes a complete Maven module to disk."""

    def test_writes_pom_xml(self, tmp_path, monkeypatch):
        # Create a fake _analysis directory so the FileNotFoundError doesn't fire
        codebase = tmp_path / "fakecodebase"
        (codebase / "_analysis").mkdir(parents=True)

        # Stub out the spec generator + graph index so we don't need real input
        import java_codegen as jc

        class FakeGraph:
            def program_names(self):
                return ["COSGN00C"]

        monkeypatch.setattr(jc, "GraphIndex", lambda *a, **k: FakeGraph())
        monkeypatch.setattr(jc, "_load_program_data", lambda *a, **k: {})
        monkeypatch.setattr(jc, "generate_program_spec", lambda *a, **k: _make_spec())

        out = tmp_path / "out"
        result = generate_java_for_program(
            "COSGN00C",
            codebase,
            out,
            codebase_name="carddemo",
        )

        assert isinstance(result, JavaCodegenResult)
        assert (result.module_root / "pom.xml").exists()

    def test_writes_main_class(self, tmp_path, monkeypatch):
        codebase = tmp_path / "fakecodebase"
        (codebase / "_analysis").mkdir(parents=True)
        import java_codegen as jc

        class FakeGraph:
            def program_names(self): return ["COSGN00C"]

        monkeypatch.setattr(jc, "GraphIndex", lambda *a, **k: FakeGraph())
        monkeypatch.setattr(jc, "_load_program_data", lambda *a, **k: {})
        monkeypatch.setattr(jc, "generate_program_spec", lambda *a, **k: _make_spec())

        out = tmp_path / "out"
        result = generate_java_for_program("COSGN00C", codebase, out, "carddemo")

        main_path = (
            result.module_root / "src/main/java/com/modernization/carddemo/cosgn00c/Main.java"
        )
        assert main_path.exists()
        assert "public class Main" in main_path.read_text(encoding="utf-8")

    def test_cics_program_writes_controller(self, tmp_path, monkeypatch):
        codebase = tmp_path / "fakecodebase"
        (codebase / "_analysis").mkdir(parents=True)
        import java_codegen as jc

        class FakeGraph:
            def program_names(self): return ["COSGN00C"]

        monkeypatch.setattr(jc, "GraphIndex", lambda *a, **k: FakeGraph())
        monkeypatch.setattr(jc, "_load_program_data", lambda *a, **k: {})
        monkeypatch.setattr(
            jc, "generate_program_spec",
            lambda *a, **k: _make_spec(program_type="CICS Online"),
        )

        out = tmp_path / "out"
        result = generate_java_for_program("COSGN00C", codebase, out, "carddemo")

        controller = (
            result.module_root
            / "src/main/java/com/modernization/carddemo/cosgn00c/controller/Cosgn00cController.java"
        )
        assert controller.exists()

    def test_missing_analysis_dir_raises(self, tmp_path):
        # No _analysis subdirectory → should raise FileNotFoundError
        codebase = tmp_path / "no_analysis_codebase"
        codebase.mkdir()

        with pytest.raises(FileNotFoundError, match="_analysis"):
            generate_java_for_program("COSGN00C", codebase, tmp_path / "out", "x")


# ── CLI ────────────────────────────────────────────────────────────────────


class TestCli:
    def test_help_runs(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            java_codegen_main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "--codebase" in captured.out
        assert "--program" in captured.out
        assert "--output" in captured.out

    def test_missing_required_args_exits(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            java_codegen_main([])
        # argparse exits with code 2 on missing required args
        assert exc_info.value.code == 2

    def test_single_program_runs(self, tmp_path, monkeypatch, capsys):
        codebase = tmp_path / "fakecodebase"
        (codebase / "_analysis").mkdir(parents=True)
        import java_codegen as jc

        class FakeGraph:
            def program_names(self): return ["COSGN00C"]

        monkeypatch.setattr(jc, "GraphIndex", lambda *a, **k: FakeGraph())
        monkeypatch.setattr(jc, "_load_program_data", lambda *a, **k: {})
        monkeypatch.setattr(jc, "generate_program_spec", lambda *a, **k: _make_spec())

        rc = java_codegen_main([
            "--codebase", str(codebase),
            "--output", str(tmp_path / "out"),
            "--program", "COSGN00C",
            "--codebase-name", "carddemo",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "COSGN00C" in out
        assert "Generated" in out

"""Tests for spec_generator.py — behavioral specification generation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spec_generator import (
    generate_program_spec,
    generate_all_specs,
    render_spec_markdown,
    ProgramSpec,
    ParagraphSpec,
    DataContract,
    _infer_modern_pattern,
    _extract_validation_fields,
    _build_perform_graph,
    _find_entry_paragraphs,
    _find_exit_points,
)
from graph_context import GraphIndex

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"


class TestModernPatternInference:
    def test_cics_with_screens(self):
        result = _infer_modern_pattern(True, False, False, ["SEND(MAP)", "RECEIVE(MAP)"])
        assert "REST API" in result or "SPA" in result

    def test_batch_with_files(self):
        result = _infer_modern_pattern(False, True, False, [])
        assert "pipeline" in result.lower() or "batch" in result.lower() or "job" in result.lower()

    def test_standalone(self):
        result = _infer_modern_pattern(False, False, False, [])
        assert "standalone" in result.lower() or "library" in result.lower()


class TestValidationFields:
    def test_detects_status_fields(self):
        paragraphs = [{"data_flows": [
            {"flow_type": "MOVE", "sources": ["X"], "targets": ["WS-STATUS-CODE"]},
            {"flow_type": "MOVE", "sources": ["Y"], "targets": ["ACCT-BALANCE"]},
        ]}]
        fields = _extract_validation_fields([], paragraphs)
        assert "WS-STATUS-CODE" in fields
        assert "ACCT-BALANCE" not in fields

    def test_detects_return_code(self):
        paragraphs = [{"data_flows": [
            {"flow_type": "COMPUTE", "sources": [], "targets": ["WS-RETURN-CODE"]},
        ]}]
        fields = _extract_validation_fields([], paragraphs)
        assert "WS-RETURN-CODE" in fields


class TestPerformGraph:
    def test_builds_graph(self):
        paragraphs = [
            {"name": "MAIN", "performs": [{"target_paragraph": "INIT"}, {"target_paragraph": "PROCESS"}]},
            {"name": "INIT", "performs": []},
            {"name": "PROCESS", "performs": [{"target_paragraph": "CLEANUP"}]},
            {"name": "CLEANUP", "performs": []},
        ]
        graph = _build_perform_graph(paragraphs)
        assert graph["MAIN"] == ["INIT", "PROCESS"]
        assert graph["PROCESS"] == ["CLEANUP"]
        assert graph["CLEANUP"] == []

    def test_entry_points(self):
        paragraphs = [
            {"name": "MAIN", "performs": [{"target_paragraph": "INIT"}]},
            {"name": "INIT", "performs": []},
        ]
        graph = _build_perform_graph(paragraphs)
        entries = _find_entry_paragraphs(paragraphs, graph)
        assert "MAIN" in entries
        assert "INIT" not in entries

    def test_exit_points(self):
        paragraphs = [
            {"name": "MAIN-PROCESS"},
            {"name": "PROGRAM-EXIT"},
            {"name": "CLEANUP-AND-STOP"},
        ]
        exits = _find_exit_points(paragraphs)
        assert "PROGRAM-EXIT" in exits
        assert "CLEANUP-AND-STOP" in exits
        assert "MAIN-PROCESS" not in exits


class TestSpecGeneration:
    def test_generates_spec_for_carddemo_program(self):
        if not CARDDEMO.exists():
            return
        analysis_dir = CARDDEMO / "_analysis"
        graph = GraphIndex(str(analysis_dir))
        from spec_generator import _load_program_data
        program_data = _load_program_data(analysis_dir)

        programs = sorted(graph.program_names())
        assert len(programs) > 0

        spec = generate_program_spec(programs[0], graph, program_data, str(CARDDEMO))
        assert spec is not None
        assert spec.program == programs[0]
        assert spec.code_lines > 0
        assert spec.readiness_score > 0
        assert spec.complexity_grade in ("LOW", "MODERATE", "HIGH", "VERY HIGH", "UNKNOWN")

    def test_render_markdown(self):
        spec = ProgramSpec(
            program="TEST001",
            program_type="Batch",
            source_file="test001.cbl",
            total_lines=200,
            code_lines=150,
            paragraph_count=5,
            cyclomatic_complexity=10,
            max_nesting=3,
            complexity_grade="MODERATE",
            callers=["MAIN"],
            callees=["SUB1"],
            copybooks=["CPYTEST"],
            files_accessed=["TESTFILE (READS_FILE)"],
            readiness_score=75.0,
            effort_days=2.5,
            risk_level="MEDIUM",
            paragraphs=[ParagraphSpec(
                name="PROCESS-RECORD",
                performs=["VALIDATE"],
                calls=["SUB1"],
                cics_ops=[],
                data_flows_in=["ACCT-NUM"],
                data_flows_out=["WS-RESULT"],
                decision_indicators=3,
                is_entry_point=True,
            )],
            data_contracts=[DataContract(
                copybook="CPYTEST",
                field_count=10,
                key_fields=["ACCT-NUM"],
                shared_with=["OTHER"],
            )],
            cics_operations=[],
            data_flow_summary={"total_flows": 25, "fields_written": ["A", "B"], "fields_read": ["C"]},
            decision_count=10,
            computation_count=5,
            validation_fields=["WS-STATUS"],
            modern_pattern="Event-driven pipeline",
            migration_wave="Wave 1: Quick Wins",
            notes=["Isolated program"],
            entry_paragraphs=["PROCESS-RECORD"],
            exit_points=["PROGRAM-EXIT"],
            perform_graph={"PROCESS-RECORD": ["VALIDATE"]},
        )
        md = render_spec_markdown(spec)
        assert "# Behavioral Specification: TEST001" in md
        assert "Batch" in md
        assert "MODERATE" in md
        assert "PROCESS-RECORD" in md
        assert "Wave 1" in md
        assert "Event-driven pipeline" in md

    def test_generate_all_specs(self):
        if not CARDDEMO.exists():
            return
        results = generate_all_specs(str(CARDDEMO))
        assert len(results) > 20
        specs_dir = CARDDEMO / "_analysis" / "specs"
        assert specs_dir.exists()
        assert (specs_dir / "INDEX.md").exists()
        md_files = list(specs_dir.glob("*.md"))
        assert len(md_files) > 20

"""Tests for JavaRenderer.render_module — full Maven module emission (W3).

These tests verify the new render_module / write_module API:
  - The expected file set is produced (pom.xml, Main.java, DTOs, services, controller)
  - File contents include the right package declarations, imports, and CobolDecimal wiring
  - Generation is deterministic (byte-identical across runs)
  - Optionally, the generated module compiles with `mvn compile` if Maven is on PATH

The single-string render() method is left untouched and covered by
test_multi_language.py — no overlap.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skeleton_ir import JavaRenderer, spec_to_ir
from spec_generator import ProgramSpec, ParagraphSpec, DataContract


# ── Reusable IR fixture ────────────────────────────────────────────────────


def _make_spec(program_type: str = "Batch", has_cics: bool = False) -> ProgramSpec:
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


# ── File set tests ─────────────────────────────────────────────────────────


class TestRenderModuleFileSet:
    """render_module emits the expected set of files at the right paths."""

    def test_batch_module_has_pom(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        assert "pom.xml" in files

    def test_batch_module_has_main_class(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        main_path = "src/main/java/com/modernization/carddemo/testpgm1/Main.java"
        assert main_path in files

    def test_batch_module_has_dto_for_each_dataclass(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        dto_path = "src/main/java/com/modernization/carddemo/testpgm1/dto/Cpytest.java"
        assert dto_path in files

    def test_batch_module_has_service_for_each_stub(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        svc_path = "src/main/java/com/modernization/carddemo/testpgm1/service/CobdatftService.java"
        assert svc_path in files

    def test_batch_module_has_no_controller(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        assert not any("controller" in p for p in files), \
            "Batch programs should not get a Spring controller"

    def test_cics_module_has_controller(self):
        ir = spec_to_ir(_make_spec(program_type="CICS Online", has_cics=True))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        controller_path = (
            "src/main/java/com/modernization/carddemo/testpgm1/controller/"
            "Testpgm1Controller.java"
        )
        assert controller_path in files


# ── Content tests ──────────────────────────────────────────────────────────


class TestRenderModuleContents:
    """File contents have the right structure for downstream tooling."""

    def test_pom_declares_cobol_decimal_dependency(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        pom = files["pom.xml"]
        assert "<artifactId>cobol-decimal</artifactId>" in pom
        assert "<groupId>com.modernization.masquerade</groupId>" in pom

    def test_pom_omits_spring_for_batch(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        pom = files["pom.xml"]
        assert "spring-boot-starter-web" not in pom, \
            "Batch programs should not pull in Spring (OD-5)"

    def test_pom_includes_spring_for_cics(self):
        ir = spec_to_ir(_make_spec(program_type="CICS Online", has_cics=True))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        pom = files["pom.xml"]
        assert "spring-boot-starter-web" in pom

    def test_main_class_imports_cobol_decimal(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        main = files["src/main/java/com/modernization/carddemo/testpgm1/Main.java"]
        assert "import com.modernization.masquerade.cobol.CobolDecimal;" in main

    def test_main_class_has_run_method(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        main = files["src/main/java/com/modernization/carddemo/testpgm1/Main.java"]
        assert "public void run()" in main

    def test_main_class_has_static_main(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        main = files["src/main/java/com/modernization/carddemo/testpgm1/Main.java"]
        assert "public static void main(String[] args)" in main

    def test_main_class_has_paragraph_methods(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        main = files["src/main/java/com/modernization/carddemo/testpgm1/Main.java"]
        assert "public void mainProcess()" in main
        assert "public void init()" in main
        assert "public void processRecords()" in main

    def test_dto_has_correct_package(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        dto = files["src/main/java/com/modernization/carddemo/testpgm1/dto/Cpytest.java"]
        assert "package com.modernization.carddemo.testpgm1.dto;" in dto
        assert "public class Cpytest" in dto

    def test_service_has_execute_method(self):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        svc = files[
            "src/main/java/com/modernization/carddemo/testpgm1/service/CobdatftService.java"
        ]
        assert "public void execute()" in svc

    def test_controller_has_rest_annotations(self):
        ir = spec_to_ir(_make_spec(program_type="CICS Online", has_cics=True))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        controller = files[
            "src/main/java/com/modernization/carddemo/testpgm1/controller/"
            "Testpgm1Controller.java"
        ]
        assert "@RestController" in controller
        assert "@RequestMapping" in controller
        assert "@PostMapping" in controller

    def test_no_legacy_unsupported_op_in_main_class_signature(self):
        """Each generated paragraph method should still have a body."""
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        files = JavaRenderer().render_module(ir, codebase="carddemo")
        main = files["src/main/java/com/modernization/carddemo/testpgm1/Main.java"]
        # Braces must be balanced
        assert main.count("{") == main.count("}"), \
            "Unbalanced braces in generated Main.java"


# ── Determinism ────────────────────────────────────────────────────────────


class TestRenderModuleDeterminism:
    """Same input → byte-identical output across runs."""

    def test_two_renders_produce_identical_files(self):
        ir1 = spec_to_ir(_make_spec(program_type="Batch"))
        ir2 = spec_to_ir(_make_spec(program_type="Batch"))
        files1 = JavaRenderer().render_module(ir1, codebase="carddemo")
        files2 = JavaRenderer().render_module(ir2, codebase="carddemo")
        assert files1.keys() == files2.keys()
        for path in files1:
            assert files1[path] == files2[path], \
                f"Non-deterministic output for {path}"

    def test_cics_renders_deterministically(self):
        ir1 = spec_to_ir(_make_spec(program_type="CICS Online", has_cics=True))
        ir2 = spec_to_ir(_make_spec(program_type="CICS Online", has_cics=True))
        files1 = JavaRenderer().render_module(ir1, codebase="carddemo")
        files2 = JavaRenderer().render_module(ir2, codebase="carddemo")
        for path in files1:
            assert files1[path] == files2[path]


# ── write_module disk emission ─────────────────────────────────────────────


class TestWriteModule:
    """write_module persists the dict to disk under output_dir."""

    def test_writes_all_files_to_disk(self, tmp_path):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        out = JavaRenderer().write_module(ir, tmp_path / "mod", codebase="carddemo")
        assert (out / "pom.xml").exists()
        assert (
            out / "src/main/java/com/modernization/carddemo/testpgm1/Main.java"
        ).exists()
        assert (
            out / "src/main/java/com/modernization/carddemo/testpgm1/dto/Cpytest.java"
        ).exists()

    def test_creates_intermediate_directories(self, tmp_path):
        ir = spec_to_ir(_make_spec(program_type="CICS Online", has_cics=True))
        out = JavaRenderer().write_module(ir, tmp_path / "deep" / "nested" / "mod", codebase="carddemo")
        assert (
            out / "src/main/java/com/modernization/carddemo/testpgm1/controller/"
            "Testpgm1Controller.java"
        ).exists()


# ── Optional: real Maven compile gate ──────────────────────────────────────


def _maven_available() -> bool:
    """Return True if `mvn -version` runs successfully via the inline env prefix."""
    java_home = "C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot"
    mvn_bin = "C:/Users/mcint/tools/apache-maven-3.9.14/bin/mvn"
    if not Path(mvn_bin + ".cmd").exists() and not Path(mvn_bin).exists():
        return False
    if not Path(java_home).exists():
        return False
    try:
        env = os.environ.copy()
        env["JAVA_HOME"] = java_home
        env["PATH"] = f"{java_home}/bin;C:/Users/mcint/tools/apache-maven-3.9.14/bin;{env.get('PATH', '')}"
        result = subprocess.run(
            [mvn_bin + ".cmd", "-version"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(not _maven_available(), reason="Maven 3.9.14 not at expected location")
class TestRealMavenCompile:
    """End-to-end gate: a generated module must actually compile.

    Requires the cobol-decimal artifact to be installed in the local Maven
    repo first (mvn install -pl pipeline/reimpl/java/cobol-decimal/). Skipped
    if not present so the test suite stays green on machines without the
    Java toolchain configured.
    """

    def test_batch_module_compiles(self, tmp_path):
        ir = spec_to_ir(_make_spec(program_type="Batch"))
        out = JavaRenderer().write_module(ir, tmp_path / "batchmod", codebase="carddemo")

        java_home = "C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot"
        mvn_bin = "C:/Users/mcint/tools/apache-maven-3.9.14/bin/mvn.cmd"
        env = os.environ.copy()
        env["JAVA_HOME"] = java_home
        env["PATH"] = f"{java_home}/bin;C:/Users/mcint/tools/apache-maven-3.9.14/bin;{env.get('PATH', '')}"

        result = subprocess.run(
            [mvn_bin, "-q", "-B", "compile"],
            cwd=str(out),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, (
            f"mvn compile failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

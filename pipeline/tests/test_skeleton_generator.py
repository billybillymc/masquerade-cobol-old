"""Tests for skeleton_generator.py — Python skeleton generation from COBOL specs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skeleton_generator import (
    generate_skeleton,
    generate_all_skeletons,
    _cobol_name_to_python,
    _cobol_name_to_class,
    _pic_to_python_type,
    SkeletonResult,
)
from spec_generator import ProgramSpec, ParagraphSpec, DataContract

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"


class TestNameConversion:
    def test_hyphen_to_snake(self):
        assert _cobol_name_to_python("MAIN-PROCESS") == "main_process"
        assert _cobol_name_to_python("WS-RETURN-CODE") == "ws_return_code"

    def test_to_class(self):
        assert _cobol_name_to_class("COSGN00C") == "Cosgn00c"
        assert _cobol_name_to_class("MAIN-PROCESS") == "MainProcess"

    def test_pic_types(self):
        assert _pic_to_python_type("9(5)") == "int"
        assert _pic_to_python_type("X(20)") == "str"
        assert _pic_to_python_type("S9(7)V9(2)") == "Decimal"
        assert _pic_to_python_type("") == "str"


class TestSkeletonGeneration:
    def _make_spec(self, program_type="Batch", has_cics=False) -> ProgramSpec:
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
                cics_ops=["SEND(MAP)" , "RECEIVE(MAP)"] if has_cics else [],
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

    def test_generates_valid_python(self):
        spec = self._make_spec()
        code = generate_skeleton(spec)
        compile(code, "<skeleton>", "exec")

    def test_has_class(self):
        spec = self._make_spec()
        code = generate_skeleton(spec)
        assert "class Testpgm1:" in code

    def test_has_methods_for_paragraphs(self):
        spec = self._make_spec()
        code = generate_skeleton(spec)
        assert "def main_process(self)" in code
        assert "def init(self)" in code
        assert "def process_records(self)" in code

    def test_has_copybook_dataclass(self):
        spec = self._make_spec()
        code = generate_skeleton(spec)
        assert "@dataclass" in code
        assert "class Cpytest:" in code

    def test_has_service_stubs(self):
        spec = self._make_spec()
        code = generate_skeleton(spec)
        assert "CobdatftService" in code

    def test_has_entry_point(self):
        spec = self._make_spec()
        code = generate_skeleton(spec)
        assert "def run(self)" in code
        assert 'if __name__ == "__main__"' in code

    def test_cics_program_has_api_comments(self):
        spec = self._make_spec(program_type="CICS Online", has_cics=True)
        code = generate_skeleton(spec)
        assert "REST" in code or "API" in code
        assert "CICS SEND" in code or "endpoint" in code

    def test_batch_program_has_batch_comments(self):
        spec = self._make_spec()
        code = generate_skeleton(spec)
        assert "batch" in code.lower() or "scheduled" in code.lower() or "CLI" in code


class TestCopybookWiring:
    """IQ-02: Tests for wiring copybook fields into skeleton dataclasses."""

    CARDDEMO_CPY = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo" / "app" / "cpy"

    def _make_spec_with_copybook(self, copybook_name: str) -> ProgramSpec:
        """Build a minimal ProgramSpec referencing a single copybook."""
        return ProgramSpec(
            program="TESTPGM",
            program_type="Batch",
            source_file="test.cbl",
            total_lines=100,
            code_lines=80,
            paragraph_count=1,
            cyclomatic_complexity=5,
            max_nesting=2,
            complexity_grade="LOW",
            callers=[],
            callees=[],
            copybooks=[copybook_name],
            files_accessed=[],
            readiness_score=80.0,
            effort_days=1.0,
            risk_level="LOW",
            paragraphs=[ParagraphSpec(
                name="MAIN-PARA",
                performs=[], calls=[], cics_ops=[],
                data_flows_in=[], data_flows_out=[],
                decision_indicators=0, is_entry_point=True,
            )],
            data_contracts=[DataContract(
                copybook=copybook_name,
                field_count=5,
                key_fields=[],
                shared_with=[],
            )],
            cics_operations=[],
            data_flow_summary={"total_flows": 0, "fields_written": [], "fields_read": []},
            decision_count=0,
            computation_count=0,
            validation_fields=[],
            modern_pattern="Standalone service",
            migration_wave="Wave 1",
            notes=[],
            entry_paragraphs=["MAIN-PARA"],
            exit_points=[],
            perform_graph={},
        )

    def _write_cpy(self, tmp_path, name, content):
        """Write a synthetic .cpy file and return a CopybookDictionary."""
        cpy_dir = tmp_path / "cpy"
        cpy_dir.mkdir(exist_ok=True)
        (cpy_dir / f"{name}.cpy").write_text(content, encoding="utf-8")
        from copybook_dict import CopybookDictionary
        return CopybookDictionary(str(cpy_dir))

    # --- Test 1: Basic wiring — flat copybook gets typed fields, not pass ---
    def test_csusr01y_has_typed_fields(self):
        """CSUSR01Y is a flat copybook (01 -> 05 fields). The generated dataclass
        should have actual typed fields (sec_usr_id, sec_usr_fname, etc.),
        NOT 'pass' with a TODO comment."""
        from copybook_dict import CopybookDictionary
        cbd = CopybookDictionary(str(self.CARDDEMO_CPY))
        spec = self._make_spec_with_copybook("CSUSR01Y")
        code = generate_skeleton(spec, copybook_dict=cbd)
        # Must NOT have pass body
        assert "    pass\n" not in code
        assert "TODO: Map fields" not in code
        # Must have actual fields from the copybook
        assert "sec_usr_id" in code
        assert "sec_usr_fname" in code
        assert "sec_usr_lname" in code
        assert "sec_usr_pwd" in code
        assert "sec_usr_type" in code

    # --- Test 2: PIC X -> str with enforced max_length metadata ---
    def test_pic_x_produces_str_with_max_length_metadata(self, tmp_path):
        """PIC X(08) must produce a str field with metadata={'pic': 'X(08)',
        'max_length': 8}. The metadata is machine-readable for IQ-03 enforcement."""
        cbd = self._write_cpy(tmp_path, "TPICX", """
           01  TEST-REC.
               05  TEST-FIELD         PIC X(08).
        """)
        spec = self._make_spec_with_copybook("TPICX")
        code = generate_skeleton(spec, copybook_dict=cbd)
        assert "test_field: str" in code
        assert "'max_length': 8" in code or '"max_length": 8' in code
        assert "'pic': 'X(08)'" in code or '"pic": "X(08)"' in code

    # --- Test 3: PIC S9 COMP -> int with signed + usage metadata ---
    def test_pic_s9_comp_produces_int(self, tmp_path):
        """PIC S9(09) COMP must produce an int field with metadata containing
        max_digits=9, signed=True, usage='COMP'."""
        cbd = self._write_cpy(tmp_path, "TCOMP", """
           01  TEST-REC.
               05  TEST-COUNT         PIC S9(09) COMP.
        """)
        spec = self._make_spec_with_copybook("TCOMP")
        code = generate_skeleton(spec, copybook_dict=cbd)
        assert "test_count: int" in code
        assert "'max_digits': 9" in code or '"max_digits": 9' in code
        assert "'signed': True" in code or '"signed": True' in code
        assert "'usage': 'COMP'" in code or '"usage": "COMP"' in code

    # --- Test 4: PIC with V (decimal) -> Decimal with scale metadata ---
    def test_pic_decimal_produces_decimal_with_scale(self, tmp_path):
        """PIC S9(10)V99 must produce a Decimal field with metadata containing
        max_digits=10, scale=2, signed=True."""
        cbd = self._write_cpy(tmp_path, "TDEC", """
           01  TEST-REC.
               05  TEST-AMT           PIC S9(10)V99.
        """)
        spec = self._make_spec_with_copybook("TDEC")
        code = generate_skeleton(spec, copybook_dict=cbd)
        assert "test_amt: Decimal" in code
        assert "'scale': 2" in code or '"scale": 2' in code
        assert "'max_digits': 10" in code or '"max_digits": 10' in code
        assert "'signed': True" in code or '"signed": True' in code

    # --- Test 5: OCCURS -> list[T] with pre-populated factory ---
    def test_occurs_produces_list(self, tmp_path):
        """OCCURS 10 must produce list[T] field with default_factory that
        pre-populates 10 elements, and metadata={'occurs': 10}."""
        cbd = self._write_cpy(tmp_path, "TOCC", """
           01  TEST-REC.
               05  TEST-TABLE.
                   10  TEST-ENTRY OCCURS 10.
                       15  TEST-NAME   PIC X(30).
                       15  TEST-AMT    PIC 9(07)V99.
        """)
        spec = self._make_spec_with_copybook("TOCC")
        code = generate_skeleton(spec, copybook_dict=cbd)
        assert "list[TestEntry]" in code or "List[TestEntry]" in code
        assert "'occurs': 10" in code or '"occurs": 10' in code
        assert "range(10)" in code  # pre-populated factory

    # --- Test 6: REDEFINES -> Optional field with comment ---
    def test_redefines_produces_optional_with_comment(self, tmp_path):
        """REDEFINES must produce an Optional field defaulting to None,
        with a comment indicating which field it redefines."""
        cbd = self._write_cpy(tmp_path, "TREDEF", """
           01  TEST-REC.
               05  WS-DATE-FIELD           PIC X(08).
               05  WS-DATE-PARTS REDEFINES WS-DATE-FIELD.
                   10  WS-YEAR             PIC X(04).
                   10  WS-MONTH            PIC X(02).
                   10  WS-DAY              PIC X(02).
        """)
        spec = self._make_spec_with_copybook("TREDEF")
        code = generate_skeleton(spec, copybook_dict=cbd)
        assert "Optional[WsDateParts]" in code or "Optional['WsDateParts']" in code
        assert "None" in code  # default value
        assert "REDEFINES WS-DATE-FIELD" in code

    # --- Test 7: Level-88 -> ClassVar constants ---
    def test_level_88_produces_class_constants(self, tmp_path):
        """Level-88 conditions must produce ClassVar constants on the dataclass."""
        cbd = self._write_cpy(tmp_path, "T88", """
           01  TEST-REC.
               05  TEST-TYPE              PIC X(01).
                   88  TYPE-ADMIN         VALUE 'A'.
                   88  TYPE-USER          VALUE 'U'.
        """)
        spec = self._make_spec_with_copybook("T88")
        code = generate_skeleton(spec, copybook_dict=cbd)
        assert "ClassVar" in code
        assert "TYPE_ADMIN" in code
        assert "'A'" in code
        assert "TYPE_USER" in code
        assert "'U'" in code

    # --- Test 8: Nested groups -> nested dataclasses ---
    def test_nested_groups_produce_nested_dataclasses(self):
        """COCOM01Y has 01 -> 05 groups -> 10 fields. Must produce nested
        dataclasses: CarddemoCommarea contains CdemoGeneralInfo, etc."""
        from copybook_dict import CopybookDictionary
        cbd = CopybookDictionary(str(self.CARDDEMO_CPY))
        spec = self._make_spec_with_copybook("COCOM01Y")
        code = generate_skeleton(spec, copybook_dict=cbd)
        # Must have nested dataclass for group items
        assert "class CdemoGeneralInfo" in code
        assert "class CdemoCustomerInfo" in code
        # Parent must reference nested classes
        assert "cdemo_general_info: CdemoGeneralInfo" in code or \
               "cdemo_general_info:" in code
        # Elementary fields must be inside nested classes
        assert "cdemo_from_tranid" in code
        assert "cdemo_cust_id" in code

    # --- Test 9: FILLER fields skipped ---
    def test_filler_fields_are_skipped(self, tmp_path):
        """Fields named FILLER must not appear in the generated dataclass."""
        cbd = self._write_cpy(tmp_path, "TFILLER", """
           01  TEST-REC.
               05  TEST-ID               PIC 9(05).
               05  FILLER                PIC X(100).
        """)
        spec = self._make_spec_with_copybook("TFILLER")
        code = generate_skeleton(spec, copybook_dict=cbd)
        assert "test_id" in code  # real field present
        assert "filler" not in code.lower().replace("# filler", "").replace("filler", "x", 1) or \
               "filler" not in [line.strip().split(":")[0] for line in code.split("\n") if ":" in line]
        # Simpler assertion: no field named filler
        lines = code.split("\n")
        field_lines = [l.strip() for l in lines if l.strip().startswith("filler")]
        assert len(field_lines) == 0

    # --- Test 10: Backward compat — no dict means pass stub ---
    def test_backward_compat_no_dict_produces_pass_stub(self):
        """Without a CopybookDictionary, the old pass-stub behavior is preserved."""
        spec = self._make_spec_with_copybook("ANYTHING")
        code = generate_skeleton(spec)  # no copybook_dict
        assert "pass" in code
        assert "TODO: Map fields" in code

    # --- Test 11: Generated skeleton with fields compiles ---
    def test_generated_skeleton_with_fields_compiles(self):
        """Full skeleton with typed copybook fields must be valid Python."""
        from copybook_dict import CopybookDictionary
        cbd = CopybookDictionary(str(self.CARDDEMO_CPY))
        for copybook_name in ["CSUSR01Y", "COCOM01Y", "CVACT01Y"]:
            spec = self._make_spec_with_copybook(copybook_name)
            code = generate_skeleton(spec, copybook_dict=cbd)
            try:
                compile(code, f"<{copybook_name}>", "exec")
            except SyntaxError as e:
                raise AssertionError(
                    f"Skeleton for {copybook_name} has syntax error: {e}\n"
                    f"Generated code:\n{code}"
                )

    # --- Test 12: Real copybook CVACT01Y has Decimal fields ---
    def test_cvact01y_has_decimal_fields(self):
        """CVACT01Y has PIC S9(10)V99 fields (ACCT-CURR-BAL, etc.).
        These must produce Decimal typed fields with scale metadata."""
        from copybook_dict import CopybookDictionary
        cbd = CopybookDictionary(str(self.CARDDEMO_CPY))
        spec = self._make_spec_with_copybook("CVACT01Y")
        code = generate_skeleton(spec, copybook_dict=cbd)
        assert "acct_curr_bal: Decimal" in code
        assert "acct_credit_limit: Decimal" in code
        assert "'scale': 2" in code or '"scale": 2' in code


class TestFullCodebaseSkeletons:
    def test_generates_carddemo_skeletons(self):
        if not CARDDEMO.exists():
            return
        results = generate_all_skeletons(str(CARDDEMO))
        assert len(results) > 20
        skeletons_dir = CARDDEMO / "_analysis" / "skeletons"
        assert skeletons_dir.exists()
        assert (skeletons_dir / "__init__.py").exists()

        for pgm, sr in list(results.items())[:5]:
            code = sr.python_code
            try:
                compile(code, f"<{pgm}>", "exec")
            except SyntaxError as e:
                raise AssertionError(f"Skeleton for {pgm} has syntax error: {e}")

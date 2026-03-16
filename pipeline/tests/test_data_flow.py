"""Tests for data flow extraction from COBOL parser."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cobol_parser import parse_cobol_file, DataFlow


@pytest.fixture
def carddemo_dir():
    root = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
    if not root.exists():
        pytest.skip("carddemo test codebase not available")
    return root


def _find_cobol_file(carddemo_dir, name_prefix):
    for f in carddemo_dir.rglob("*.cbl"):
        if f.stem.upper().startswith(name_prefix.upper()):
            return f
    for f in carddemo_dir.rglob("*.CBL"):
        if f.stem.upper().startswith(name_prefix.upper()):
            return f
    return None


class TestDataFlowExtraction:
    def test_move_statements_extracted(self, carddemo_dir):
        """Verify MOVE statements are captured as data flows."""
        f = _find_cobol_file(carddemo_dir, "COSGN00C")
        assert f is not None, "COSGN00C not found"
        pgm = parse_cobol_file(f)
        moves = [df for df in pgm.data_flows if df.flow_type == 'MOVE']
        assert len(moves) > 0, "Expected MOVE data flows in COSGN00C"

    def test_data_flow_has_source_and_target(self, carddemo_dir):
        f = _find_cobol_file(carddemo_dir, "COSGN00C")
        pgm = parse_cobol_file(f)
        for df in pgm.data_flows[:5]:
            assert len(df.sources) > 0, f"Data flow missing sources: {df}"
            assert len(df.targets) > 0, f"Data flow missing targets: {df}"

    def test_data_flow_assigned_to_paragraphs(self, carddemo_dir):
        f = _find_cobol_file(carddemo_dir, "COSGN00C")
        pgm = parse_cobol_file(f)
        flows_with_para = [df for df in pgm.data_flows if df.paragraph]
        assert len(flows_with_para) > 0, "Expected some flows assigned to paragraphs"

    def test_paragraphs_contain_data_flows(self, carddemo_dir):
        f = _find_cobol_file(carddemo_dir, "COSGN00C")
        pgm = parse_cobol_file(f)
        paras_with_flows = [p for p in pgm.paragraphs if p.data_flows]
        assert len(paras_with_flows) > 0, "Expected paragraphs with data flows"

    def test_compute_statements_extracted(self, carddemo_dir):
        """Look for COMPUTE in a program that does calculations."""
        f = _find_cobol_file(carddemo_dir, "CBACT04C")
        if f is None:
            pytest.skip("CBACT04C not found")
        pgm = parse_cobol_file(f)
        computes = [df for df in pgm.data_flows if df.flow_type == 'COMPUTE']
        # CBACT04C is the interest calculation — should have COMPUTEs
        assert len(computes) > 0, "Expected COMPUTE data flows in CBACT04C"

    def test_call_using_args_captured(self, carddemo_dir):
        """Verify CALL USING arguments are captured."""
        # Find a program that uses CALL with USING
        for f in carddemo_dir.rglob("*.cbl"):
            pgm = parse_cobol_file(f)
            calls_with_args = [c for c in pgm.call_targets if c.using_args]
            if calls_with_args:
                assert len(calls_with_args[0].using_args) > 0
                return
        pytest.skip("No CALL USING statements found")

    def test_data_flow_count_reasonable(self, carddemo_dir):
        """A real program should have a reasonable number of data flows."""
        f = _find_cobol_file(carddemo_dir, "COACTUPC")
        if f is None:
            pytest.skip("COACTUPC not found")
        pgm = parse_cobol_file(f)
        assert len(pgm.data_flows) >= 5, f"Expected >= 5 data flows, got {len(pgm.data_flows)}"

    def test_flow_types_present(self, carddemo_dir):
        """Across all programs, we should see multiple flow types."""
        flow_types = set()
        for f in list(carddemo_dir.rglob("*.cbl"))[:10]:
            pgm = parse_cobol_file(f)
            for df in pgm.data_flows:
                flow_types.add(df.flow_type)
        assert 'MOVE' in flow_types, "Expected MOVE flows"
        # Other types depend on the code

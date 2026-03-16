"""Tests for cross-reference and field search functionality."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph_context import DataFlowIndex


@pytest.fixture
def dfi():
    carddemo = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo" / "_analysis"
    if not carddemo.exists():
        pytest.skip("carddemo analysis not available")
    return DataFlowIndex(str(carddemo))


class TestSearchFields:
    def test_search_returns_matches(self, dfi):
        results = dfi.search_fields("ACCT")
        assert len(results) > 0
        assert all("ACCT" in r for r in results)

    def test_search_case_insensitive(self, dfi):
        upper = dfi.search_fields("ACCT")
        lower = dfi.search_fields("acct")
        assert upper == lower

    def test_search_empty_returns_empty(self, dfi):
        results = dfi.search_fields("ZZZNONEXISTENTZZZZ")
        assert len(results) == 0


class TestCrossReference:
    def test_returns_programs(self, dfi):
        fields = dfi.search_fields("RETURN")
        if not fields:
            return
        xref = dfi.cross_reference(fields[0])
        assert xref["total_programs"] >= 1
        assert len(xref["programs"]) >= 1

    def test_counts_reads_writes(self, dfi):
        fields = dfi.search_fields("RETURN")
        if not fields:
            return
        xref = dfi.cross_reference(fields[0])
        assert xref["total_writes"] >= 0
        assert xref["total_reads"] >= 0
        assert xref["total_writes"] + xref["total_reads"] > 0

    def test_by_program_has_detail(self, dfi):
        fields = dfi.search_fields("RETURN")
        if not fields:
            return
        xref = dfi.cross_reference(fields[0])
        for pgm, info in xref["by_program"].items():
            assert "writes" in info
            assert "reads" in info
            assert "call_passing" in info
            assert "write_count" in info

    def test_nonexistent_field(self, dfi):
        xref = dfi.cross_reference("ZZZZNONEXISTENTZZZZ")
        assert xref["total_programs"] == 0
        assert xref["total_writes"] == 0

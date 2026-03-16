"""Tests for the graph context module — in-memory graph index for COBOL analysis."""

import json
import os
import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph_context import GraphIndex


@pytest.fixture
def sample_graph_json():
    """Minimal graph.json matching the format produced by analyze.py."""
    return {
        "nodes": [
            {"id": "PGM:MAINPGM", "name": "MAINPGM", "type": "PROGRAM", "source_file": "main.cbl", "metadata": {"total_lines": 500, "code_lines": 400}},
            {"id": "PGM:SUBPGMA", "name": "SUBPGMA", "type": "PROGRAM", "source_file": "suba.cbl", "metadata": {"total_lines": 200, "code_lines": 150}},
            {"id": "PGM:SUBPGMB", "name": "SUBPGMB", "type": "PROGRAM", "source_file": "subb.cbl", "metadata": {"total_lines": 100, "code_lines": 80}},
            {"id": "PGM:LEAFPGM", "name": "LEAFPGM", "type": "PROGRAM", "source_file": "leaf.cbl", "metadata": {"total_lines": 50, "code_lines": 40}},
            {"id": "CPY:SHARED01", "name": "SHARED01", "type": "COPYBOOK", "source_file": None, "metadata": {}},
            {"id": "CPY:SHARED02", "name": "SHARED02", "type": "COPYBOOK", "source_file": None, "metadata": {}},
            {"id": "CPY:PRIVATE01", "name": "PRIVATE01", "type": "COPYBOOK", "source_file": None, "metadata": {}},
            {"id": "FILE:TRANSACT", "name": "TRANSACT", "type": "FILE", "source_file": None, "metadata": {}},
        ],
        "edges": [
            {"source": "PGM:MAINPGM", "target": "PGM:SUBPGMA", "type": "CALL", "evidence": [{"file": "main.cbl", "line": 100}]},
            {"source": "PGM:MAINPGM", "target": "PGM:SUBPGMB", "type": "CALL", "evidence": [{"file": "main.cbl", "line": 120}]},
            {"source": "PGM:SUBPGMA", "target": "PGM:LEAFPGM", "type": "CALL", "evidence": [{"file": "suba.cbl", "line": 50}]},
            {"source": "PGM:MAINPGM", "target": "CPY:SHARED01", "type": "COPIES", "evidence": [{"file": "main.cbl", "line": 10}]},
            {"source": "PGM:SUBPGMA", "target": "CPY:SHARED01", "type": "COPIES", "evidence": [{"file": "suba.cbl", "line": 10}]},
            {"source": "PGM:SUBPGMB", "target": "CPY:SHARED01", "type": "COPIES", "evidence": [{"file": "subb.cbl", "line": 10}]},
            {"source": "PGM:MAINPGM", "target": "CPY:SHARED02", "type": "COPIES", "evidence": [{"file": "main.cbl", "line": 15}]},
            {"source": "PGM:SUBPGMA", "target": "CPY:SHARED02", "type": "COPIES", "evidence": [{"file": "suba.cbl", "line": 15}]},
            {"source": "PGM:LEAFPGM", "target": "CPY:PRIVATE01", "type": "COPIES", "evidence": [{"file": "leaf.cbl", "line": 10}]},
            {"source": "PGM:MAINPGM", "target": "FILE:TRANSACT", "type": "READS_FILE", "evidence": [{"file": "main.cbl", "line": 200}]},
            {"source": "PGM:SUBPGMB", "target": "FILE:TRANSACT", "type": "READS_FILE", "evidence": [{"file": "subb.cbl", "line": 200}]},
        ],
    }


@pytest.fixture
def analysis_dir(tmp_path, sample_graph_json):
    """Create a temporary _analysis/ directory with graph.json."""
    d = tmp_path / "_analysis"
    d.mkdir()
    (d / "graph.json").write_text(json.dumps(sample_graph_json))
    return str(d)


@pytest.fixture
def graph(analysis_dir):
    return GraphIndex(analysis_dir)


class TestGraphIndexLoading:
    def test_loads_nodes(self, graph):
        assert len(graph.nodes) == 8

    def test_loads_edges(self, graph):
        assert len(graph.edges) >= 11

    def test_programs_indexed(self, graph):
        programs = graph.program_names()
        assert "MAINPGM" in programs
        assert "SUBPGMA" in programs
        assert "LEAFPGM" in programs

    def test_copybooks_indexed(self, graph):
        copybooks = graph.copybook_names()
        assert "SHARED01" in copybooks
        assert "PRIVATE01" in copybooks

    def test_load_from_missing_dir_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            GraphIndex(str(tmp_path / "nonexistent"))


class TestCallerCalleeQueries:
    def test_callees_of_main(self, graph):
        callees = graph.callees("MAINPGM")
        assert set(callees) == {"SUBPGMA", "SUBPGMB"}

    def test_callers_of_subpgma(self, graph):
        callers = graph.callers("SUBPGMA")
        assert callers == ["MAINPGM"]

    def test_callers_of_root_is_empty(self, graph):
        callers = graph.callers("MAINPGM")
        assert callers == []

    def test_callees_of_leaf_is_empty(self, graph):
        callees = graph.callees("LEAFPGM")
        assert callees == []

    def test_transitive_callees(self, graph):
        reached = graph.callees_transitive("MAINPGM", max_depth=3)
        assert "SUBPGMA" in reached
        assert "SUBPGMB" in reached
        assert "LEAFPGM" in reached

    def test_unknown_program_returns_empty(self, graph):
        assert graph.callers("NONEXISTENT") == []
        assert graph.callees("NONEXISTENT") == []


class TestCopybookQueries:
    def test_copybooks_of_program(self, graph):
        cbs = graph.copybooks_of("MAINPGM")
        assert set(cbs) == {"SHARED01", "SHARED02"}

    def test_users_of_shared_copybook(self, graph):
        users = graph.copybook_users("SHARED01")
        assert set(users) == {"MAINPGM", "SUBPGMA", "SUBPGMB"}

    def test_users_of_private_copybook(self, graph):
        users = graph.copybook_users("PRIVATE01")
        assert users == ["LEAFPGM"]

    def test_programs_sharing_copybooks_with(self, graph):
        shared = graph.programs_sharing_copybooks_with("MAINPGM")
        assert "SUBPGMA" in shared
        assert "SUBPGMB" in shared
        assert "MAINPGM" not in shared


class TestCentrality:
    def test_hub_programs_ordered_by_degree(self, graph):
        hubs = graph.hub_programs(top_n=4)
        names = [name for name, _ in hubs]
        assert names[0] in ("MAINPGM", "SUBPGMA")
        scores = [s for _, s in hubs]
        assert scores == sorted(scores, reverse=True)

    def test_leaf_programs_have_no_callees(self, graph):
        leaves = graph.leaf_programs()
        assert "LEAFPGM" in leaves
        assert "SUBPGMB" in leaves
        assert "MAINPGM" not in leaves

    def test_degree_centrality_values(self, graph):
        main_score = graph.degree_centrality("MAINPGM")
        leaf_score = graph.degree_centrality("LEAFPGM")
        assert main_score > leaf_score

    def test_isolated_clusters(self, graph):
        clusters = graph.connected_components()
        assert len(clusters) >= 1
        largest = max(clusters, key=len)
        assert "MAINPGM" in largest


class TestImpactAnalysis:
    def test_impact_from_shared_copybook(self, graph):
        impact = graph.impact_of("CPY:SHARED01", max_depth=2)
        affected_programs = {name for name, _ in impact}
        assert "MAINPGM" in affected_programs
        assert "SUBPGMA" in affected_programs
        assert "SUBPGMB" in affected_programs

    def test_impact_from_program_includes_callers(self, graph):
        impact = graph.impact_of("PGM:SUBPGMA", max_depth=2)
        affected = {name for name, _ in impact}
        assert "MAINPGM" in affected

    def test_impact_respects_max_depth(self, graph):
        impact_1 = graph.impact_of("PGM:LEAFPGM", max_depth=1)
        impact_3 = graph.impact_of("PGM:LEAFPGM", max_depth=3)
        assert len(impact_3) >= len(impact_1)

    def test_impact_includes_distance(self, graph):
        impact = graph.impact_of("PGM:LEAFPGM", max_depth=3)
        distances = {name: dist for name, dist in impact}
        assert distances.get("SUBPGMA") == 1
        assert distances.get("MAINPGM") == 2

    def test_impact_from_file_node(self, graph):
        impact = graph.impact_of("FILE:TRANSACT", max_depth=1)
        affected = {name for name, _ in impact}
        assert "MAINPGM" in affected
        assert "SUBPGMB" in affected


class TestDependencyTree:
    def test_dependency_tree_structure(self, graph):
        tree = graph.dependency_tree("MAINPGM")
        assert tree["name"] == "MAINPGM"
        assert "calls" in tree
        assert "copybooks" in tree
        child_names = {c["name"] for c in tree["calls"]}
        assert "SUBPGMA" in child_names
        assert "SUBPGMB" in child_names

    def test_dependency_tree_depth(self, graph):
        tree = graph.dependency_tree("MAINPGM", max_depth=2)
        suba = next(c for c in tree["calls"] if c["name"] == "SUBPGMA")
        leaf_names = {c["name"] for c in suba.get("calls", [])}
        assert "LEAFPGM" in leaf_names


class TestGraphEnrichment:
    def test_enrichment_data_for_program(self, graph):
        data = graph.enrichment_for("MAINPGM")
        assert set(data["callees"]) == {"SUBPGMA", "SUBPGMB"}
        assert data["callers"] == []
        assert set(data["copybooks"]) == {"SHARED01", "SHARED02"}
        assert "SUBPGMA" in data["programs_sharing_copybooks"]
        assert data["hub_score"] > 0

    def test_enrichment_for_unknown_returns_empty(self, graph):
        data = graph.enrichment_for("NONEXISTENT")
        assert data["callees"] == []
        assert data["callers"] == []
        assert data["copybooks"] == []
        assert data["hub_score"] == 0.0

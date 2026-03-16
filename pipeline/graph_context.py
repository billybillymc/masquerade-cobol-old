"""
In-memory graph index for COBOL dependency analysis.

Loads the graph.json produced by analyze.py and provides fast lookups
for callers, callees, copybook sharing, centrality, impact analysis,
and dependency trees. Used both during ingestion (to enrich chunks)
and at query time (for graph-neighbor expansion).
"""

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional


class GraphIndex:
    def __init__(self, analysis_dir: str):
        analysis_path = Path(analysis_dir)
        self.analysis_dir = analysis_dir
        graph_file = analysis_path / "graph.json"
        if not graph_file.exists():
            raise FileNotFoundError(f"graph.json not found in {analysis_dir}")

        with open(graph_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.stats: dict = {}
        stats_file = analysis_path / "stats.json"
        if stats_file.exists():
            with open(stats_file, "r", encoding="utf-8") as f:
                self.stats = json.load(f)

        self.nodes: dict[str, dict] = {}
        self.edges: list[dict] = data.get("edges", [])

        self._programs: set[str] = set()
        self._copybooks: set[str] = set()

        # Adjacency lists keyed by node id
        self._forward: dict[str, list[tuple[str, str, dict]]] = defaultdict(list)
        self._reverse: dict[str, list[tuple[str, str, dict]]] = defaultdict(list)

        # Program-level adjacency (by name, not node id)
        self._call_forward: dict[str, list[str]] = defaultdict(list)
        self._call_reverse: dict[str, list[str]] = defaultdict(list)
        self._copy_edges: dict[str, list[str]] = defaultdict(list)  # program -> copybooks
        self._copybook_users: dict[str, list[str]] = defaultdict(list)  # copybook -> programs

        for node in data.get("nodes", []):
            nid = node["id"]
            self.nodes[nid] = node
            if node["type"] == "PROGRAM":
                self._programs.add(node["name"])
            elif node["type"] == "COPYBOOK":
                self._copybooks.add(node["name"])

        for edge in self.edges:
            src = edge["source"]
            tgt = edge["target"]
            etype = edge["type"]
            self._forward[src].append((tgt, etype, edge))
            self._reverse[tgt].append((src, etype, edge))

            if etype in ("CALL", "XCTL", "LINK"):
                src_name = self._node_name(src)
                tgt_name = self._node_name(tgt)
                if src_name and tgt_name:
                    self._call_forward[src_name].append(tgt_name)
                    self._call_reverse[tgt_name].append(src_name)

            elif etype == "COPIES":
                src_name = self._node_name(src)
                tgt_name = self._node_name(tgt)
                if src_name and tgt_name:
                    self._copy_edges[src_name].append(tgt_name)
                    self._copybook_users[tgt_name].append(src_name)

        # Deduplicate adjacency lists
        for k in self._call_forward:
            self._call_forward[k] = list(dict.fromkeys(self._call_forward[k]))
        for k in self._call_reverse:
            self._call_reverse[k] = list(dict.fromkeys(self._call_reverse[k]))
        for k in self._copy_edges:
            self._copy_edges[k] = list(dict.fromkeys(self._copy_edges[k]))
        for k in self._copybook_users:
            self._copybook_users[k] = list(dict.fromkeys(self._copybook_users[k]))

        self._centrality_cache: Optional[dict[str, float]] = None

    def _node_name(self, node_id: str) -> Optional[str]:
        node = self.nodes.get(node_id)
        return node["name"] if node else node_id.split(":")[-1]

    # --- Basic lookups ---

    def program_names(self) -> list[str]:
        return sorted(self._programs)

    def copybook_names(self) -> list[str]:
        return sorted(self._copybooks)

    def callees(self, program: str) -> list[str]:
        return self._call_forward.get(program.upper(), [])

    def callers(self, program: str) -> list[str]:
        return self._call_reverse.get(program.upper(), [])

    def callees_transitive(self, program: str, max_depth: int = 5) -> list[str]:
        visited = set()
        queue = deque([(program.upper(), 0)])
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for callee in self._call_forward.get(current, []):
                if callee not in visited and callee != program.upper():
                    visited.add(callee)
                    queue.append((callee, depth + 1))
        return sorted(visited)

    def copybooks_of(self, program: str) -> list[str]:
        return self._copy_edges.get(program.upper(), [])

    def copybook_users(self, copybook: str) -> list[str]:
        return self._copybook_users.get(copybook.upper(), [])

    def programs_sharing_copybooks_with(self, program: str) -> list[str]:
        pgm = program.upper()
        cbs = self._copy_edges.get(pgm, [])
        shared: set[str] = set()
        for cb in cbs:
            for user in self._copybook_users.get(cb, []):
                if user != pgm:
                    shared.add(user)
        return sorted(shared)

    # --- Centrality ---

    def _compute_centrality(self) -> dict[str, float]:
        if self._centrality_cache is not None:
            return self._centrality_cache

        scores: dict[str, float] = {}
        for pgm in self._programs:
            out_degree = len(self._call_forward.get(pgm, []))
            in_degree = len(self._call_reverse.get(pgm, []))
            copy_degree = len(self._copy_edges.get(pgm, []))
            scores[pgm] = out_degree + in_degree + copy_degree * 0.5
        self._centrality_cache = scores
        return scores

    def degree_centrality(self, program: str) -> float:
        return self._compute_centrality().get(program.upper(), 0.0)

    def hub_programs(self, top_n: int = 10) -> list[tuple[str, float]]:
        scores = self._compute_centrality()
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_n]

    def leaf_programs(self) -> list[str]:
        leaves = []
        for pgm in self._programs:
            if not self._call_forward.get(pgm):
                leaves.append(pgm)
        return sorted(leaves)

    def connected_components(self) -> list[set[str]]:
        """Find connected components among program nodes (undirected)."""
        adj: dict[str, set[str]] = defaultdict(set)
        for pgm in self._programs:
            for callee in self._call_forward.get(pgm, []):
                if callee in self._programs:
                    adj[pgm].add(callee)
                    adj[callee].add(pgm)
            for peer in self.programs_sharing_copybooks_with(pgm):
                if peer in self._programs:
                    adj[pgm].add(peer)
                    adj[peer].add(pgm)

        visited: set[str] = set()
        components: list[set[str]] = []
        for pgm in self._programs:
            if pgm in visited:
                continue
            component: set[str] = set()
            queue = deque([pgm])
            while queue:
                node = queue.popleft()
                if node in visited:
                    continue
                visited.add(node)
                component.add(node)
                for neighbor in adj.get(node, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)
            if component:
                components.append(component)
        return components

    # --- Impact analysis ---

    def impact_of(self, node_id: str, max_depth: int = 3) -> list[tuple[str, int]]:
        """BFS reverse traversal: find all nodes affected if node_id changes.

        Returns list of (node_name, distance) for program nodes reachable
        by walking reverse edges (callers, copybook users).
        """
        visited: dict[str, int] = {}
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current, depth = queue.popleft()
            if current in visited:
                continue
            visited[current] = depth

            if depth >= max_depth:
                continue

            for src, etype, edge in self._reverse.get(current, []):
                if src not in visited:
                    queue.append((src, depth + 1))

        result = []
        for nid, dist in visited.items():
            if dist == 0:
                continue
            node = self.nodes.get(nid)
            if node and node["type"] == "PROGRAM":
                result.append((node["name"], dist))

        result.sort(key=lambda x: (x[1], x[0]))
        return result

    # --- Dependency tree ---

    def dependency_tree(self, program: str, max_depth: int = 3, _depth: int = 0, _visited: set = None) -> dict:
        pgm = program.upper()
        if _visited is None:
            _visited = set()

        tree = {
            "name": pgm,
            "copybooks": self.copybooks_of(pgm),
            "calls": [],
        }

        if pgm in _visited or _depth >= max_depth:
            return tree

        _visited.add(pgm)
        for callee in self.callees(pgm):
            child = self.dependency_tree(callee, max_depth, _depth + 1, _visited)
            tree["calls"].append(child)

        return tree

    # --- Enrichment bundle for ingestion ---

    def enrichment_for(self, program: str) -> dict:
        """Return a dict of graph context for a program, suitable for chunk metadata."""
        pgm = program.upper()
        if pgm not in self._programs:
            return {
                "callees": [],
                "callers": [],
                "copybooks": [],
                "programs_sharing_copybooks": [],
                "hub_score": 0.0,
            }
        return {
            "callees": self.callees(pgm),
            "callers": self.callers(pgm),
            "copybooks": self.copybooks_of(pgm),
            "programs_sharing_copybooks": self.programs_sharing_copybooks_with(pgm),
            "hub_score": self.degree_centrality(pgm),
        }

    # --- Graph-neighbor expansion for retrieval ---

    def neighbors_for_retrieval(self, program_names: list[str], copybook_names: list[str], max_per_type: int = 5) -> dict:
        """Given programs and copybooks from initial retrieval, return
        structurally related programs and copybooks for context expansion."""
        extra_programs: set[str] = set()
        extra_copybooks: set[str] = set()

        seen = set(p.upper() for p in program_names)

        for pgm in program_names:
            pgm = pgm.upper()
            for callee in self.callees(pgm):
                if callee not in seen:
                    extra_programs.add(callee)
            for caller in self.callers(pgm):
                if caller not in seen:
                    extra_programs.add(caller)
            for cb in self.copybooks_of(pgm):
                extra_copybooks.add(cb)

        for cb in copybook_names:
            for user in self.copybook_users(cb.upper()):
                if user.upper() not in seen:
                    extra_programs.add(user.upper())

        ranked_programs = sorted(
            extra_programs,
            key=lambda p: self.degree_centrality(p),
            reverse=True,
        )

        return {
            "programs": ranked_programs[:max_per_type],
            "copybooks": sorted(extra_copybooks)[:max_per_type],
        }

    # --- Estate summary ---

    def summary(self) -> dict:
        """Compute estate-level summary from graph data and stats.json."""
        s = self.stats

        # Node/edge type breakdowns
        node_types: dict[str, int] = defaultdict(int)
        for node in self.nodes.values():
            node_types[node["type"]] += 1

        edge_types: dict[str, int] = defaultdict(int)
        for edge in self.edges:
            edge_types[edge["type"]] += 1

        # Copybook sharing analysis
        shared_copybooks = []
        for cb in self.copybook_names():
            users = self.copybook_users(cb)
            if len(users) > 1:
                shared_copybooks.append((cb, len(users), users))
        shared_copybooks.sort(key=lambda x: x[1], reverse=True)

        # Program classification
        cics_programs = []
        batch_programs = []
        for pgm in self.program_names():
            node_id = f"PGM:{pgm}"
            has_cics = any(
                e["type"] == "CICS_IO" for e in self.edges if e["source"] == node_id
            )
            if has_cics:
                cics_programs.append(pgm)
            else:
                batch_programs.append(pgm)

        # Components
        components = self.connected_components()
        components.sort(key=len, reverse=True)

        # Unresolved references
        unresolved_cbs = s.get("unresolved_copybooks", [])
        unresolved_calls = s.get("unresolved_calls", [])

        return {
            "total_programs": len(self._programs),
            "total_copybooks": len(self._copybooks),
            "total_loc": s.get("total_loc", 0),
            "total_code_lines": s.get("total_code_lines", 0),
            "total_comment_lines": s.get("total_comment_lines", 0),
            "cics_programs": cics_programs,
            "batch_programs": batch_programs,
            "node_types": dict(node_types),
            "edge_types": dict(edge_types),
            "total_edges": len(self.edges),
            "shared_copybooks": shared_copybooks[:15],
            "components": components,
            "hub_programs": self.hub_programs(10),
            "leaf_programs": self.leaf_programs(),
            "unresolved_copybooks": unresolved_cbs,
            "unresolved_calls": unresolved_calls,
            "total_paragraphs": s.get("total_paragraphs", 0),
        }

    # --- Readiness scoring ---

    def readiness_score(self, program: str) -> dict:
        """Compute reimplementation readiness score for a single program.

        Higher score = more suitable for reimplementation.
        Components:
        - isolation: fewer callers and shared copybooks = easier to extract
        - simplicity: fewer LOC, paragraphs, CICS ops = easier to reimplement
        - dependency_clarity: fewer unresolved refs touching this program
        - testability: leaf programs with clear I/O are more testable
        """
        pgm = program.upper()
        node_id = f"PGM:{pgm}"
        node = self.nodes.get(node_id, {})
        meta = node.get("metadata", {})

        callers = self.callers(pgm)
        callees = self.callees(pgm)
        copybooks = self.copybooks_of(pgm)
        shared_peers = self.programs_sharing_copybooks_with(pgm)

        total_lines = meta.get("total_lines", 0)
        code_lines = meta.get("code_lines", 0)
        para_count = meta.get("paragraph_count", 0)

        has_cics = any(
            e["type"] == "CICS_IO" for e in self.edges if e["source"] == node_id
        )

        # Unresolved refs touching this program
        unresolved_cbs = set(self.stats.get("unresolved_copybooks", []))
        unresolved_calls = set(self.stats.get("unresolved_calls", []))
        my_unresolved_cbs = [cb for cb in copybooks if cb in unresolved_cbs]
        my_unresolved_calls = [c for c in callees if c in unresolved_calls]

        # --- Score components (0-100 each) ---

        # Isolation: fewer inbound dependencies = easier to extract
        caller_penalty = min(len(callers) * 15, 80)
        shared_penalty = min(len(shared_peers) * 5, 40)
        isolation = max(0, 100 - caller_penalty - shared_penalty)

        # Simplicity: smaller = easier to reimplement
        if code_lines == 0:
            simplicity = 50  # unknown size
        elif code_lines <= 100:
            simplicity = 95
        elif code_lines <= 300:
            simplicity = 80
        elif code_lines <= 500:
            simplicity = 60
        elif code_lines <= 1000:
            simplicity = 40
        else:
            simplicity = 20

        # CICS penalty — online programs are harder to reimplement
        if has_cics:
            simplicity = max(0, simplicity - 20)

        # Dependency clarity: fewer unknowns = higher confidence
        unresolved_penalty = len(my_unresolved_cbs) * 15 + len(my_unresolved_calls) * 20
        dependency_clarity = max(0, 100 - unresolved_penalty)

        # Testability: leaf programs with clear boundaries are most testable
        testability = 60
        if not callees:
            testability += 20  # leaf program
        if not has_cics:
            testability += 10  # batch is easier to test
        if len(callers) <= 1:
            testability += 10  # clear entry point
        testability = min(testability, 100)

        # Weighted composite
        composite = (
            isolation * 0.30
            + simplicity * 0.25
            + dependency_clarity * 0.25
            + testability * 0.20
        )

        return {
            "program": pgm,
            "composite": round(composite, 1),
            "isolation": round(isolation, 1),
            "simplicity": round(simplicity, 1),
            "dependency_clarity": round(dependency_clarity, 1),
            "testability": round(testability, 1),
            "details": {
                "code_lines": code_lines,
                "total_lines": total_lines,
                "paragraph_count": para_count,
                "callers": len(callers),
                "callees": len(callees),
                "copybooks": len(copybooks),
                "shared_peers": len(shared_peers),
                "has_cics": has_cics,
                "unresolved_copybooks": my_unresolved_cbs,
                "unresolved_calls": my_unresolved_calls,
            },
        }

    def readiness_ranking(self) -> list[dict]:
        """Rank all programs by reimplementation readiness (highest first).
        Excludes unresolved/ghost programs that have no source code."""
        scores = []
        for pgm in self.program_names():
            node_id = f"PGM:{pgm}"
            node = self.nodes.get(node_id, {})
            if not node.get("source_file"):
                continue
            scores.append(self.readiness_score(pgm))
        scores.sort(key=lambda x: x["composite"], reverse=True)
        return scores


    def dead_code_analysis(self) -> dict:
        """Detect potentially dead code across the codebase.

        Identifies:
        - Unreachable paragraphs (no PERFORM path from any entry paragraph)
        - Orphan programs (no callers and not a likely entry point)
        - Unused copybooks (not COPY'd by any program)
        """
        # --- Unreachable paragraphs ---
        unreachable_paragraphs: list[dict] = []

        for pgm in self.program_names():
            pgm_prefix = f"PGM:{pgm}::PARA:"
            para_nodes = {
                nid: node for nid, node in self.nodes.items()
                if nid.startswith(pgm_prefix)
            }
            if not para_nodes:
                continue

            # Find entry paragraphs (those with no inbound PERFORMS within this program)
            has_inbound = set()
            para_graph: dict[str, list[str]] = defaultdict(list)
            for edge in self.edges:
                if edge["type"] == "PERFORMS" and edge["source"].startswith(f"PGM:{pgm}::PARA:"):
                    has_inbound.add(edge["target"])
                    src_para = edge["source"].split("::PARA:")[1] if "::PARA:" in edge["source"] else ""
                    tgt_para = edge["target"].split("::PARA:")[1] if "::PARA:" in edge["target"] else ""
                    if src_para and tgt_para:
                        para_graph[src_para].append(tgt_para)

            entry_paras = [
                nid.split("::PARA:")[1]
                for nid in para_nodes
                if nid not in has_inbound
            ]

            # BFS from entry paragraphs
            reachable = set()
            queue = deque(entry_paras)
            while queue:
                current = queue.popleft()
                if current in reachable:
                    continue
                reachable.add(current)
                for child in para_graph.get(current, []):
                    if child not in reachable:
                        queue.append(child)

            all_paras = {nid.split("::PARA:")[1] for nid in para_nodes}
            unreachable = all_paras - reachable
            for para_name in sorted(unreachable):
                node_id = f"PGM:{pgm}::PARA:{para_name}"
                node = self.nodes.get(node_id, {})
                meta = node.get("metadata", {})
                unreachable_paragraphs.append({
                    "program": pgm,
                    "paragraph": para_name,
                    "start_line": meta.get("start_line", 0),
                    "end_line": meta.get("end_line", 0),
                    "has_calls": meta.get("call_count", 0) > 0,
                    "has_cics": meta.get("cics_count", 0) > 0,
                })

        # --- Orphan programs ---
        orphan_programs: list[dict] = []
        for pgm in self.program_names():
            node_id = f"PGM:{pgm}"
            node = self.nodes.get(node_id, {})
            if not node.get("source_file"):
                continue  # ghost node
            callers = self.callers(pgm)
            if not callers:
                orphan_programs.append({
                    "program": pgm,
                    "code_lines": node.get("metadata", {}).get("code_lines", 0),
                    "has_cics": any(
                        e["type"] == "CICS_IO"
                        for e in self.edges if e["source"] == node_id
                    ),
                    "callees": self.callees(pgm),
                })

        # --- Unused copybooks ---
        used_copybooks = set()
        for edge in self.edges:
            if edge["type"] == "COPIES":
                tgt = edge["target"]
                if tgt.startswith("CPY:"):
                    used_copybooks.add(tgt[4:])

        all_copybooks = self.copybook_names()
        unused_copybooks = sorted(set(all_copybooks) - used_copybooks)

        return {
            "unreachable_paragraphs": unreachable_paragraphs,
            "orphan_programs": orphan_programs,
            "unused_copybooks": unused_copybooks,
            "summary": {
                "total_paragraphs": sum(
                    1 for nid in self.nodes if "::PARA:" in nid
                ),
                "unreachable_count": len(unreachable_paragraphs),
                "total_programs": len([
                    p for p in self.program_names()
                    if self.nodes.get(f"PGM:{p}", {}).get("source_file")
                ]),
                "orphan_count": len(orphan_programs),
                "total_copybooks": len(all_copybooks),
                "unused_count": len(unused_copybooks),
            },
        }


class DataFlowIndex:
    """Field-level data lineage from programs.json data flows.

    Builds a directed graph of field assignments across all programs,
    enabling forward/backward tracing of data items.
    """

    def __init__(self, analysis_dir: str):
        programs_file = Path(analysis_dir) / "programs.json"
        if not programs_file.exists():
            raise FileNotFoundError(f"programs.json not found in {analysis_dir}")

        with open(programs_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # programs.json is a dict keyed by program name
        self._programs: list[dict] = list(raw.values()) if isinstance(raw, dict) else raw

        # field -> list of (source_fields, program, paragraph, line, flow_type)
        self._writes_to: dict[str, list[dict]] = defaultdict(list)
        # field -> list of (target_fields, program, paragraph, line, flow_type)
        self._reads_from: dict[str, list[dict]] = defaultdict(list)
        # program -> list of data flows
        self._program_flows: dict[str, list[dict]] = defaultdict(list)
        # field -> set of programs that touch it
        self._field_programs: dict[str, set[str]] = defaultdict(set)
        # program -> data items
        self._program_data_items: dict[str, list[dict]] = {}
        # CALL USING bindings: (caller, callee) -> list of field names passed
        self._call_bindings: dict[tuple[str, str], list[str]] = defaultdict(list)

        for pgm in self._programs:
            pid = pgm["program_id"].upper()
            self._program_data_items[pid] = pgm.get("data_items_sample", [])

            for df in pgm.get("data_flows", []):
                flow_type = df["type"]
                sources = [s.upper() for s in df.get("sources", [])]
                targets = [t.upper() for t in df.get("targets", [])]
                paragraph = df.get("paragraph", "")
                line = df.get("line", 0)

                flow_record = {
                    "program": pid,
                    "paragraph": paragraph,
                    "line": line,
                    "flow_type": flow_type,
                    "sources": sources,
                    "targets": targets,
                }

                self._program_flows[pid].append(flow_record)

                for tgt in targets:
                    self._writes_to[tgt].append(flow_record)
                    self._field_programs[tgt].add(pid)
                for src in sources:
                    self._reads_from[src].append(flow_record)
                    self._field_programs[src].add(pid)

            for ct in pgm.get("call_targets", []):
                using = ct.get("using", [])
                if using:
                    callee = ct["target"].upper()
                    for arg in using:
                        self._call_bindings[(pid, callee)].append(arg.upper())
                        self._field_programs[arg.upper()].add(pid)

    def trace_field(self, field_name: str, direction: str = "both", max_depth: int = 3) -> dict:
        """Trace a field through data flow assignments.

        direction: 'forward' (where does this field go?),
                   'backward' (where does this field come from?),
                   'both'
        """
        field = field_name.upper()
        result = {
            "field": field,
            "programs_touching": sorted(self._field_programs.get(field, set())),
            "forward_trace": [],
            "backward_trace": [],
        }

        if direction in ("forward", "both"):
            result["forward_trace"] = self._trace_forward(field, max_depth)

        if direction in ("backward", "both"):
            result["backward_trace"] = self._trace_backward(field, max_depth)

        return result

    def _trace_forward(self, field: str, max_depth: int, max_results: int = 50) -> list[dict]:
        """Where does this field's value flow to?

        Follows: field X is used as a SOURCE -> targets are downstream.
        Uses _reads_from[X] to find flows where X feeds into other fields.
        """
        visited = set()
        trace = []
        queue = deque([(field, 0)])

        while queue and len(trace) < max_results:
            current, depth = queue.popleft()
            if current in visited or depth > max_depth:
                continue
            visited.add(current)

            for flow in self._reads_from.get(current, []):
                for tgt in flow["targets"]:
                    entry = {
                        "field": tgt,
                        "from_field": current,
                        "program": flow["program"],
                        "paragraph": flow["paragraph"],
                        "line": flow["line"],
                        "flow_type": flow["flow_type"],
                        "depth": depth + 1,
                    }
                    trace.append(entry)
                    if tgt not in visited and len(trace) < max_results:
                        queue.append((tgt, depth + 1))

        return trace

    def _trace_backward(self, field: str, max_depth: int, max_results: int = 50) -> list[dict]:
        """Where does this field's value come from?

        Follows: field X is a TARGET -> sources are upstream.
        Uses _writes_to[X] to find flows that write into X.
        """
        visited = set()
        trace = []
        queue = deque([(field, 0)])

        while queue and len(trace) < max_results:
            current, depth = queue.popleft()
            if current in visited or depth > max_depth:
                continue
            visited.add(current)

            for flow in self._writes_to.get(current, []):
                for src in flow["sources"]:
                    if src not in visited:
                        entry = {
                            "field": src,
                            "feeds_into": current,
                            "program": flow["program"],
                            "paragraph": flow["paragraph"],
                            "line": flow["line"],
                            "flow_type": flow["flow_type"],
                            "depth": depth + 1,
                        }
                        trace.append(entry)
                        if len(trace) < max_results:
                            queue.append((src, depth + 1))

        return trace

    def field_definition(self, field_name: str) -> list[dict]:
        """Find the DATA DIVISION definition(s) for a field."""
        field = field_name.upper()
        defs = []
        for pid, items in self._program_data_items.items():
            for item in items:
                if item.get("name", "").upper() == field:
                    defs.append({
                        "program": pid,
                        "level": item.get("level"),
                        "name": item.get("name"),
                        "picture": item.get("picture"),
                        "occurs": item.get("occurs"),
                    })
        return defs

    def cross_program_bindings(self, field_name: str) -> list[dict]:
        """Find CALL USING bindings that pass this field between programs."""
        field = field_name.upper()
        bindings = []
        for (caller, callee), args in self._call_bindings.items():
            if field in args:
                bindings.append({
                    "caller": caller,
                    "callee": callee,
                    "field": field,
                    "all_args": args,
                })
        return bindings

    def program_flow_summary(self, program: str) -> dict:
        """Summarize data flows within a program."""
        pgm = program.upper()
        flows = self._program_flows.get(pgm, [])
        if not flows:
            return {"program": pgm, "total_flows": 0, "paragraphs": {}}

        by_para: dict[str, list[dict]] = defaultdict(list)
        for f in flows:
            by_para[f["paragraph"] or "(top-level)"].append(f)

        fields_written = set()
        fields_read = set()
        for f in flows:
            fields_written.update(f["targets"])
            fields_read.update(f["sources"])

        return {
            "program": pgm,
            "total_flows": len(flows),
            "fields_written": sorted(fields_written),
            "fields_read": sorted(fields_read),
            "flow_types": dict(defaultdict(int, {f["flow_type"]: sum(1 for ff in flows if ff["flow_type"] == f["flow_type"]) for f in flows})),
            "paragraphs": {
                para: {
                    "flow_count": len(pflows),
                    "writes": sorted({t for f in pflows for t in f["targets"]}),
                    "reads": sorted({s for f in pflows for s in f["sources"]}),
                }
                for para, pflows in by_para.items()
            },
        }

    def cross_reference(self, field_name: str) -> dict:
        """Full cross-reference for a field across all programs.

        Returns every program, paragraph, flow type, and line where the
        field is read, written, or passed as a CALL USING argument.
        """
        field = field_name.upper()
        writes = self._writes_to.get(field, [])
        reads = self._reads_from.get(field, [])
        programs = sorted(self._field_programs.get(field, set()))

        call_refs = []
        for (caller, callee), args in self._call_bindings.items():
            if field in args:
                call_refs.append({"caller": caller, "callee": callee, "position": args.index(field) + 1})

        by_program: dict[str, dict] = {}
        for pgm in programs:
            pgm_writes = [w for w in writes if w["program"] == pgm]
            pgm_reads = [r for r in reads if r["program"] == pgm]
            pgm_calls = [c for c in call_refs if c["caller"] == pgm]

            by_program[pgm] = {
                "writes": [
                    {"paragraph": w["paragraph"], "line": w["line"], "flow_type": w["flow_type"],
                     "sources": w["sources"], "targets": w["targets"]}
                    for w in pgm_writes
                ],
                "reads": [
                    {"paragraph": r["paragraph"], "line": r["line"], "flow_type": r["flow_type"],
                     "sources": r["sources"], "targets": r["targets"]}
                    for r in pgm_reads
                ],
                "call_passing": pgm_calls,
                "write_count": len(pgm_writes),
                "read_count": len(pgm_reads),
            }

        return {
            "field": field,
            "total_programs": len(programs),
            "programs": programs,
            "total_writes": len(writes),
            "total_reads": len(reads),
            "total_call_refs": len(call_refs),
            "by_program": by_program,
        }

    def search_fields(self, pattern: str) -> list[str]:
        """Search for fields matching a pattern (case-insensitive substring)."""
        pattern = pattern.upper()
        return sorted(f for f in self._field_programs.keys() if pattern in f)

"""
BMS map parser — extracts screen layouts, fields, and attributes from
CICS BMS (Basic Mapping Support) map definitions.

Builds a screen flow graph by combining BMS maps with COBOL program
SEND MAP/RECEIVE MAP and XCTL/LINK/RETURN TRANSID references.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class BmsField:
    name: str
    row: int
    col: int
    length: int
    initial: str
    color: str
    attributes: list[str]
    is_input: bool
    is_protected: bool

    @property
    def field_type(self) -> str:
        if not self.name or self.name.startswith("DFHMDF"):
            return "label"
        if self.is_input:
            return "input"
        return "output"


@dataclass
class BmsMap:
    """A single map (screen) within a mapset."""
    name: str
    mapset: str
    rows: int
    cols: int
    fields: list[BmsField] = field(default_factory=list)

    @property
    def input_fields(self) -> list[BmsField]:
        return [f for f in self.fields if f.is_input]

    @property
    def output_fields(self) -> list[BmsField]:
        return [f for f in self.fields if f.field_type == "output"]

    @property
    def labels(self) -> list[BmsField]:
        return [f for f in self.fields if f.field_type == "label" and f.initial]


@dataclass
class BmsMapset:
    """A complete mapset file containing one or more maps."""
    name: str
    source_file: str
    description: str
    maps: list[BmsMap] = field(default_factory=list)


_RE_DFHMSD = re.compile(r'^(\w+)\s+DFHMSD\s', re.IGNORECASE)
_RE_DFHMDI = re.compile(r'^(\w+)\s+DFHMDI\s', re.IGNORECASE)
_RE_DFHMDF = re.compile(r'^(\w*)\s*DFHMDF\s', re.IGNORECASE)
_RE_FINAL = re.compile(r'DFHMSD\s+TYPE=FINAL', re.IGNORECASE)
_RE_POS = re.compile(r'POS=\((\d+),(\d+)\)', re.IGNORECASE)
_RE_LENGTH = re.compile(r'LENGTH=(\d+)', re.IGNORECASE)
_RE_INITIAL = re.compile(r"INITIAL='([^']*(?:'\s*-\s*\n\s*'[^']*)*)'", re.IGNORECASE | re.MULTILINE)
_RE_COLOR = re.compile(r'COLOR=(\w+)', re.IGNORECASE)
_RE_ATTRB = re.compile(r'ATTRB=\(([^)]+)\)', re.IGNORECASE)
_RE_SIZE = re.compile(r'SIZE=\((\d+),(\d+)\)', re.IGNORECASE)
_RE_HILIGHT = re.compile(r'HILIGHT=(\w+)', re.IGNORECASE)


def _merge_continuations(lines: list[str]) -> list[str]:
    """Merge BMS continuation lines (ending with - before col 72)."""
    merged = []
    current = ""
    for line in lines:
        stripped = line.rstrip()
        if stripped.startswith("*"):
            continue
        if stripped.endswith("-"):
            current += stripped[:-1].rstrip() + " "
        else:
            current += stripped
            merged.append(current.strip())
            current = ""
    if current.strip():
        merged.append(current.strip())
    return merged


def _extract_description(lines: list[str]) -> str:
    for line in lines[:5]:
        if line.startswith("*") and not line.startswith("**"):
            text = line[1:].strip().strip("*").strip()
            if text and "copyright" not in text.lower() and "license" not in text.lower():
                return text
    return ""


def parse_bms_file(filepath: Path) -> Optional[BmsMapset]:
    """Parse a BMS file into a BmsMapset with maps and fields."""
    raw = filepath.read_text(encoding="utf-8", errors="replace")
    original_lines = raw.splitlines()
    description = _extract_description(original_lines)
    lines = _merge_continuations(original_lines)

    mapset_name = filepath.stem.upper()
    mapset = BmsMapset(
        name=mapset_name,
        source_file=str(filepath),
        description=description,
    )

    current_map: Optional[BmsMap] = None

    for line in lines:
        msd = _RE_DFHMSD.match(line)
        if msd:
            mapset_name = msd.group(1)
            mapset.name = mapset_name
            continue

        if _RE_FINAL.search(line):
            continue

        mdi = _RE_DFHMDI.match(line)
        if mdi:
            map_name = mdi.group(1)
            size_m = _RE_SIZE.search(line)
            rows = int(size_m.group(1)) if size_m else 24
            cols = int(size_m.group(2)) if size_m else 80
            current_map = BmsMap(name=map_name, mapset=mapset_name, rows=rows, cols=cols)
            mapset.maps.append(current_map)
            continue

        mdf = _RE_DFHMDF.match(line)
        if mdf and current_map is not None:
            field_name = mdf.group(1).strip() or ""

            pos_m = _RE_POS.search(line)
            row = int(pos_m.group(1)) if pos_m else 0
            col = int(pos_m.group(2)) if pos_m else 0

            len_m = _RE_LENGTH.search(line)
            length = int(len_m.group(1)) if len_m else 0

            initial_m = _RE_INITIAL.search(line)
            initial = initial_m.group(1).replace("\n", "").replace("               ", "") if initial_m else ""

            color_m = _RE_COLOR.search(line)
            color = color_m.group(1).upper() if color_m else ""

            attrb_m = _RE_ATTRB.search(line)
            attrs = [a.strip().upper() for a in attrb_m.group(1).split(",")] if attrb_m else []

            is_input = "UNPROT" in attrs or "IC" in attrs
            is_protected = "PROT" in attrs or "ASKIP" in attrs

            current_map.fields.append(BmsField(
                name=field_name, row=row, col=col, length=length,
                initial=initial, color=color, attributes=attrs,
                is_input=is_input, is_protected=is_protected,
            ))

    return mapset if mapset.maps else None


class ScreenFlowIndex:
    """Screen flow graph combining BMS maps with COBOL program navigation."""

    def __init__(self, codebase_dir: str, graph_index=None):
        self.codebase_dir = codebase_dir
        self.mapsets: dict[str, BmsMapset] = {}
        self._map_to_mapset: dict[str, str] = {}
        self._program_maps: dict[str, list[str]] = defaultdict(list)
        self._mapset_programs: dict[str, list[str]] = defaultdict(list)
        self._screen_transitions: list[dict] = []

        for bms_file in Path(codebase_dir).rglob("*.bms"):
            try:
                mapset = parse_bms_file(bms_file)
                if mapset:
                    self.mapsets[mapset.name] = mapset
                    for m in mapset.maps:
                        self._map_to_mapset[m.name] = mapset.name
            except Exception:
                continue

        # Scan COBOL programs for MAP/MAPSET references and XCTL/RETURN TRANSID
        _re_map = re.compile(r"MAP\s*\(\s*'([^']+)'\s*\)", re.IGNORECASE)
        _re_mapset = re.compile(r"MAPSET\s*\(\s*'([^']+)'\s*\)", re.IGNORECASE)
        _re_xctl = re.compile(r"XCTL\s+PROGRAM\s*\(\s*'([^']+)'\s*\)", re.IGNORECASE)
        _re_return_transid = re.compile(r"RETURN\s+TRANSID\s*\(\s*'([^']+)'\s*\)", re.IGNORECASE)
        _re_link = re.compile(r"LINK\s+PROGRAM\s*\(\s*'([^']+)'\s*\)", re.IGNORECASE)
        _re_pgm_move = re.compile(r"MOVE\s+'([A-Z0-9]+C?)'\s+TO\s+\S*(?:TO-PROGRAM|NEXT-PGM|PGM-NAME)", re.IGNORECASE)

        for cbl_file in Path(codebase_dir).rglob("*.cbl"):
            try:
                content = cbl_file.read_text(encoding="utf-8", errors="replace")
                pgm_name = cbl_file.stem.upper()

                maps = set(_re_map.findall(content))
                mapsets = set(_re_mapset.findall(content))
                xctls = set(_re_xctl.findall(content))
                returns = set(_re_return_transid.findall(content))
                links = set(_re_link.findall(content))
                pgm_moves = set(_re_pgm_move.findall(content))

                for ms in mapsets:
                    ms_upper = ms.upper()
                    self._program_maps[pgm_name].append(ms_upper)
                    self._mapset_programs[ms_upper].append(pgm_name)

                # XCTL = screen navigation
                for target in xctls:
                    self._screen_transitions.append({
                        "from": pgm_name,
                        "to": target.upper(),
                        "type": "XCTL",
                    })

                for target in links:
                    self._screen_transitions.append({
                        "from": pgm_name,
                        "to": target.upper(),
                        "type": "LINK",
                    })

                for target in pgm_moves:
                    if target.upper() != pgm_name:
                        self._screen_transitions.append({
                            "from": pgm_name,
                            "to": target.upper(),
                            "type": "NAVIGATE",
                        })

            except Exception:
                continue

    def summary(self) -> dict:
        total_fields = sum(
            len(m.fields) for ms in self.mapsets.values() for m in ms.maps
        )
        total_inputs = sum(
            len(m.input_fields) for ms in self.mapsets.values() for m in ms.maps
        )
        programs_with_screens = set()
        for pgm, maps in self._program_maps.items():
            if maps:
                programs_with_screens.add(pgm)

        return {
            "total_mapsets": len(self.mapsets),
            "total_maps": sum(len(ms.maps) for ms in self.mapsets.values()),
            "total_fields": total_fields,
            "total_input_fields": total_inputs,
            "programs_with_screens": len(programs_with_screens),
            "screen_transitions": len(self._screen_transitions),
        }

    def screen_detail(self, mapset_name: str) -> Optional[dict]:
        ms = self.mapsets.get(mapset_name.upper())
        if not ms:
            return None

        programs = self._mapset_programs.get(mapset_name.upper(), [])
        maps = []
        for m in ms.maps:
            maps.append({
                "name": m.name,
                "rows": m.rows,
                "cols": m.cols,
                "input_fields": [
                    {"name": f.name, "row": f.row, "col": f.col, "length": f.length, "color": f.color}
                    for f in m.input_fields
                ],
                "output_fields": [
                    {"name": f.name, "row": f.row, "col": f.col, "length": f.length}
                    for f in m.output_fields
                ],
                "labels": [
                    {"text": f.initial, "row": f.row, "col": f.col}
                    for f in m.labels
                ],
            })

        return {
            "name": ms.name,
            "description": ms.description,
            "source_file": ms.source_file,
            "programs": list(set(programs)),
            "maps": maps,
        }

    def screen_flow(self) -> dict:
        """Build the complete screen navigation graph."""
        nodes = []
        edges = []
        seen_nodes = set()

        for pgm, maps in self._program_maps.items():
            if pgm not in seen_nodes:
                seen_nodes.add(pgm)
                screen_name = maps[0] if maps else ""
                ms = self.mapsets.get(screen_name)
                desc = ms.description if ms else ""
                nodes.append({
                    "id": pgm,
                    "type": "screen",
                    "mapset": screen_name,
                    "description": desc,
                })

        for t in self._screen_transitions:
            if t["to"] in self._program_maps:
                edges.append({
                    "from": t["from"],
                    "to": t["to"],
                    "type": t["type"],
                })
                if t["to"] not in seen_nodes:
                    seen_nodes.add(t["to"])
                    maps = self._program_maps.get(t["to"], [])
                    screen_name = maps[0] if maps else ""
                    ms = self.mapsets.get(screen_name)
                    desc = ms.description if ms else ""
                    nodes.append({
                        "id": t["to"],
                        "type": "screen",
                        "mapset": screen_name,
                        "description": desc,
                    })

        return {"nodes": nodes, "edges": edges}

    def render_screen_ascii(self, mapset_name: str) -> Optional[str]:
        """Render a BMS map as ASCII art (24x80 terminal emulation)."""
        ms = self.mapsets.get(mapset_name.upper())
        if not ms or not ms.maps:
            return None

        m = ms.maps[0]
        grid = [[" "] * m.cols for _ in range(m.rows)]

        for f in sorted(m.fields, key=lambda x: (x.row, x.col)):
            if f.row < 1 or f.row > m.rows or f.col < 1:
                continue

            row_idx = f.row - 1
            col_idx = f.col - 1

            if f.initial:
                text = f.initial[:f.length] if f.length else f.initial
            elif f.is_input:
                text = "_" * max(f.length, 1)
            elif f.name:
                text = f"[{f.name}]"
            else:
                continue

            for ci, ch in enumerate(text):
                target_col = col_idx + ci
                if target_col < m.cols:
                    grid[row_idx][target_col] = ch

        lines = ["".join(row).rstrip() for row in grid]
        while lines and not lines[-1].strip():
            lines.pop()

        border = "+" + "-" * m.cols + "+"
        rendered = [border]
        for line in lines:
            rendered.append("|" + line.ljust(m.cols) + "|")
        rendered.append(border)

        return "\n".join(rendered)

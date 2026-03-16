"""
COBOL complexity metrics — cyclomatic complexity, nesting depth, and
Halstead-inspired operator/operand counts.

Cyclomatic complexity counts branching decision points:
  IF, EVALUATE/WHEN, PERFORM UNTIL/VARYING, ON SIZE ERROR, AT END,
  INVALID KEY, NOT ON SIZE ERROR, etc.

Formula: M = decision_points + 1 (per paragraph/program)
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ComplexityResult:
    program: str
    cyclomatic: int
    max_nesting: int
    decision_points: int
    paragraphs: int
    avg_complexity_per_paragraph: float
    hotspot_paragraphs: list[dict]


_DECISION_PATTERNS = [
    re.compile(r'^\s+IF\s', re.IGNORECASE),
    re.compile(r'^\s+EVALUATE\s', re.IGNORECASE),
    re.compile(r'^\s+WHEN\s+(?!OTHER)', re.IGNORECASE),
    re.compile(r'^\s+PERFORM\s+.*\s+UNTIL\s', re.IGNORECASE),
    re.compile(r'^\s+PERFORM\s+.*\s+VARYING\s', re.IGNORECASE),
    re.compile(r'^\s+ON\s+SIZE\s+ERROR', re.IGNORECASE),
    re.compile(r'^\s+NOT\s+ON\s+SIZE\s+ERROR', re.IGNORECASE),
    re.compile(r'^\s+AT\s+END\b', re.IGNORECASE),
    re.compile(r'^\s+NOT\s+AT\s+END\b', re.IGNORECASE),
    re.compile(r'^\s+INVALID\s+KEY', re.IGNORECASE),
    re.compile(r'^\s+NOT\s+INVALID\s+KEY', re.IGNORECASE),
    re.compile(r'^\s+ON\s+EXCEPTION', re.IGNORECASE),
    re.compile(r'^\s+SEARCH\s', re.IGNORECASE),
]

_RE_NESTING_OPEN = re.compile(r'^\s+(IF|EVALUATE|PERFORM|SEARCH)\s', re.IGNORECASE)
_RE_NESTING_CLOSE = re.compile(r'^\s+(END-IF|END-EVALUATE|END-PERFORM|END-SEARCH)\b', re.IGNORECASE)
_RE_PARA_HEADER = re.compile(r'^\s{7}\s*([A-Z0-9][\w-]+)\s*\.\s*$', re.IGNORECASE)

_COBOL_RESERVED = {
    'PERFORM', 'MOVE', 'COMPUTE', 'IF', 'ELSE', 'END-IF', 'EVALUATE', 'WHEN',
    'ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE', 'DISPLAY', 'ACCEPT', 'CALL',
    'STOP', 'GOBACK', 'GO', 'EXIT', 'CONTINUE', 'INITIALIZE', 'STRING',
    'UNSTRING', 'INSPECT', 'SEARCH', 'READ', 'WRITE', 'REWRITE', 'DELETE',
    'OPEN', 'CLOSE', 'START', 'RETURN', 'SORT', 'MERGE', 'SET', 'EXEC',
    'END-EXEC', 'COPY', 'SECTION', 'DIVISION',
}


def compute_complexity(source_path: str) -> Optional[ComplexityResult]:
    """Compute cyclomatic complexity for a COBOL source file."""
    path = Path(source_path)
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()

    program_name = path.stem.upper()
    for line in lines[:30]:
        upper = line.upper()
        if "PROGRAM-ID" in upper:
            parts = upper.split("PROGRAM-ID")
            if len(parts) > 1:
                pid = parts[1].strip().strip(".").strip()
                if pid:
                    program_name = pid.split()[0].strip(".")

    total_decisions = 0
    max_nesting = 0
    current_nesting = 0

    in_procedure = False
    current_para = None
    para_decisions: dict[str, int] = {}

    for line in lines:
        if len(line) > 6 and line[6] in ("*", "/"):
            continue

        upper = line.upper()
        if "PROCEDURE" in upper and "DIVISION" in upper:
            in_procedure = True
            continue

        if not in_procedure:
            continue

        m = _RE_PARA_HEADER.match(line)
        if m:
            name = m.group(1).upper()
            if name not in _COBOL_RESERVED and not name.endswith("DIVISION") and not name.endswith("SECTION"):
                current_para = name
                para_decisions.setdefault(current_para, 0)

        for pat in _DECISION_PATTERNS:
            if pat.search(line):
                total_decisions += 1
                if current_para:
                    para_decisions[current_para] = para_decisions.get(current_para, 0) + 1
                break

        if _RE_NESTING_OPEN.search(line):
            current_nesting += 1
            max_nesting = max(max_nesting, current_nesting)
        if _RE_NESTING_CLOSE.search(line):
            current_nesting = max(0, current_nesting - 1)

    cyclomatic = total_decisions + 1
    n_paragraphs = len(para_decisions) if para_decisions else 1
    avg_per_para = total_decisions / n_paragraphs if n_paragraphs else 0

    hotspots = sorted(
        [{"paragraph": k, "decisions": v, "complexity": v + 1}
         for k, v in para_decisions.items() if v > 0],
        key=lambda x: -x["decisions"],
    )[:10]

    return ComplexityResult(
        program=program_name,
        cyclomatic=cyclomatic,
        max_nesting=max_nesting,
        decision_points=total_decisions,
        paragraphs=n_paragraphs,
        avg_complexity_per_paragraph=round(avg_per_para, 1),
        hotspot_paragraphs=hotspots,
    )


def complexity_grade(cyclomatic: int, code_lines: int) -> str:
    """Risk classification based on cyclomatic complexity."""
    density = cyclomatic / max(code_lines, 1) * 100
    if cyclomatic <= 10:
        return "LOW"
    elif cyclomatic <= 30:
        return "MODERATE"
    elif cyclomatic <= 60:
        return "HIGH"
    return "VERY HIGH"


def compute_all(codebase_dir: str) -> list[ComplexityResult]:
    """Compute complexity for all COBOL files in a codebase."""
    results = []
    for cbl_file in sorted(Path(codebase_dir).rglob("*.cbl")):
        result = compute_complexity(str(cbl_file))
        if result:
            results.append(result)
    return results

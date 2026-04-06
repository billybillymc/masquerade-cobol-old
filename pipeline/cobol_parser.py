"""
Structural COBOL parser — extracts programs, divisions, sections, paragraphs,
copybook references, CALL/PERFORM/EXEC CICS targets, data items, and file controls.

Targets IBM Enterprise COBOL fixed-format (cols 1-6 seq, col 7 indicator, 8-72 code).
Not a full compiler — a structural extractor for dependency analysis.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SourceSpan:
    file: str
    start_line: int
    end_line: int


@dataclass
class DataItem:
    level: int
    name: str
    picture: Optional[str]
    usage: Optional[str]
    occurs: Optional[int]
    redefines: Optional[str]
    span: SourceSpan


@dataclass
class CopyStatement:
    copybook_name: str
    replacing: list[tuple[str, str]]
    span: SourceSpan


@dataclass
class CallTarget:
    target_program: str
    using_args: list[str]
    call_type: str  # 'CALL', 'XCTL', 'LINK'
    span: SourceSpan


@dataclass
class PerformTarget:
    target_paragraph: str
    thru_paragraph: Optional[str]
    is_loop: bool  # PERFORM VARYING / PERFORM UNTIL
    span: SourceSpan


@dataclass
class FileControl:
    select_name: str
    assign_to: str
    organization: Optional[str]
    access_mode: Optional[str]
    span: SourceSpan


@dataclass
class CicsOperation:
    operation: str  # READ, WRITE, SEND, RECEIVE, XCTL, LINK, etc.
    dataset: Optional[str]
    map_name: Optional[str]
    mapset: Optional[str]
    program: Optional[str]
    span: SourceSpan


@dataclass
class DataFlow:
    """A data assignment: MOVE source TO target, or COMPUTE target = expression."""
    flow_type: str  # 'MOVE', 'COMPUTE', 'ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE', 'STRING', 'UNSTRING', 'ACCEPT', 'READ_INTO'
    sources: list[str]  # source field names
    targets: list[str]  # target field names
    paragraph: Optional[str]
    span: SourceSpan


# ---------------------------------------------------------------------------
# IQ-01: Conditional logic dataclasses
#
# Design decisions documented in specs/iq-01-conditional-logic/spec.md
# DD-02: Structured predicates with raw_text fallback
# DD-03: EVALUATE as own block type (not normalized to IF)
# DD-04: GO TO in both block list and paragraph-level field
# DD-05: Inline PERFORM as conditional block
# ---------------------------------------------------------------------------

@dataclass
class Predicate:
    """Structured representation of a COBOL condition.

    Leaf nodes have left/operator/right.
    Compound nodes (AND/OR/NOT) use operator + children.
    raw_text is always present as a lossless fallback (DD-02 caveat).
    """
    left: Optional[str]
    operator: str  # '=', '>', '<', '>=', '<=', 'NOT =', 'NUMERIC', 'SPACES', 'ZEROS', 'AND', 'OR', 'NOT', '88_CONDITION'
    right: Optional[str]
    children: list['Predicate'] = field(default_factory=list)
    raw_text: str = ''
    is_88_condition: bool = False


@dataclass
class GoTo:
    """GO TO transfer — simple or DEPENDING ON (DD-04)."""
    targets: list[str]
    depending_on: Optional[str]  # field name for GO TO ... DEPENDING ON
    span: SourceSpan


@dataclass
class Statement:
    """A tagged union for statements inside conditional branches.

    stmt_type identifies the variant; data holds the typed payload.
    This lets branch bodies contain MOVEs, PERFORMs, CALLs, CICS ops,
    nested IFs, EVALUATEs, GO TOs, inline PERFORMs, and raw text.
    """
    stmt_type: str  # 'IF', 'EVALUATE', 'GOTO', 'PERFORM_INLINE', 'MOVE', 'PERFORM', 'CALL', 'CICS', 'SET', 'DISPLAY', 'OTHER'
    data: object  # typed payload: IfBlock | EvaluateBlock | GoTo | PerformInline | DataFlow | PerformTarget | CallTarget | CicsOperation | str
    span: Optional[SourceSpan] = None


@dataclass
class IfBlock:
    """IF ... ELSE ... END-IF with structured predicate and body statements (DD-01)."""
    condition: Predicate
    then_body: list[Statement] = field(default_factory=list)
    else_body: list[Statement] = field(default_factory=list)
    span: Optional[SourceSpan] = None


@dataclass
class WhenBranch:
    """One WHEN arm of an EVALUATE block (DD-03)."""
    conditions: list[str]  # match values or ["OTHER"]; multiple for WHEN val1 WHEN val2 fall-through
    condition_predicate: Optional[Predicate] = None  # structured form when EVALUATE TRUE
    body: list[Statement] = field(default_factory=list)
    span: Optional[SourceSpan] = None


@dataclass
class EvaluateBlock:
    """EVALUATE ... END-EVALUATE — preserved as own type for match/switch mapping (DD-03)."""
    subjects: list[str]  # ["WS-RESP-CD"] or ["TRUE"] or multiple for ALSO
    branches: list[WhenBranch] = field(default_factory=list)
    span: Optional[SourceSpan] = None


@dataclass
class PerformInline:
    """Inline PERFORM ... END-PERFORM with body (DD-05).

    varying: {counter, from_val, by_val} for PERFORM VARYING
    until: structured predicate for PERFORM UNTIL
    """
    varying: Optional[dict] = None
    until: Optional[Predicate] = None
    body: list[Statement] = field(default_factory=list)
    span: Optional[SourceSpan] = None


@dataclass
class Paragraph:
    name: str
    performs: list[PerformTarget]
    calls: list[CallTarget]
    cics_ops: list[CicsOperation]
    data_flows: list[DataFlow]
    span: SourceSpan
    conditional_blocks: list[Statement] = field(default_factory=list)
    goto_targets: list[GoTo] = field(default_factory=list)


@dataclass
class CobolProgram:
    program_id: str
    source_file: str
    identification_division: Optional[SourceSpan]
    environment_division: Optional[SourceSpan]
    data_division: Optional[SourceSpan]
    procedure_division: Optional[SourceSpan]
    author: Optional[str]
    paragraphs: list[Paragraph]
    copy_statements: list[CopyStatement]
    call_targets: list[CallTarget]
    perform_targets: list[PerformTarget]
    cics_operations: list[CicsOperation]
    data_items: list[DataItem]
    file_controls: list[FileControl]
    data_flows: list[DataFlow]
    total_lines: int
    code_lines: int
    comment_lines: int


def _strip_fixed_format(raw_lines: list[str]) -> list[tuple[int, str]]:
    """Extract code from fixed-format COBOL lines.
    Returns (original_line_number, stripped_code) pairs.
    Handles continuation lines (col 7 = '-') by appending to previous."""
    result = []
    for i, raw in enumerate(raw_lines):
        line_num = i + 1
        if len(raw) < 7:
            result.append((line_num, ''))
            continue

        indicator = raw[6] if len(raw) > 6 else ' '

        if indicator in ('*', '/', 'D', 'd'):
            result.append((line_num, ''))
            continue

        code = raw[7:72] if len(raw) > 7 else ''

        if indicator == '-':
            # continuation: strip leading spaces and append to previous code line
            cont_text = code.lstrip()
            if cont_text.startswith("'"):
                cont_text = cont_text[1:]
            if result:
                prev_num, prev_code = result[-1]
                result[-1] = (prev_num, prev_code.rstrip() + cont_text)
            continue

        result.append((line_num, code))

    return result


def _join_statements(code_lines: list[tuple[int, str]]) -> list[tuple[int, int, str]]:
    """Join multi-line COBOL statements terminated by periods.
    Returns (start_line, end_line, statement_text) tuples."""
    statements = []
    current_stmt = []
    start_line = 0

    for line_num, code in code_lines:
        stripped = code.strip()
        if not stripped:
            continue

        if not current_stmt:
            start_line = line_num

        current_stmt.append(stripped)

        if stripped.endswith('.'):
            full = ' '.join(current_stmt)
            statements.append((start_line, line_num, full))
            current_stmt = []

    if current_stmt:
        full = ' '.join(current_stmt)
        statements.append((start_line, line_num, full))

    return statements


_RE_PROGRAM_ID = re.compile(r'PROGRAM-ID\.\s+(\S+?)[\s.]', re.IGNORECASE)
_RE_AUTHOR = re.compile(r'AUTHOR\.\s+(.+?)\.', re.IGNORECASE)
_RE_COPY = re.compile(r'COPY\s+(\S+)', re.IGNORECASE)
_RE_REPLACING_PAIR = re.compile(
    r'(?:==([^=]+)==|\'([^\']+)\')\s+BY\s+(?:==([^=]+)==|\'([^\']+)\'|(\S+))',
    re.IGNORECASE,
)


def _parse_replacing_pairs(text: str) -> list[tuple[str, str]]:
    """Parse all old/new pairs from a COPY REPLACING clause.

    Handles both ==pseudo-text== (IBM standard) and 'quoted' syntax,
    and correctly extracts multiple pairs from a single REPLACING clause.
    """
    replacing_start = re.search(r'\bREPLACING\b', text, re.IGNORECASE)
    if not replacing_start:
        return []
    pairs = []
    for m in _RE_REPLACING_PAIR.finditer(text, replacing_start.end()):
        old = (m.group(1) or m.group(2) or '').strip()
        new = (m.group(3) or m.group(4) or m.group(5) or '').strip().rstrip('.')
        if old and new:
            pairs.append((old, new))
    return pairs
_RE_CALL = re.compile(r"CALL\s+'([^']+)'", re.IGNORECASE)
_RE_PERFORM = re.compile(r'PERFORM\s+([A-Z0-9][\w-]*)', re.IGNORECASE)
_RE_PERFORM_THRU = re.compile(r'PERFORM\s+([A-Z0-9][\w-]*)\s+THRU\s+([A-Z0-9][\w-]*)', re.IGNORECASE)
_RE_PERFORM_LOOP = re.compile(r'PERFORM\s+(VARYING|UNTIL|TIMES)', re.IGNORECASE)
_RE_PERFORM_PARA_LOOP = re.compile(r'PERFORM\s+([A-Z0-9][\w-]*)\s+(?:THRU\s+\S+\s+)?(?:VARYING|UNTIL|TIMES)', re.IGNORECASE)
_RE_SELECT = re.compile(r'SELECT\s+(\S+)\s+ASSIGN\s+TO\s+(\S+)', re.IGNORECASE)
_RE_MOVE = re.compile(r'MOVE\s+(.+?)\s+TO\s+(.+?)(?:\.|$)', re.IGNORECASE)
_RE_COMPUTE = re.compile(r'COMPUTE\s+([A-Z0-9][\w-]*(?:\s*\([^)]*\))?)\s*=\s*(.+?)(?:\.|END-COMPUTE|$)', re.IGNORECASE)
_RE_ADD_TO = re.compile(r'ADD\s+(.+?)\s+TO\s+(.+?)(?:\s+GIVING\s+(.+?))?(?:\.|END-ADD|$)', re.IGNORECASE)
_RE_SUBTRACT = re.compile(r'SUBTRACT\s+(.+?)\s+FROM\s+(.+?)(?:\s+GIVING\s+(.+?))?(?:\.|END-SUBTRACT|$)', re.IGNORECASE)
_RE_CALL_USING = re.compile(r"CALL\s+'([^']+)'\s+USING\s+(.+?)(?:\.|END-CALL|$)", re.IGNORECASE)
_RE_READ_INTO = re.compile(r'READ\s+(\S+)\s+INTO\s+(\S+)', re.IGNORECASE)
_RE_ACCEPT = re.compile(r'ACCEPT\s+([A-Z0-9][\w-]*)', re.IGNORECASE)
_RE_DIVISION = re.compile(r'(IDENTIFICATION|ID|ENVIRONMENT|DATA|PROCEDURE)\s+DIVISION', re.IGNORECASE)
_RE_SECTION = re.compile(r'([A-Z0-9][\w-]*)\s+SECTION\s*\.', re.IGNORECASE)
_RE_DATA_ITEM = re.compile(r'(\d{2})\s+([A-Z0-9][\w-]*)\s+PIC\s+(\S+)', re.IGNORECASE)
_RE_LEVEL = re.compile(r'^(\d{2})\s+([A-Z0-9][\w-]*)', re.IGNORECASE)

_COBOL_RESERVED = {
    'PERFORM', 'MOVE', 'COMPUTE', 'IF', 'ELSE', 'END-IF', 'EVALUATE', 'WHEN',
    'ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE', 'DISPLAY', 'ACCEPT', 'CALL',
    'STOP', 'GOBACK', 'GO', 'EXIT', 'CONTINUE', 'INITIALIZE', 'STRING',
    'UNSTRING', 'INSPECT', 'SEARCH', 'READ', 'WRITE', 'REWRITE', 'DELETE',
    'OPEN', 'CLOSE', 'START', 'RETURN', 'SORT', 'MERGE', 'SET', 'EXEC',
    'END-EXEC', 'COPY', 'REPLACE', 'SECTION', 'DIVISION', 'WORKING-STORAGE',
    'LINKAGE', 'FILE', 'PROCEDURE', 'DATA', 'ENVIRONMENT', 'IDENTIFICATION',
    'ID', 'CONFIGURATION', 'INPUT-OUTPUT', 'FD', 'SD', 'SELECT', 'ASSIGN',
    'VARYING', 'UNTIL', 'TIMES', 'THRU', 'THROUGH', 'WITH', 'USING',
    'GIVING', 'INTO', 'FROM', 'TO', 'BY', 'ON', 'NOT', 'AND', 'OR',
    'TRUE', 'FALSE', 'OTHER', 'END-EVALUATE', 'END-PERFORM', 'END-CALL',
    'END-READ', 'END-WRITE', 'END-COMPUTE', 'END-STRING', 'END-SEARCH',
    'END-MULTIPLY', 'END-DIVIDE', 'END-ADD', 'END-SUBTRACT',
}


def _extract_field_names(text: str) -> list[str]:
    """Extract COBOL field names from a text fragment, filtering reserved words and literals."""
    tokens = re.findall(r'[A-Z0-9][\w-]*', text.upper())
    return [t for t in tokens if t not in _COBOL_RESERVED
            and not t.isdigit()
            and not t.startswith('END-')
            and len(t) > 1]


def _extract_data_flows(stmt: str, upper_stmt: str, start_line: int, end_line: int,
                        src_file: str, para_name: Optional[str]) -> list[DataFlow]:
    """Extract data flow statements (MOVE, COMPUTE, ADD, SUBTRACT, etc.)."""
    flows = []

    for m in _RE_MOVE.finditer(stmt):
        sources = _extract_field_names(m.group(1))
        targets = _extract_field_names(m.group(2))
        if sources and targets:
            flows.append(DataFlow(
                flow_type='MOVE', sources=sources, targets=targets,
                paragraph=para_name,
                span=SourceSpan(src_file, start_line, end_line),
            ))

    for m in _RE_COMPUTE.finditer(stmt):
        target_name = re.match(r'([A-Z0-9][\w-]*)', m.group(1).strip(), re.IGNORECASE)
        if target_name:
            targets = [target_name.group(1).upper()]
            sources = _extract_field_names(m.group(2))
            if targets and sources:
                flows.append(DataFlow(
                    flow_type='COMPUTE', sources=sources, targets=targets,
                    paragraph=para_name,
                    span=SourceSpan(src_file, start_line, end_line),
                ))

    for m in _RE_ADD_TO.finditer(stmt):
        sources = _extract_field_names(m.group(1))
        targets = _extract_field_names(m.group(3) or m.group(2))
        if sources and targets:
            flows.append(DataFlow(
                flow_type='ADD', sources=sources, targets=targets,
                paragraph=para_name,
                span=SourceSpan(src_file, start_line, end_line),
            ))

    for m in _RE_SUBTRACT.finditer(stmt):
        sources = _extract_field_names(m.group(1))
        targets = _extract_field_names(m.group(3) or m.group(2))
        if sources and targets:
            flows.append(DataFlow(
                flow_type='SUBTRACT', sources=sources, targets=targets,
                paragraph=para_name,
                span=SourceSpan(src_file, start_line, end_line),
            ))

    for m in _RE_READ_INTO.finditer(stmt):
        source = m.group(1).strip().rstrip('.').upper()
        target = m.group(2).strip().rstrip('.').upper()
        if source and target and source not in _COBOL_RESERVED and target not in _COBOL_RESERVED:
            flows.append(DataFlow(
                flow_type='READ_INTO', sources=[source], targets=[target],
                paragraph=para_name,
                span=SourceSpan(src_file, start_line, end_line),
            ))

    for m in _RE_ACCEPT.finditer(stmt):
        target = m.group(1).upper()
        if target not in _COBOL_RESERVED:
            flows.append(DataFlow(
                flow_type='ACCEPT', sources=['SYSTEM-INPUT'], targets=[target],
                paragraph=para_name,
                span=SourceSpan(src_file, start_line, end_line),
            ))

    return flows


def _extract_call_using_args(stmt: str) -> list[str]:
    """Extract USING arguments from a CALL statement."""
    m = _RE_CALL_USING.search(stmt)
    if not m:
        return []
    using_text = m.group(2)
    args = _extract_field_names(using_text)
    return args


def _is_paragraph_header(stmt: str) -> Optional[str]:
    """Check if a statement is a paragraph header (name followed by period)."""
    stripped = stmt.strip().rstrip('.')
    if not stripped:
        return None
    parts = stripped.split()
    if len(parts) == 1:
        name = parts[0].upper()
        if (re.match(r'^[A-Z0-9][\w-]*$', name)
                and name not in _COBOL_RESERVED
                and not name.endswith('DIVISION')
                and not name.endswith('SECTION')):
            return name
    return None


def _extract_cics(stmt: str, start_line: int, end_line: int, src_file: str) -> Optional[CicsOperation]:
    """Extract EXEC CICS operation details."""
    m = re.search(r'EXEC\s+CICS\s+(\w+)', stmt, re.IGNORECASE)
    if not m:
        return None

    op = m.group(1).upper()
    dataset = None
    map_name = None
    mapset = None
    program = None

    dm = re.search(r'DATASET\s*\(\s*([^)]+)\s*\)', stmt, re.IGNORECASE)
    if not dm:
        dm = re.search(r'FILE\s*\(\s*([^)]+)\s*\)', stmt, re.IGNORECASE)
    if dm:
        dataset = dm.group(1).strip().strip("'")

    mm = re.search(r"MAP\s*\(\s*'([^']+)'\s*\)", stmt, re.IGNORECASE)
    if mm:
        map_name = mm.group(1)

    ms = re.search(r"MAPSET\s*\(\s*'([^']+)'\s*\)", stmt, re.IGNORECASE)
    if ms:
        mapset = ms.group(1)

    pm = re.search(r'PROGRAM\s*\(\s*([^)]+)\s*\)', stmt, re.IGNORECASE)
    if pm:
        program = pm.group(1).strip().strip("'")

    return CicsOperation(
        operation=op,
        dataset=dataset,
        map_name=map_name,
        mapset=mapset,
        program=program,
        span=SourceSpan(src_file, start_line, end_line),
    )


# ---------------------------------------------------------------------------
# IQ-01: Conditional logic extraction — recursive descent parser
#
# Post-processes each paragraph's code lines to build a decision tree of
# IF/EVALUATE/PERFORM-inline/GO-TO blocks with structured predicates.
# Runs after the main parse loop; does not modify existing extraction logic.
# ---------------------------------------------------------------------------

_EXECUTABLE_VERBS = frozenset({
    'MOVE', 'SET', 'DISPLAY', 'CALL', 'ADD', 'SUBTRACT', 'COMPUTE',
    'EXEC', 'READ', 'WRITE', 'OPEN', 'CLOSE', 'ACCEPT', 'STOP',
    'GOBACK', 'EXIT', 'STRING', 'UNSTRING', 'INSPECT', 'SEARCH',
    'INITIALIZE', 'CONTINUE', 'DELETE', 'REWRITE', 'SORT', 'MERGE',
    'RETURN', 'START', 'MULTIPLY', 'DIVIDE',
    'IF', 'EVALUATE', 'PERFORM', 'GO',
})

_BLOCK_TERMINATORS = frozenset({
    'END-IF', 'END-EVALUATE', 'END-PERFORM', 'ELSE', 'WHEN',
})

_STMT_TYPE_MAP = {
    'MOVE': 'MOVE', 'SET': 'SET', 'DISPLAY': 'DISPLAY', 'CALL': 'CALL',
    'ADD': 'ADD', 'SUBTRACT': 'SUBTRACT', 'COMPUTE': 'COMPUTE',
    'ACCEPT': 'ACCEPT', 'EXEC': 'CICS', 'CONTINUE': 'CONTINUE',
    'INITIALIZE': 'INITIALIZE', 'STOP': 'STOP', 'GOBACK': 'GOBACK',
    'EXIT': 'EXIT', 'READ': 'READ', 'WRITE': 'WRITE', 'OPEN': 'OPEN',
    'CLOSE': 'CLOSE', 'DELETE': 'DELETE', 'REWRITE': 'REWRITE',
    'STRING': 'STRING', 'UNSTRING': 'UNSTRING', 'INSPECT': 'INSPECT',
    'SEARCH': 'SEARCH', 'SORT': 'SORT', 'MERGE': 'MERGE',
    'MULTIPLY': 'MULTIPLY', 'DIVIDE': 'DIVIDE', 'RETURN': 'RETURN',
    'START': 'START', 'PERFORM': 'PERFORM',
}


def _tokenize_cobol_line(text: str) -> list[str]:
    """Split a COBOL code line into word tokens, preserving string literals and parens."""
    tokens = []
    i = 0
    while i < len(text):
        c = text[i]
        if c in ' \t':
            i += 1
        elif c == "'":
            end = text.find("'", i + 1)
            if end == -1:
                end = len(text) - 1
            tokens.append(text[i:end + 1])
            i = end + 1
        elif c == '(':
            depth = 1
            end = i + 1
            while end < len(text) and depth > 0:
                if text[end] == '(':
                    depth += 1
                elif text[end] == ')':
                    depth -= 1
                end += 1
            tokens.append(text[i:end])
            i = end
        elif c == '.':
            i += 1
        elif c == ')':
            i += 1
        else:
            end = i
            while end < len(text) and text[end] not in " \t.'()":
                end += 1
            if end > i:
                tokens.append(text[i:end])
            i = end
    return tokens


def _build_token_stream(code_tuples, para_start, para_end):
    """Build (line_number, UPPER_word, original_word) token list for a paragraph."""
    stream = []
    for line_num, code in code_tuples:
        if line_num <= para_start:
            continue
        if line_num > para_end:
            break
        stripped = code.strip()
        if not stripped:
            continue
        for w in _tokenize_cobol_line(stripped):
            stream.append((line_num, w.upper(), w))
    return stream


def _peek_upper(stream, pos, offset=0):
    idx = pos + offset
    if 0 <= idx < len(stream):
        return stream[idx][1]
    return None


def _parse_predicate(cond_words: list[str]) -> Predicate:
    """Parse condition words into a structured Predicate (DD-02).

    Always populates raw_text as lossless fallback.
    Handles: simple comparisons, NOT prefix, AND/OR combinators, level-88 names.
    Falls back to operator='COMPLEX' for unrecognized patterns.
    """
    raw = ' '.join(cond_words)
    uppers = [w.upper() for w in cond_words]

    if not cond_words:
        return Predicate(left=None, operator='EMPTY', right=None, raw_text='')

    # NOT prefix
    if uppers[0] == 'NOT':
        child = _parse_predicate(cond_words[1:])
        return Predicate(
            left=None, operator='NOT', right=None,
            children=[child], raw_text=raw,
        )

    # Top-level OR then AND (right-to-left scan for lowest precedence first)
    for combinator in ('OR', 'AND'):
        paren_depth = 0
        for i in range(len(uppers) - 1, 0, -1):
            tok = uppers[i]
            if tok.startswith('('):
                paren_depth += 1
            elif tok.endswith(')'):
                paren_depth -= 1
            elif tok == combinator and paren_depth == 0:
                left_part = _parse_predicate(cond_words[:i])
                right_part = _parse_predicate(cond_words[i + 1:])
                return Predicate(
                    left=None, operator=combinator, right=None,
                    children=[left_part, right_part], raw_text=raw,
                )

    # Single word — level-88 condition name
    if len(uppers) == 1 and uppers[0] not in _COBOL_RESERVED:
        return Predicate(
            left=uppers[0], operator='88_CONDITION', right=None,
            raw_text=raw, is_88_condition=True,
        )

    # Binary comparison: scan for operator token
    for i, tok in enumerate(uppers):
        if i == 0:
            continue
        if tok in ('=', '>', '<', '>=', '<='):
            left = ' '.join(uppers[:i])
            right = ' '.join(uppers[i + 1:]) if i + 1 < len(uppers) else ''
            return Predicate(left=left, operator=tok, right=right, raw_text=raw)
        if tok == 'NOT' and i + 1 < len(uppers) and uppers[i + 1] in ('=', 'EQUAL', 'NUMERIC'):
            left = ' '.join(uppers[:i])
            op = 'NOT ' + uppers[i + 1]
            right = ' '.join(uppers[i + 2:]) if i + 2 < len(uppers) else ''
            return Predicate(left=left, operator=op, right=right or None, raw_text=raw)
        if tok in ('EQUAL', 'EQUALS'):
            left = ' '.join(uppers[:i])
            ni = i + 1
            if ni < len(uppers) and uppers[ni] == 'TO':
                ni += 1
            right = ' '.join(uppers[ni:])
            return Predicate(left=left, operator='=', right=right, raw_text=raw)
        if tok == 'NUMERIC' and i > 0:
            left = ' '.join(uppers[:i])
            if uppers[i - 1] == 'IS':
                left = ' '.join(uppers[:i - 1])
            return Predicate(left=left, operator='NUMERIC', right=None, raw_text=raw)
        if tok == 'SPACES' and i > 0 and uppers[i - 1] == '=':
            continue
        if tok == 'ZEROS' and i > 0 and uppers[i - 1] == '=':
            continue

    # Fallback
    return Predicate(
        left=uppers[0] if uppers else None,
        operator='COMPLEX',
        right=' '.join(uppers[1:]) if len(uppers) > 1 else None,
        raw_text=raw,
    )


def _is_inline_perform(stream, pos):
    """True if PERFORM at pos starts an inline block (UNTIL/VARYING without paragraph name first)."""
    next_tok = _peek_upper(stream, pos, 1)
    return next_tok in ('UNTIL', 'VARYING', 'WITH', 'TEST')


def _parse_body(stream, pos, src_file, stop_tokens):
    """Parse a sequence of statements until a stop token or end of stream.

    Recursively descends into IF, EVALUATE, inline PERFORM blocks.
    Returns (statements, gotos, new_pos).
    """
    statements = []
    gotos = []

    while pos < len(stream):
        upper = stream[pos][1]

        if upper in stop_tokens:
            break

        if upper == 'IF':
            blk, pos = _parse_if_block(stream, pos, src_file)
            statements.append(Statement('IF', blk, blk.span))

        elif upper == 'EVALUATE':
            blk, pos = _parse_evaluate_block(stream, pos, src_file)
            statements.append(Statement('EVALUATE', blk, blk.span))

        elif upper == 'PERFORM' and _is_inline_perform(stream, pos):
            blk, pos = _parse_inline_perform_block(stream, pos, src_file)
            statements.append(Statement('PERFORM_INLINE', blk, blk.span))

        elif upper == 'GO' and _peek_upper(stream, pos, 1) == 'TO':
            node, pos = _parse_goto_node(stream, pos, src_file)
            gotos.append(node)
            statements.append(Statement('GOTO', node, node.span))

        elif upper in _EXECUTABLE_VERBS:
            start_line = stream[pos][0]
            stmt_type = _STMT_TYPE_MAP.get(upper, 'OTHER')
            raw_words = [stream[pos][2]]
            pos += 1

            if upper == 'EXEC':
                while pos < len(stream):
                    raw_words.append(stream[pos][2])
                    if stream[pos][1] == 'END-EXEC':
                        pos += 1
                        break
                    pos += 1
            else:
                while pos < len(stream):
                    u2 = stream[pos][1]
                    if u2 in _EXECUTABLE_VERBS or u2 in _BLOCK_TERMINATORS or u2 in stop_tokens:
                        break
                    raw_words.append(stream[pos][2])
                    pos += 1

            end_line = stream[pos - 1][0] if pos > 0 else start_line
            statements.append(Statement(
                stmt_type, ' '.join(raw_words),
                SourceSpan(src_file, start_line, end_line),
            ))
        else:
            pos += 1

    return statements, gotos, pos


def _parse_if_block(stream, pos, src_file):
    """Parse IF ... [ELSE ...] END-IF from token stream."""
    start_line = stream[pos][0]
    pos += 1  # skip IF

    cond_words = []
    while pos < len(stream):
        upper = stream[pos][1]
        if upper == 'THEN':
            pos += 1
            break
        if upper in _EXECUTABLE_VERBS or upper in _BLOCK_TERMINATORS:
            break
        cond_words.append(stream[pos][2])
        pos += 1

    condition = _parse_predicate(cond_words)

    then_body, _, pos = _parse_body(stream, pos, src_file, {'ELSE', 'END-IF'})

    else_body = []
    if pos < len(stream) and stream[pos][1] == 'ELSE':
        pos += 1
        else_body, _, pos = _parse_body(stream, pos, src_file, {'END-IF'})

    end_line = start_line
    if pos < len(stream) and stream[pos][1] == 'END-IF':
        end_line = stream[pos][0]
        pos += 1
    elif pos > 0:
        end_line = stream[pos - 1][0]

    return IfBlock(
        condition=condition,
        then_body=then_body,
        else_body=else_body,
        span=SourceSpan(src_file, start_line, end_line),
    ), pos


def _parse_evaluate_block(stream, pos, src_file):
    """Parse EVALUATE ... END-EVALUATE from token stream (DD-03)."""
    start_line = stream[pos][0]
    pos += 1  # skip EVALUATE

    subjects = []
    current = []
    while pos < len(stream):
        upper = stream[pos][1]
        if upper == 'WHEN':
            break
        if upper == 'ALSO':
            if current:
                subjects.append(' '.join(current))
                current = []
            pos += 1
            continue
        current.append(upper)
        pos += 1
    if current:
        subjects.append(' '.join(current))

    branches = []
    while pos < len(stream) and stream[pos][1] == 'WHEN':
        branch, pos = _parse_when_branch(stream, pos, src_file, subjects)
        branches.append(branch)

    end_line = start_line
    if pos < len(stream) and stream[pos][1] == 'END-EVALUATE':
        end_line = stream[pos][0]
        pos += 1
    elif pos > 0:
        end_line = stream[pos - 1][0]

    return EvaluateBlock(
        subjects=subjects,
        branches=branches,
        span=SourceSpan(src_file, start_line, end_line),
    ), pos


def _parse_when_branch(stream, pos, src_file, subjects):
    """Parse WHEN clause(s) with body. Handles fall-through (consecutive WHENs)."""
    start_line = stream[pos][0]
    all_conditions = []
    first_cond_words = None

    while pos < len(stream) and stream[pos][1] == 'WHEN':
        pos += 1  # skip WHEN
        cond_words = []
        while pos < len(stream):
            upper = stream[pos][1]
            if upper in _EXECUTABLE_VERBS or upper == 'WHEN' or upper == 'END-EVALUATE':
                break
            cond_words.append(stream[pos][2])
            pos += 1

        cond_text = ' '.join(w.upper() for w in cond_words)
        all_conditions.append(cond_text)
        if first_cond_words is None:
            first_cond_words = cond_words

        if pos < len(stream) and stream[pos][1] == 'WHEN':
            continue
        break

    cond_pred = None
    if subjects == ['TRUE'] and all_conditions and all_conditions[0] != 'OTHER':
        cond_pred = _parse_predicate(first_cond_words or [])

    body, _, pos = _parse_body(stream, pos, src_file, {'WHEN', 'END-EVALUATE'})

    end_line = stream[pos - 1][0] if pos > 0 else start_line
    return WhenBranch(
        conditions=all_conditions,
        condition_predicate=cond_pred,
        body=body,
        span=SourceSpan(src_file, start_line, end_line),
    ), pos


def _parse_inline_perform_block(stream, pos, src_file):
    """Parse inline PERFORM [VARYING|UNTIL] ... END-PERFORM (DD-05)."""
    start_line = stream[pos][0]
    pos += 1  # skip PERFORM

    varying = None
    until = None
    upper = _peek_upper(stream, pos)

    if upper == 'VARYING':
        pos += 1
        counter = stream[pos][2] if pos < len(stream) else ''
        pos += 1
        from_val = '1'
        by_val = '1'
        until_words = []
        while pos < len(stream):
            u = stream[pos][1]
            if u == 'FROM':
                pos += 1
                if pos < len(stream):
                    from_val = stream[pos][2]
                    pos += 1
            elif u == 'BY':
                pos += 1
                if pos < len(stream):
                    by_val = stream[pos][2]
                    pos += 1
            elif u == 'UNTIL':
                pos += 1
                while pos < len(stream):
                    u2 = stream[pos][1]
                    if u2 in _EXECUTABLE_VERBS or u2 in _BLOCK_TERMINATORS:
                        break
                    until_words.append(stream[pos][2])
                    pos += 1
                break
            else:
                break
        varying = {'counter': counter, 'from_val': from_val, 'by_val': by_val}
        if until_words:
            until = _parse_predicate(until_words)

    elif upper == 'UNTIL':
        pos += 1
        until_words = []
        while pos < len(stream):
            u = stream[pos][1]
            if u in _EXECUTABLE_VERBS or u in _BLOCK_TERMINATORS:
                break
            until_words.append(stream[pos][2])
            pos += 1
        if until_words:
            until = _parse_predicate(until_words)

    body, _, pos = _parse_body(stream, pos, src_file, {'END-PERFORM'})

    end_line = start_line
    if pos < len(stream) and stream[pos][1] == 'END-PERFORM':
        end_line = stream[pos][0]
        pos += 1
    elif pos > 0:
        end_line = stream[pos - 1][0]

    return PerformInline(
        varying=varying,
        until=until,
        body=body,
        span=SourceSpan(src_file, start_line, end_line),
    ), pos


def _parse_goto_node(stream, pos, src_file):
    """Parse GO TO target(s) [DEPENDING ON field] (DD-04)."""
    start_line = stream[pos][0]
    pos += 2  # skip GO TO

    targets = []
    depending_on = None
    while pos < len(stream):
        upper = stream[pos][1]
        if upper == 'DEPENDING':
            pos += 1
            if pos < len(stream) and stream[pos][1] == 'ON':
                pos += 1
            if pos < len(stream):
                depending_on = stream[pos][1]
                pos += 1
            break
        if upper in _EXECUTABLE_VERBS or upper in _BLOCK_TERMINATORS:
            break
        targets.append(upper)
        pos += 1

    end_line = stream[pos - 1][0] if pos > 0 else start_line
    return GoTo(
        targets=targets,
        depending_on=depending_on,
        span=SourceSpan(src_file, start_line, end_line),
    ), pos


_CONDITIONAL_TYPES = frozenset({'IF', 'EVALUATE', 'PERFORM_INLINE', 'GOTO'})


def _extract_paragraph_conditionals(code_tuples, paragraph, src_file):
    """Enrich a Paragraph with conditional_blocks and goto_targets.

    Post-processing step: builds token stream from raw code lines,
    runs recursive descent parser, keeps only block-level statements
    at the paragraph top level.
    """
    stream = _build_token_stream(
        code_tuples, paragraph.span.start_line, paragraph.span.end_line
    )
    if not stream:
        return

    all_stmts, gotos, _ = _parse_body(stream, 0, src_file, stop_tokens=set())

    paragraph.conditional_blocks = [s for s in all_stmts if s.stmt_type in _CONDITIONAL_TYPES]
    paragraph.goto_targets = gotos


def parse_cobol_file(filepath: Path) -> CobolProgram:
    """Parse a single COBOL source file and extract structural information."""
    raw_text = filepath.read_text(encoding='utf-8', errors='replace')
    raw_lines = raw_text.splitlines()
    total_lines = len(raw_lines)

    comment_lines = 0
    for line in raw_lines:
        if len(line) > 6 and line[6] in ('*', '/'):
            comment_lines += 1

    code_tuples = _strip_fixed_format(raw_lines)
    code_lines_count = sum(1 for _, c in code_tuples if c.strip())

    statements = _join_statements(code_tuples)

    src_file = str(filepath)
    program_id = filepath.stem
    author = None
    divisions = {}
    current_division = None
    paragraphs: list[Paragraph] = []
    copy_stmts: list[CopyStatement] = []
    all_calls: list[CallTarget] = []
    all_performs: list[PerformTarget] = []
    all_cics: list[CicsOperation] = []
    data_items: list[DataItem] = []
    file_controls: list[FileControl] = []
    all_data_flows: list[DataFlow] = []

    current_para_name = None
    current_para_start = 0
    current_para_performs: list[PerformTarget] = []
    current_para_calls: list[CallTarget] = []
    current_para_cics: list[CicsOperation] = []
    current_para_flows: list[DataFlow] = []
    in_procedure = False

    def _close_paragraph():
        nonlocal current_para_name
        if current_para_name and in_procedure:
            paragraphs.append(Paragraph(
                name=current_para_name,
                performs=list(current_para_performs),
                calls=list(current_para_calls),
                cics_ops=list(current_para_cics),
                data_flows=list(current_para_flows),
                span=SourceSpan(src_file, current_para_start, prev_end),
            ))
            current_para_performs.clear()
            current_para_calls.clear()
            current_para_cics.clear()
            current_para_flows.clear()
            current_para_name = None

    prev_end = 0

    for start_line, end_line, stmt in statements:
        prev_end = end_line
        upper_stmt = stmt.upper()

        # Division detection
        div_m = _RE_DIVISION.search(upper_stmt)
        if div_m:
            div_name = div_m.group(1).upper()
            if div_name == 'ID':
                div_name = 'IDENTIFICATION'
            divisions[div_name] = start_line
            current_division = div_name
            if div_name == 'PROCEDURE':
                in_procedure = True
            continue

        # Program ID
        pid_m = _RE_PROGRAM_ID.search(stmt)
        if pid_m:
            program_id = pid_m.group(1).rstrip('.')
            continue

        # Author
        auth_m = _RE_AUTHOR.search(stmt)
        if auth_m:
            author = auth_m.group(1).strip()
            continue

        # COPY statements — finditer for multiple in one statement
        copy_matches = list(_RE_COPY.finditer(stmt))
        if copy_matches:
            for copy_m in copy_matches:
                cb_name = copy_m.group(1).rstrip('.').strip("'")
                if cb_name.upper() in _COBOL_RESERVED:
                    continue
                rest = stmt[copy_m.end():]
                replacings = _parse_replacing_pairs(rest)
                copy_stmts.append(CopyStatement(
                    copybook_name=cb_name,
                    replacing=replacings,
                    span=SourceSpan(src_file, start_line, end_line),
                ))

        # SELECT ... ASSIGN TO
        sel_m = _RE_SELECT.search(stmt)
        if sel_m:
            org = None
            acc = None
            om = re.search(r'ORGANIZATION\s+IS\s+(\w+)', stmt, re.IGNORECASE)
            if om:
                org = om.group(1)
            am = re.search(r'ACCESS\s+MODE\s+IS\s+(\w+)', stmt, re.IGNORECASE)
            if am:
                acc = am.group(1)
            file_controls.append(FileControl(
                select_name=sel_m.group(1).rstrip('.'),
                assign_to=sel_m.group(2).rstrip('.'),
                organization=org,
                access_mode=acc,
                span=SourceSpan(src_file, start_line, end_line),
            ))

        # Data items (basic extraction)
        if current_division == 'DATA':
            level_m = _RE_LEVEL.match(stmt.strip())
            if level_m:
                level = int(level_m.group(1))
                name = level_m.group(2)
                pic_m = re.search(r'PIC\s+(\S+)', stmt, re.IGNORECASE)
                picture = pic_m.group(1).rstrip('.') if pic_m else None
                usage_m = re.search(r'USAGE\s+(\w+)', stmt, re.IGNORECASE)
                if not usage_m:
                    usage_m = re.search(r'\b(COMP|COMP-3|COMP-1|COMP-2|BINARY|PACKED-DECIMAL|DISPLAY)\b', upper_stmt)
                usage = usage_m.group(1) if usage_m else None
                occ_m = re.search(r'OCCURS\s+(\d+)', stmt, re.IGNORECASE)
                occurs = int(occ_m.group(1)) if occ_m else None
                redef_m = re.search(r'REDEFINES\s+(\S+)', stmt, re.IGNORECASE)
                redefines = redef_m.group(1).rstrip('.') if redef_m else None

                data_items.append(DataItem(
                    level=level, name=name, picture=picture,
                    usage=usage, occurs=occurs, redefines=redefines,
                    span=SourceSpan(src_file, start_line, end_line),
                ))

        # Procedure division analysis
        if in_procedure:
            # Paragraph headers
            para_name = _is_paragraph_header(stmt)
            if para_name:
                _close_paragraph()
                current_para_name = para_name
                current_para_start = start_line
                continue

            # Data flow extraction (MOVE, COMPUTE, ADD, etc.)
            para_flows = _extract_data_flows(
                stmt, upper_stmt, start_line, end_line, src_file, current_para_name
            )
            all_data_flows.extend(para_flows)
            current_para_flows.extend(para_flows)

            # CALL statements — finditer to catch multiple CALLs in one statement
            using_args = _extract_call_using_args(stmt)
            for call_m in _RE_CALL.finditer(stmt):
                ct = CallTarget(
                    target_program=call_m.group(1),
                    using_args=using_args,
                    call_type='CALL',
                    span=SourceSpan(src_file, start_line, end_line),
                )
                all_calls.append(ct)
                current_para_calls.append(ct)

            # EXEC CICS — finditer for multiple EXEC CICS in one statement
            for cics_m in re.finditer(r'EXEC\s+CICS\s+\w+', upper_stmt):
                cics_start = cics_m.start()
                cics_end_m = re.search(r'END-EXEC', upper_stmt[cics_start:])
                if cics_end_m:
                    cics_text = stmt[cics_start:cics_start + cics_end_m.end()]
                else:
                    cics_text = stmt[cics_start:]
                cics = _extract_cics(cics_text, start_line, end_line, src_file)
                if cics:
                    all_cics.append(cics)
                    current_para_cics.append(cics)
                    if cics.operation in ('XCTL', 'LINK') and cics.program:
                        ct = CallTarget(
                            target_program=cics.program,
                            using_args=[],
                            call_type=cics.operation,
                            span=SourceSpan(src_file, start_line, end_line),
                        )
                        all_calls.append(ct)
                        current_para_calls.append(ct)

            # PERFORM statements — finditer for multiple PERFORMs in one statement
            perform_seen = set()
            for perf_m in re.finditer(r'PERFORM\s+([A-Z0-9][\w-]*)', upper_stmt):
                target = perf_m.group(1)
                if target in _COBOL_RESERVED:
                    continue
                pos = perf_m.start()
                after = upper_stmt[perf_m.end():perf_m.end() + 80]

                thru = None
                is_loop = False
                thru_match = re.match(r'\s+THRU\s+([A-Z0-9][\w-]*)', after)
                if thru_match:
                    thru = thru_match.group(1)
                    after_thru = after[thru_match.end():]
                    is_loop = bool(re.match(r'\s+(VARYING|UNTIL|TIMES)', after_thru))
                else:
                    is_loop = bool(re.match(r'\s+(VARYING|UNTIL|TIMES)', after))

                key = (target, thru)
                if key not in perform_seen:
                    perform_seen.add(key)
                    pt = PerformTarget(
                        target_paragraph=target,
                        thru_paragraph=thru,
                        is_loop=is_loop,
                        span=SourceSpan(src_file, start_line, end_line),
                    )
                    all_performs.append(pt)
                    current_para_performs.append(pt)

    _close_paragraph()

    # IQ-01: post-process paragraphs to extract conditional block trees
    for para in paragraphs:
        _extract_paragraph_conditionals(code_tuples, para, src_file)

    def _make_span(div_name):
        if div_name in divisions:
            return SourceSpan(src_file, divisions[div_name], divisions[div_name])
        return None

    return CobolProgram(
        program_id=program_id,
        source_file=src_file,
        identification_division=_make_span('IDENTIFICATION'),
        environment_division=_make_span('ENVIRONMENT'),
        data_division=_make_span('DATA'),
        procedure_division=_make_span('PROCEDURE'),
        author=author,
        paragraphs=paragraphs,
        copy_statements=copy_stmts,
        call_targets=all_calls,
        perform_targets=all_performs,
        cics_operations=all_cics,
        data_items=data_items,
        file_controls=file_controls,
        data_flows=all_data_flows,
        total_lines=total_lines,
        code_lines=code_lines_count,
        comment_lines=comment_lines,
    )

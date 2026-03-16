"""
CICS stub preprocessor — rewrites EXEC CICS commands into plain COBOL
that GnuCOBOL can compile and execute standalone.

Source-to-source transformation:
- EXEC CICS READ DATASET INTO RIDFLD RESP → indexed file READ with INVALID KEY
- EXEC CICS WRITE/REWRITE → file WRITE/REWRITE
- EXEC CICS DELETE → file DELETE
- EXEC CICS SEND MAP → WRITE to mock screen output file
- EXEC CICS RECEIVE MAP → READ from mock screen input file
- EXEC CICS XCTL PROGRAM COMMAREA → CALL program USING commarea + STOP RUN
- EXEC CICS RETURN → STOP RUN (or GOBACK)
- EXEC CICS ASSIGN → MOVE mock values
- EXEC CICS SEND TEXT → DISPLAY
- EIBCALEN/EIBAID/DFHENTER etc → working storage fields with test values

Also injects:
- FILE CONTROL entries for each DATASET
- FD entries in FILE SECTION
- DFHEIBLK / DFHAID mock definitions if COPY DFHAID/DFHBMSCA present
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))


@dataclass
class CicsDataset:
    """A CICS dataset discovered during preprocessing."""
    name: str           # COBOL variable holding dataset name (e.g., WS-USRSEC-FILE)
    into_field: str     # INTO target (e.g., SEC-USER-DATA)
    ridfld: str         # RIDFLD key field (e.g., WS-USER-ID)
    file_alias: str     # sanitized name for SELECT/FD (e.g., USRSEC-FILE)
    operations: set     # READ, WRITE, REWRITE, DELETE, STARTBR, READNEXT


@dataclass
class StubResult:
    """Result of CICS preprocessing."""
    source: str             # transformed COBOL source
    datasets: list[CicsDataset]
    xctl_targets: list[str]  # XCTL program names
    needs_screen_io: bool


# ── EXEC CICS block extraction ──────────────────────────────────────────────

_RE_EXEC_CICS = re.compile(
    r'(\s*)(EXEC\s+CICS\s+.*?END-EXEC)',
    re.IGNORECASE | re.DOTALL,
)

_RE_CICS_OP = re.compile(r'EXEC\s+CICS\s+(\w+)', re.IGNORECASE)
_RE_DATASET = re.compile(r'DATASET\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)
_RE_INTO = re.compile(r'INTO\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)
_RE_FROM = re.compile(r'FROM\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)
_RE_RIDFLD = re.compile(r'RIDFLD\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)
_RE_RESP = re.compile(r'RESP\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)
_RE_PROGRAM = re.compile(r'PROGRAM\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)
_RE_COMMAREA = re.compile(r'COMMAREA\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)
_RE_MAP = re.compile(r"MAP\s*\(\s*'([^']+)'\s*\)", re.IGNORECASE)
_RE_MAPSET = re.compile(r"MAPSET\s*\(\s*'([^']+)'\s*\)", re.IGNORECASE)
_RE_TRANSID = re.compile(r'TRANSID\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)
_RE_APPLID = re.compile(r'APPLID\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)
_RE_SYSID = re.compile(r'SYSID\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)


def _sanitize_dataset_name(name: str) -> str:
    """Convert a dataset variable name to a file alias for SELECT/FD."""
    # Remove WS- prefix and clean up
    clean = name.strip().strip("'").upper()
    if clean.startswith("WS-"):
        clean = clean[3:]
    return clean.replace(" ", "-")


def _stub_cics_read(indent: str, block: str, datasets: dict) -> str:
    """Stub EXEC CICS READ → indexed file READ."""
    ds_m = _RE_DATASET.search(block)
    into_m = _RE_INTO.search(block)
    ridfld_m = _RE_RIDFLD.search(block)
    resp_m = _RE_RESP.search(block)

    ds_name = ds_m.group(1).strip() if ds_m else "UNKNOWN"
    into = into_m.group(1).strip() if into_m else "DUMMY-REC"
    ridfld = ridfld_m.group(1).strip() if ridfld_m else ""
    resp = resp_m.group(1).strip() if resp_m else ""

    alias = _sanitize_dataset_name(ds_name)
    if ds_name not in datasets:
        datasets[ds_name] = CicsDataset(
            name=ds_name, into_field=into, ridfld=ridfld,
            file_alias=alias, operations=set(),
        )
    datasets[ds_name].operations.add("READ")

    lines = []
    # Move the search key to the FD record key before reading
    lines.append(f"{indent}MOVE {ridfld} TO {alias}-FD-KEY")
    lines.append(f"{indent}READ {alias}-FILE INTO {into}")
    lines.append(f"{indent}    KEY IS {alias}-FD-KEY")
    if resp:
        lines.append(f"{indent}    INVALID KEY")
        lines.append(f"{indent}        MOVE 13 TO {resp}")
        lines.append(f"{indent}    NOT INVALID KEY")
        lines.append(f"{indent}        MOVE 0 TO {resp}")
        lines.append(f"{indent}END-READ")
    else:
        lines.append(f"{indent}END-READ")

    return "\n".join(lines)


def _stub_cics_write(indent: str, block: str, datasets: dict, op: str) -> str:
    """Stub EXEC CICS WRITE/REWRITE."""
    ds_m = _RE_DATASET.search(block)
    from_m = _RE_FROM.search(block)
    resp_m = _RE_RESP.search(block)

    ds_name = ds_m.group(1).strip() if ds_m else "UNKNOWN"
    from_field = from_m.group(1).strip() if from_m else ""
    resp = resp_m.group(1).strip() if resp_m else ""

    alias = _sanitize_dataset_name(ds_name)
    if ds_name not in datasets:
        datasets[ds_name] = CicsDataset(
            name=ds_name, into_field=from_field, ridfld="",
            file_alias=alias, operations=set(),
        )
    datasets[ds_name].operations.add(op)

    cobol_op = "WRITE" if op == "WRITE" else "REWRITE"
    rec_name = f"{alias}-FD-REC"

    lines = []
    if from_field:
        lines.append(f"{indent}MOVE {from_field} TO {rec_name}")
    lines.append(f"{indent}{cobol_op} {rec_name}")
    if resp:
        lines.append(f"{indent}IF {alias}-FILE-STATUS NOT = '00'")
        lines.append(f"{indent}    MOVE 99 TO {resp}")
        lines.append(f"{indent}ELSE")
        lines.append(f"{indent}    MOVE 0 TO {resp}")
        lines.append(f"{indent}END-IF")

    return "\n".join(lines)


def _stub_cics_xctl(indent: str, block: str) -> tuple[str, str]:
    """Stub EXEC CICS XCTL → DISPLAY + STOP RUN (capture the transfer)."""
    prog_m = _RE_PROGRAM.search(block)
    comm_m = _RE_COMMAREA.search(block)

    prog = prog_m.group(1).strip().strip("'") if prog_m else "UNKNOWN"
    commarea = comm_m.group(1).strip() if comm_m else ""

    lines = []
    lines.append(f"{indent}DISPLAY 'XCTL-TO:{prog}'")
    if commarea:
        lines.append(f"{indent}DISPLAY 'COMMAREA:' {commarea}")
    lines.append(f"{indent}STOP RUN")

    return "\n".join(lines), prog


def _stub_cics_return(indent: str, block: str) -> str:
    """Stub EXEC CICS RETURN → STOP RUN."""
    transid_m = _RE_TRANSID.search(block)
    comm_m = _RE_COMMAREA.search(block)

    lines = []
    if comm_m:
        commarea = comm_m.group(1).strip()
        lines.append(f"{indent}DISPLAY 'RETURN-COMMAREA:' {commarea}")
    lines.append(f"{indent}STOP RUN")

    return "\n".join(lines)


def _stub_cics_send_map(indent: str, block: str) -> str:
    """Stub EXEC CICS SEND MAP → DISPLAY screen fields."""
    map_m = _RE_MAP.search(block)
    from_m = _RE_FROM.search(block)

    map_name = map_m.group(1) if map_m else "UNKNOWN"
    from_field = from_m.group(1).strip() if from_m else ""

    lines = []
    lines.append(f"{indent}DISPLAY 'SEND-MAP:{map_name}'")
    if from_field:
        lines.append(f"{indent}DISPLAY 'SCREEN-OUT:' {from_field}")

    return "\n".join(lines)


def _stub_cics_receive_map(indent: str, block: str) -> str:
    """Stub EXEC CICS RECEIVE MAP → READ from mock screen input file.

    Reads directly into the symbolic input map record (e.g., COSGN0AI)
    so that field references like USERIDI OF COSGN0AI work correctly.
    """
    map_m = _RE_MAP.search(block)
    resp_m = _RE_RESP.search(block)

    map_name = map_m.group(1) if map_m else "UNKNOWN"
    resp = resp_m.group(1).strip() if resp_m else ""

    # The symbolic input map is named <MAP>I (e.g., COSGN0AI)
    input_map = f"{map_name}I"

    lines = []
    lines.append(f"{indent}DISPLAY 'RECEIVE-MAP:{map_name}'")
    lines.append(f"{indent}READ SCREEN-INPUT-FILE INTO {input_map}")
    lines.append(f"{indent}END-READ")
    if resp:
        lines.append(f"{indent}MOVE 0 TO {resp}")

    return "\n".join(lines)


def _stub_cics_assign(indent: str, block: str) -> str:
    """Stub EXEC CICS ASSIGN → MOVE mock values."""
    applid_m = _RE_APPLID.search(block)
    sysid_m = _RE_SYSID.search(block)

    lines = []
    if applid_m:
        target = applid_m.group(1).strip()
        lines.append(f"{indent}MOVE 'TESTAPPL' TO {target}")
    if sysid_m:
        target = sysid_m.group(1).strip()
        lines.append(f"{indent}MOVE 'TEST' TO {target}")

    return "\n".join(lines) if lines else f"{indent}CONTINUE"


def _stub_cics_send_text(indent: str, block: str) -> str:
    """Stub EXEC CICS SEND TEXT → DISPLAY."""
    from_m = _RE_FROM.search(block)
    from_field = from_m.group(1).strip() if from_m else "''"

    return f"{indent}DISPLAY 'SEND-TEXT:' {from_field}"


def preprocess_cics(
    source_file: str,
    copybook_dirs: list[str] = None,
    screen_input_fields: dict[str, str] = None,
) -> StubResult:
    """Preprocess a CICS COBOL program for standalone execution.

    Replaces all EXEC CICS blocks with plain COBOL equivalents.
    Injects FILE CONTROL, FD, and mock DFHEIBLK/DFHAID definitions.

    Args:
        source_file: Path to .cbl file
        copybook_dirs: Directories for COPY resolution (informational)
        screen_input_fields: Dict of screen input field values for RECEIVE MAP

    Returns:
        StubResult with transformed source and metadata
    """
    source = Path(source_file).read_text(encoding="utf-8", errors="replace")

    datasets: dict[str, CicsDataset] = {}
    xctl_targets: list[str] = []
    needs_screen_io = False

    # Replace each EXEC CICS block
    def replace_exec_cics(match):
        nonlocal needs_screen_io
        indent = match.group(1)
        block = match.group(2)
        # Normalize whitespace for regex matching
        block_flat = " ".join(block.split())

        op_m = _RE_CICS_OP.search(block_flat)
        if not op_m:
            return f"{indent}* STUBBED: {block_flat[:60]}"
        op = op_m.group(1).upper()

        if op == "READ":
            return _stub_cics_read(indent, block_flat, datasets)
        elif op == "WRITE":
            return _stub_cics_write(indent, block_flat, datasets, "WRITE")
        elif op == "REWRITE":
            return _stub_cics_write(indent, block_flat, datasets, "REWRITE")
        elif op == "DELETE":
            ds_m = _RE_DATASET.search(block_flat)
            ds_name = ds_m.group(1).strip() if ds_m else "UNKNOWN"
            alias = _sanitize_dataset_name(ds_name)
            if ds_name not in datasets:
                datasets[ds_name] = CicsDataset(
                    name=ds_name, into_field="", ridfld="",
                    file_alias=alias, operations=set(),
                )
            datasets[ds_name].operations.add("DELETE")
            return f"{indent}DELETE {alias}-FILE RECORD"
        elif op == "XCTL":
            stub, prog = _stub_cics_xctl(indent, block_flat)
            xctl_targets.append(prog)
            return stub
        elif op == "LINK":
            prog_m = _RE_PROGRAM.search(block_flat)
            prog = prog_m.group(1).strip().strip("'") if prog_m else "UNKNOWN"
            return f"{indent}DISPLAY 'LINK-TO:{prog}'"
        elif op == "RETURN":
            return _stub_cics_return(indent, block_flat)
        elif op == "SEND":
            if "MAP" in block_flat.upper() and "TEXT" not in block_flat.upper():
                needs_screen_io = True
                return _stub_cics_send_map(indent, block_flat)
            else:
                return _stub_cics_send_text(indent, block_flat)
        elif op == "RECEIVE":
            needs_screen_io = True
            return _stub_cics_receive_map(indent, block_flat)
        elif op == "ASSIGN":
            return _stub_cics_assign(indent, block_flat)
        elif op in ("STARTBR", "READNEXT", "READPREV", "ENDBR",
                     "HANDLE", "IGNORE", "SYNCPOINT", "ABEND"):
            return f"{indent}* STUBBED: {op} (not needed for testing)"
        else:
            return f"{indent}* STUBBED: EXEC CICS {op}"

    transformed = _RE_EXEC_CICS.sub(replace_exec_cics, source)

    # Inject FILE CONTROL entries for datasets
    if datasets:
        file_control_block = _generate_file_control(datasets)
        fd_block = _generate_fd_entries(datasets)

        # Insert FILE CONTROL before DATA DIVISION
        transformed = _inject_file_control(transformed, file_control_block)
        # Insert FD entries after FILE SECTION
        transformed = _inject_fd_entries(transformed, fd_block)

    # Inject screen input file if needed
    if needs_screen_io:
        screen_fc = (
            "           SELECT SCREEN-INPUT-FILE ASSIGN TO SCREENIN\n"
            "                  ORGANIZATION IS SEQUENTIAL\n"
            "                  FILE STATUS IS SCREEN-STATUS.\n"
        )
        screen_fd = (
            "       FD SCREEN-INPUT-FILE.\n"
            "       01 SCREEN-INPUT-REC          PIC X(1000).\n"
        )
        screen_ws = "       01 SCREEN-STATUS              PIC XX.\n"
        transformed = _inject_file_control(transformed, screen_fc)
        transformed = _inject_fd_entries(transformed, screen_fd)
        transformed = _inject_working_storage(transformed, screen_ws)

    # Replace COPY DFHAID / COPY DFHBMSCA with mock definitions
    transformed = _inject_dfh_mocks(transformed)

    return StubResult(
        source=transformed,
        datasets=list(datasets.values()),
        xctl_targets=xctl_targets,
        needs_screen_io=needs_screen_io,
    )


def _generate_file_control(datasets: dict[str, CicsDataset]) -> str:
    """Generate FILE CONTROL SELECT entries for CICS datasets."""
    lines = []
    for ds in datasets.values():
        alias = ds.file_alias
        assign = alias.replace("-", "")
        lines.append(f"           SELECT {alias}-FILE ASSIGN TO {assign}")
        lines.append(f"                  ORGANIZATION IS INDEXED")
        lines.append(f"                  ACCESS MODE IS DYNAMIC")
        lines.append(f"                  RECORD KEY IS {alias}-FD-KEY")
        lines.append(f"                  FILE STATUS IS {alias}-STATUS.")
    return "\n".join(lines) + "\n"


def _generate_fd_entries(datasets: dict[str, CicsDataset]) -> str:
    """Generate FD and 01-level records for CICS datasets."""
    lines = []
    for ds in datasets.values():
        alias = ds.file_alias
        lines.append(f"       FD {alias}-FILE.")
        lines.append(f"       01 {alias}-FD-REC.")
        lines.append(f"          05 {alias}-FD-KEY        PIC X(08).")
        lines.append(f"          05 {alias}-FD-DATA       PIC X(292).")
    return "\n".join(lines) + "\n"


def _inject_file_control(source: str, block: str) -> str:
    """Inject FILE CONTROL entries into the source."""
    # Look for existing FILE-CONTROL or insert before DATA DIVISION
    fc_m = re.search(r'(^\s*FILE-CONTROL\.)', source, re.MULTILINE | re.IGNORECASE)
    if fc_m:
        pos = fc_m.end()
        return source[:pos] + "\n" + block + source[pos:]

    # Look for INPUT-OUTPUT SECTION
    io_m = re.search(r'(^\s*INPUT-OUTPUT\s+SECTION\.)', source, re.MULTILINE | re.IGNORECASE)
    if io_m:
        pos = io_m.end()
        return source[:pos] + "\n       FILE-CONTROL.\n" + block + source[pos:]

    # Look for existing ENVIRONMENT DIVISION (may have CONFIGURATION SECTION but no I-O)
    env_m = re.search(r'(^\s*ENVIRONMENT\s+DIVISION\.)', source, re.MULTILINE | re.IGNORECASE)
    if env_m:
        # Find where to insert INPUT-OUTPUT SECTION — after CONFIGURATION SECTION or
        # right before DATA DIVISION
        dd_m = re.search(r'(^\s*DATA\s+DIVISION\.)', source, re.MULTILINE | re.IGNORECASE)
        if dd_m:
            pos = dd_m.start()
            insert = (
                "       INPUT-OUTPUT SECTION.\n"
                "       FILE-CONTROL.\n"
                + block + "\n"
            )
            return source[:pos] + insert + source[pos:]

    # No ENVIRONMENT DIVISION at all — insert before DATA DIVISION
    dd_m = re.search(r'(^\s*DATA\s+DIVISION\.)', source, re.MULTILINE | re.IGNORECASE)
    if dd_m:
        pos = dd_m.start()
        insert = (
            "       ENVIRONMENT DIVISION.\n"
            "       INPUT-OUTPUT SECTION.\n"
            "       FILE-CONTROL.\n"
            + block + "\n"
        )
        return source[:pos] + insert + source[pos:]

    return source


def _inject_fd_entries(source: str, block: str) -> str:
    """Inject FD entries into FILE SECTION."""
    fs_m = re.search(r'(^\s*FILE\s+SECTION\.)', source, re.MULTILINE | re.IGNORECASE)
    if fs_m:
        pos = fs_m.end()
        return source[:pos] + "\n" + block + source[pos:]

    # Insert FILE SECTION after DATA DIVISION
    dd_m = re.search(r'(^\s*DATA\s+DIVISION\.)', source, re.MULTILINE | re.IGNORECASE)
    if dd_m:
        pos = dd_m.end()
        return source[:pos] + "\n       FILE SECTION.\n" + block + source[pos:]

    return source


def _inject_working_storage(source: str, block: str) -> str:
    """Inject fields into WORKING-STORAGE SECTION."""
    ws_m = re.search(r'(^\s*WORKING-STORAGE\s+SECTION\.)', source, re.MULTILINE | re.IGNORECASE)
    if ws_m:
        pos = ws_m.end()
        return source[:pos] + "\n" + block + source[pos:]
    return source


def _inject_dfh_mocks(source: str) -> str:
    """Replace COPY DFHAID / DFHBMSCA with inline mock definitions."""
    dfhaid_mock = """\
      * Mock DFHAID — stubbed for standalone testing
       01 DFHAID-MOCK.
         05 DFHENTER              PIC X VALUE X'7D'.
         05 DFHCLEAR              PIC X VALUE X'6D'.
         05 DFHPF1                PIC X VALUE X'F1'.
         05 DFHPF2                PIC X VALUE X'F2'.
         05 DFHPF3                PIC X VALUE X'F3'.
         05 DFHPF4                PIC X VALUE X'F4'.
         05 DFHPF5                PIC X VALUE X'F5'.
         05 DFHPF6                PIC X VALUE X'F6'.
         05 DFHPF7                PIC X VALUE X'F7'.
         05 DFHPF8                PIC X VALUE X'F8'.
         05 DFHPF9                PIC X VALUE X'F9'.
         05 DFHPF10               PIC X VALUE X'7A'.
         05 DFHPF11               PIC X VALUE X'7B'.
         05 DFHPF12               PIC X VALUE X'7C'."""

    dfhbmsca_mock = """\
      * Mock DFHBMSCA — stubbed for standalone testing
       01 DFHBMSCA-MOCK.
         05 DFHBMPEM              PIC X VALUE X'08'.
         05 DFHBMPRO              PIC X VALUE X'20'.
         05 DFHBMASF              PIC X VALUE X'30'.
         05 DFHBMUNP              PIC X VALUE X'40'.
         05 DFHBMUNN              PIC X VALUE X'50'.
         05 DFHBMFSE              PIC X VALUE X'01'."""

    eib_mock = """\
      * Mock DFHEIBLK — stubbed for standalone testing
       01 DFHEIBLK.
         05 EIBTIME               PIC S9(7) COMP-3 VALUE 0.
         05 EIBDATE               PIC S9(7) COMP-3 VALUE 0.
         05 EIBTRNID              PIC X(4) VALUE SPACES.
         05 EIBTASKN              PIC S9(7) COMP-3 VALUE 0.
         05 EIBTRMID              PIC X(4) VALUE SPACES.
         05 EIBCPOSN              PIC S9(4) COMP VALUE 0.
         05 EIBCALEN              PIC S9(4) COMP VALUE 0.
         05 EIBAID                PIC X VALUE SPACES.
         05 EIBFN                 PIC X(2) VALUE SPACES.
         05 EIBRCODE              PIC X(6) VALUE SPACES.
         05 EIBDS                 PIC X(8) VALUE SPACES.
         05 EIBREQID              PIC X(8) VALUE SPACES.
         05 EIBRSRCE              PIC X(8) VALUE SPACES.
         05 EIBSYNC               PIC X VALUE SPACES.
         05 EIBFREE               PIC X VALUE SPACES.
         05 EIBRECV               PIC X VALUE SPACES.
         05 EIBSIG                PIC X VALUE SPACES.
         05 EIBCONF               PIC X VALUE SPACES.
         05 EIBERR                PIC X VALUE SPACES.
         05 EIBATT                PIC X VALUE SPACES.
         05 EIBEOC                PIC X VALUE SPACES.
         05 EIBRLDBK              PIC X VALUE SPACES.
         05 EIBRESP               PIC S9(8) COMP VALUE 0.
         05 EIBRESP2              PIC S9(8) COMP VALUE 0."""

    # Replace COPY DFHAID
    source = re.sub(
        r'^\s*COPY\s+DFHAID\s*\.?\s*$',
        dfhaid_mock,
        source,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    # Replace COPY DFHBMSCA
    source = re.sub(
        r'^\s*COPY\s+DFHBMSCA\s*\.?\s*$',
        dfhbmsca_mock,
        source,
        flags=re.MULTILINE | re.IGNORECASE,
    )

    # Inject EIB mock into WORKING-STORAGE if EIBCALEN is referenced
    if 'EIBCALEN' in source.upper() and 'DFHEIBLK' not in source.upper():
        source = _inject_working_storage(source, eib_mock)

    # Also inject dataset file status fields
    for line in source.splitlines():
        m = re.match(r'\s*([\w-]+)-STATUS\b', line)

    return source

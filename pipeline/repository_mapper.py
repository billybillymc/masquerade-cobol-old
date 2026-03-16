"""
Repository pattern mapper — converts CICS file operations and sequential
file I/O into typed repository interfaces.

Maps:
- CICS READ + RIDFLD → find_by_id(key) -> RecordType
- CICS WRITE → save(record) -> None
- CICS REWRITE → update(record) -> None
- CICS DELETE → delete(key) -> None
- CICS STARTBR + READNEXT + ENDBR → browse(start_key) -> Iterator[RecordType]
- Sequential OPEN/READ/CLOSE → context manager reader/writer
"""

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from skeleton_generator import _cobol_name_to_python, _cobol_name_to_class


# ── Data model ──────────────────────────────────────────────────────────────


@dataclass
class RepositoryMethod:
    """A single repository method derived from a CICS file operation."""
    name: str              # find_by_id, save, update, delete, browse
    operation: str         # READ, WRITE, REWRITE, DELETE, STARTBR
    key_field: str         # RIDFLD field name (for find_by_id, delete, browse)
    record_type: str       # INTO target → copybook record class name
    record_field: str      # INTO target raw COBOL name


@dataclass
class RepositorySpec:
    """Repository interface for a CICS dataset."""
    dataset: str           # raw COBOL dataset name (e.g., WS-USRSEC-FILE)
    class_name: str        # PascalCase class name (e.g., WsUsrsecFileRepository)
    methods: list[RepositoryMethod]
    programs: list[str]    # programs that use this dataset


@dataclass
class FileReaderSpec:
    """Sequential file reader/writer specification."""
    file_name: str         # COBOL file name from SELECT
    assign_to: str         # physical file assignment
    organization: str      # SEQUENTIAL
    mode: str              # input or output
    class_name: str        # PascalCase class name


# ── CICS detail extraction ──────────────────────────────────────────────────

_RE_INTO = re.compile(r'INTO\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)
_RE_RIDFLD = re.compile(r'RIDFLD\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)
_RE_KEYLENGTH = re.compile(r'KEYLENGTH\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)
_RE_FROM = re.compile(r'FROM\s*\(\s*([^)]+)\s*\)', re.IGNORECASE)


def extract_cics_details(source_file: str, start_line: int, end_line: int) -> dict:
    """Extract INTO, RIDFLD, KEYLENGTH, FROM from CICS statement source lines.

    Reads the specified line range from the source file and parses
    CICS-specific clauses that the main parser doesn't capture.
    """
    result = {"into": None, "ridfld": None, "keylength": None, "from_field": None}

    try:
        lines = Path(source_file).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return result

    # Extract the relevant lines (1-indexed)
    stmt_lines = lines[max(0, start_line - 1):end_line]
    stmt_text = " ".join(l[6:72] if len(l) > 6 else l for l in stmt_lines)

    m = _RE_INTO.search(stmt_text)
    if m:
        result["into"] = m.group(1).strip()

    m = _RE_RIDFLD.search(stmt_text)
    if m:
        result["ridfld"] = m.group(1).strip()

    m = _RE_KEYLENGTH.search(stmt_text)
    if m:
        result["keylength"] = m.group(1).strip()

    m = _RE_FROM.search(stmt_text)
    if m:
        result["from_field"] = m.group(1).strip()

    return result


# ── CICS repository mapping ────────────────────────────────────────────────


def map_cics_repositories(
    program_id: str,
    program_data: dict,
    source_dir: str = "",
) -> list[RepositorySpec]:
    """Map CICS file operations to repository specs for a program.

    Scans all paragraphs for CICS file ops (READ, WRITE, REWRITE, DELETE,
    STARTBR, READNEXT, ENDBR), groups by dataset, and builds a RepositorySpec
    with methods derived from the operations.
    """
    # Collect operations per dataset
    dataset_ops: dict[str, dict] = {}  # dataset -> {ops: set, spans: list, details: dict}

    for para in program_data.get("paragraphs", []):
        for op in para.get("cics_ops", []):
            ds = op.get("dataset")
            operation = op.get("operation", "").upper()
            if not ds or operation not in (
                "READ", "WRITE", "REWRITE", "DELETE",
                "STARTBR", "READNEXT", "READPREV", "ENDBR",
            ):
                continue

            if ds not in dataset_ops:
                dataset_ops[ds] = {"ops": set(), "details": {}}

            dataset_ops[ds]["ops"].add(operation)

            # Extract INTO/RIDFLD from source if available
            if operation == "READ" and source_dir and "into" not in dataset_ops[ds]["details"]:
                span = para.get("span", {})
                src_file = span.get("file", "")
                if src_file:
                    # Resolve relative path
                    src_path = Path(src_file)
                    if not src_path.is_absolute():
                        src_path = Path(source_dir) / src_path.name
                    if not src_path.exists():
                        # Try finding the file in source_dir
                        candidates = list(Path(source_dir).glob(f"*{Path(src_file).name}"))
                        if candidates:
                            src_path = candidates[0]

                    if src_path.exists():
                        # Scan the paragraph for EXEC CICS READ
                        para_start = span.get("start_line", 0)
                        para_end = span.get("end_line", 0)
                        details = extract_cics_details(str(src_path), para_start, para_end)
                        if details.get("into") or details.get("ridfld"):
                            dataset_ops[ds]["details"].update(
                                {k: v for k, v in details.items() if v}
                            )

            # For WRITE/REWRITE, try to get FROM field
            if operation in ("WRITE", "REWRITE") and source_dir and "from_field" not in dataset_ops[ds]["details"]:
                span = para.get("span", {})
                src_file = span.get("file", "")
                if src_file:
                    src_path = Path(src_file)
                    if not src_path.is_absolute():
                        src_path = Path(source_dir) / src_path.name
                    if not src_path.exists():
                        candidates = list(Path(source_dir).glob(f"*{Path(src_file).name}"))
                        if candidates:
                            src_path = candidates[0]
                    if src_path.exists():
                        para_start = span.get("start_line", 0)
                        para_end = span.get("end_line", 0)
                        details = extract_cics_details(str(src_path), para_start, para_end)
                        if details.get("from_field"):
                            dataset_ops[ds]["details"]["from_field"] = details["from_field"]
                        if details.get("ridfld") and "ridfld" not in dataset_ops[ds]["details"]:
                            dataset_ops[ds]["details"]["ridfld"] = details["ridfld"]

    # Build RepositorySpec for each dataset
    repos = []
    for ds, info in sorted(dataset_ops.items()):
        ops = info["ops"]
        details = info["details"]

        into_field = details.get("into", "")
        ridfld = details.get("ridfld", "")
        from_field = details.get("from_field", "")

        record_type = _cobol_name_to_class(into_field) if into_field else "dict"
        record_field = into_field or ""
        key_field = ridfld or ""

        # If no INTO but have FROM, use FROM as record type
        if record_type == "dict" and from_field:
            record_type = _cobol_name_to_class(from_field)
            record_field = from_field

        class_name = _cobol_name_to_class(ds) + "Repository"

        methods = []

        if "READ" in ops:
            methods.append(RepositoryMethod(
                name="find_by_id",
                operation="READ",
                key_field=key_field,
                record_type=record_type,
                record_field=record_field,
            ))

        if "WRITE" in ops:
            methods.append(RepositoryMethod(
                name="save",
                operation="WRITE",
                key_field=key_field,
                record_type=record_type,
                record_field=record_field,
            ))

        if "REWRITE" in ops:
            methods.append(RepositoryMethod(
                name="update",
                operation="REWRITE",
                key_field=key_field,
                record_type=record_type,
                record_field=record_field,
            ))

        if "DELETE" in ops:
            methods.append(RepositoryMethod(
                name="delete",
                operation="DELETE",
                key_field=key_field,
                record_type=record_type,
                record_field=record_field,
            ))

        if "STARTBR" in ops or "READNEXT" in ops:
            methods.append(RepositoryMethod(
                name="browse",
                operation="STARTBR",
                key_field=key_field,
                record_type=record_type,
                record_field=record_field,
            ))

        repos.append(RepositorySpec(
            dataset=ds,
            class_name=class_name,
            methods=methods,
            programs=[program_id],
        ))

    return repos


# ── Sequential file mapping ────────────────────────────────────────────────


def map_sequential_files(
    program_id: str,
    program_data: dict,
) -> list[FileReaderSpec]:
    """Map sequential file controls to reader/writer specs."""
    specs = []

    for fc in program_data.get("file_controls", []):
        org = fc.get("organization", "").upper()
        if org != "SEQUENTIAL":
            continue

        file_name = fc.get("name", "")
        assign_to = fc.get("assign_to", "")

        # Heuristic: input files have IN/INPUT in the name, output have OUT/OUTPUT
        name_upper = (file_name + assign_to).upper()
        if "OUT" in name_upper or "OP" in name_upper[:2]:
            mode = "output"
        else:
            mode = "input"

        class_name = _cobol_name_to_class(file_name) + ("Writer" if mode == "output" else "Reader")

        specs.append(FileReaderSpec(
            file_name=file_name,
            assign_to=assign_to,
            organization=org,
            mode=mode,
            class_name=class_name,
        ))

    return specs


# ── Code generation ─────────────────────────────────────────────────────────


def generate_repository_code(repo: RepositorySpec) -> str:
    """Generate Python repository class code from a RepositorySpec."""
    lines = []
    lines.append(f"class {repo.class_name}:")
    lines.append(f'    """Repository for CICS dataset {repo.dataset}.')
    lines.append(f"")
    lines.append(f"    Used by: {', '.join(repo.programs)}")
    lines.append(f'    """')
    lines.append(f"")

    for method in repo.methods:
        key_py = _cobol_name_to_python(method.key_field) if method.key_field else "key"
        record_cls = method.record_type if method.record_type != "dict" else "dict"

        if method.name == "find_by_id":
            lines.append(f"    def find_by_id(self, {key_py}: str) -> Optional[{record_cls}]:")
            lines.append(f'        """Read record by key (CICS READ DATASET({repo.dataset}) RIDFLD({method.key_field or "?"}))')
            lines.append(f"")
            lines.append(f"        Returns {record_cls} or None if not found (RESP 13).")
            lines.append(f'        """')
            lines.append(f"        raise NotImplementedError")
            lines.append(f"")

        elif method.name == "save":
            record_py = _cobol_name_to_python(method.record_field) if method.record_field else "record"
            lines.append(f"    def save(self, {record_py}: {record_cls}) -> None:")
            lines.append(f'        """Write new record (CICS WRITE DATASET({repo.dataset}))."""')
            lines.append(f"        raise NotImplementedError")
            lines.append(f"")

        elif method.name == "update":
            record_py = _cobol_name_to_python(method.record_field) if method.record_field else "record"
            lines.append(f"    def update(self, {record_py}: {record_cls}) -> None:")
            lines.append(f'        """Update existing record (CICS REWRITE DATASET({repo.dataset}))."""')
            lines.append(f"        raise NotImplementedError")
            lines.append(f"")

        elif method.name == "delete":
            lines.append(f"    def delete(self, {key_py}: str) -> None:")
            lines.append(f'        """Delete record by key (CICS DELETE DATASET({repo.dataset}))."""')
            lines.append(f"        raise NotImplementedError")
            lines.append(f"")

        elif method.name == "browse":
            lines.append(f"    def browse(self, start_key: str = '') -> 'Iterator[{record_cls}]':")
            lines.append(f'        """Browse records (CICS STARTBR/READNEXT/ENDBR on {repo.dataset})."""')
            lines.append(f"        raise NotImplementedError")
            lines.append(f"")

    return "\n".join(lines)


def generate_file_reader_code(spec: FileReaderSpec) -> str:
    """Generate Python context manager code for a sequential file."""
    lines = []
    lines.append(f"class {spec.class_name}:")
    lines.append(f'    """{"Reader" if spec.mode == "input" else "Writer"} for sequential file {spec.file_name}.')
    lines.append(f"")
    lines.append(f"    Assigned to: {spec.assign_to}")
    lines.append(f'    """')
    lines.append(f"")
    lines.append(f"    def __init__(self, file_path: str):")
    lines.append(f"        self.file_path = file_path")
    lines.append(f"        self._handle = None")
    lines.append(f"")
    lines.append(f"    def __enter__(self):")

    if spec.mode == "input":
        lines.append(f"        self._handle = open(self.file_path, 'r')")
    else:
        lines.append(f"        self._handle = open(self.file_path, 'w')")
    lines.append(f"        return self")
    lines.append(f"")
    lines.append(f"    def __exit__(self, exc_type, exc_val, exc_tb):")
    lines.append(f"        if self._handle:")
    lines.append(f"            self._handle.close()")
    lines.append(f"        return False")
    lines.append(f"")

    if spec.mode == "input":
        lines.append(f"    def __iter__(self):")
        lines.append(f"        return self")
        lines.append(f"")
        lines.append(f"    def __next__(self) -> str:")
        lines.append(f'        """Read next record (COBOL READ ... AT END → StopIteration)."""')
        lines.append(f"        line = self._handle.readline()")
        lines.append(f"        if not line:")
        lines.append(f"            raise StopIteration")
        lines.append(f"        return line.rstrip('\\n')")
    else:
        lines.append(f"    def write(self, record: str) -> None:")
        lines.append(f'        """Write a record (COBOL WRITE)."""')
        lines.append(f"        self._handle.write(record + '\\n')")

    lines.append(f"")
    return "\n".join(lines)

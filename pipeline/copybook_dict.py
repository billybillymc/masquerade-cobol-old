"""
Copybook data dictionary — parses all .cpy files in a codebase to build
a searchable field catalog with types, sizes, and relationships.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CopybookField:
    name: str
    level: int
    picture: Optional[str]
    usage: Optional[str]
    occurs: Optional[int]
    redefines: Optional[str]
    condition_values: list[tuple[str, str]] = field(default_factory=list)
    line: int = 0

    @property
    def field_type(self) -> str:
        if not self.picture:
            if self.level == 88:
                return "condition"
            return "group"
        pic = self.picture.upper()
        if "9" in pic and "V" in pic:
            return "decimal"
        if "9" in pic:
            return "numeric"
        if "X" in pic:
            return "alphanumeric"
        if "A" in pic:
            return "alphabetic"
        return "other"

    @property
    def size_bytes(self) -> int:
        if not self.picture:
            return 0
        pic = self.picture.upper().replace(".", "")
        # Expand shorthand like 9(05) -> 99999
        expanded = re.sub(r'([9XASV])\((\d+)\)', lambda m: m.group(1) * int(m.group(2)), pic)
        expanded = expanded.replace("V", "").replace("S", "")
        usage = (self.usage or "").upper()
        char_count = len(expanded)
        if "COMP-3" in usage or "PACKED" in usage:
            return (char_count + 2) // 2
        if "COMP" in usage or "BINARY" in usage:
            if char_count <= 4:
                return 2
            elif char_count <= 9:
                return 4
            return 8
        return char_count


@dataclass
class CopybookRecord:
    name: str
    source_file: str
    fields: list[CopybookField]
    total_lines: int
    comment_lines: int

    @property
    def field_count(self) -> int:
        return len([f for f in self.fields if f.level != 88])

    @property
    def condition_count(self) -> int:
        return len([f for f in self.fields if f.level == 88])


_RE_COBOL_ID = re.compile(r'^[A-Z0-9][A-Z0-9-]*$', re.IGNORECASE)


def apply_replacing(source_text: str, replacements: list[tuple[str, str]]) -> str:
    """Apply COPY REPLACING substitutions to copybook source text.

    Two replacement strategies are used depending on *old*:

    - **Valid COBOL identifier** (only letters, digits, hyphens): token-boundary
      replacement so that ``WS-CUST`` does not accidentally match inside the
      longer token ``WS-CUST-NAME``.
    - **Placeholder pattern** (contains non-identifier characters such as ``:``):
      plain substring replacement.  The common ``==:PREF:== BY ==WS-ACCT==``
      convention embeds the placeholder inside a longer name like ``:PREF:-NAME``
      and relies on substring matching to produce ``WS-ACCT-NAME``.
    """
    for old, new in replacements:
        old = old.strip()
        new = new.strip()
        if not old:
            continue
        if _RE_COBOL_ID.match(old):
            # Pure COBOL identifier — respect token boundaries.
            pattern = r'(?<![A-Z0-9-])' + re.escape(old) + r'(?![A-Z0-9-])'
            source_text = re.sub(pattern, new, source_text, flags=re.IGNORECASE)
        else:
            # Placeholder (e.g. :PREF:) — plain substring, case-sensitive.
            source_text = source_text.replace(old, new)
    return source_text


_RE_LEVEL = re.compile(r'^\s*(\d{2})\s+([A-Z0-9][\w-]*)', re.IGNORECASE)
_RE_PIC = re.compile(r'PIC(?:TURE)?\s+IS\s+(\S+)|PIC(?:TURE)?\s+(\S+)', re.IGNORECASE)
_RE_USAGE = re.compile(r'USAGE\s+IS\s+(\S+)|USAGE\s+(\S+)', re.IGNORECASE)
_RE_COMP = re.compile(r'\b(COMP|COMP-1|COMP-2|COMP-3|BINARY|PACKED-DECIMAL|DISPLAY)\b', re.IGNORECASE)
_RE_OCCURS = re.compile(r'OCCURS\s+(\d+)', re.IGNORECASE)
_RE_REDEFINES = re.compile(r'REDEFINES\s+(\S+)', re.IGNORECASE)
_RE_VALUE = re.compile(r"VALUE\s+'([^']*)'|VALUE\s+(\S+)", re.IGNORECASE)
_RE_88_VALUE = re.compile(r"VALUE\s+'([^']*)'|VALUE\s+(\S+)", re.IGNORECASE)


def parse_copybook(filepath: Path, source_text: Optional[str] = None) -> CopybookRecord:
    """Parse a single copybook file into a CopybookRecord.

    If *source_text* is provided it is used instead of reading the file,
    which allows callers to pass COPY REPLACING-substituted text.
    """
    raw = source_text if source_text is not None else filepath.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()
    total_lines = len(lines)
    comment_lines = 0

    fields: list[CopybookField] = []
    current_88_parent: Optional[str] = None

    for i, line in enumerate(lines):
        line_num = i + 1
        if len(line) > 6 and line[6] in ("*", "/"):
            comment_lines += 1
            continue

        code = line[7:72] if len(line) > 7 else line
        code = code.strip()
        if not code:
            continue

        level_m = _RE_LEVEL.match(code)
        if not level_m:
            # Check for 88-level on continuation of previous
            if code.startswith("88 ") or code.startswith("88  "):
                level_m = _RE_LEVEL.match(code)
            if not level_m:
                continue

        level = int(level_m.group(1))
        name = level_m.group(2).rstrip(".")

        pic_m = _RE_PIC.search(code)
        picture = (pic_m.group(1) or pic_m.group(2)).rstrip(".") if pic_m else None

        usage_m = _RE_USAGE.search(code)
        if usage_m:
            usage = (usage_m.group(1) or usage_m.group(2)).rstrip(".")
        else:
            comp_m = _RE_COMP.search(code)
            usage = comp_m.group(1) if comp_m else None

        occ_m = _RE_OCCURS.search(code)
        occurs = int(occ_m.group(1)) if occ_m else None

        redef_m = _RE_REDEFINES.search(code)
        redefines = redef_m.group(1).rstrip(".") if redef_m else None

        condition_values = []
        if level == 88:
            val_m = _RE_88_VALUE.search(code)
            if val_m:
                val = val_m.group(1) if val_m.group(1) is not None else val_m.group(2)
                condition_values.append((name, val.rstrip(".")))

        f = CopybookField(
            name=name, level=level, picture=picture,
            usage=usage, occurs=occurs, redefines=redefines,
            condition_values=condition_values, line=line_num,
        )
        fields.append(f)

        if level != 88:
            current_88_parent = name

    return CopybookRecord(
        name=filepath.stem.upper(),
        source_file=str(filepath),
        fields=fields,
        total_lines=total_lines,
        comment_lines=comment_lines,
    )


class CopybookDictionary:
    """Searchable field catalog across all copybooks in a codebase."""

    def __init__(self, codebase_dir: str):
        self.codebase_dir = codebase_dir
        self.records: dict[str, CopybookRecord] = {}
        self._field_index: dict[str, list[tuple[str, CopybookField]]] = defaultdict(list)
        self._source_texts: dict[str, str] = {}

        for cpy_file in Path(codebase_dir).rglob("*.cpy"):
            try:
                raw = cpy_file.read_text(encoding="utf-8", errors="replace")
                rec = parse_copybook(cpy_file, source_text=raw)
                self.records[rec.name] = rec
                self._source_texts[rec.name] = raw
                for f in rec.fields:
                    self._field_index[f.name.upper()].append((rec.name, f))
            except Exception:
                continue

    def resolve_with_replacing(
        self,
        copybook_name: str,
        replacing: list[tuple[str, str]],
    ) -> Optional[CopybookRecord]:
        """Return a CopybookRecord with COPY REPLACING substitutions applied.

        Field names in the returned record reflect the substituted names as they
        appear in the including program — not the original names in the .cpy file.
        Returns None if the copybook is not found or has no stored source text.
        """
        name = copybook_name.upper()
        raw = self._source_texts.get(name)
        if raw is None:
            return None
        if not replacing:
            return self.records.get(name)
        substituted = apply_replacing(raw, replacing)
        rec = self.records.get(name)
        if rec is None:
            return None
        source_path = Path(rec.source_file)
        return parse_copybook(source_path, source_text=substituted)

    def lookup_field(self, field_name: str) -> list[dict]:
        """Find a field across all copybooks."""
        key = field_name.upper()
        results = []
        for cb_name, f in self._field_index.get(key, []):
            results.append({
                "copybook": cb_name,
                "name": f.name,
                "level": f.level,
                "picture": f.picture,
                "usage": f.usage,
                "type": f.field_type,
                "size_bytes": f.size_bytes,
                "occurs": f.occurs,
                "redefines": f.redefines,
                "conditions": f.condition_values,
                "line": f.line,
            })
        return results

    def search_fields(self, pattern: str) -> list[dict]:
        """Search for fields by partial name match."""
        pattern = pattern.upper()
        results = []
        for field_name, entries in self._field_index.items():
            if pattern in field_name:
                for cb_name, f in entries:
                    results.append({
                        "copybook": cb_name,
                        "name": f.name,
                        "level": f.level,
                        "picture": f.picture,
                        "type": f.field_type,
                        "size_bytes": f.size_bytes,
                    })
        return results

    def copybook_detail(self, copybook_name: str) -> Optional[dict]:
        """Get full detail for a specific copybook."""
        rec = self.records.get(copybook_name.upper())
        if not rec:
            return None
        return {
            "name": rec.name,
            "source_file": rec.source_file,
            "total_lines": rec.total_lines,
            "field_count": rec.field_count,
            "condition_count": rec.condition_count,
            "fields": [
                {
                    "name": f.name,
                    "level": f.level,
                    "picture": f.picture,
                    "usage": f.usage,
                    "type": f.field_type,
                    "size_bytes": f.size_bytes,
                    "occurs": f.occurs,
                    "redefines": f.redefines,
                    "conditions": f.condition_values,
                    "line": f.line,
                }
                for f in rec.fields
            ],
        }

    def summary(self) -> dict:
        """Overall dictionary summary."""
        total_fields = sum(r.field_count for r in self.records.values())
        total_conditions = sum(r.condition_count for r in self.records.values())
        largest = max(self.records.values(), key=lambda r: r.field_count) if self.records else None
        return {
            "total_copybooks": len(self.records),
            "total_fields": total_fields,
            "total_conditions": total_conditions,
            "largest_copybook": largest.name if largest else None,
            "largest_field_count": largest.field_count if largest else 0,
        }

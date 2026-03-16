"""
Symbol table with hierarchical field resolution and scope tracking.

Builds a tree of SymbolNodes from copybook field definitions (IQ-02),
supporting:
- Hierarchical lookup by COBOL level numbers
- Qualified reference resolution (FIELD OF GROUP OF RECORD)
- REDEFINES tracking (shared memory offset)
- Section scope tags (WORKING-STORAGE, LINKAGE, FILE SECTION)
- Ambiguous reference detection
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from copybook_dict import CopybookDictionary, CopybookField, CopybookRecord


class AmbiguousReferenceError(Exception):
    """Raised when an unqualified field name matches multiple symbols."""
    def __init__(self, field_name: str, matches: list['SymbolNode']):
        self.field_name = field_name
        self.matches = matches
        parents = [f"{m.name} OF {m.parent.name}" if m.parent else m.name for m in matches]
        super().__init__(
            f"Ambiguous reference '{field_name}': found in {len(matches)} locations: "
            + ", ".join(parents)
        )


@dataclass
class SymbolNode:
    """A node in the symbol table tree."""
    name: str
    level: int
    parent: Optional['SymbolNode'] = None
    children: list['SymbolNode'] = field(default_factory=list)
    picture: Optional[str] = None
    usage: Optional[str] = None
    redefines_target: Optional[str] = None
    copybook_origin: str = ""
    section: str = "WORKING-STORAGE"
    is_group: bool = False
    condition_values: list[tuple[str, str]] = field(default_factory=list)

    def fully_qualified_name(self) -> str:
        """Return the full hierarchical path: FIELD.GROUP.RECORD."""
        parts = [self.name]
        node = self.parent
        while node is not None:
            parts.append(node.name)
            node = node.parent
        return ".".join(parts)

    def __repr__(self) -> str:
        return f"SymbolNode({self.name}, level={self.level}, section={self.section})"


class SymbolTable:
    """Hierarchical symbol table for COBOL field resolution."""

    def __init__(self):
        self._roots: list[SymbolNode] = []
        self._index: dict[str, list[SymbolNode]] = {}  # name → [nodes]

    def root_count(self) -> int:
        return len(self._roots)

    def add_root(self, node: SymbolNode) -> None:
        """Add a root-level (01) symbol."""
        self._roots.append(node)
        self._index_node(node)

    def _index_node(self, node: SymbolNode) -> None:
        """Recursively index a node and all its children by name."""
        key = node.name.upper()
        if key not in self._index:
            self._index[key] = []
        self._index[key].append(node)
        for child in node.children:
            self._index_node(child)

    def find(self, name: str) -> Optional[SymbolNode]:
        """Find the first symbol with this name (case-insensitive).

        Returns None if not found. Does NOT raise on ambiguity — use
        resolve() for that.
        """
        nodes = self._index.get(name.upper(), [])
        return nodes[0] if nodes else None

    def find_all(self, name: str) -> list[SymbolNode]:
        """Find all symbols with this name."""
        return self._index.get(name.upper(), [])

    def resolve(
        self,
        name: str,
        qualifier: Optional[str] = None,
    ) -> Optional[SymbolNode]:
        """Resolve a field reference, optionally qualified.

        - `resolve("SEC-USR-ID")` — unqualified, must be unique or raises
        - `resolve("ERRMSGO", qualifier="COSGN0AO")` — qualified, name must
          be a descendant of qualifier

        Raises AmbiguousReferenceError if unqualified and multiple matches exist.
        """
        nodes = self.find_all(name)
        if not nodes:
            return None

        if qualifier:
            # Filter to nodes whose ancestor chain includes the qualifier
            qualified = []
            for node in nodes:
                ancestor = node.parent
                while ancestor is not None:
                    if ancestor.name.upper() == qualifier.upper():
                        qualified.append(node)
                        break
                    ancestor = ancestor.parent
            if len(qualified) == 1:
                return qualified[0]
            elif len(qualified) > 1:
                return qualified[0]  # multiple matches under same qualifier — take first
            return None

        # Unqualified
        if len(nodes) == 1:
            return nodes[0]

        # Ambiguous
        raise AmbiguousReferenceError(name, nodes)


def _build_tree_from_fields(
    fields: list[CopybookField],
    copybook_name: str,
    section: str,
) -> list[SymbolNode]:
    """Build a tree of SymbolNodes from a flat list of CopybookFields.

    Uses COBOL level numbers to determine hierarchy: a field at level N
    is a child of the nearest preceding field at a lower level.
    """
    roots: list[SymbolNode] = []
    stack: list[SymbolNode] = []

    for f in fields:
        if f.level == 88:
            # Level-88 conditions attach to the most recent non-88 field
            if stack:
                stack[-1].condition_values.extend(f.condition_values)
            continue

        node = SymbolNode(
            name=f.name,
            level=f.level,
            picture=f.picture,
            usage=f.usage,
            redefines_target=f.redefines,
            copybook_origin=copybook_name,
            section=section,
            is_group=(f.picture is None and f.level != 88),
        )

        # Pop stack until we find a parent with lower level
        while stack and stack[-1].level >= f.level:
            stack.pop()

        if stack:
            node.parent = stack[-1]
            stack[-1].children.append(node)
        else:
            roots.append(node)

        stack.append(node)

    return roots


def build_symbol_table(
    copybook_names: list[str],
    copybook_dict: CopybookDictionary,
    section: str = "WORKING-STORAGE",
) -> SymbolTable:
    """Build a SymbolTable from one or more copybooks.

    Each copybook's fields are parsed into a hierarchical tree and added
    to the symbol table with the specified section scope.
    """
    st = SymbolTable()

    for cb_name in copybook_names:
        record = copybook_dict.records.get(cb_name.upper())
        if not record:
            continue

        roots = _build_tree_from_fields(record.fields, cb_name.upper(), section)
        for root in roots:
            st.add_root(root)

    return st

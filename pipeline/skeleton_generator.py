"""
Modern language skeleton generator — produces Python module stubs from
COBOL structural analysis. No API keys required.

Maps COBOL structures to Python equivalents:
- PROGRAM-ID -> Python module + main class
- Paragraphs -> methods
- Copybooks -> dataclasses
- PERFORM -> method calls
- CALL -> service dependency
- CICS ops -> annotated API stubs
- Data items -> typed fields
- File I/O -> context managers
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from spec_generator import ProgramSpec, generate_program_spec, _load_program_data
from graph_context import GraphIndex
from copybook_dict import CopybookDictionary, CopybookField, CopybookRecord


@dataclass
class SkeletonResult:
    program: str
    python_code: str
    output_path: str
    dataclass_count: int
    method_count: int


_PIC_TYPE_MAP = {
    "9": "int",
    "S9": "int",
    "X": "str",
    "A": "str",
    "V9": "float",
    "S9V9": "float",
}


def _pic_to_python_type(pic: str) -> str:
    if not pic:
        return "str"
    pic = pic.upper().replace("(", "").replace(")", "")
    if "V" in pic or "." in pic:
        return "Decimal"
    if pic.startswith("S9") or pic.startswith("9"):
        return "int"
    return "str"


def _pic_to_field_metadata(pic: str, usage: Optional[str] = None) -> tuple[str, dict]:
    """Extract Python type and machine-readable metadata from PIC/USAGE.

    Returns (python_type, metadata_dict).
    """
    if not pic:
        return "str", {}

    pic_upper = pic.upper()
    metadata = {"pic": pic_upper}

    # Parse digit/scale counts from PIC
    # Expand shorthand: 9(05) -> 99999, X(08) -> XXXXXXXX
    expanded = re.sub(
        r'([9XASV])\((\d+)\)',
        lambda m: m.group(1) * int(m.group(2)),
        pic_upper,
    )

    # Count integer digits (9s before V), scale digits (9s after V)
    has_sign = "S" in expanded
    has_decimal = "V" in expanded

    if has_decimal:
        before_v, after_v = expanded.split("V", 1)
        integer_digits = before_v.count("9")
        scale_digits = after_v.count("9")
    else:
        integer_digits = expanded.count("9")
        scale_digits = 0

    char_count = expanded.replace("V", "").replace("S", "")

    # Determine Python type and metadata
    if "X" in pic_upper or "A" in pic_upper:
        py_type = "str"
        length = len(char_count)
        metadata["max_length"] = length
    elif has_decimal:
        py_type = "Decimal"
        metadata["max_digits"] = integer_digits
        metadata["scale"] = scale_digits
        if has_sign:
            metadata["signed"] = True
    elif "9" in pic_upper:
        py_type = "int"
        metadata["max_digits"] = integer_digits
        if has_sign:
            metadata["signed"] = True
    else:
        py_type = "str"
        length = len(char_count)
        metadata["max_length"] = length

    # USAGE clause
    if usage:
        usage_upper = usage.upper()
        metadata["usage"] = usage_upper

    return py_type, metadata


def _default_for_type(py_type: str) -> str:
    """Return the default value expression for a Python type."""
    if py_type == "int":
        return "0"
    if py_type == "Decimal":
        return "Decimal('0')"
    return "''"


def _metadata_repr(metadata: dict) -> str:
    """Produce a repr string for metadata dict suitable for embedding in code."""
    if not metadata:
        return "{}"
    parts = []
    for k, v in metadata.items():
        if isinstance(v, str):
            parts.append(f"'{k}': '{v}'")
        elif isinstance(v, bool):
            parts.append(f"'{k}': {v}")
        else:
            parts.append(f"'{k}': {v}")
    return "{" + ", ".join(parts) + "}"


@dataclass
class _FieldNode:
    """Tree node representing a COBOL field in the hierarchy."""
    field: CopybookField
    children: list  # list[_FieldNode]


def _build_field_hierarchy(fields: list[CopybookField]) -> list[_FieldNode]:
    """Convert flat field list to tree based on COBOL level numbers.

    COBOL levels define hierarchy: a field at level N is a child of the
    nearest preceding field at a lower level number.
    """
    if not fields:
        return []

    roots = []
    stack: list[_FieldNode] = []  # stack of (node, level)

    for f in fields:
        node = _FieldNode(field=f, children=[])

        if f.level == 88:
            # Level-88 conditions attach to the most recent non-88 field
            if stack:
                stack[-1].children.append(node)
            continue

        # Pop stack until we find a parent with lower level
        while stack and stack[-1].field.level >= f.level:
            stack.pop()

        if stack:
            stack[-1].children.append(node)
        else:
            roots.append(node)

        stack.append(node)

    return roots


def _generate_nested_dataclasses(
    node: _FieldNode,
    indent: str = "",
) -> tuple[list[str], list[str]]:
    """Generate dataclass code for a group node and its nested groups.

    Returns (pre_classes, class_lines):
    - pre_classes: nested dataclass definitions that must appear before the parent
    - class_lines: field lines for the parent class body
    """
    pre_classes: list[str] = []
    class_lines: list[str] = []

    # Collect level-88 conditions from direct children
    conditions_88 = []
    regular_children = []
    for child in node.children:
        if child.field.level == 88:
            conditions_88.append(child)
        else:
            regular_children.append(child)

    # Generate ClassVar constants for level-88 conditions
    for cond in conditions_88:
        for name, value in cond.field.condition_values:
            const_name = _cobol_name_to_python(name).upper()
            class_lines.append(f"{indent}    {const_name}: ClassVar[str] = '{value}'")

    # Generate fields for regular children
    for child in regular_children:
        f = child.field

        # Skip FILLER
        if f.name.upper() == "FILLER":
            continue

        py_name = _cobol_name_to_python(f.name)

        if f.field_type == "group" and not f.picture:
            # Group item -> nested dataclass
            nested_class_name = _cobol_name_to_class(f.name)

            # Recursively generate the nested class
            nested_pre, nested_body = _generate_nested_dataclasses(child)
            pre_classes.extend(nested_pre)

            # Build the nested class definition
            nested_lines = []
            nested_lines.append(f"@dataclass")
            nested_lines.append(f"class {nested_class_name}:")
            nested_lines.append(f'    """Data structure from COBOL group {f.name}."""')

            if nested_body:
                nested_lines.extend(nested_body)
            else:
                nested_lines.append(f"    pass")
            nested_lines.append("")

            pre_classes.append("\n".join(nested_lines))

            # Field on parent referencing the nested class
            if f.redefines:
                class_lines.append(
                    f"{indent}    {py_name}: Optional[{nested_class_name}] = None"
                    f"  # REDEFINES {f.redefines}"
                )
            elif f.occurs:
                meta = _metadata_repr({"occurs": f.occurs})
                class_lines.append(
                    f"{indent}    {py_name}: list[{nested_class_name}] = field("
                    f"default_factory=lambda: [{nested_class_name}() for _ in range({f.occurs})], "
                    f"metadata={meta})"
                )
            else:
                class_lines.append(
                    f"{indent}    {py_name}: {nested_class_name} = field("
                    f"default_factory={nested_class_name})"
                )
        else:
            # Elementary item -> typed field
            py_type, metadata = _pic_to_field_metadata(f.picture, f.usage)
            default = _default_for_type(py_type)

            # Collect level-88 conditions from this field's children
            child_88s = [c for c in child.children if c.field.level == 88]
            for cond in child_88s:
                for name, value in cond.field.condition_values:
                    const_name = _cobol_name_to_python(name).upper()
                    class_lines.append(f"{indent}    {const_name}: ClassVar[str] = '{value}'")

            if f.redefines:
                meta_str = _metadata_repr(metadata)
                class_lines.append(
                    f"{indent}    {py_name}: Optional[{py_type}] = field("
                    f"default=None, metadata={meta_str})"
                    f"  # REDEFINES {f.redefines}"
                )
            elif f.occurs:
                metadata["occurs"] = f.occurs
                meta_str = _metadata_repr(metadata)
                class_lines.append(
                    f"{indent}    {py_name}: list[{py_type}] = field("
                    f"default_factory=lambda: [{default} for _ in range({f.occurs})], "
                    f"metadata={meta_str})"
                )
            else:
                meta_str = _metadata_repr(metadata)
                class_lines.append(
                    f"{indent}    {py_name}: {py_type} = field("
                    f"default={default}, metadata={meta_str})"
                )

    return pre_classes, class_lines


def _generate_dataclass_for_copybook(
    copybook_name: str,
    copybook_dict: Optional[CopybookDictionary] = None,
) -> str:
    """Generate a dataclass for a copybook.

    When copybook_dict is provided, generates typed fields from the parsed
    copybook. When None, falls back to the original pass-stub behavior.
    """
    class_name = _cobol_name_to_class(copybook_name)

    # If no dictionary, fall back to stub
    if copybook_dict is None:
        return (
            f"@dataclass\n"
            f"class {class_name}:\n"
            f'    """Data structure from COBOL copybook {copybook_name}.\n'
            f"    \n"
            f"    TODO: Map fields from copybook definition.\n"
            f'    """\n'
            f"    pass\n"
        )

    # Look up the copybook record
    record = copybook_dict.records.get(copybook_name.upper())
    if record is None:
        return (
            f"@dataclass\n"
            f"class {class_name}:\n"
            f'    """Data structure from COBOL copybook {copybook_name}.\n'
            f"    \n"
            f"    TODO: Map fields from copybook definition.\n"
            f'    """\n'
            f"    pass\n"
        )

    # Build field hierarchy from parsed copybook
    hierarchy = _build_field_hierarchy(record.fields)

    # For each root (01-level record), generate the dataclass
    all_pre_classes: list[str] = []
    all_body_lines: list[str] = []

    for root_node in hierarchy:
        # The root is typically the 01-level record
        pre_classes, body_lines = _generate_nested_dataclasses(root_node)
        all_pre_classes.extend(pre_classes)
        all_body_lines.extend(body_lines)

    # Assemble: pre-classes first, then the main class
    parts = []
    for pc in all_pre_classes:
        parts.append(pc)
        parts.append("")

    # Main copybook class — use the 01-level record name as the class name
    # if it differs from the copybook file name
    root_class_name = class_name
    if hierarchy and hierarchy[0].field.name.upper() != copybook_name.upper():
        root_class_name = _cobol_name_to_class(hierarchy[0].field.name)

    parts.append(f"@dataclass")
    parts.append(f"class {root_class_name}:")
    parts.append(f'    """Data structure from COBOL copybook {copybook_name}."""')

    if all_body_lines:
        parts.extend(all_body_lines)
    else:
        parts.append(f"    pass")

    # If root class name differs from copybook class name, add an alias
    if root_class_name != class_name:
        parts.append("")
        parts.append(f"{class_name} = {root_class_name}")

    parts.append("")
    return "\n".join(parts)


def _cobol_name_to_python(name: str) -> str:
    """Convert COBOL name (HYPHEN-CASE) to python_snake_case."""
    result = name.lower().replace("-", "_").replace(".", "_").replace("(", "").replace(")", "")
    if result and result[0].isdigit():
        result = "p_" + result
    return result


def _cobol_name_to_class(name: str) -> str:
    """Convert COBOL name to PascalCase class name.

    Splits on hyphens and dots so source names like ``callback.tpl`` become
    ``CallbackTpl`` (dots are illegal in Java class names).
    """
    import re
    parts = re.split(r"[-.]", name)
    cleaned = "".join("".join(c for c in p if c.isalnum()).capitalize() for p in parts if p)
    if cleaned and cleaned[0].isdigit():
        cleaned = "P" + cleaned
    return cleaned


def _generate_method_for_paragraph(para) -> str:
    """Generate a method stub from a paragraph spec."""
    method_name = _cobol_name_to_python(para.name)
    lines = []
    lines.append(f"    def {method_name}(self) -> None:")

    doc_parts = []
    if para.performs:
        doc_parts.append(f"COBOL PERFORMs: {', '.join(para.performs)}")
    if para.calls:
        doc_parts.append(f"COBOL CALLs: {', '.join(para.calls)}")
    if para.cics_ops:
        doc_parts.append(f"CICS: {', '.join(para.cics_ops)}")
    if para.data_flows_out:
        out_sample = para.data_flows_out[:5]
        doc_parts.append(f"Writes: {', '.join(out_sample)}")

    if doc_parts:
        lines.append(f'        """')
        for dp in doc_parts:
            lines.append(f"        {dp}")
        lines.append(f'        """')

    # Generate perform calls
    for target in para.performs:
        if target:
            lines.append(f"        self.{_cobol_name_to_python(target)}()")

    # Generate external calls
    for call in para.calls:
        if call:
            lines.append(f"        # CALL {call}")
            lines.append(f"        self._{_cobol_name_to_python(call)}_service.execute()")

    # Generate CICS stubs
    for op in para.cics_ops:
        lines.append(f"        # CICS {op}")
        op_name = op.split("(")[0].lower() if "(" in op else op.lower()
        if "send" in op_name or "receive" in op_name:
            lines.append(f"        # TODO: Replace with API endpoint handler")
        elif "read" in op_name or "write" in op_name:
            lines.append(f"        # TODO: Replace with database operation")
        elif "xctl" in op_name or "link" in op_name:
            lines.append(f"        # TODO: Replace with service call")

    if not para.performs and not para.calls and not para.cics_ops:
        lines.append(f"        raise NotImplementedError")

    lines.append("")
    return "\n".join(lines)


def generate_skeleton(
    spec: ProgramSpec,
    copybook_dict: Optional[CopybookDictionary] = None,
) -> str:
    """Generate a Python skeleton module from a ProgramSpec.

    When copybook_dict is provided, copybook dataclasses are populated with
    typed fields from the parsed copybook definitions.
    """
    class_name = _cobol_name_to_class(spec.program)
    module_name = _cobol_name_to_python(spec.program)

    lines = []

    # Module header
    lines.append(f'"""')
    lines.append(f"Modern Python equivalent of COBOL program {spec.program}.")
    lines.append(f"")
    lines.append(f"Original: {spec.source_file.replace(chr(92), '/')}")
    lines.append(f"Type: {spec.program_type}")
    lines.append(f"Lines: {spec.code_lines} code / {spec.total_lines} total")
    lines.append(f"Complexity: {spec.cyclomatic_complexity} (grade: {spec.complexity_grade})")
    lines.append(f"Readiness: {spec.readiness_score}/100")
    lines.append(f"Effort estimate: {spec.effort_days} person-days")
    lines.append(f"")
    lines.append(f"Generated by Masquerade COBOL Intelligence Engine.")
    lines.append(f'"""')
    lines.append(f"")
    lines.append(f"from dataclasses import dataclass, field")
    lines.append(f"from decimal import Decimal")
    lines.append(f"from typing import ClassVar, Optional, List")
    if spec.program_type == "CICS Online":
        lines.append(f"# Original CICS program — suggest REST/API framework")
        lines.append(f"# from fastapi import APIRouter, HTTPException")
    else:
        lines.append(f"# Original batch program — suggest scheduled job / CLI")
        lines.append(f"# import argparse")
    lines.append(f"")
    lines.append(f"")

    # Copybook dataclasses
    for contract in spec.data_contracts:
        lines.append(_generate_dataclass_for_copybook(contract.copybook, copybook_dict))
        lines.append("")

    # Service dependency stubs
    external_calls = set()
    for para in spec.paragraphs:
        for call in para.calls:
            if call:
                external_calls.add(call)

    if external_calls:
        lines.append("")
        lines.append("# --- External service dependencies ---")
        lines.append("")
        for call in sorted(external_calls):
            svc_class = _cobol_name_to_class(call) + "Service"
            lines.append(f"class {svc_class}:")
            lines.append(f'    """Stub for external COBOL program {call}."""')
            lines.append(f"    def execute(self, **kwargs):")
            lines.append(f"        raise NotImplementedError")
            lines.append(f"")
        lines.append("")

    # Main program class
    lines.append(f"class {class_name}:")
    lines.append(f'    """')
    lines.append(f"    Modern equivalent of COBOL program {spec.program}.")
    lines.append(f"    ")
    if spec.callers:
        lines.append(f"    Called by: {', '.join(spec.callers)}")
    if spec.callees:
        lines.append(f"    Calls: {', '.join(spec.callees)}")
    if spec.files_accessed:
        lines.append(f"    Files: {', '.join(spec.files_accessed)}")
    lines.append(f'    """')
    lines.append(f"")

    # Constructor
    lines.append(f"    def __init__(self):")
    if spec.data_contracts:
        for contract in spec.data_contracts:
            attr_name = _cobol_name_to_python(contract.copybook)
            class_ref = _cobol_name_to_class(contract.copybook)
            lines.append(f"        self.{attr_name} = {class_ref}()")
    if external_calls:
        for call in sorted(external_calls):
            attr = _cobol_name_to_python(call)
            svc_class = _cobol_name_to_class(call) + "Service"
            lines.append(f"        self._{attr}_service = {svc_class}()")
    if spec.validation_fields:
        for vf in spec.validation_fields[:10]:
            lines.append(f"        self.{_cobol_name_to_python(vf)}: str = ''")
    if not spec.data_contracts and not external_calls and not spec.validation_fields:
        lines.append(f"        pass")
    lines.append(f"")

    # Paragraph methods
    for para in spec.paragraphs:
        lines.append(_generate_method_for_paragraph(para))

    # Entry point
    lines.append(f"    def run(self) -> None:")
    lines.append(f'        """Main entry point — mirrors PROCEDURE DIVISION."""')
    if spec.entry_paragraphs:
        for ep in spec.entry_paragraphs[:3]:
            lines.append(f"        self.{_cobol_name_to_python(ep)}()")
    else:
        lines.append(f"        raise NotImplementedError")
    lines.append(f"")

    # Module-level entry
    lines.append(f"")
    lines.append(f'if __name__ == "__main__":')
    lines.append(f"    program = {class_name}()")
    lines.append(f"    program.run()")
    lines.append(f"")

    return "\n".join(lines)


def generate_all_skeletons(codebase_dir: str) -> dict[str, SkeletonResult]:
    """Generate Python skeletons for all programs in a codebase."""
    analysis_dir = Path(codebase_dir) / "_analysis"
    graph = GraphIndex(str(analysis_dir))
    program_data = _load_program_data(analysis_dir)

    # Build copybook dictionary from codebase
    copybook_dict = CopybookDictionary(codebase_dir)

    skeletons_dir = analysis_dir / "skeletons"
    skeletons_dir.mkdir(exist_ok=True)

    results = {}
    for pgm in sorted(graph.program_names()):
        spec = generate_program_spec(pgm, graph, program_data, codebase_dir)
        if not spec or spec.code_lines == 0:
            continue

        code = generate_skeleton(spec, copybook_dict=copybook_dict)
        filename = f"{_cobol_name_to_python(pgm)}.py"
        out_path = skeletons_dir / filename
        out_path.write_text(code, encoding="utf-8")

        results[pgm] = SkeletonResult(
            program=pgm,
            python_code=code,
            output_path=str(out_path),
            dataclass_count=len(spec.data_contracts),
            method_count=len(spec.paragraphs),
        )

    # Write an __init__.py
    init_lines = [f'"""Auto-generated Python skeletons for {Path(codebase_dir).name} COBOL programs."""', ""]
    for pgm, sr in sorted(results.items()):
        mod = _cobol_name_to_python(pgm)
        cls = _cobol_name_to_class(pgm)
        init_lines.append(f"# from .{mod} import {cls}")
    init_lines.append("")
    (skeletons_dir / "__init__.py").write_text("\n".join(init_lines), encoding="utf-8")

    return results

"""
Language-neutral skeleton IR with pluggable renderers.

Separates structural mapping (spec_to_ir) from language-specific code emission
(PythonRenderer, JavaRenderer, CSharpRenderer).

The IR captures: classes, fields, methods, calls, constants, imports — everything
a renderer needs to emit a valid skeleton in any target language.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from spec_generator import ProgramSpec
from skeleton_generator import (
    _cobol_name_to_python,
    _cobol_name_to_class,
    _pic_to_field_metadata,
    _default_for_type,
)


# ── IR Data Model ───────────────────────────────────────────────────────────


@dataclass
class IRField:
    """A typed field in a class."""
    name: str              # snake_case
    type: str              # language-neutral: "str", "int", "Decimal", class name
    default: str           # default value expression
    metadata: dict = field(default_factory=dict)
    is_optional: bool = False
    is_list: bool = False
    is_constant: bool = False
    constant_value: str = ""
    comment: str = ""


@dataclass
class IRClass:
    """A data class / record / POJO."""
    name: str              # PascalCase
    docstring: str = ""
    fields: list[IRField] = field(default_factory=list)
    is_dataclass: bool = True


@dataclass
class IRMethodCall:
    """A method call or service invocation in a method body."""
    target: str            # method or service name
    call_type: str         # "self", "service", "cics"
    comment: str = ""


@dataclass
class IRMethod:
    """A method (from a COBOL paragraph)."""
    name: str              # snake_case
    docstring: str = ""
    calls: list[IRMethodCall] = field(default_factory=list)
    is_entry_point: bool = False


@dataclass
class IRModule:
    """Complete skeleton module — the language-neutral IR."""
    name: str              # module/file name (snake_case)
    main_class: str        # PascalCase main class name
    docstring: str = ""
    program_type: str = "Batch"  # "Batch" or "CICS Online"
    source_file: str = ""
    dataclasses: list[IRClass] = field(default_factory=list)
    service_stubs: list[IRClass] = field(default_factory=list)
    methods: list[IRMethod] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    constructor_fields: list[IRField] = field(default_factory=list)
    # Metadata for doc headers
    total_lines: int = 0
    code_lines: int = 0
    complexity: int = 0
    complexity_grade: str = ""
    readiness: float = 0.0
    effort_days: float = 0.0
    callers: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)
    files_accessed: list[str] = field(default_factory=list)


# ── Spec → IR conversion ───────────────────────────────────────────────────


def spec_to_ir(spec: ProgramSpec, copybook_dict=None) -> IRModule:
    """Convert a ProgramSpec to a language-neutral IRModule.

    Args:
        spec: The program specification.
        copybook_dict: Optional CopybookDictionary. When provided, each
            DataContract's copybook is looked up and its PIC-typed fields are
            populated into the IRClass.fields list. Without this, dataclass
            bodies are empty (pre-GAP-1 behavior, preserved for backward
            compatibility with tests that don't have a copybook dictionary).
    """
    module_name = _cobol_name_to_python(spec.program)
    class_name = _cobol_name_to_class(spec.program)

    # Dataclasses from copybooks
    dataclasses = []
    for contract in spec.data_contracts:
        dc = IRClass(
            name=_cobol_name_to_class(contract.copybook),
            docstring=f"Data structure from COBOL copybook {contract.copybook}.",
            is_dataclass=True,
        )

        # GAP 1 closure: populate fields from the copybook dictionary.
        # Each field gets a type (str/int/Decimal), a default, and PIC
        # metadata (digits, scale, signed, usage) that renderers use to
        # emit language-specific typed declarations (e.g., CobolDecimal
        # in Java, Decimal in Python).
        if copybook_dict is not None:
            detail = copybook_dict.copybook_detail(contract.copybook)
            if detail:
                for f_info in detail.get("fields", []):
                    level = f_info.get("level", 0)
                    picture = f_info.get("picture")
                    if level == 88:      # skip 88-level conditions
                        continue
                    if picture is None:  # skip group-level (no PIC)
                        continue
                    fname = f_info.get("name", "FILLER")
                    if fname.upper() == "FILLER":  # skip COBOL padding
                        continue

                    # Level-88 conditions → constants
                    if level == 88:
                        conditions = f_info.get("conditions", [])
                        for cond_name, cond_val in conditions:
                            dc.fields.append(IRField(
                                name=_cobol_name_to_python(cond_name),
                                type="str",
                                default=f'"{cond_val}"',
                                is_constant=True,
                                constant_value=cond_val,
                                comment=f"Level-88 condition on {fname}",
                            ))
                        continue

                    py_type, metadata = _pic_to_field_metadata(
                        picture, f_info.get("usage"),
                    )
                    ir_meta = {}
                    if "max_digits" in metadata:
                        ir_meta["digits"] = metadata["max_digits"]
                    if "scale" in metadata:
                        ir_meta["scale"] = metadata["scale"]
                    if "signed" in metadata:
                        ir_meta["signed"] = metadata["signed"]
                    if "usage" in metadata:
                        ir_meta["usage"] = metadata["usage"]
                    if "max_length" in metadata:
                        ir_meta["max_length"] = metadata["max_length"]

                    # OCCURS → List field
                    occurs = f_info.get("occurs")
                    is_list = occurs is not None and occurs > 0

                    # REDEFINES → Optional/union field
                    redefines = f_info.get("redefines")
                    is_optional = redefines is not None

                    if is_list and occurs:
                        ir_meta["occurs"] = occurs
                    if redefines:
                        ir_meta["redefines"] = redefines

                    dc.fields.append(IRField(
                        name=_cobol_name_to_python(f_info["name"]),
                        type=py_type,
                        default=_default_for_type(py_type),
                        metadata=ir_meta,
                        is_list=is_list,
                        is_optional=is_optional,
                        comment=f"REDEFINES {redefines}" if redefines else "",
                    ))

        dataclasses.append(dc)

    # Service stubs from external calls
    external_calls = set()
    for para in spec.paragraphs:
        for call in para.calls:
            if call:
                external_calls.add(call)

    service_stubs = []
    for call in sorted(external_calls):
        stub = IRClass(
            name=_cobol_name_to_class(call) + "Service",
            docstring=f"Stub for external COBOL program {call}.",
            is_dataclass=False,
        )
        stub.fields.append(IRField(
            name="execute",
            type="method",
            default="",
            comment="Call the external program",
        ))
        service_stubs.append(stub)

    # Methods from paragraphs
    methods = []
    for para in spec.paragraphs:
        method = IRMethod(
            name=_cobol_name_to_python(para.name),
            is_entry_point=para.is_entry_point,
        )

        # Docstring parts
        doc_parts = []
        if para.performs:
            doc_parts.append(f"COBOL PERFORMs: {', '.join(para.performs)}")
        if para.calls:
            doc_parts.append(f"COBOL CALLs: {', '.join(para.calls)}")
        if para.cics_ops:
            doc_parts.append(f"CICS: {', '.join(para.cics_ops)}")
        if para.data_flows_out:
            doc_parts.append(f"Writes: {', '.join(para.data_flows_out[:5])}")
        method.docstring = "\n".join(doc_parts)

        # Calls
        for target in para.performs:
            if target:
                method.calls.append(IRMethodCall(
                    target=_cobol_name_to_python(target),
                    call_type="self",
                ))

        for call in para.calls:
            if call:
                method.calls.append(IRMethodCall(
                    target=_cobol_name_to_python(call),
                    call_type="service",
                    comment=f"CALL {call}",
                ))

        for op in para.cics_ops:
            op_name = op.split("(")[0].lower() if "(" in op else op.lower()
            if "send" in op_name or "receive" in op_name:
                comment = "TODO: Replace with API endpoint handler"
            elif "read" in op_name or "write" in op_name:
                comment = "TODO: Replace with database operation"
            elif "xctl" in op_name or "link" in op_name:
                comment = "TODO: Replace with service call"
            else:
                comment = f"CICS {op}"
            method.calls.append(IRMethodCall(
                target=op,
                call_type="cics",
                comment=comment,
            ))

        methods.append(method)

    # Constructor fields
    constructor_fields = []
    for contract in spec.data_contracts:
        constructor_fields.append(IRField(
            name=_cobol_name_to_python(contract.copybook),
            type=_cobol_name_to_class(contract.copybook),
            default="new",
        ))
    for call in sorted(external_calls):
        constructor_fields.append(IRField(
            name=f"_{_cobol_name_to_python(call)}_service",
            type=_cobol_name_to_class(call) + "Service",
            default="new",
        ))
    for vf in (spec.validation_fields or [])[:10]:
        constructor_fields.append(IRField(
            name=_cobol_name_to_python(vf),
            type="str",
            default="''",
        ))

    # Entry points
    entry_points = [_cobol_name_to_python(ep) for ep in (spec.entry_paragraphs or [])]

    return IRModule(
        name=module_name,
        main_class=class_name,
        docstring=f"Modern equivalent of COBOL program {spec.program}.",
        program_type=spec.program_type,
        source_file=spec.source_file,
        dataclasses=dataclasses,
        service_stubs=service_stubs,
        methods=methods,
        entry_points=entry_points,
        constructor_fields=constructor_fields,
        total_lines=spec.total_lines,
        code_lines=spec.code_lines,
        complexity=spec.cyclomatic_complexity,
        complexity_grade=spec.complexity_grade,
        readiness=spec.readiness_score,
        effort_days=spec.effort_days,
        callers=spec.callers or [],
        callees=spec.callees or [],
        files_accessed=spec.files_accessed or [],
    )


# ── Python Renderer ─────────────────────────────────────────────────────────


class PythonRenderer:
    """Render IRModule as Python code (matches existing skeleton_generator output)."""

    def render(self, ir: IRModule) -> str:
        lines = []

        # Module header
        lines.append(f'"""')
        lines.append(f"Modern Python equivalent of COBOL program {ir.main_class}.")
        lines.append(f"")
        lines.append(f"Original: {ir.source_file.replace(chr(92), '/')}")
        lines.append(f"Type: {ir.program_type}")
        lines.append(f"Lines: {ir.code_lines} code / {ir.total_lines} total")
        lines.append(f"Complexity: {ir.complexity} (grade: {ir.complexity_grade})")
        lines.append(f"Readiness: {ir.readiness}/100")
        lines.append(f"Effort estimate: {ir.effort_days} person-days")
        lines.append(f"")
        lines.append(f"Generated by Masquerade COBOL Intelligence Engine.")
        lines.append(f'"""')
        lines.append(f"")
        lines.append(f"from dataclasses import dataclass, field")
        lines.append(f"from decimal import Decimal")
        lines.append(f"from typing import ClassVar, Optional, List")
        if ir.program_type == "CICS Online":
            lines.append(f"# Original CICS program — suggest REST/API framework")
            lines.append(f"# from fastapi import APIRouter, HTTPException")
        else:
            lines.append(f"# Original batch program — suggest scheduled job / CLI")
            lines.append(f"# import argparse")
        lines.append(f"")
        lines.append(f"")

        # Dataclasses
        for dc in ir.dataclasses:
            lines.append(f"@dataclass")
            lines.append(f"class {dc.name}:")
            lines.append(f'    """{dc.docstring}"""')
            if dc.fields:
                for f in dc.fields:
                    lines.append(f"    {f.name}: {f.type} = {f.default}")
            else:
                lines.append(f"    pass")
            lines.append(f"")
            lines.append(f"")

        # Service stubs
        if ir.service_stubs:
            lines.append(f"# --- External service dependencies ---")
            lines.append(f"")
            for stub in ir.service_stubs:
                lines.append(f"class {stub.name}:")
                lines.append(f'    """{stub.docstring}"""')
                lines.append(f"    def execute(self, **kwargs):")
                lines.append(f"        raise NotImplementedError")
                lines.append(f"")
            lines.append(f"")

        # Main class
        lines.append(f"class {ir.main_class}:")
        lines.append(f'    """')
        lines.append(f"    {ir.docstring}")
        lines.append(f"    ")
        if ir.callers:
            lines.append(f"    Called by: {', '.join(ir.callers)}")
        if ir.callees:
            lines.append(f"    Calls: {', '.join(ir.callees)}")
        if ir.files_accessed:
            lines.append(f"    Files: {', '.join(ir.files_accessed)}")
        lines.append(f'    """')
        lines.append(f"")

        # Constructor
        lines.append(f"    def __init__(self):")
        if ir.constructor_fields:
            for cf in ir.constructor_fields:
                if cf.default == "new":
                    lines.append(f"        self.{cf.name} = {cf.type}()")
                else:
                    lines.append(f"        self.{cf.name}: {cf.type} = {cf.default}")
        else:
            lines.append(f"        pass")
        lines.append(f"")

        # Methods
        for method in ir.methods:
            lines.append(f"    def {method.name}(self) -> None:")
            if method.docstring:
                lines.append(f'        """')
                for dl in method.docstring.split("\n"):
                    lines.append(f"        {dl}")
                lines.append(f'        """')
            for call in method.calls:
                if call.call_type == "self":
                    lines.append(f"        self.{call.target}()")
                elif call.call_type == "service":
                    lines.append(f"        # {call.comment}")
                    lines.append(f"        self._{call.target}_service.execute()")
                elif call.call_type == "cics":
                    lines.append(f"        # CICS {call.target}")
                    if call.comment.startswith("TODO"):
                        lines.append(f"        # {call.comment}")
            if not method.calls:
                lines.append(f"        raise NotImplementedError")
            lines.append(f"")

        # Entry point
        lines.append(f"    def run(self) -> None:")
        lines.append(f'        """Main entry point — mirrors PROCEDURE DIVISION."""')
        if ir.entry_points:
            for ep in ir.entry_points[:3]:
                lines.append(f"        self.{ep}()")
        else:
            lines.append(f"        raise NotImplementedError")
        lines.append(f"")

        # Module-level entry
        lines.append(f"")
        lines.append(f'if __name__ == "__main__":')
        lines.append(f"    program = {ir.main_class}()")
        lines.append(f"    program.run()")
        lines.append(f"")

        return "\n".join(lines)


# ── Java Renderer ───────────────────────────────────────────────────────────


_JAVA_RESERVED = frozenset({
    "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
    "class", "const", "continue", "default", "do", "double", "else", "enum",
    "extends", "final", "finally", "float", "for", "goto", "if", "implements",
    "import", "instanceof", "int", "interface", "long", "native", "new",
    "package", "private", "protected", "public", "return", "short", "static",
    "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
    "transient", "try", "void", "volatile", "while", "true", "false", "null",
    "yield", "record", "sealed", "permits", "var",
})


def _escape_java_reserved(ident: str) -> str:
    """Append an underscore to a Java reserved word so it can be used as an identifier."""
    return ident + "_" if ident in _JAVA_RESERVED else ident


def _to_camel_case(snake: str) -> str:
    """Convert snake_case to camelCase, escaping Java reserved words."""
    parts = snake.split("_")
    camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
    return _escape_java_reserved(camel)


def _to_pascal_case(snake: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(p.capitalize() for p in snake.split("_"))


class JavaRenderer:
    """Render IRModule as Java code with Spring Boot conventions."""

    def render(self, ir: IRModule) -> str:
        lines = []
        pkg = ir.name.replace("_", "").lower()

        # Package and imports
        lines.append(f"package com.modernization.{pkg};")
        lines.append(f"")
        lines.append(f"import java.math.BigDecimal;")
        lines.append(f"import java.util.*;")
        if ir.program_type == "CICS Online":
            lines.append(f"import org.springframework.web.bind.annotation.*;")
        lines.append(f"")

        # Header comment
        lines.append(f"/**")
        lines.append(f" * {ir.docstring}")
        lines.append(f" *")
        lines.append(f" * Original: {ir.source_file}")
        lines.append(f" * Type: {ir.program_type}")
        lines.append(f" * Lines: {ir.code_lines} code / {ir.total_lines} total")
        lines.append(f" * Generated by Masquerade COBOL Intelligence Engine.")
        lines.append(f" */")
        lines.append(f"")

        # Data classes
        for dc in ir.dataclasses:
            lines.append(f"/** {dc.docstring} */")
            lines.append(f"public class {dc.name} {{")
            if dc.fields:
                for f in dc.fields:
                    jtype = self._java_type(f.type)
                    lines.append(f"    private {jtype} {_to_camel_case(f.name)};")
            lines.append(f"}}")
            lines.append(f"")

        # Service stubs
        for stub in ir.service_stubs:
            lines.append(f"/** {stub.docstring} */")
            lines.append(f"public class {stub.name} {{")
            lines.append(f"    public void execute() {{")
            lines.append(f"        throw new UnsupportedOperationException();")
            lines.append(f"    }}")
            lines.append(f"}}")
            lines.append(f"")

        # Main class
        if ir.program_type == "CICS Online":
            lines.append(f"@RestController")
        lines.append(f"public class {ir.main_class} {{")
        lines.append(f"")

        # Fields
        for cf in ir.constructor_fields:
            jtype = cf.type
            jname = _to_camel_case(cf.name.lstrip("_"))
            if cf.default == "new":
                lines.append(f"    private {jtype} {jname} = new {jtype}();")
            else:
                jtype_f = self._java_type(cf.type)
                lines.append(f"    private {jtype_f} {jname} = {self._java_default(cf.type)};")
        lines.append(f"")

        # Methods
        for method in ir.methods:
            jmethod = _to_camel_case(method.name)
            lines.append(f"    /**")
            if method.docstring:
                for dl in method.docstring.split("\n"):
                    lines.append(f"     * {dl}")
            lines.append(f"     */")
            lines.append(f"    public void {jmethod}() {{")
            for call in method.calls:
                if call.call_type == "self":
                    lines.append(f"        this.{_to_camel_case(call.target)}();")
                elif call.call_type == "service":
                    svc = _to_camel_case(call.target.lstrip("_"))
                    lines.append(f"        // {call.comment}")
                    lines.append(f"        this.{svc}Service.execute();")
                elif call.call_type == "cics":
                    lines.append(f"        // CICS {call.target}")
                    if call.comment.startswith("TODO"):
                        lines.append(f"        // {call.comment}")
            if not method.calls:
                lines.append(f"        throw new UnsupportedOperationException();")
            lines.append(f"    }}")
            lines.append(f"")

        # run() entry point
        lines.append(f"    public void run() {{")
        for ep in ir.entry_points[:3]:
            lines.append(f"        this.{_to_camel_case(ep)}();")
        if not ir.entry_points:
            lines.append(f"        throw new UnsupportedOperationException();")
        lines.append(f"    }}")
        lines.append(f"")

        # main method
        lines.append(f"    public static void main(String[] args) {{")
        lines.append(f"        {ir.main_class} program = new {ir.main_class}();")
        lines.append(f"        program.run();")
        lines.append(f"    }}")

        lines.append(f"}}")
        lines.append(f"")
        return "\n".join(lines)

    def _java_type(self, t: str) -> str:
        return {"str": "String", "int": "int", "Decimal": "BigDecimal"}.get(t, t)

    def _java_default(self, t: str) -> str:
        return {"str": '""', "int": "0", "Decimal": "BigDecimal.ZERO"}.get(t, "null")

    # ── render_module: full Maven project emission (W3) ─────────────────

    # The methods below produce a complete Maven module instead of a single
    # concatenated .java file. The original render() above is preserved for
    # backwards compatibility with test_multi_language.py and any caller that
    # wants the legacy single-string output.
    #
    # Numeric fields use the project's own CobolDecimal class (the W1 Java
    # port of cobol_decimal.py) instead of raw BigDecimal — per OD-6 in the
    # PRD, explicit CobolDecimal fields rather than annotation+AOP magic.

    COBOL_DECIMAL_FQN = "com.modernization.masquerade.cobol.CobolDecimal"
    COBOL_DECIMAL_VERSION = "0.1.0-SNAPSHOT"

    def render_module(
        self,
        ir: "IRModule",
        codebase: str = "generated",
    ) -> dict:
        """Render an IRModule as a complete Maven module.

        Returns a dict mapping relative file paths (under the module root) to
        UTF-8 file contents. Generation is deterministic — the same input
        produces byte-identical output across runs.

        Caller writes them to disk via :meth:`write_module` or directly. The
        emitted layout is::

            <module_root>/
              pom.xml
              src/main/java/com/modernization/<codebase>/<program>/
                Main.java
                dto/<DataClass>.java        (one per IR dataclass)
                service/<Stub>.java         (one per IR service stub)
                controller/<Program>Controller.java  (CICS Online only)
        """
        files = {}
        pkg = self._java_package(codebase, ir.name)
        pkg_path = pkg.replace(".", "/")
        is_cics = ir.program_type == "CICS Online"

        files["pom.xml"] = self._render_pom(ir, codebase, is_cics)
        files[f"src/main/java/{pkg_path}/Main.java"] = self._render_main_class(
            ir, pkg, is_cics,
        )

        for dc in ir.dataclasses:
            files[f"src/main/java/{pkg_path}/dto/{dc.name}.java"] = self._render_dto(
                dc, pkg + ".dto",
            )

        for stub in ir.service_stubs:
            files[f"src/main/java/{pkg_path}/service/{stub.name}.java"] = (
                self._render_service(stub, pkg + ".service")
            )

        if is_cics:
            controller_name = ir.main_class + "Controller"
            files[
                f"src/main/java/{pkg_path}/controller/{controller_name}.java"
            ] = self._render_controller(ir, pkg + ".controller", pkg)

        return files

    def write_module(
        self,
        ir: "IRModule",
        output_dir,
        codebase: str = "generated",
    ):
        """Write the rendered module to disk under output_dir. Returns the path."""
        from pathlib import Path as _Path

        out = _Path(output_dir)
        files = self.render_module(ir, codebase)
        for rel_path, contents in files.items():
            full_path = out / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(contents, encoding="utf-8")
        return out

    # ── render_module helpers ───────────────────────────────────────────

    @staticmethod
    def _java_package(codebase: str, module_name: str) -> str:
        """Build a stable Java package name for a generated module."""
        clean_codebase = "".join(c for c in codebase.lower() if c.isalnum() or c == "_")
        clean_module = "".join(c for c in module_name.lower() if c.isalnum() or c == "_")
        return f"com.modernization.{clean_codebase}.{clean_module}"

    def _render_pom(self, ir: "IRModule", codebase: str, is_cics: bool) -> str:
        """pom.xml for the generated module.

        Depends on the cobol-decimal artifact. The cobol-decimal module must be
        installed locally first via `mvn install -pl pipeline/reimpl/java/cobol-decimal/`.
        For CICS programs, also pulls in spring-boot-starter-web for the
        @RestController class.
        """
        artifact_id = ir.name.replace("_", "-")
        spring_block = ""
        if is_cics:
            spring_block = """
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
            <version>3.2.5</version>
        </dependency>
"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.modernization.{codebase.lower()}</groupId>
    <artifactId>{artifact_id}</artifactId>
    <version>0.1.0-SNAPSHOT</version>
    <packaging>jar</packaging>

    <name>{ir.main_class} (Java reimplementation)</name>
    <description>
        Modern Java equivalent of COBOL program {ir.main_class}.
        Original source: {ir.source_file}
        Type: {ir.program_type}
        Generated by Masquerade COBOL Intelligence Engine.
    </description>

    <properties>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
        <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    </properties>

    <dependencies>
        <dependency>
            <groupId>com.modernization.masquerade</groupId>
            <artifactId>cobol-decimal</artifactId>
            <version>{self.COBOL_DECIMAL_VERSION}</version>
        </dependency>{spring_block}    </dependencies>
</project>
"""

    def _render_main_class(self, ir: "IRModule", pkg: str, is_cics: bool) -> str:
        lines = []
        lines.append(f"package {pkg};")
        lines.append("")
        lines.append(f"import {self.COBOL_DECIMAL_FQN};")
        if ir.dataclasses:
            lines.append(f"import {pkg}.dto.*;")
        if ir.service_stubs:
            lines.append(f"import {pkg}.service.*;")
        lines.append("")

        # Header comment
        lines.append("/**")
        lines.append(f" * Modern Java equivalent of COBOL program {ir.main_class}.")
        lines.append(" *")
        lines.append(f" * Original: {ir.source_file.replace(chr(92), '/')}")
        lines.append(f" * Type: {ir.program_type}")
        lines.append(f" * Lines: {ir.code_lines} code / {ir.total_lines} total")
        if ir.complexity:
            lines.append(f" * Complexity: {ir.complexity} (grade: {ir.complexity_grade})")
        if ir.readiness:
            lines.append(f" * Readiness: {ir.readiness}/100")
        lines.append(" *")
        lines.append(" * Generated by Masquerade COBOL Intelligence Engine.")
        lines.append(" */")
        lines.append(f"public class Main {{")
        lines.append("")

        # Constructor fields
        for cf in ir.constructor_fields:
            jname = _to_camel_case(cf.name.lstrip("_"))
            if cf.default == "new":
                lines.append(f"    private final {cf.type} {jname} = new {cf.type}();")
            elif cf.type == "Decimal":
                # Use CobolDecimal with default PIC; metadata-driven precision
                # comes once spec_to_ir populates IRField.metadata from the
                # copybook dictionary (see review point R4).
                d = cf.metadata.get("digits", 9) if cf.metadata else 9
                s = cf.metadata.get("scale", 0) if cf.metadata else 0
                signed = cf.metadata.get("signed", True) if cf.metadata else True
                lines.append(
                    f"    private final CobolDecimal {jname} = "
                    f"new CobolDecimal({d}, {s}, {str(signed).lower()});"
                )
            else:
                jtype = self._java_type(cf.type)
                default = self._java_default(cf.type)
                lines.append(f"    private {jtype} {jname} = {default};")
        if ir.constructor_fields:
            lines.append("")

        # Methods (paragraphs)
        for method in ir.methods:
            jmethod = _to_camel_case(method.name)
            lines.append("    /**")
            if method.docstring:
                for dl in method.docstring.split("\n"):
                    lines.append(f"     * {dl}")
            else:
                lines.append(f"     * COBOL paragraph {method.name.upper()}")
            lines.append("     */")
            lines.append(f"    public void {jmethod}() {{")
            for call in method.calls:
                if call.call_type == "self":
                    lines.append(f"        this.{_to_camel_case(call.target)}();")
                elif call.call_type == "service":
                    svc = _to_camel_case(call.target.lstrip("_"))
                    if call.comment:
                        lines.append(f"        // {call.comment}")
                    lines.append(f"        // TODO: invoke {svc} service")
                elif call.call_type == "cics":
                    lines.append(f"        // CICS {call.target}")
                    if call.comment.startswith("TODO"):
                        lines.append(f"        // {call.comment}")
            if not method.calls:
                lines.append(
                    '        throw new UnsupportedOperationException('
                    '"TODO: implement ' + method.name + '");'
                )
            lines.append("    }")
            lines.append("")

        # run() entry point — mirrors PROCEDURE DIVISION top-level
        lines.append("    /** Main entry point — mirrors PROCEDURE DIVISION. */")
        lines.append("    public void run() {")
        if ir.entry_points:
            for ep in ir.entry_points[:3]:
                lines.append(f"        this.{_to_camel_case(ep)}();")
        else:
            lines.append(
                '        throw new UnsupportedOperationException('
                '"No entry point identified");'
            )
        lines.append("    }")
        lines.append("")

        # main() so the JAR is executable
        lines.append("    public static void main(String[] args) {")
        lines.append("        new Main().run();")
        lines.append("    }")
        lines.append("}")
        lines.append("")
        return "\n".join(lines)

    def _render_dto(self, dc: "IRClass", pkg: str) -> str:
        """Render a DTO class for a copybook record with typed fields,
        getters/setters, OCCURS arrays, REDEFINES comments, and level-88
        constants.
        """
        lines = []
        lines.append(f"package {pkg};")
        lines.append("")
        lines.append(f"import {self.COBOL_DECIMAL_FQN};")
        has_list = any(f.is_list for f in dc.fields)
        if has_list:
            lines.append("import java.util.ArrayList;")
            lines.append("import java.util.List;")
        lines.append("")
        lines.append("/**")
        lines.append(f" * {dc.docstring}")
        regular = [f for f in dc.fields if not f.is_constant]
        constants = [f for f in dc.fields if f.is_constant]
        if regular:
            lines.append(f" * {len(regular)} fields extracted from PIC clauses.")
        if constants:
            lines.append(f" * {len(constants)} level-88 condition constants.")
        if not regular and not constants:
            lines.append(" * No PIC fields found (copybook may not have been parsed).")
        lines.append(" */")
        lines.append(f"public class {dc.name} {{")

        # Level-88 constants
        for f in constants:
            if f.comment:
                lines.append(f"    /** {f.comment} */")
            safe_val = f.constant_value.replace('"', '\\"')
            lines.append(
                f'    public static final String {f.name.upper()} = "{safe_val}";'
            )
        if constants:
            lines.append("")

        # Fields
        for f in regular:
            jname = _to_camel_case(f.name)
            if f.comment:
                lines.append(f"    /** {f.comment} */")

            if f.is_list:
                # OCCURS array
                elem_type = self._java_type(f.type)
                if f.type == "Decimal":
                    elem_type = "CobolDecimal"
                occurs = f.metadata.get("occurs", 1) if f.metadata else 1
                lines.append(
                    f"    private List<{self._java_boxed(f.type)}> {jname} "
                    f"= new ArrayList<>({occurs});"
                )
            elif f.type == "Decimal":
                d = f.metadata.get("digits", 9) if f.metadata else 9
                s = f.metadata.get("scale", 0) if f.metadata else 0
                signed = f.metadata.get("signed", True) if f.metadata else True
                lines.append(
                    f"    private CobolDecimal {jname} = "
                    f"new CobolDecimal({d}, {s}, {str(signed).lower()});"
                )
            else:
                jtype = self._java_type(f.type)
                default = self._java_default(f.type)
                lines.append(f"    private {jtype} {jname} = {default};")

        # Getters and setters
        if regular:
            lines.append("")
        for f in regular:
            jname = _to_camel_case(f.name)
            cap = jname[0].upper() + jname[1:] if jname else ""

            if f.is_list:
                ret_type = f"List<{self._java_boxed(f.type)}>"
                lines.append(f"    public {ret_type} get{cap}() {{ return {jname}; }}")
                lines.append(
                    f"    public void set{cap}({ret_type} value) {{ this.{jname} = value; }}"
                )
            elif f.type == "Decimal":
                lines.append(f"    public CobolDecimal get{cap}() {{ return {jname}; }}")
                lines.append(
                    f"    public void set{cap}(CobolDecimal value) {{ this.{jname} = value; }}"
                )
            else:
                jtype = self._java_type(f.type)
                lines.append(f"    public {jtype} get{cap}() {{ return {jname}; }}")
                lines.append(
                    f"    public void set{cap}({jtype} value) {{ this.{jname} = value; }}"
                )

        lines.append("}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _java_boxed(t: str) -> str:
        """Return the boxed Java type for use in generics (List<Integer> not List<int>)."""
        return {"str": "String", "int": "Integer", "Decimal": "CobolDecimal"}.get(t, t)

    def _render_service(self, stub: "IRClass", pkg: str) -> str:
        lines = []
        lines.append(f"package {pkg};")
        lines.append("")
        lines.append("/**")
        lines.append(f" * {stub.docstring}")
        lines.append(" *")
        lines.append(" * Stub for an external program reference. Replace the body of")
        lines.append(" * execute() with the real call when the dependency is reimplemented.")
        lines.append(" */")
        lines.append(f"public class {stub.name} {{")
        lines.append("    public void execute() {")
        lines.append(
            '        throw new UnsupportedOperationException("TODO: integrate dependency");'
        )
        lines.append("    }")
        lines.append("}")
        lines.append("")
        return "\n".join(lines)

    def _render_controller(self, ir: "IRModule", pkg: str, main_pkg: str) -> str:
        """Spring REST controller for a CICS Online program.

        BMS map → REST endpoint mapping is left as a stub — that work lives in
        the api_contract_mapper Java emitter (W5).
        """
        controller_name = ir.main_class + "Controller"
        lines = []
        lines.append(f"package {pkg};")
        lines.append("")
        lines.append("import org.springframework.web.bind.annotation.RestController;")
        lines.append("import org.springframework.web.bind.annotation.RequestMapping;")
        lines.append("import org.springframework.web.bind.annotation.PostMapping;")
        lines.append(f"import {main_pkg}.Main;")
        lines.append("")
        lines.append("/**")
        lines.append(f" * REST controller stub for CICS Online program {ir.main_class}.")
        lines.append(" *")
        lines.append(" * BMS screen → endpoint mapping is generated by the api_contract_mapper")
        lines.append(" * Java emitter (W5). Until that lands, this is a placeholder that")
        lines.append(" * delegates to Main.run().")
        lines.append(" */")
        lines.append("@RestController")
        lines.append(f'@RequestMapping("/{ir.name.lower()}")')
        lines.append(f"public class {controller_name} {{")
        lines.append("")
        lines.append("    private final Main program = new Main();")
        lines.append("")
        lines.append('    @PostMapping("/run")')
        lines.append("    public String run() {")
        lines.append("        program.run();")
        lines.append('        return "OK";')
        lines.append("    }")
        lines.append("}")
        lines.append("")
        return "\n".join(lines)


# ── C# Renderer ─────────────────────────────────────────────────────────────


class CSharpRenderer:
    """Render IRModule as C# code with .NET conventions."""

    def render(self, ir: IRModule) -> str:
        lines = []
        ns = _to_pascal_case(ir.name)

        # Usings
        lines.append(f"using System;")
        lines.append(f"using System.Collections.Generic;")
        if ir.program_type == "CICS Online":
            lines.append(f"using Microsoft.AspNetCore.Mvc;")
        lines.append(f"")

        # Header comment
        lines.append(f"/// <summary>")
        lines.append(f"/// {ir.docstring}")
        lines.append(f"///")
        lines.append(f"/// Original: {ir.source_file}")
        lines.append(f"/// Type: {ir.program_type}")
        lines.append(f"/// Generated by Masquerade COBOL Intelligence Engine.")
        lines.append(f"/// </summary>")

        # Namespace
        lines.append(f"namespace Modernization.{ns}")
        lines.append(f"{{")

        # Data classes as records
        for dc in ir.dataclasses:
            lines.append(f"    /// <summary>{dc.docstring}</summary>")
            lines.append(f"    public record {dc.name}")
            lines.append(f"    {{")
            if dc.fields:
                for f in dc.fields:
                    cstype = self._cs_type(f.type)
                    lines.append(f"        public {cstype} {_to_pascal_case(f.name)} {{ get; set; }}")
            lines.append(f"    }}")
            lines.append(f"")

        # Service stubs
        for stub in ir.service_stubs:
            lines.append(f"    /// <summary>{stub.docstring}</summary>")
            lines.append(f"    public class {stub.name}")
            lines.append(f"    {{")
            lines.append(f"        public void Execute()")
            lines.append(f"        {{")
            lines.append(f"            throw new NotImplementedException();")
            lines.append(f"        }}")
            lines.append(f"    }}")
            lines.append(f"")

        # Main class
        if ir.program_type == "CICS Online":
            lines.append(f"    [ApiController]")
        lines.append(f"    public class {ir.main_class}")
        lines.append(f"    {{")

        # Fields
        for cf in ir.constructor_fields:
            csname = _to_pascal_case(cf.name.lstrip("_"))
            if cf.default == "new":
                lines.append(f"        private {cf.type} {csname} = new {cf.type}();")
            else:
                cstype = self._cs_type(cf.type)
                lines.append(f"        private {cstype} {csname} = {self._cs_default(cf.type)};")
        lines.append(f"")

        # Methods
        for method in ir.methods:
            csmethod = _to_pascal_case(method.name)
            if method.docstring:
                lines.append(f"        /// <summary>")
                for dl in method.docstring.split("\n"):
                    lines.append(f"        /// {dl}")
                lines.append(f"        /// </summary>")
            lines.append(f"        public void {csmethod}()")
            lines.append(f"        {{")
            for call in method.calls:
                if call.call_type == "self":
                    lines.append(f"            this.{_to_pascal_case(call.target)}();")
                elif call.call_type == "service":
                    svc = _to_pascal_case(call.target.lstrip("_"))
                    lines.append(f"            // {call.comment}")
                    lines.append(f"            this.{svc}Service.Execute();")
                elif call.call_type == "cics":
                    lines.append(f"            // CICS {call.target}")
                    if call.comment.startswith("TODO"):
                        lines.append(f"            // {call.comment}")
            if not method.calls:
                lines.append(f"            throw new NotImplementedException();")
            lines.append(f"        }}")
            lines.append(f"")

        # Run entry point
        lines.append(f"        public void Run()")
        lines.append(f"        {{")
        for ep in ir.entry_points[:3]:
            lines.append(f"            this.{_to_pascal_case(ep)}();")
        if not ir.entry_points:
            lines.append(f"            throw new NotImplementedException();")
        lines.append(f"        }}")
        lines.append(f"")

        # Main
        lines.append(f"        public static void Main(string[] args)")
        lines.append(f"        {{")
        lines.append(f"            var program = new {ir.main_class}();")
        lines.append(f"            program.Run();")
        lines.append(f"        }}")

        lines.append(f"    }}")  # close class
        lines.append(f"}}")  # close namespace
        lines.append(f"")
        return "\n".join(lines)

    def _cs_type(self, t: str) -> str:
        return {"str": "string", "int": "int", "Decimal": "decimal"}.get(t, t)

    def _cs_default(self, t: str) -> str:
        return {"str": '""', "int": "0", "Decimal": "0m"}.get(t, "null")

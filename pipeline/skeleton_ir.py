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
from skeleton_generator import _cobol_name_to_python, _cobol_name_to_class


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


def spec_to_ir(spec: ProgramSpec) -> IRModule:
    """Convert a ProgramSpec to a language-neutral IRModule."""
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


def _to_camel_case(snake: str) -> str:
    """Convert snake_case to camelCase."""
    parts = snake.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


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

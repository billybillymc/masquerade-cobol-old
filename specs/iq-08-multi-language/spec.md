# IQ-08: Multi-Language Skeleton Support — Design Specification

**Status**: In Progress
**Created**: 2026-03-15

---

## Problem Statement

`skeleton_generator.py` is hardcoded to Python. Most COBOL shops target Java
(Spring Boot) or C# (.NET). The structural mapping logic is language-independent
but currently emits Python syntax directly.

---

## Design Decisions

### DD-01: Language-neutral SkeletonIR
IRModule → IRClass (dataclasses) + IRMethod (paragraphs) + IRField (typed fields).
`spec_to_ir()` produces the IR; renderers consume it.

### DD-02: PythonRenderer — refactored current behavior
Identical output to current `generate_skeleton()`.

### DD-03: JavaRenderer — Spring Boot conventions
@Data for data classes, @RestController for CICS, package declaration.

### DD-04: CSharpRenderer — .NET conventions
record types for data, [ApiController] for CICS, namespace.

### DD-05: Structural validity checks instead of compilation
Matching braces, required keywords, no cross-language leaks.

---

## New module: `pipeline/skeleton_ir.py`
## Test file: `pipeline/tests/test_multi_language.py`

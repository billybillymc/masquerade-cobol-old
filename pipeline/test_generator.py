"""
Test case generator — produces pytest test stubs from COBOL program specs
and Python skeletons. No API keys required.

Generates test scenarios based on:
- Data flow analysis (fields read/written)
- Paragraph structure (entry/exit points)
- Validation fields (status codes, return codes)
- CICS operations (screen I/O, file access)
- External calls (service dependencies requiring mocks)
- Complexity hotspots
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from spec_generator import ProgramSpec, generate_program_spec, _load_program_data
from skeleton_generator import _cobol_name_to_python, _cobol_name_to_class
from graph_context import GraphIndex


@dataclass
class GeneratedTestCase:
    name: str
    category: str  # "init", "happy_path", "validation", "boundary", "error", "integration"
    description: str
    setup: list[str]
    assertions: list[str]
    mocks: list[str]


@dataclass
class TestSuiteResult:
    program: str
    test_code: str
    output_path: str
    test_count: int


def _generate_init_tests(spec: ProgramSpec) -> list[GeneratedTestCase]:
    """Tests that the program class can be instantiated."""
    tests = [GeneratedTestCase(
        name="test_can_instantiate",
        category="init",
        description=f"{spec.program} can be created without errors",
        setup=[],
        assertions=[f"assert program is not None"],
        mocks=[],
    )]
    if spec.data_contracts:
        for c in spec.data_contracts[:3]:
            attr = _cobol_name_to_python(c.copybook)
            tests.append(GeneratedTestCase(
                name=f"test_has_{attr}_data_structure",
                category="init",
                description=f"Program has {c.copybook} data structure initialized",
                setup=[],
                assertions=[f"assert hasattr(program, '{attr}')"],
                mocks=[],
            ))
    return tests


def _generate_paragraph_tests(spec: ProgramSpec) -> list[GeneratedTestCase]:
    """Tests for each paragraph method's existence and callability."""
    tests = []
    for para in spec.paragraphs:
        method = _cobol_name_to_python(para.name)
        tests.append(GeneratedTestCase(
            name=f"test_{method}_exists",
            category="happy_path",
            description=f"Method {method} exists (from paragraph {para.name})",
            setup=[],
            assertions=[f"assert hasattr(program, '{method}')", f"assert callable(getattr(program, '{method}'))"],
            mocks=[],
        ))
    return tests


def _generate_validation_tests(spec: ProgramSpec) -> list[GeneratedTestCase]:
    """Tests for validation/status fields."""
    tests = []
    for vf in spec.validation_fields:
        attr = _cobol_name_to_python(vf)
        tests.append(GeneratedTestCase(
            name=f"test_{attr}_default",
            category="validation",
            description=f"Validation field {vf} has expected default",
            setup=[],
            assertions=[f"assert program.{attr} == ''", f"# TODO: verify correct default for {vf}"],
            mocks=[],
        ))
        tests.append(GeneratedTestCase(
            name=f"test_{attr}_invalid_input",
            category="error",
            description=f"Setting {vf} to invalid value is handled",
            setup=[f"program.{attr} = 'INVALID'"],
            assertions=[f"# TODO: assert error handling for invalid {vf}"],
            mocks=[],
        ))
    return tests


def _generate_call_mock_tests(spec: ProgramSpec) -> list[GeneratedTestCase]:
    """Tests with mocked external service dependencies."""
    tests = []
    external_calls = set()
    for para in spec.paragraphs:
        for call in para.calls:
            if call:
                external_calls.add(call)

    for call in sorted(external_calls):
        svc = _cobol_name_to_python(call)
        svc_class = _cobol_name_to_class(call) + "Service"
        tests.append(GeneratedTestCase(
            name=f"test_{svc}_service_called",
            category="integration",
            description=f"External program {call} is invoked",
            setup=[],
            assertions=[f"mock_{svc}.execute.assert_called()"],
            mocks=[f"mock_{svc} = MagicMock(spec={svc_class})", f"program._{svc}_service = mock_{svc}"],
        ))

    return tests


def _generate_cics_tests(spec: ProgramSpec) -> list[GeneratedTestCase]:
    """Tests for CICS operations."""
    tests = []
    has_send = any("SEND" in op.upper() for para in spec.paragraphs for op in para.cics_ops)
    has_receive = any("RECEIVE" in op.upper() for para in spec.paragraphs for op in para.cics_ops)
    has_read = any("READ" in op.upper() and "RECEIVE" not in op.upper() for para in spec.paragraphs for op in para.cics_ops)

    if has_send:
        tests.append(GeneratedTestCase(
            name="test_screen_output_generated",
            category="integration",
            description="Program produces screen output (CICS SEND MAP)",
            setup=[],
            assertions=["# TODO: assert API response or template render"],
            mocks=[],
        ))
    if has_receive:
        tests.append(GeneratedTestCase(
            name="test_screen_input_processed",
            category="happy_path",
            description="Program processes screen input (CICS RECEIVE MAP)",
            setup=["# TODO: provide mock screen input data"],
            assertions=["# TODO: assert correct processing of input"],
            mocks=[],
        ))
    if has_read:
        tests.append(GeneratedTestCase(
            name="test_file_read_success",
            category="happy_path",
            description="Program reads file/record successfully",
            setup=["# TODO: mock file/database read"],
            assertions=["# TODO: assert record data populated"],
            mocks=[],
        ))
        tests.append(GeneratedTestCase(
            name="test_file_read_not_found",
            category="error",
            description="Program handles record not found",
            setup=["# TODO: mock file/database read returning not-found"],
            assertions=["# TODO: assert error handling for missing record"],
            mocks=[],
        ))

    return tests


def _generate_entry_exit_tests(spec: ProgramSpec) -> list[GeneratedTestCase]:
    """Tests for the main run() method."""
    tests = [GeneratedTestCase(
        name="test_run_method_exists",
        category="happy_path",
        description="Program has a run() entry point",
        setup=[],
        assertions=["assert hasattr(program, 'run')", "assert callable(program.run)"],
        mocks=[],
    )]

    if spec.callees:
        mocks = []
        for call in spec.callees[:5]:
            svc = _cobol_name_to_python(call)
            mocks.append(f"program._{svc}_service = MagicMock()")
        tests.append(GeneratedTestCase(
            name="test_run_completes_with_mocked_deps",
            category="integration",
            description="Full program run completes with dependencies mocked",
            setup=mocks,
            assertions=["# TODO: program.run() should complete without error"],
            mocks=[],
        ))

    return tests


def _generate_behavioral_tests(
    spec: ProgramSpec,
    program_data: dict,
) -> list[GeneratedTestCase]:
    """Generate behavioral tests from conditional blocks (IQ-01) and business rules (IQ-04).

    Each leaf branch in the decision tree produces a test scenario with:
    - Setup: field values that trigger the branch
    - Assertions: data flow targets + service calls from the branch body
    """
    tests = []

    for para in program_data.get("paragraphs", []):
        para_name = para.get("name", "")
        method_name = _cobol_name_to_python(para_name)
        blocks = para.get("conditional_blocks", [])

        for block in blocks:
            stmt_type = block.get("stmt_type", "")

            if stmt_type == "EVALUATE":
                subjects = block.get("subjects", [])
                subject_snake = "_".join(_cobol_name_to_python(s) for s in subjects)

                for branch in block.get("branches", []):
                    conditions = branch.get("conditions", [])
                    cond_label = "_".join(
                        str(c).lower().replace(" ", "_").replace("'", "")
                        for c in conditions
                    )
                    body = branch.get("body", [])

                    # Extract actions from branch body
                    moves, cics_ops, performs, nested_ifs = _extract_body_actions(body)

                    if nested_ifs:
                        # Generate separate tests for each nested IF branch
                        for nif in nested_ifs:
                            nif_cond = nif.get("condition", {})
                            raw_text = nif_cond.get("raw_text", "") if isinstance(nif_cond, dict) else ""
                            is_88 = nif_cond.get("is_88_condition", False) if isinstance(nif_cond, dict) else False

                            # THEN branch
                            then_moves, then_cics, then_performs, _ = _extract_body_actions(
                                nif.get("then_body", [])
                            )
                            then_label = _condition_label(nif_cond, positive=True)
                            test_name = f"test_{method_name}_{subject_snake}_{cond_label}_{then_label}"
                            test_name = _sanitize_test_name(test_name)

                            setup, assertions = _build_scenario(
                                subjects, conditions, nif_cond, positive=True,
                                moves=moves + then_moves,
                                cics_ops=then_cics,
                                performs=then_performs,
                            )
                            desc = _build_description(
                                para_name, subjects, conditions, raw_text,
                                positive=True, is_88=is_88,
                                then_moves=then_moves, then_cics=then_cics,
                            )

                            tests.append(GeneratedTestCase(
                                name=test_name,
                                category="happy_path" if cond_label == "0" else "decision_branch",
                                description=desc,
                                setup=setup,
                                assertions=assertions,
                                mocks=[],
                            ))

                            # ELSE branch (if exists)
                            else_body = nif.get("else_body", [])
                            if else_body:
                                else_moves, else_cics, else_performs, _ = _extract_body_actions(else_body)
                                else_label = _condition_label(nif_cond, positive=False)
                                test_name_else = f"test_{method_name}_{subject_snake}_{cond_label}_{else_label}"
                                test_name_else = _sanitize_test_name(test_name_else)

                                setup_e, assertions_e = _build_scenario(
                                    subjects, conditions, nif_cond, positive=False,
                                    moves=else_moves,
                                    cics_ops=else_cics,
                                    performs=else_performs,
                                )
                                desc_e = _build_description(
                                    para_name, subjects, conditions, raw_text,
                                    positive=False, is_88=is_88,
                                    then_moves=else_moves, then_cics=else_cics,
                                )

                                tests.append(GeneratedTestCase(
                                    name=test_name_else,
                                    category="error_path",
                                    description=desc_e,
                                    setup=setup_e,
                                    assertions=assertions_e,
                                    mocks=[],
                                ))
                    else:
                        # Simple branch — no nested IFs
                        test_name = f"test_{method_name}_{subject_snake}_{cond_label}"
                        test_name = _sanitize_test_name(test_name)

                        setup = [f"# Set {', '.join(subjects)} = {', '.join(str(c) for c in conditions)}"]
                        assertions = _assertions_from_actions(moves, cics_ops, performs)

                        # Describe what the branch does
                        action_desc = _summarize_actions(moves, cics_ops, performs)
                        if cond_label == "other":
                            desc = f"{para_name}: default branch — {action_desc}"
                            category = "error_path"
                        elif cond_label == "13":
                            desc = f"{para_name}: user not found (RESP 13) — {action_desc}"
                            category = "error_path"
                        else:
                            desc = f"{para_name}: {', '.join(subjects)}={', '.join(str(c) for c in conditions)} — {action_desc}"
                            category = "decision_branch"

                        tests.append(GeneratedTestCase(
                            name=test_name,
                            category=category,
                            description=desc,
                            setup=setup,
                            assertions=assertions,
                            mocks=[],
                        ))

            elif stmt_type == "IF":
                condition = block.get("condition", {})
                raw_text = condition.get("raw_text", "") if isinstance(condition, dict) else ""
                then_body = block.get("then_body", [])
                else_body = block.get("else_body", [])

                then_moves, then_cics, then_performs, _ = _extract_body_actions(then_body)
                then_label = _condition_label(condition, positive=True)
                test_name = f"test_{method_name}_when_{then_label}"
                test_name = _sanitize_test_name(test_name)

                setup = [f"# Set condition: {raw_text}"]
                assertions = _assertions_from_actions(then_moves, then_cics, then_performs)

                tests.append(GeneratedTestCase(
                    name=test_name,
                    category="decision_branch",
                    description=f"{para_name}: when {raw_text} — then branch",
                    setup=setup,
                    assertions=assertions,
                    mocks=[],
                ))

                if else_body:
                    else_moves, else_cics, else_performs, _ = _extract_body_actions(else_body)
                    else_label = _condition_label(condition, positive=False)
                    test_name_else = f"test_{method_name}_when_{else_label}"
                    test_name_else = _sanitize_test_name(test_name_else)

                    setup_e = [f"# Set condition NOT: {raw_text}"]
                    assertions_e = _assertions_from_actions(else_moves, else_cics, else_performs)

                    tests.append(GeneratedTestCase(
                        name=test_name_else,
                        category="error_path",
                        description=f"{para_name}: when NOT {raw_text} — else branch",
                        setup=setup_e,
                        assertions=assertions_e,
                        mocks=[],
                    ))

    return tests


def _extract_body_actions(body: list[dict]) -> tuple[list, list, list, list]:
    """Extract MOVEs, CICS ops, PERFORMs, and nested IFs from a statement body."""
    moves = []
    cics_ops = []
    performs = []
    nested_ifs = []
    for stmt in body:
        st = stmt.get("stmt_type", "")
        raw = stmt.get("raw", "")
        if st == "MOVE":
            moves.append(raw)
        elif st == "CICS":
            cics_ops.append(raw)
        elif st == "PERFORM":
            target = stmt.get("target", raw)
            performs.append(target)
        elif st == "IF":
            nested_ifs.append(stmt)
    return moves, cics_ops, performs, nested_ifs


def _condition_label(condition: dict, positive: bool) -> str:
    """Create a short label from a condition for test naming."""
    if not isinstance(condition, dict):
        return "condition" if positive else "not_condition"
    left = condition.get("left", "")
    is_88 = condition.get("is_88_condition", False)
    label = _cobol_name_to_python(left) if left else "condition"
    if is_88:
        return label if positive else f"not_{label}"
    right = condition.get("right", "")
    op = condition.get("operator", "=")
    if positive:
        return f"{_cobol_name_to_python(left)}_match" if right else label
    else:
        return f"{_cobol_name_to_python(left)}_mismatch" if right else f"not_{label}"


def _sanitize_test_name(name: str) -> str:
    """Make a valid Python test function name."""
    name = name.lower().replace("-", "_").replace(" ", "_").replace("'", "")
    name = "".join(c for c in name if c.isalnum() or c == "_")
    # Collapse multiple underscores
    while "__" in name:
        name = name.replace("__", "_")
    return name.rstrip("_")[:80]


def _assertions_from_actions(moves: list, cics_ops: list, performs: list) -> list[str]:
    """Generate assertion lines from branch actions."""
    assertions = []
    for move in moves:
        # Parse "MOVE X TO Y" → assert Y was set
        parts = move.upper().split(" TO ")
        if len(parts) == 2:
            source = parts[0].replace("MOVE", "").strip()
            targets = [t.strip().rstrip(".") for t in parts[1].split(",")]
            for target in targets[:2]:
                target_py = _cobol_name_to_python(target.split(" OF ")[0].strip())
                assertions.append(
                    f"assert True  # {target_py} should be set from {source}"
                )
    for cics in cics_ops:
        if "XCTL" in cics.upper():
            # Extract program name from XCTL
            prog = ""
            if "PROGRAM" in cics.upper():
                import re
                m = re.search(r"PROGRAM\s*\(\s*'?(\w+)'?\s*\)", cics, re.IGNORECASE)
                if m:
                    prog = m.group(1)
            if prog:
                assertions.append(
                    f"assert True  # Should transfer control to {prog} via XCTL"
                )
            else:
                assertions.append("assert True  # Should transfer control via XCTL")
    for perf in performs:
        perf_target = perf.upper().replace("PERFORM", "").strip().split()[0] if perf else ""
        if perf_target:
            assertions.append(
                f"assert True  # Should PERFORM {perf_target}"
            )
    if not assertions:
        assertions.append("assert True  # Branch reached — verify expected state")
    return assertions


def _summarize_actions(moves: list, cics_ops: list, performs: list) -> str:
    """Create a short human-readable summary of branch actions."""
    parts = []
    for move in moves[:2]:
        parts.append(move[:60])
    for cics in cics_ops[:2]:
        if "XCTL" in cics.upper():
            import re
            m = re.search(r"PROGRAM\s*\(\s*'?(\w+)'?\s*\)", cics, re.IGNORECASE)
            if m:
                parts.append(f"XCTL to {m.group(1)}")
    for perf in performs[:1]:
        parts.append(f"PERFORM {perf}")
    return "; ".join(parts) if parts else "execute branch"


def _build_scenario(
    subjects, conditions, nested_cond, positive,
    moves, cics_ops, performs,
) -> tuple[list[str], list[str]]:
    """Build setup and assertion lines for a scenario."""
    setup = []
    setup.append(f"# Set {', '.join(subjects)} = {', '.join(str(c) for c in conditions)}")
    if isinstance(nested_cond, dict):
        raw = nested_cond.get("raw_text", "")
        if positive:
            setup.append(f"# Set condition TRUE: {raw}")
        else:
            setup.append(f"# Set condition FALSE: {raw}")
    assertions = _assertions_from_actions(moves, cics_ops, performs)
    return setup, assertions


def _build_description(
    para_name, subjects, conditions, raw_text,
    positive, is_88, then_moves, then_cics,
) -> str:
    """Build a human-readable test description."""
    subj = ", ".join(subjects)
    cond = ", ".join(str(c) for c in conditions)
    if positive:
        branch = f"{raw_text} is true" if is_88 else f"{raw_text} matches"
    else:
        branch = f"{raw_text} is false" if is_88 else f"{raw_text} does not match (wrong password/mismatch)"

    action_parts = []
    for cics in then_cics:
        if "XCTL" in cics.upper():
            import re
            m = re.search(r"PROGRAM\s*\(\s*'?(\w+)'?\s*\)", cics, re.IGNORECASE)
            if m:
                action_parts.append(f"routes to {m.group(1)}")
    for move in then_moves[:2]:
        if "ERR" in move.upper() or "MESSAGE" in move.upper():
            action_parts.append("sets error message")
            break

    action = ", ".join(action_parts) if action_parts else "executes branch"
    return f"{para_name}: when {subj}={cond} and {branch} — {action}"


def generate_test_suite(spec: ProgramSpec, program_data: dict = None) -> str:
    """Generate a pytest test file from a program spec."""
    class_name = _cobol_name_to_class(spec.program)
    module_name = _cobol_name_to_python(spec.program)
    test_class = f"Test{class_name}"

    all_tests = []
    all_tests.extend(_generate_init_tests(spec))
    all_tests.extend(_generate_paragraph_tests(spec))
    all_tests.extend(_generate_validation_tests(spec))
    all_tests.extend(_generate_call_mock_tests(spec))
    all_tests.extend(_generate_cics_tests(spec))
    all_tests.extend(_generate_entry_exit_tests(spec))

    # Behavioral tests from conditional blocks (IQ-05)
    behavioral_tests = []
    if program_data:
        behavioral_tests = _generate_behavioral_tests(spec, program_data)
        all_tests.extend(behavioral_tests)

    lines = []
    lines.append(f'"""')
    lines.append(f"Generated test suite for COBOL program {spec.program}.")
    lines.append(f"")
    lines.append(f"Program type: {spec.program_type}")
    lines.append(f"Paragraphs: {spec.paragraph_count}")
    lines.append(f"Complexity: {spec.cyclomatic_complexity} ({spec.complexity_grade})")
    lines.append(f"")
    lines.append(f"Generated by Masquerade COBOL Intelligence Engine.")
    lines.append(f'"""')
    lines.append(f"")
    lines.append(f"import pytest")
    lines.append(f"from unittest.mock import MagicMock, patch")
    lines.append(f"")
    lines.append(f"from skeletons.{module_name} import {class_name}")
    lines.append(f"")

    # Import service stubs
    external_calls = set()
    for para in spec.paragraphs:
        for call in para.calls:
            if call:
                external_calls.add(call)
    if external_calls:
        imports = ", ".join(f"{_cobol_name_to_class(c)}Service" for c in sorted(external_calls))
        lines.append(f"from skeletons.{module_name} import {imports}")
        lines.append(f"")

    lines.append(f"")
    lines.append(f"@pytest.fixture")
    lines.append(f"def program():")
    lines.append(f'    """Create a fresh {spec.program} instance for each test."""')
    lines.append(f"    return {class_name}()")
    lines.append(f"")
    lines.append(f"")

    lines.append(f"class {test_class}:")
    lines.append(f'    """Tests for {spec.program} ({spec.program_type}, {spec.code_lines} LOC)."""')
    lines.append(f"")

    behavioral_names = {tc.name for tc in behavioral_tests}
    for tc in all_tests:
        if tc.name in behavioral_names:
            lines.append(f'    @pytest.mark.skip(reason="skeleton not yet implemented")')
        lines.append(f"    def {tc.name}(self, program):")
        lines.append(f'        """{tc.description}."""')
        for mock_line in tc.mocks:
            lines.append(f"        {mock_line}")
        for setup_line in tc.setup:
            lines.append(f"        {setup_line}")
        for assertion in tc.assertions:
            lines.append(f"        {assertion}")
        lines.append(f"")

    return "\n".join(lines)


def generate_all_test_suites(codebase_dir: str) -> dict[str, TestSuiteResult]:
    """Generate test suites for all programs in a codebase."""
    analysis_dir = Path(codebase_dir) / "_analysis"
    graph = GraphIndex(str(analysis_dir))
    program_data = _load_program_data(analysis_dir)

    tests_dir = analysis_dir / "generated_tests"
    tests_dir.mkdir(exist_ok=True)

    results = {}
    for pgm in sorted(graph.program_names()):
        spec = generate_program_spec(pgm, graph, program_data, codebase_dir)
        if not spec or spec.code_lines == 0:
            continue

        code = generate_test_suite(spec)
        filename = f"test_{_cobol_name_to_python(pgm)}.py"
        out_path = tests_dir / filename
        out_path.write_text(code, encoding="utf-8")

        test_count = code.count("    def test_")
        results[pgm] = TestSuiteResult(
            program=pgm,
            test_code=code,
            output_path=str(out_path),
            test_count=test_count,
        )

    # conftest
    conftest = (
        '"""Shared fixtures for generated COBOL modernization tests."""\n'
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parent.parent))\n"
    )
    (tests_dir / "conftest.py").write_text(conftest, encoding="utf-8")

    return results

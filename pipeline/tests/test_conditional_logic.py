"""
IQ-01: Conditional Logic Extraction — Test Suite

Tests parse real COBOL files from test-codebases/ and assert that the parser
extracts conditional blocks (IF, EVALUATE, GO TO, inline PERFORM) with
structured predicates and statement bodies.

Design decisions documented in specs/iq-01-conditional-logic/spec.md:
  DD-01: Full decision tree with statement bodies
  DD-02: Structured predicates with raw_text fallback
  DD-03: EVALUATE as own block type
  DD-04: GO TO context-dependent
  DD-05: Inline PERFORM as conditional block

Primary fixture: COSGN00C.cbl (sign-on screen — IF, EVALUATE, nested, level-88)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cobol_parser import (
    parse_cobol_file,
    Paragraph,
    IfBlock,
    EvaluateBlock,
    Predicate,
    Statement,
)

CARDDEMO_DIR = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
COSGN00C = CARDDEMO_DIR / "app" / "cbl" / "COSGN00C.cbl"


@pytest.fixture(scope="module")
def cosgn00c_program():
    """Parse COSGN00C once for the whole module."""
    assert COSGN00C.exists(), f"Fixture file missing: {COSGN00C}"
    return parse_cobol_file(COSGN00C)


def _find_paragraph(program, name: str) -> Paragraph:
    """Find a paragraph by name, or fail the test."""
    for p in program.paragraphs:
        if p.name == name:
            return p
    pytest.fail(f"Paragraph {name} not found. Available: {[p.name for p in program.paragraphs]}")


def _find_block(blocks: list, stmt_type: str):
    """Find the first Statement of a given type in a block list."""
    for b in blocks:
        if isinstance(b, Statement) and b.stmt_type == stmt_type:
            return b
    return None


# --------------------------------------------------------------------------
# Test 1: Simple IF/ELSE extraction from MAIN-PARA
#
# COBOL (lines 80-96):
#   IF EIBCALEN = 0
#       MOVE LOW-VALUES TO COSGN0AO
#       MOVE -1 TO USERIDL OF COSGN0AI
#       PERFORM SEND-SIGNON-SCREEN
#   ELSE
#       EVALUATE EIBAID ...
#   END-IF
#
# Verifies: conditional_blocks contains an IF, predicate is structured,
#           both then_body and else_body are non-empty.
# --------------------------------------------------------------------------

class TestIfElseExtraction:
    def test_main_para_has_conditional_blocks(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "MAIN-PARA")
        assert len(para.conditional_blocks) > 0, (
            "MAIN-PARA should have conditional_blocks but got empty list"
        )

    def test_main_para_first_block_is_if(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "MAIN-PARA")
        first = para.conditional_blocks[0]
        assert isinstance(first, Statement), f"Expected Statement, got {type(first)}"
        assert first.stmt_type == "IF", f"Expected IF, got {first.stmt_type}"

    def test_main_para_if_predicate_structured(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "MAIN-PARA")
        if_stmt = para.conditional_blocks[0]
        if_block = if_stmt.data
        assert isinstance(if_block, IfBlock), f"Expected IfBlock, got {type(if_block)}"
        cond = if_block.condition
        assert isinstance(cond, Predicate)
        assert cond.left == "EIBCALEN", f"Expected left=EIBCALEN, got {cond.left}"
        assert cond.operator == "=", f"Expected operator='=', got {cond.operator}"
        assert cond.right == "0", f"Expected right='0', got {cond.right}"

    def test_main_para_if_has_then_body(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "MAIN-PARA")
        if_block = para.conditional_blocks[0].data
        assert len(if_block.then_body) > 0, "then_body should contain MOVE/PERFORM statements"

    def test_main_para_if_has_else_body(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "MAIN-PARA")
        if_block = para.conditional_blocks[0].data
        assert len(if_block.else_body) > 0, "else_body should contain EVALUATE block"


# --------------------------------------------------------------------------
# Test 2: EVALUATE nested inside IF ELSE branch
#
# COBOL (lines 85-95, inside the ELSE of the above IF):
#   EVALUATE EIBAID
#       WHEN DFHENTER   → PERFORM PROCESS-ENTER-KEY
#       WHEN DFHPF3     → MOVE msg, PERFORM SEND-PLAIN-TEXT
#       WHEN OTHER      → set error, PERFORM SEND-SIGNON-SCREEN
#   END-EVALUATE
#
# Verifies: EVALUATE is its own type (DD-03), nested in else_body,
#           has correct subjects and branch count.
# --------------------------------------------------------------------------

class TestEvaluateExtraction:
    def test_evaluate_in_else_body(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "MAIN-PARA")
        if_block = para.conditional_blocks[0].data
        eval_stmt = _find_block(if_block.else_body, "EVALUATE")
        assert eval_stmt is not None, (
            "ELSE body should contain an EVALUATE block. "
            f"Got types: {[s.stmt_type for s in if_block.else_body]}"
        )

    def test_evaluate_subject_is_eibaid(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "MAIN-PARA")
        if_block = para.conditional_blocks[0].data
        eval_stmt = _find_block(if_block.else_body, "EVALUATE")
        eval_block = eval_stmt.data
        assert isinstance(eval_block, EvaluateBlock)
        assert eval_block.subjects == ["EIBAID"], f"Expected ['EIBAID'], got {eval_block.subjects}"

    def test_evaluate_has_three_branches(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "MAIN-PARA")
        if_block = para.conditional_blocks[0].data
        eval_stmt = _find_block(if_block.else_body, "EVALUATE")
        eval_block = eval_stmt.data
        assert len(eval_block.branches) == 3, (
            f"Expected 3 WHEN branches (DFHENTER, DFHPF3, OTHER), got {len(eval_block.branches)}"
        )

    def test_evaluate_dfhenter_branch_has_perform(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "MAIN-PARA")
        if_block = para.conditional_blocks[0].data
        eval_stmt = _find_block(if_block.else_body, "EVALUATE")
        eval_block = eval_stmt.data
        first_branch = eval_block.branches[0]
        assert "DFHENTER" in first_branch.conditions, (
            f"First branch should match DFHENTER, got {first_branch.conditions}"
        )
        perform_stmts = [s for s in first_branch.body if s.stmt_type == "PERFORM"]
        assert len(perform_stmts) > 0, "DFHENTER branch should contain a PERFORM statement"


# --------------------------------------------------------------------------
# Test 3: EVALUATE with nested IF in READ-USER-SEC-FILE
#
# COBOL (lines 221-257):
#   EVALUATE WS-RESP-CD
#       WHEN 0
#           IF SEC-USR-PWD = WS-USER-PWD
#               ...set fields...
#               IF CDEMO-USRTYP-ADMIN → XCTL COADM01C
#               ELSE → XCTL COMEN01C
#           ELSE
#               "Wrong Password" → PERFORM SEND-SIGNON-SCREEN
#       WHEN 13
#           "User not found" → PERFORM SEND-SIGNON-SCREEN
#       WHEN OTHER
#           "Unable to verify" → PERFORM SEND-SIGNON-SCREEN
#   END-EVALUATE
#
# Verifies: nested IF inside EVALUATE WHEN branch, 3-level depth,
#           password comparison predicate is structured.
# --------------------------------------------------------------------------

class TestNestedIfInEvaluate:
    def test_read_user_sec_has_evaluate(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "READ-USER-SEC-FILE")
        eval_stmt = _find_block(para.conditional_blocks, "EVALUATE")
        assert eval_stmt is not None, "READ-USER-SEC-FILE should have an EVALUATE block"

    def test_evaluate_subject_is_resp_cd(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "READ-USER-SEC-FILE")
        eval_stmt = _find_block(para.conditional_blocks, "EVALUATE")
        eval_block = eval_stmt.data
        assert eval_block.subjects == ["WS-RESP-CD"], (
            f"Expected ['WS-RESP-CD'], got {eval_block.subjects}"
        )

    def test_when_zero_has_nested_if(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "READ-USER-SEC-FILE")
        eval_stmt = _find_block(para.conditional_blocks, "EVALUATE")
        eval_block = eval_stmt.data
        when_zero = eval_block.branches[0]
        assert "0" in when_zero.conditions, f"First branch should be WHEN 0, got {when_zero.conditions}"
        if_stmt = _find_block(when_zero.body, "IF")
        assert if_stmt is not None, "WHEN 0 branch should contain a nested IF block"

    def test_password_comparison_predicate(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "READ-USER-SEC-FILE")
        eval_stmt = _find_block(para.conditional_blocks, "EVALUATE")
        eval_block = eval_stmt.data
        when_zero = eval_block.branches[0]
        if_stmt = _find_block(when_zero.body, "IF")
        if_block = if_stmt.data
        cond = if_block.condition
        assert cond.left == "SEC-USR-PWD", f"Expected left=SEC-USR-PWD, got {cond.left}"
        assert cond.operator == "=", f"Expected operator='=', got {cond.operator}"
        assert cond.right == "WS-USER-PWD", f"Expected right=WS-USER-PWD, got {cond.right}"

    def test_evaluate_has_when_13_and_other(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "READ-USER-SEC-FILE")
        eval_stmt = _find_block(para.conditional_blocks, "EVALUATE")
        eval_block = eval_stmt.data
        branch_conditions = [b.conditions for b in eval_block.branches]
        assert any("13" in c for c in branch_conditions), f"Missing WHEN 13 branch in {branch_conditions}"
        assert any("OTHER" in c for c in branch_conditions), f"Missing WHEN OTHER branch in {branch_conditions}"


# --------------------------------------------------------------------------
# Test 4: EVALUATE TRUE (boolean-style) from PROCESS-ENTER-KEY
#
# COBOL (lines 117-130):
#   EVALUATE TRUE
#       WHEN USERIDI OF COSGN0AI = SPACES OR LOW-VALUES
#           ...
#       WHEN PASSWDI OF COSGN0AI = SPACES OR LOW-VALUES
#           ...
#       WHEN OTHER
#           CONTINUE
#   END-EVALUATE
#
# Verifies: subject is "TRUE", branches have condition_predicate (not just
#           match value), first branch references USERIDI.
# --------------------------------------------------------------------------

class TestEvaluateTrue:
    def test_process_enter_key_has_evaluate_true(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "PROCESS-ENTER-KEY")
        eval_stmt = _find_block(para.conditional_blocks, "EVALUATE")
        assert eval_stmt is not None, "PROCESS-ENTER-KEY should have an EVALUATE block"
        eval_block = eval_stmt.data
        assert eval_block.subjects == ["TRUE"], f"Expected ['TRUE'], got {eval_block.subjects}"

    def test_evaluate_true_branches_have_predicates(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "PROCESS-ENTER-KEY")
        eval_stmt = _find_block(para.conditional_blocks, "EVALUATE")
        eval_block = eval_stmt.data
        non_other = [b for b in eval_block.branches if "OTHER" not in b.conditions]
        assert len(non_other) >= 2, f"Expected at least 2 non-OTHER branches, got {len(non_other)}"
        for branch in non_other:
            assert branch.condition_predicate is not None, (
                f"EVALUATE TRUE branch should have condition_predicate, "
                f"conditions={branch.conditions}"
            )

    def test_first_branch_references_useridi(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "PROCESS-ENTER-KEY")
        eval_stmt = _find_block(para.conditional_blocks, "EVALUATE")
        eval_block = eval_stmt.data
        first_branch = eval_block.branches[0]
        pred = first_branch.condition_predicate
        assert pred is not None
        all_text = pred.raw_text.upper()
        assert "USERIDI" in all_text, (
            f"First branch predicate should reference USERIDI, raw_text={pred.raw_text}"
        )


# --------------------------------------------------------------------------
# Test 5: IF with level-88 condition name
#
# COBOL (lines 138-140):
#   IF NOT ERR-FLG-ON
#       PERFORM READ-USER-SEC-FILE
#   END-IF
#
# Verifies: predicate recognizes NOT as operator with child predicate,
#           child has is_88_condition=True.
# --------------------------------------------------------------------------

class TestLevel88Condition:
    def test_if_not_err_flg_on_extracted(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "PROCESS-ENTER-KEY")
        if_stmts = [s for s in para.conditional_blocks if s.stmt_type == "IF"]
        assert len(if_stmts) > 0, "PROCESS-ENTER-KEY should have at least one IF block"

    def test_not_operator_with_88_condition(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "PROCESS-ENTER-KEY")
        if_stmts = [s for s in para.conditional_blocks if s.stmt_type == "IF"]
        found_not_88 = False
        for stmt in if_stmts:
            cond = stmt.data.condition
            if cond.operator == "NOT" and len(cond.children) > 0:
                child = cond.children[0]
                if child.is_88_condition and child.left == "ERR-FLG-ON":
                    found_not_88 = True
                    break
        assert found_not_88, (
            "Should find IF NOT ERR-FLG-ON with NOT operator and "
            "is_88_condition=True child predicate"
        )


# --------------------------------------------------------------------------
# Test 6: raw_text always present (DD-02 caveat)
#
# Every Predicate in every conditional block of COSGN00C should have a
# non-empty raw_text field. This guarantees graceful degradation when
# structured parsing is incomplete.
# --------------------------------------------------------------------------

class TestRawTextFallback:
    def _collect_predicates(self, blocks: list) -> list:
        """Recursively collect all Predicate objects from conditional blocks."""
        predicates = []
        for stmt in blocks:
            if not isinstance(stmt, Statement):
                continue
            if stmt.stmt_type == "IF":
                blk = stmt.data
                predicates.append(blk.condition)
                predicates.extend(self._collect_predicates(blk.then_body))
                predicates.extend(self._collect_predicates(blk.else_body))
            elif stmt.stmt_type == "EVALUATE":
                blk = stmt.data
                for branch in blk.branches:
                    if branch.condition_predicate:
                        predicates.append(branch.condition_predicate)
                    predicates.extend(self._collect_predicates(branch.body))
            elif stmt.stmt_type == "PERFORM_INLINE":
                blk = stmt.data
                if blk.until:
                    predicates.append(blk.until)
                predicates.extend(self._collect_predicates(blk.body))
        return predicates

    def test_all_predicates_have_raw_text(self, cosgn00c_program):
        all_predicates = []
        for para in cosgn00c_program.paragraphs:
            all_predicates.extend(self._collect_predicates(para.conditional_blocks))
        assert len(all_predicates) > 0, "Should find at least one predicate in COSGN00C"
        for pred in all_predicates:
            assert pred.raw_text.strip() != "", (
                f"Predicate has empty raw_text: left={pred.left}, op={pred.operator}"
            )


# --------------------------------------------------------------------------
# Test 7: Paragraph with no conditionals
#
# POPULATE-HEADER-INFO has only MOVEs and CICS ASSIGN — no IF, EVALUATE,
# GO TO, or inline PERFORM. Its conditional_blocks should be empty.
# --------------------------------------------------------------------------

class TestNoConditionals:
    def test_populate_header_info_has_no_conditional_blocks(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "POPULATE-HEADER-INFO")
        assert para.conditional_blocks == [], (
            f"POPULATE-HEADER-INFO should have no conditional blocks, "
            f"got {len(para.conditional_blocks)}"
        )

    def test_populate_header_info_has_no_goto(self, cosgn00c_program):
        para = _find_paragraph(cosgn00c_program, "POPULATE-HEADER-INFO")
        assert para.goto_targets == [], (
            f"POPULATE-HEADER-INFO should have no goto targets, "
            f"got {len(para.goto_targets)}"
        )

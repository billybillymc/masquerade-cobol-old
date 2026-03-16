"""Tests for business_rules.py — structural and LLM-assisted business rule extraction.

IQ-04: Extracts structured, evidence-anchored business rules from COBOL
conditional blocks and data flows.
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from business_rules import (
    BusinessRule,
    Evidence,
    extract_structural_rules,
    parse_llm_rules_output,
    validate_evidence,
    save_rules,
    load_rules,
)

CARDDEMO = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
PROGRAMS_JSON = CARDDEMO / "_analysis" / "programs.json"


def _load_program(program_id: str) -> dict:
    """Load a program's data from programs.json."""
    data = json.loads(PROGRAMS_JSON.read_text())
    return data[program_id]


class TestStructuralExtraction:
    """Structural extraction: deterministic rules from conditional blocks."""

    def test_read_user_sec_file_identifies_authentication(self):
        """READ-USER-SEC-FILE has EVALUATE WS-RESP-CD → WHEN 0 →
        IF SEC-USR-PWD = WS-USER-PWD. This must produce an ACCESS_CONTROL
        rule about password/authentication."""
        pgm = _load_program("COSGN00C")
        rules = extract_structural_rules("COSGN00C", pgm)
        auth_rules = [r for r in rules if r.rule_type == "ACCESS_CONTROL"]
        assert len(auth_rules) >= 1
        # At least one rule mentions password or authentication
        auth_claims = " ".join(r.claim.lower() for r in auth_rules)
        assert "password" in auth_claims or "pwd" in auth_claims or "auth" in auth_claims

    def test_read_user_sec_file_identifies_routing(self):
        """EVALUATE WS-RESP-CD with WHEN 0/13/OTHER must produce ROUTING rules
        for response code handling."""
        pgm = _load_program("COSGN00C")
        rules = extract_structural_rules("COSGN00C", pgm)
        routing_rules = [r for r in rules if r.rule_type == "ROUTING"]
        assert len(routing_rules) >= 1
        # Should reference RESP or response code
        routing_claims = " ".join(r.claim.lower() for r in routing_rules)
        assert "resp" in routing_claims or "response" in routing_claims or "route" in routing_claims

    def test_evidence_has_source_spans(self):
        """Every extracted rule must have at least one Evidence with file and
        line range from the conditional block's span."""
        pgm = _load_program("COSGN00C")
        rules = extract_structural_rules("COSGN00C", pgm)
        assert len(rules) >= 1
        for rule in rules:
            assert len(rule.evidence) >= 1, f"Rule {rule.rule_id} has no evidence"
            for ev in rule.evidence:
                assert ev.file, f"Evidence for {rule.rule_id} has no file"
                assert ev.start_line > 0, f"Evidence for {rule.rule_id} has no start_line"
                assert ev.end_line >= ev.start_line

    def test_rule_ids_are_unique(self):
        """All rule IDs within a program must be unique."""
        pgm = _load_program("COSGN00C")
        rules = extract_structural_rules("COSGN00C", pgm)
        ids = [r.rule_id for r in rules]
        assert len(ids) == len(set(ids)), f"Duplicate rule IDs: {ids}"

    def test_paragraphs_without_conditionals_produce_no_rules(self):
        """SEND-SIGNON-SCREEN and SEND-PLAIN-TEXT have 0 conditional blocks.
        They should produce no structural rules."""
        pgm = _load_program("COSGN00C")
        rules = extract_structural_rules("COSGN00C", pgm)
        # No rules should reference paragraphs without conditionals
        simple_paras = {"SEND-SIGNON-SCREEN", "SEND-PLAIN-TEXT", "POPULATE-HEADER-INFO"}
        rules_from_simple = [r for r in rules if r.paragraph in simple_paras]
        assert len(rules_from_simple) == 0

    def test_admin_routing_rule_detected(self):
        """The nested IF CDEMO-USRTYP-ADMIN → XCTL COADM01C should produce
        a rule about admin user routing."""
        pgm = _load_program("COSGN00C")
        rules = extract_structural_rules("COSGN00C", pgm)
        all_claims = " ".join(r.claim.lower() for r in rules)
        assert "admin" in all_claims

    def test_confidence_is_valid(self):
        """All rules must have confidence HIGH, MEDIUM, or LOW."""
        pgm = _load_program("COSGN00C")
        rules = extract_structural_rules("COSGN00C", pgm)
        for rule in rules:
            assert rule.confidence in ("HIGH", "MEDIUM", "LOW"), \
                f"Rule {rule.rule_id} has invalid confidence: {rule.confidence}"


class TestLlmOutputParsing:
    """Parse the RULES_PROMPT_TEMPLATE output format into BusinessRule objects."""

    SAMPLE_LLM_OUTPUT = """RULE: When user lookup returns response code 0, the system compares the stored password with the entered password to authenticate the user.
EVIDENCE: app/cbl/COSGN00C.cbl:221-257
CONFIDENCE: HIGH
TYPE: ACCESS_CONTROL
UNCERTAINTY: None
---
RULE: If the user type is admin (CDEMO-USRTYP-ADMIN), the system routes to the admin program COADM01C via XCTL.
EVIDENCE: app/cbl/COSGN00C.cbl:230-240
CONFIDENCE: HIGH
TYPE: ROUTING
UNCERTAINTY: None
---
RULE: When RESP code is 13, the user was not found in the security file, and an error message is displayed.
EVIDENCE: app/cbl/COSGN00C.cbl:247-250
CONFIDENCE: MEDIUM
TYPE: VALIDATION
UNCERTAINTY: The exact error message text is not visible in context.
---"""

    def test_parses_multiple_rules(self):
        """The parser should extract 3 rules from the sample output."""
        rules = parse_llm_rules_output(
            self.SAMPLE_LLM_OUTPUT, program="COSGN00C", paragraph="READ-USER-SEC-FILE"
        )
        assert len(rules) == 3

    def test_parses_fields_correctly(self):
        """Each parsed rule should have the correct claim, confidence, type."""
        rules = parse_llm_rules_output(
            self.SAMPLE_LLM_OUTPUT, program="COSGN00C", paragraph="READ-USER-SEC-FILE"
        )
        assert rules[0].rule_type == "ACCESS_CONTROL"
        assert rules[0].confidence == "HIGH"
        assert "password" in rules[0].claim.lower()

        assert rules[1].rule_type == "ROUTING"
        assert "admin" in rules[1].claim.lower()

        assert rules[2].rule_type == "VALIDATION"
        assert rules[2].confidence == "MEDIUM"

    def test_parses_evidence_spans(self):
        """Evidence should be parsed into file + line range."""
        rules = parse_llm_rules_output(
            self.SAMPLE_LLM_OUTPUT, program="COSGN00C", paragraph="READ-USER-SEC-FILE"
        )
        ev = rules[0].evidence[0]
        assert "COSGN00C" in ev.file
        assert ev.start_line == 221
        assert ev.end_line == 257

    def test_handles_malformed_output_gracefully(self):
        """Malformed LLM output should not crash — return empty or partial."""
        rules = parse_llm_rules_output(
            "This is not structured output at all.",
            program="TEST", paragraph="PARA"
        )
        assert isinstance(rules, list)
        # May be empty, but should not raise


class TestEvidenceValidation:
    """Anti-hallucination: validate evidence spans against source files."""

    def test_valid_evidence_passes(self):
        """A rule with real file and line range passes validation."""
        source_file = str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl")
        rule = BusinessRule(
            rule_id="COSGN00C.READ-USER-SEC-FILE.R1",
            claim="Password comparison for authentication",
            evidence=[Evidence(
                file=source_file,
                start_line=221,
                end_line=257,
                code_text="EVALUATE WS-RESP-CD",
                block_type="EVALUATE",
            )],
            confidence="HIGH",
            rule_type="ACCESS_CONTROL",
            paragraph="READ-USER-SEC-FILE",
            program="COSGN00C",
            uncertainty="",
        )
        validated = validate_evidence(rule, source_dir=str(CARDDEMO / "app" / "cbl"))
        assert validated.confidence != "REJECTED"

    def test_fabricated_evidence_rejected(self):
        """A rule citing a non-existent file gets REJECTED."""
        rule = BusinessRule(
            rule_id="FAKE.PARA.R1",
            claim="This rule is fabricated",
            evidence=[Evidence(
                file="/nonexistent/path/FAKE.cbl",
                start_line=1,
                end_line=10,
                code_text="FAKE CODE",
                block_type="IF",
            )],
            confidence="HIGH",
            rule_type="VALIDATION",
            paragraph="FAKE-PARA",
            program="FAKE",
            uncertainty="",
        )
        validated = validate_evidence(rule, source_dir="/nonexistent")
        assert validated.confidence == "REJECTED"

    def test_out_of_range_lines_rejected(self):
        """A rule citing lines beyond the file's length gets REJECTED."""
        source_file = str(CARDDEMO / "app" / "cbl" / "COSGN00C.cbl")
        rule = BusinessRule(
            rule_id="COSGN00C.PARA.R1",
            claim="Out of range evidence",
            evidence=[Evidence(
                file=source_file,
                start_line=99999,
                end_line=99999,
                code_text="FAKE",
                block_type="IF",
            )],
            confidence="HIGH",
            rule_type="VALIDATION",
            paragraph="MAIN-PARA",
            program="COSGN00C",
            uncertainty="",
        )
        validated = validate_evidence(rule, source_dir=str(CARDDEMO / "app" / "cbl"))
        assert validated.confidence == "REJECTED"


class TestSerialization:
    """Rules serialize to and deserialize from JSON."""

    def test_round_trip(self, tmp_path):
        """save_rules then load_rules produces identical data."""
        rules = [
            BusinessRule(
                rule_id="TEST.PARA.R1",
                claim="Test rule",
                evidence=[Evidence(
                    file="test.cbl",
                    start_line=10,
                    end_line=20,
                    code_text="IF X = Y",
                    block_type="IF",
                )],
                confidence="HIGH",
                rule_type="VALIDATION",
                paragraph="PARA",
                program="TEST",
                uncertainty="none",
            ),
        ]
        save_rules(rules, "TEST", str(tmp_path))
        loaded = load_rules("TEST", str(tmp_path))
        assert len(loaded) == 1
        assert loaded[0].rule_id == "TEST.PARA.R1"
        assert loaded[0].claim == "Test rule"
        assert loaded[0].evidence[0].start_line == 10
        assert loaded[0].rule_type == "VALIDATION"

"""
Business rule extraction from COBOL structural analysis.

Two-tier extraction:
1. Structural (deterministic): walks conditional blocks from IQ-01 and classifies
   rules by pattern matching on field names, operators, and block structure.
2. LLM-assisted (optional): parses RULES_PROMPT_TEMPLATE output into structured
   BusinessRule objects, validated against structural evidence.

Output: _analysis/rules/{program}.json
"""

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ── Schema ──────────────────────────────────────────────────────────────────


@dataclass
class Evidence:
    """Source span backing a business rule claim."""
    file: str
    start_line: int
    end_line: int
    code_text: str       # actual COBOL statements
    block_type: str      # IF / EVALUATE / COMPUTE / PERFORM / MOVE / etc.


@dataclass
class BusinessRule:
    """Structured business rule extracted from COBOL analysis."""
    rule_id: str          # "{PROGRAM}.{PARAGRAPH}.R{N}"
    claim: str            # plain-language description
    evidence: list[Evidence]
    confidence: str       # HIGH / MEDIUM / LOW / REJECTED
    rule_type: str        # VALIDATION / CALCULATION / ROUTING / THRESHOLD /
                          # STATE_TRANSITION / ACCESS_CONTROL / DATA_TRANSFORM
    paragraph: str
    program: str
    uncertainty: str      # caveats, missing context


# ── Field-name pattern matching for rule type classification ────────────────

_ACCESS_CONTROL_PATTERNS = re.compile(
    r'(PWD|PASSWORD|USR-PWD|USER-PWD|SEC-USR|USRTYP|USER-TYPE|SIGN.?ON|LOGON|AUTH)',
    re.IGNORECASE,
)
_ROUTING_PATTERNS = re.compile(
    r'(RESP|RESPONSE|EIBAID|EIBRESP|DFHENTER|DFHPF|XCTL|LINK|RETURN|ROUTE)',
    re.IGNORECASE,
)
_VALIDATION_PATTERNS = re.compile(
    r'(STATUS|FLAG|VALID|ERR|ERROR|INVALID|CHECK|VERIFY)',
    re.IGNORECASE,
)
_CALCULATION_PATTERNS = re.compile(
    r'(COMPUTE|ADD|SUBTRACT|MULTIPLY|DIVIDE|CALC|TOTAL|SUM|AMT|AMOUNT|BAL|BALANCE)',
    re.IGNORECASE,
)
_THRESHOLD_PATTERNS = re.compile(
    r'(LIMIT|MAX|MIN|THRESHOLD|EXCEED|OVER|UNDER|GREATER|LESS)',
    re.IGNORECASE,
)
_STATE_PATTERNS = re.compile(
    r'(STATE|STATUS|MODE|PHASE|STEP|CONTEXT|PGM-CONTEXT)',
    re.IGNORECASE,
)


def _classify_rule_type(text: str) -> str:
    """Classify rule type from combined text of conditions and fields."""
    if _ACCESS_CONTROL_PATTERNS.search(text):
        return "ACCESS_CONTROL"
    if _ROUTING_PATTERNS.search(text):
        return "ROUTING"
    if _VALIDATION_PATTERNS.search(text):
        return "VALIDATION"
    if _CALCULATION_PATTERNS.search(text):
        return "CALCULATION"
    if _THRESHOLD_PATTERNS.search(text):
        return "THRESHOLD"
    if _STATE_PATTERNS.search(text):
        return "STATE_TRANSITION"
    return "DATA_TRANSFORM"


# ── Structural extraction ───────────────────────────────────────────────────


def _extract_text_from_block(block: dict) -> str:
    """Extract all meaningful text from a conditional block for classification."""
    parts = []
    stmt_type = block.get("stmt_type", "")
    parts.append(stmt_type)

    # Condition text
    condition = block.get("condition", {})
    if isinstance(condition, dict):
        parts.append(condition.get("raw_text", ""))
        parts.append(condition.get("left", ""))
        parts.append(condition.get("right", ""))
        parts.append(condition.get("operator", ""))

    # Subjects (for EVALUATE)
    for subj in block.get("subjects", []):
        parts.append(subj)

    # Branch conditions
    for branch in block.get("branches", []):
        for cond in branch.get("conditions", []):
            parts.append(str(cond))
        cp = branch.get("condition_predicate", {})
        if cp and isinstance(cp, dict):
            parts.append(cp.get("raw_text", ""))

    # Recurse into bodies
    for body_key in ("then_body", "else_body", "body"):
        for child in block.get(body_key, []):
            parts.append(child.get("stmt_type", ""))
            raw = child.get("raw", "")
            if raw:
                parts.append(raw)
            # Recurse into nested conditions
            parts.append(_extract_text_from_block(child))

    # Branch bodies
    for branch in block.get("branches", []):
        for child in branch.get("body", []):
            parts.append(child.get("stmt_type", ""))
            raw = child.get("raw", "")
            if raw:
                parts.append(raw)
            parts.append(_extract_text_from_block(child))

    return " ".join(p for p in parts if p)


def _describe_evaluate_block(block: dict) -> list[str]:
    """Generate human-readable descriptions for an EVALUATE block."""
    descriptions = []
    subjects = block.get("subjects", [])
    subject_text = ", ".join(subjects) if subjects else "unknown"

    for branch in block.get("branches", []):
        conditions = branch.get("conditions", [])
        cond_text = ", ".join(str(c) for c in conditions)

        # Collect body statement types for description
        body_actions = []
        for stmt in branch.get("body", []):
            st = stmt.get("stmt_type", "")
            if st == "IF":
                cond = stmt.get("condition", {})
                raw = cond.get("raw_text", "") if isinstance(cond, dict) else str(cond)
                body_actions.append(f"IF {raw}")
            elif st in ("CICS", "CALL"):
                raw = stmt.get("raw", "")
                body_actions.append(raw or st)
            elif st == "MOVE":
                raw = stmt.get("raw", "")
                body_actions.append(raw or "MOVE")

        action_summary = "; ".join(body_actions[:3]) if body_actions else "execute statements"

        if cond_text.upper() == "OTHER":
            desc = f"When {subject_text} has no matching case (OTHER), {action_summary}"
        else:
            desc = f"When {subject_text} = {cond_text}, {action_summary}"
        descriptions.append(desc)

    return descriptions


def _describe_if_block(block: dict) -> str:
    """Generate human-readable description for an IF block."""
    condition = block.get("condition", {})
    if isinstance(condition, dict):
        raw = condition.get("raw_text", "")
        left = condition.get("left", "")
        op = condition.get("operator", "")
        right = condition.get("right", "")
        is_88 = condition.get("is_88_condition", False)

        if is_88:
            return f"When condition {left} is true"
        elif raw:
            return f"When {raw}"
        else:
            return f"When {left} {op} {right}"
    return "Conditional check"


def _evidence_from_span(span: dict) -> Evidence:
    """Create an Evidence object from a span dict."""
    return Evidence(
        file=span.get("file", ""),
        start_line=span.get("start_line", 0),
        end_line=span.get("end_line", 0),
        code_text="",  # filled later if needed
        block_type="",
    )


def extract_structural_rules(program_id: str, program_data: dict) -> list[BusinessRule]:
    """Extract business rules deterministically from conditional blocks.

    Walks each paragraph's conditional_blocks, classifies by field name
    patterns, and produces Evidence-anchored BusinessRule objects.
    """
    rules: list[BusinessRule] = []
    rule_counter = 0

    for para in program_data.get("paragraphs", []):
        para_name = para.get("name", "")
        blocks = para.get("conditional_blocks", [])

        for block in blocks:
            stmt_type = block.get("stmt_type", "")
            span = block.get("span", {})
            all_text = _extract_text_from_block(block)
            rule_type = _classify_rule_type(all_text)

            evidence = Evidence(
                file=span.get("file", ""),
                start_line=span.get("start_line", 0),
                end_line=span.get("end_line", 0),
                code_text="",
                block_type=stmt_type,
            )

            if stmt_type == "EVALUATE":
                # One rule per EVALUATE block for the routing pattern
                subjects = block.get("subjects", [])
                branches = block.get("branches", [])
                branch_descriptions = _describe_evaluate_block(block)

                # For EVALUATE, classify based on subjects first (top-level intent),
                # not the nested body text which may have different patterns
                subject_text = " ".join(subjects)
                eval_rule_type = _classify_rule_type(subject_text)
                # EVALUATE with multiple branches is inherently a ROUTING pattern
                if eval_rule_type == "DATA_TRANSFORM" and len(branches) >= 2:
                    eval_rule_type = "ROUTING"

                rule_counter += 1
                claim = (
                    f"Routes based on {', '.join(subjects)} "
                    f"with {len(branches)} branches: "
                    + "; ".join(branch_descriptions[:3])
                )

                rules.append(BusinessRule(
                    rule_id=f"{program_id}.{para_name}.R{rule_counter}",
                    claim=claim,
                    evidence=[evidence],
                    confidence="HIGH",
                    rule_type=eval_rule_type,
                    paragraph=para_name,
                    program=program_id,
                    uncertainty="",
                ))

                # Also extract nested IF blocks within branches as separate rules
                for branch in branches:
                    for child in branch.get("body", []):
                        if child.get("stmt_type") == "IF":
                            child_text = _extract_text_from_block(child)
                            child_type = _classify_rule_type(child_text)
                            child_span = child.get("span", {})
                            child_desc = _describe_if_block(child)

                            # Check for nested IFs (e.g., admin routing)
                            nested_descriptions = []
                            for body_key in ("then_body", "else_body"):
                                for nested in child.get(body_key, []):
                                    if nested.get("stmt_type") == "IF":
                                        nested_descriptions.append(
                                            _describe_if_block(nested)
                                        )

                            rule_counter += 1
                            full_claim = child_desc
                            if nested_descriptions:
                                full_claim += " → " + "; ".join(nested_descriptions)

                            rules.append(BusinessRule(
                                rule_id=f"{program_id}.{para_name}.R{rule_counter}",
                                claim=full_claim,
                                evidence=[Evidence(
                                    file=child_span.get("file", ""),
                                    start_line=child_span.get("start_line", 0),
                                    end_line=child_span.get("end_line", 0),
                                    code_text="",
                                    block_type="IF",
                                )],
                                confidence="HIGH",
                                rule_type=child_type,
                                paragraph=para_name,
                                program=program_id,
                                uncertainty="",
                            ))

            elif stmt_type == "IF":
                rule_counter += 1
                desc = _describe_if_block(block)

                rules.append(BusinessRule(
                    rule_id=f"{program_id}.{para_name}.R{rule_counter}",
                    claim=desc,
                    evidence=[evidence],
                    confidence="HIGH",
                    rule_type=rule_type,
                    paragraph=para_name,
                    program=program_id,
                    uncertainty="",
                ))

            elif stmt_type == "PERFORM_INLINE":
                rule_counter += 1
                until = block.get("until", {})
                until_text = until.get("raw_text", "") if isinstance(until, dict) else str(until)

                rules.append(BusinessRule(
                    rule_id=f"{program_id}.{para_name}.R{rule_counter}",
                    claim=f"Iterates until {until_text}" if until_text else "Inline iteration",
                    evidence=[evidence],
                    confidence="MEDIUM",
                    rule_type=rule_type,
                    paragraph=para_name,
                    program=program_id,
                    uncertainty="Loop body details not fully analyzed",
                ))

    return rules


# ── LLM output parsing ─────────────────────────────────────────────────────

_RULE_BLOCK_RE = re.compile(
    r'RULE:\s*(?P<claim>.+?)\n'
    r'EVIDENCE:\s*(?P<evidence>.+?)\n'
    r'CONFIDENCE:\s*(?P<confidence>\S+)\n'
    r'TYPE:\s*(?P<type>\S+)\n'
    r'UNCERTAINTY:\s*(?P<uncertainty>.+?)(?:\n---|$)',
    re.DOTALL,
)

_EVIDENCE_SPAN_RE = re.compile(
    r'(?P<file>[^\s:]+):(?P<start>\d+)-(?P<end>\d+)'
)


def parse_llm_rules_output(
    raw_text: str,
    program: str,
    paragraph: str,
) -> list[BusinessRule]:
    """Parse the RULES_PROMPT_TEMPLATE output into BusinessRule objects.

    Expected format per rule:
        RULE: <description>
        EVIDENCE: <file>:<start>-<end>
        CONFIDENCE: HIGH|MEDIUM|LOW
        TYPE: <rule_type>
        UNCERTAINTY: <text>
        ---
    """
    rules = []
    counter = 0

    for match in _RULE_BLOCK_RE.finditer(raw_text):
        counter += 1
        claim = match.group("claim").strip()
        evidence_raw = match.group("evidence").strip()
        confidence = match.group("confidence").strip().upper()
        rule_type = match.group("type").strip().upper()
        uncertainty = match.group("uncertainty").strip()

        # Parse evidence spans
        evidence_list = []
        for ev_match in _EVIDENCE_SPAN_RE.finditer(evidence_raw):
            evidence_list.append(Evidence(
                file=ev_match.group("file"),
                start_line=int(ev_match.group("start")),
                end_line=int(ev_match.group("end")),
                code_text="",
                block_type="",
            ))

        # If no spans parsed, create a minimal evidence entry
        if not evidence_list:
            evidence_list.append(Evidence(
                file=evidence_raw,
                start_line=0,
                end_line=0,
                code_text="",
                block_type="",
            ))

        # Validate confidence
        if confidence not in ("HIGH", "MEDIUM", "LOW"):
            confidence = "LOW"

        # Validate rule type
        valid_types = {
            "VALIDATION", "CALCULATION", "ROUTING", "THRESHOLD",
            "STATE_TRANSITION", "ACCESS_CONTROL", "DATA_TRANSFORM",
        }
        if rule_type not in valid_types:
            rule_type = "DATA_TRANSFORM"

        rules.append(BusinessRule(
            rule_id=f"{program}.{paragraph}.R{counter}",
            claim=claim,
            evidence=evidence_list,
            confidence=confidence,
            rule_type=rule_type,
            paragraph=paragraph,
            program=program,
            uncertainty=uncertainty,
        ))

    return rules


# ── Evidence validation (anti-hallucination) ────────────────────────────────


def validate_evidence(
    rule: BusinessRule,
    source_dir: str,
) -> BusinessRule:
    """Validate that a rule's evidence spans reference real code.

    Checks:
    1. File exists (absolute or relative to source_dir)
    2. Line range is within the file's bounds

    If validation fails, sets confidence='REJECTED' with a reason.
    """
    for ev in rule.evidence:
        file_path = Path(ev.file)

        # Try absolute first, then relative to source_dir
        if not file_path.is_absolute():
            # Try relative to source_dir
            candidate = Path(source_dir) / file_path
            if not candidate.exists():
                # Try just the filename in source_dir
                candidate = Path(source_dir) / file_path.name
            file_path = candidate

        if not file_path.exists():
            rule.confidence = "REJECTED"
            rule.uncertainty = f"Evidence file not found: {ev.file}"
            return rule

        # Check line range
        try:
            line_count = len(file_path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            rule.confidence = "REJECTED"
            rule.uncertainty = f"Cannot read evidence file: {ev.file}"
            return rule

        if ev.start_line > line_count or ev.end_line > line_count:
            rule.confidence = "REJECTED"
            rule.uncertainty = (
                f"Evidence lines {ev.start_line}-{ev.end_line} "
                f"exceed file length ({line_count} lines): {ev.file}"
            )
            return rule

    return rule


# ── Serialization ───────────────────────────────────────────────────────────


def save_rules(rules: list[BusinessRule], program_id: str, output_dir: str) -> Path:
    """Save rules to {output_dir}/{program_id}.json."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / f"{program_id}.json"

    data = []
    for rule in rules:
        d = {
            "rule_id": rule.rule_id,
            "claim": rule.claim,
            "evidence": [
                {
                    "file": ev.file,
                    "start_line": ev.start_line,
                    "end_line": ev.end_line,
                    "code_text": ev.code_text,
                    "block_type": ev.block_type,
                }
                for ev in rule.evidence
            ],
            "confidence": rule.confidence,
            "rule_type": rule.rule_type,
            "paragraph": rule.paragraph,
            "program": rule.program,
            "uncertainty": rule.uncertainty,
        }
        data.append(d)

    file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return file_path


def load_rules(program_id: str, rules_dir: str) -> list[BusinessRule]:
    """Load rules from {rules_dir}/{program_id}.json."""
    file_path = Path(rules_dir) / f"{program_id}.json"
    if not file_path.exists():
        return []

    data = json.loads(file_path.read_text(encoding="utf-8"))
    rules = []
    for d in data:
        evidence = [
            Evidence(
                file=ev["file"],
                start_line=ev["start_line"],
                end_line=ev["end_line"],
                code_text=ev.get("code_text", ""),
                block_type=ev.get("block_type", ""),
            )
            for ev in d.get("evidence", [])
        ]
        rules.append(BusinessRule(
            rule_id=d["rule_id"],
            claim=d["claim"],
            evidence=evidence,
            confidence=d["confidence"],
            rule_type=d["rule_type"],
            paragraph=d["paragraph"],
            program=d["program"],
            uncertainty=d.get("uncertainty", ""),
        ))

    return rules

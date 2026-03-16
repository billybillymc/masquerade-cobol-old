# Specification Quality Checklist: Dependency Graph + System Model

**Purpose**: Validate specification completeness and quality before proceeding to planning  
**Created**: 2026-03-13  
**Feature**: [spec.md](../spec.md)

## Content Quality

- [ ] No implementation details (languages, frameworks, APIs)
- [ ] Focused on user value and business needs
- [ ] Written for non-technical stakeholders
- [ ] All mandatory sections completed

## Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain
- [ ] Requirements are testable and unambiguous
- [ ] Success criteria are measurable
- [ ] Success criteria are technology-agnostic (no implementation details)
- [ ] All acceptance scenarios are defined
- [ ] Edge cases are identified
- [ ] Scope is clearly bounded
- [ ] Dependencies and assumptions identified

## Feature Readiness

- [ ] All functional requirements have clear acceptance criteria
- [ ] User scenarios cover primary flows
- [ ] Feature meets measurable outcomes defined in Success Criteria
- [ ] No implementation details leak into specification

## Traceability

- [ ] FR-001 through FR-012 map to user stories and acceptance scenarios
- [ ] SC-001 through SC-008 align with PRD success metrics (graph extraction >= 90%, unknown edges surfaced)
- [ ] Key entities (Program, Paragraph, Section, Copybook, Field, File, Table) align with PRD Section 6.2
- [ ] Key relationships (CALLS, PERFORMS, USES_COPYBOOK, READS_FIELD, WRITES_FIELD, FEEDS, SCHEDULED_BY) align with PRD Section 6.2

## Dependencies and Assumptions

- [ ] Feature 001 (COBOL parser + copybook resolution) is complete or in progress; graph extraction consumes parser output
- [ ] Parser produces typed AST with symbol tables and stable node IDs
- [ ] CardDemo (28 files, 19K LOC) and taxe-fonciere (6 files, 2.3K LOC) are available as demo/test codebases
- [ ] Best-effort parser failure policy applies: partial graph when parsing is incomplete
- [ ] Canonical IR Strategy A (typed AST + graph overlay) is the target integration model

## Notes

- Scope is bounded to graph construction only; graph storage, query API, and UI are separate features
- JCL and DB2/File/Table extraction are optional (P3); core value is CALLS, PERFORMS, USES_COPYBOOK, READS_FIELD, WRITES_FIELD
- "Unknown edges" as first-class outputs is a locked PRD decision; spec explicitly requires surfacing, not hiding
- Implementation technology (Python, Java, etc.) deferred to planning phase

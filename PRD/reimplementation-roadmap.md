# Reimplementation Roadmap (Exploration-First)

## Phase 1: Exploration System (Now)

- RAG chatbot with evidence-backed answers
- Dependency graph + lineage + impact analysis
- Module-level ROI and equivalence readiness scoring

Exit criteria:
- Users can answer key business-rule questions quickly
- Parse coverage and evidence quality stable on pilot corpus

## Phase 2: Assisted Reimplementation Pilot

- Candidate code generation for scoped, high-readiness modules
- Differential test harness (legacy vs generated)
- HITL review workflow and audit trails

Exit criteria:
- Consistent pass rates on selected module classes
- Human reviewers trust mismatch taxonomy and traceability

## Phase 3: Portfolio-Scale Migration Acceleration

- Batch candidate generation with priority queues by ROI/readiness
- Stronger semantic contracts and policy automation
- Integration into SDLC and release governance

Exit criteria:
- Repeatable modernization throughput with measurable risk control

## Prioritization Rule

A module enters Phase 2 only if:
- Readiness score >= threshold
- ROI score >= threshold
- Named human reviewers assigned

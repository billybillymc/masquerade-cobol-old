# Infrastructure and Deployment Questions

## Locked Decisions

- Deployment model: **external model mode first**
- MVP benchmark scale target: **500K LOC**
- Near-term post-MVP target: **3M+ LOC**
- Latency profile: **Reliability-first (Option A)**
- Reliability SLO profile: **Option A**

Decision tradeoff summary:
- We gain a realistic MVP delivery target that still demonstrates enterprise relevance.
- We avoid overcommitting the first release to showstopper-scale performance work.
- We keep a clear expansion narrative for sales and roadmap credibility.
- We accept that very large-estate proof points (3M+) are a near-term follow-on, not day-one.
- We prioritize trustworthy evidence and verifier depth over "instant" responses.
- We set strict reliability floors while preserving practical MVP delivery risk.
- We maximize early model capability with external inference, while enforcing local routing for sensitive/proprietary workloads.

## Deployment Model

Day-one target:
- [x] External model mode first
- [ ] Local/private mode first
- [ ] Both from day one

Rationale:

## Benchmark Scale Target

Largest codebase size to support in MVP benchmark:
- [ ] 100K LOC
- [x] 500K LOC
- [ ] 1M LOC
- [ ] 3M+ LOC

## Query Latency Targets

Production-usable p95 for:
- Lineage query: **4.0 seconds**
- Impact query: **6.0 seconds**
- RAG answer with citations: **9.0 seconds**

Stretch post-MVP targets (for later optimization):
- Lineage query: **2.0 seconds**
- Impact query: **3.0 seconds**
- RAG answer with citations: **5.0 seconds**

## Reliability Targets

Pick initial SLOs:
- Ingest success rate: **99.0%**
- Incremental refresh success rate: **99.5%**
- Parser coverage target: **90% overall; 95% for migration-candidate modules**

SLO tradeoff note:
- These targets prioritize stability and trustworthy migration gates over aggressive launch speed.
- The migration-candidate coverage threshold is intentionally higher to reduce false confidence in reimplementation workflows.


# analysis-orchestrator

Language target: Python.

## Responsibility

- Orchestrate ingest, retrieval, inference, and verifier flows.
- Enforce evidence contract for claims.
- Compute readiness signals and impact/lineage artifacts.
- Coordinate external-first inference with policy-gateway routing.

## Planned Interfaces

- `POST /analysis/run`
- `GET /analysis/run/{run_id}`
- `POST /analysis/query`
- `POST /analysis/impact`
- `POST /analysis/readiness-evaluate`
- `POST /analysis/readiness-from-validation`

## Local Run

```bash
pip install -e .[dev]
uvicorn app.main:app --reload --port 8011
pytest
```

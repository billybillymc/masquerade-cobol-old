# policy-gateway

Language target: TypeScript or Python.

## Responsibility

- Route inference requests using policy:
  - external-first by default,
  - force local/private for sensitive or proprietary workloads.
- Provide a mode-switch module with policy templates.
- Emit audit logs for every routing decision.

## Planned Interfaces

- `POST /policy/route`
- `POST /policy/switch-mode`
- `GET /policy/events/{run_id}`

## Local Run

```bash
pip install -e .[dev]
uvicorn app.main:app --reload --port 8010
pytest
```

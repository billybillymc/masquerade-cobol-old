# validation-harness

Language target: Python (with optional Java helpers).

## Responsibility

- Run differential validation between legacy and generated candidates.
- Enforce strict numeric emulation checks for migration-ready gates.
- Support sandbox bounded-equivalence runs (non-actionable).
- Emit mismatch taxonomy and confidence inputs.

## Planned Interfaces

- `POST /validation/run`
- `GET /validation/run/{run_id}`
- `GET /validation/run/{run_id}/diff`

## Local Run

```bash
pip install -e .[dev]
uvicorn app.main:app --reload --port 8012
pytest
```

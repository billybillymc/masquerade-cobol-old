# E2E Flow

`run-flow.py` validates the local end-to-end path:

1. policy routing (`sensitive` -> `local_private`)
2. validation harness run
3. readiness evaluation from validation output
4. negative strict-numeric case blocking migration-ready

## Usage

Start services:

```bash
powershell -File scripts/dev.ps1 start
```

Run flow:

```bash
powershell -File scripts/dev.ps1 e2e
```

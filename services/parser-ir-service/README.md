# parser-ir-service

Language target: Java/Kotlin.

## Responsibility

- Parse IBM Enterprise COBOL and resolve copybooks.
- Emit typed AST with stable IDs.
- Emit graph overlay edges for downstream analysis.
- Produce parse diagnostics and coverage metrics.

## Planned Interfaces

- `POST /parse/run`
- `GET /parse/run/{run_id}`
- `GET /parse/run/{run_id}/artifacts`

## Output Artifacts

- `ast.json`
- `graph-overlay.json`
- `parse-diagnostics.json`
- `coverage-report.json`

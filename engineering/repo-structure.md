# Recommended Repository Structure

```text
masquerade-cobol/
  PRD/
  engineering/
  services/
    parser-ir-service/         # Java/Kotlin
    analysis-orchestrator/     # Python
    validation-harness/        # Python (+ optional Java helpers)
    policy-gateway/            # TS or Python
    web-app/                   # TypeScript (Next.js)
  packages/
    schemas/                   # shared JSON schema / protobuf / pydantic defs
    sdk/                       # internal client libraries for service contracts
  infra/
    docker/
    k8s/
    terraform/
  scripts/
    eval/
    benchmark/
    migration-gates/
  data/
    fixtures/
    golden/
```

## Notes

- Keep shared schemas versioned and immutable by release.
- Make policy-routing tests part of CI required checks.
- Treat eval/benchmark scripts as first-class product infrastructure.

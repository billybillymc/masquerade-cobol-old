from fastapi import FastAPI
from pydantic import BaseModel, Field


class ValidationRunRequest(BaseModel):
    run_id: str = Field(min_length=1)
    module_id: str = Field(min_length=1)
    mode: str = Field(pattern="^(migration_ready|sandbox)$")
    total_cases: int = Field(ge=1)
    fail_count: int = Field(ge=0)
    strict_numeric_emulation_passed: bool


class ValidationSummary(BaseModel):
    total_cases: int
    pass_count: int
    fail_count: int
    diff_pass_rate: float


class Mismatch(BaseModel):
    case_id: str
    class_: str = Field(alias="class")
    severity: str = Field(pattern="^(low|medium|high)$")
    detail: str


class ConfidenceInputs(BaseModel):
    numeric_semantics_score: float = Field(ge=0, le=1)
    behavioral_match_score: float = Field(ge=0, le=1)


class ValidationRunResult(BaseModel):
    run_id: str
    module_id: str
    mode: str
    strict_numeric_emulation_passed: bool
    high_assurance_ready: bool
    non_actionable: bool
    summary: ValidationSummary
    mismatches: list[Mismatch]
    confidence_inputs: ConfidenceInputs


app = FastAPI(title="validation-harness", version="0.1.0")

RUN_RESULTS: dict[str, ValidationRunResult] = {}


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "validation-harness"}


@app.post("/validation/run", response_model=ValidationRunResult)
def run_validation(payload: ValidationRunRequest) -> ValidationRunResult:
    pass_count = max(payload.total_cases - payload.fail_count, 0)
    pass_rate = pass_count / payload.total_cases

    high_assurance_ready = (
        payload.mode == "migration_ready"
        and payload.strict_numeric_emulation_passed
        and payload.fail_count == 0
    )
    non_actionable = payload.mode == "sandbox"

    mismatches: list[Mismatch] = []
    if payload.fail_count > 0:
        mismatches.append(
            Mismatch(
                case_id="case-001",
                **{"class": "numeric_semantics"},
                severity="high",
                detail="Deterministic scaffold mismatch for failing case(s).",
            )
        )

    result = ValidationRunResult(
        run_id=payload.run_id,
        module_id=payload.module_id,
        mode=payload.mode,
        strict_numeric_emulation_passed=payload.strict_numeric_emulation_passed,
        high_assurance_ready=high_assurance_ready,
        non_actionable=non_actionable,
        summary=ValidationSummary(
            total_cases=payload.total_cases,
            pass_count=pass_count,
            fail_count=payload.fail_count,
            diff_pass_rate=pass_rate,
        ),
        mismatches=mismatches,
        confidence_inputs=ConfidenceInputs(
            numeric_semantics_score=1.0 if payload.strict_numeric_emulation_passed else 0.4,
            behavioral_match_score=pass_rate,
        ),
    )
    RUN_RESULTS[payload.run_id] = result
    return result


@app.get("/validation/run/{run_id}", response_model=ValidationRunResult)
def get_validation_run(run_id: str) -> ValidationRunResult:
    return RUN_RESULTS[run_id]


@app.get("/validation/run/{run_id}/diff")
def get_validation_diff(run_id: str) -> dict:
    result = RUN_RESULTS[run_id]
    return {
        "run_id": result.run_id,
        "module_id": result.module_id,
        "mismatches": [m.model_dump(by_alias=True) for m in result.mismatches],
        "diff_pass_rate": result.summary.diff_pass_rate,
    }

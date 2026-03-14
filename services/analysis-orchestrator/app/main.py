from fastapi import FastAPI
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    run_id: str = Field(min_length=1)
    question: str = Field(min_length=3)
    module_scope: str | None = None


class QueryResponse(BaseModel):
    run_id: str
    answer: str
    claims: list[dict]


class ApprovalState(BaseModel):
    modernization_engineer: bool
    domain_sme: bool
    risk_controls_owner: bool


class ReadinessEvaluateRequest(BaseModel):
    module_id: str = Field(min_length=1)
    readiness_score: float = Field(ge=0, le=1)
    threshold_profile: str = Field(pattern="^(strict|standard|permissive)$")
    high_assurance_recompute_passed: bool
    strict_numeric_emulation_passed: bool
    required_approvals: ApprovalState


class ReadinessGateResponse(BaseModel):
    module_id: str
    readiness_score: float
    threshold_profile: str
    high_assurance_recompute_passed: bool
    strict_numeric_emulation_passed: bool
    required_approvals: ApprovalState
    blockers: list[str]
    migration_ready: bool


class ReadinessFromValidationRequest(BaseModel):
    module_id: str = Field(min_length=1)
    readiness_score: float = Field(ge=0, le=1)
    threshold_profile: str = Field(pattern="^(strict|standard|permissive)$")
    high_assurance_recompute_passed: bool
    required_approvals: ApprovalState
    validation_result: dict


app = FastAPI(title="analysis-orchestrator", version="0.1.0")

PROFILE_MIN_SCORE: dict[str, float] = {"strict": 0.85, "standard": 0.70, "permissive": 0.60}


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "analysis-orchestrator"}


@app.post("/analysis/run")
def start_run(codebase_id: str) -> dict[str, str]:
    # Stubbed run id for scaffold phase.
    return {"codebase_id": codebase_id, "run_id": "run-001", "status": "started"}


@app.post("/analysis/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    # Stub response with contract-aligned claim shape.
    claim = {
        "claim_id": "claim-001",
        "claim_text": "Potential late fee logic found in scoped module.",
        "support_strength": "medium",
        "confidence_score": 0.74,
        "review_status": "needs-human",
        "evidence": [{"source_id": "program:DEMO1", "span_ref": "120-140"}],
    }
    return QueryResponse(
        run_id=payload.run_id,
        answer="Preliminary analysis complete. One candidate rule identified.",
        claims=[claim],
    )


@app.post("/analysis/readiness-evaluate", response_model=ReadinessGateResponse)
def readiness_evaluate(payload: ReadinessEvaluateRequest) -> ReadinessGateResponse:
    blockers: list[str] = []

    if payload.threshold_profile == "permissive":
        blockers.append("profile_not_eligible_for_migration_ready")

    required_min = PROFILE_MIN_SCORE[payload.threshold_profile]
    if payload.readiness_score < required_min:
        blockers.append("readiness_score_below_profile_threshold")

    if not payload.high_assurance_recompute_passed:
        blockers.append("high_assurance_recompute_required")

    if not payload.strict_numeric_emulation_passed:
        blockers.append("strict_numeric_emulation_required")

    approvals = payload.required_approvals
    if not approvals.modernization_engineer:
        blockers.append("missing_approval_modernization_engineer")
    if not approvals.domain_sme:
        blockers.append("missing_approval_domain_sme")
    if not approvals.risk_controls_owner:
        blockers.append("missing_approval_risk_controls_owner")

    return ReadinessGateResponse(
        module_id=payload.module_id,
        readiness_score=payload.readiness_score,
        threshold_profile=payload.threshold_profile,
        high_assurance_recompute_passed=payload.high_assurance_recompute_passed,
        strict_numeric_emulation_passed=payload.strict_numeric_emulation_passed,
        required_approvals=payload.required_approvals,
        blockers=blockers,
        migration_ready=len(blockers) == 0,
    )


@app.post("/analysis/readiness-from-validation", response_model=ReadinessGateResponse)
def readiness_from_validation(payload: ReadinessFromValidationRequest) -> ReadinessGateResponse:
    strict_numeric_passed = bool(
        payload.validation_result.get("strict_numeric_emulation_passed", False)
    )
    request = ReadinessEvaluateRequest(
        module_id=payload.module_id,
        readiness_score=payload.readiness_score,
        threshold_profile=payload.threshold_profile,
        high_assurance_recompute_passed=payload.high_assurance_recompute_passed,
        strict_numeric_emulation_passed=strict_numeric_passed,
        required_approvals=payload.required_approvals,
    )
    return readiness_evaluate(request)

from fastapi import FastAPI
from pydantic import BaseModel, Field


class RouteRequest(BaseModel):
    request_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    run_id: str | None = None
    workload_classification: str = Field(
        pattern="^(sensitive|proprietary|standard|public)$"
    )
    policy_template: str = Field(
        default="standard-external",
        pattern="^(standard-external|sensitive-local|custom)$",
    )


class RouteDecision(BaseModel):
    request_id: str
    tenant_id: str
    workload_classification: str
    selected_mode: str
    policy_template: str
    reason_codes: list[str]
    audit_required: bool = True


class SwitchModeRequest(BaseModel):
    tenant_id: str = Field(min_length=1)
    policy_template: str = Field(
        pattern="^(standard-external|sensitive-local|custom)$"
    )


class PolicyEvent(BaseModel):
    event_type: str
    request_id: str | None = None
    run_id: str | None = None
    tenant_id: str
    policy_template: str
    selected_mode: str | None = None
    reason_codes: list[str] = Field(default_factory=list)


app = FastAPI(title="policy-gateway", version="0.1.0")

POLICY_TEMPLATES: dict[str, dict[str, str]] = {
    "standard-external": {"default_mode": "external"},
    "sensitive-local": {"default_mode": "local_private"},
    "custom": {"default_mode": "external"},
}
TENANT_POLICY_TEMPLATE: dict[str, str] = {}
POLICY_EVENTS: list[PolicyEvent] = []


def _resolve_template(payload: RouteRequest) -> str:
    if payload.policy_template != "custom":
        return payload.policy_template
    return TENANT_POLICY_TEMPLATE.get(payload.tenant_id, "standard-external")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "policy-gateway"}


@app.post("/policy/route", response_model=RouteDecision)
def route_policy(payload: RouteRequest) -> RouteDecision:
    template = _resolve_template(payload)
    template_default = POLICY_TEMPLATES[template]["default_mode"]
    force_local = payload.workload_classification in {"sensitive", "proprietary"}
    selected_mode = "local_private" if force_local else template_default
    reasons = (
        ["classification_forced_local", f"template:{template}"]
        if force_local
        else [f"template:{template}"]
    )
    decision = RouteDecision(
        request_id=payload.request_id,
        tenant_id=payload.tenant_id,
        workload_classification=payload.workload_classification,
        selected_mode=selected_mode,
        policy_template=template,
        reason_codes=reasons,
        audit_required=True,
    )
    POLICY_EVENTS.append(
        PolicyEvent(
            event_type="route_decision",
            request_id=payload.request_id,
            run_id=payload.run_id,
            tenant_id=payload.tenant_id,
            policy_template=template,
            selected_mode=selected_mode,
            reason_codes=reasons,
        )
    )
    return decision


@app.post("/policy/switch-mode")
def switch_mode(payload: SwitchModeRequest) -> dict[str, str]:
    TENANT_POLICY_TEMPLATE[payload.tenant_id] = payload.policy_template
    POLICY_EVENTS.append(
        PolicyEvent(
            event_type="mode_switch",
            tenant_id=payload.tenant_id,
            policy_template=payload.policy_template,
            selected_mode=None,
            reason_codes=["tenant_template_updated"],
        )
    )
    return {
        "tenant_id": payload.tenant_id,
        "policy_template": payload.policy_template,
        "status": "accepted",
    }


@app.get("/policy/events/{run_id}")
def get_events(run_id: str) -> list[PolicyEvent]:
    return [event for event in POLICY_EVENTS if event.run_id == run_id]

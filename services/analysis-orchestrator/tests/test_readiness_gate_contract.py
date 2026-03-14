import json
from pathlib import Path

import jsonschema
from fastapi.testclient import TestClient

from app.main import app


def test_readiness_gate_matches_schema() -> None:
    client = TestClient(app)
    payload_path = Path(__file__).parent / "fixtures" / "readiness_evaluate_request.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    response = client.post("/analysis/readiness-evaluate", json=payload)
    assert response.status_code == 200

    schema_path = (
        Path(__file__).resolve().parents[3]
        / "packages"
        / "schemas"
        / "readiness-gate.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=response.json(), schema=schema)


def test_permissive_profile_cannot_be_migration_ready() -> None:
    client = TestClient(app)
    payload = {
        "module_id": "module-perm",
        "readiness_score": 0.95,
        "threshold_profile": "permissive",
        "high_assurance_recompute_passed": True,
        "strict_numeric_emulation_passed": True,
        "required_approvals": {
            "modernization_engineer": True,
            "domain_sme": True,
            "risk_controls_owner": True,
        },
    }
    response = client.post("/analysis/readiness-evaluate", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["migration_ready"] is False
    assert "profile_not_eligible_for_migration_ready" in body["blockers"]

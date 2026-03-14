from fastapi.testclient import TestClient

from app.main import app


def test_readiness_from_validation_blocks_on_failed_numeric() -> None:
    client = TestClient(app)
    payload = {
        "module_id": "module-a",
        "readiness_score": 0.91,
        "threshold_profile": "standard",
        "high_assurance_recompute_passed": True,
        "required_approvals": {
            "modernization_engineer": True,
            "domain_sme": True,
            "risk_controls_owner": True
        },
        "validation_result": {
            "strict_numeric_emulation_passed": False,
            "mode": "migration_ready"
        }
    }
    response = client.post("/analysis/readiness-from-validation", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["migration_ready"] is False
    assert "strict_numeric_emulation_required" in body["blockers"]

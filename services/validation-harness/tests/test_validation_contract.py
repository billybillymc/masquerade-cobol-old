import json
from pathlib import Path

import jsonschema
from fastapi.testclient import TestClient

from app.main import app


def test_validation_run_matches_schema() -> None:
    client = TestClient(app)
    fixture_path = Path(__file__).parent / "fixtures" / "validation_run_request.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    response = client.post("/validation/run", json=payload)
    assert response.status_code == 200

    schema_path = (
        Path(__file__).resolve().parents[3]
        / "packages"
        / "schemas"
        / "validation-run.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=response.json(), schema=schema)


def test_sandbox_result_is_non_actionable() -> None:
    client = TestClient(app)
    payload = {
        "run_id": "run-sandbox",
        "module_id": "module-sandbox",
        "mode": "sandbox",
        "total_cases": 10,
        "fail_count": 2,
        "strict_numeric_emulation_passed": False
    }
    response = client.post("/validation/run", json=payload)
    assert response.status_code == 200
    assert response.json()["non_actionable"] is True
    assert response.json()["high_assurance_ready"] is False

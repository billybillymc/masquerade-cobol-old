import json
from pathlib import Path

import jsonschema
from fastapi.testclient import TestClient

from app.main import app


def test_policy_route_matches_schema() -> None:
    client = TestClient(app)
    fixture_path = Path(__file__).parent / "fixtures" / "policy_route_request.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    response = client.post("/policy/route", json=payload)
    assert response.status_code == 200

    schema_path = (
        Path(__file__).resolve().parents[3]
        / "packages"
        / "schemas"
        / "policy-routing-decision.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=response.json(), schema=schema)

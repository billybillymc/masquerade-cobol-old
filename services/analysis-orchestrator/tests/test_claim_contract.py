import json
from pathlib import Path

import jsonschema
from fastapi.testclient import TestClient

from app.main import app


def test_stub_claim_matches_claim_schema() -> None:
    client = TestClient(app)
    payload_path = Path(__file__).parent / "fixtures" / "analysis_query_request.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    response = client.post("/analysis/query", json=payload)
    assert response.status_code == 200

    claim = response.json()["claims"][0]
    schema_path = (
        Path(__file__).resolve().parents[3] / "packages" / "schemas" / "claim.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=claim, schema=schema)

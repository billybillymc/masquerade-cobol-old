from fastapi.testclient import TestClient

from app.main import app


def test_sensitive_classification_forces_local_mode() -> None:
    client = TestClient(app)
    payload = {
        "request_id": "req-sensitive",
        "tenant_id": "tenant-a",
        "run_id": "run-sensitive",
        "workload_classification": "sensitive",
        "policy_template": "standard-external",
    }
    response = client.post("/policy/route", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["selected_mode"] == "local_private"
    assert "classification_forced_local" in body["reason_codes"]


def test_switch_mode_updates_custom_resolution() -> None:
    client = TestClient(app)
    switch_payload = {"tenant_id": "tenant-custom", "policy_template": "sensitive-local"}
    switch_response = client.post("/policy/switch-mode", json=switch_payload)
    assert switch_response.status_code == 200

    route_payload = {
        "request_id": "req-custom",
        "tenant_id": "tenant-custom",
        "run_id": "run-custom",
        "workload_classification": "standard",
        "policy_template": "custom",
    }
    route_response = client.post("/policy/route", json=route_payload)
    assert route_response.status_code == 200
    assert route_response.json()["selected_mode"] == "local_private"
    assert route_response.json()["policy_template"] == "sensitive-local"

    events_response = client.get("/policy/events/run-custom")
    assert events_response.status_code == 200
    assert len(events_response.json()) >= 1

import json
import sys
import urllib.error
import urllib.request


POLICY_BASE = "http://127.0.0.1:8010"
ANALYSIS_BASE = "http://127.0.0.1:8011"
VALIDATION_BASE = "http://127.0.0.1:8012"


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    try:
        route = post_json(
            f"{POLICY_BASE}/policy/route",
            {
                "request_id": "e2e-req-001",
                "tenant_id": "tenant-e2e",
                "run_id": "run-e2e-001",
                "workload_classification": "sensitive",
                "policy_template": "standard-external",
            },
        )
        assert_true(route["selected_mode"] == "local_private", "Sensitive routing did not force local.")

        validation = post_json(
            f"{VALIDATION_BASE}/validation/run",
            {
                "run_id": "run-val-e2e-001",
                "module_id": "module-e2e-001",
                "mode": "migration_ready",
                "total_cases": 12,
                "fail_count": 0,
                "strict_numeric_emulation_passed": True,
            },
        )
        assert_true(validation["high_assurance_ready"] is True, "Validation did not mark high-assurance ready.")

        readiness = post_json(
            f"{ANALYSIS_BASE}/analysis/readiness-from-validation",
            {
                "module_id": "module-e2e-001",
                "readiness_score": 0.91,
                "threshold_profile": "standard",
                "high_assurance_recompute_passed": True,
                "required_approvals": {
                    "modernization_engineer": True,
                    "domain_sme": True,
                    "risk_controls_owner": True,
                },
                "validation_result": validation,
            },
        )
        assert_true(readiness["migration_ready"] is True, "Expected migration_ready=true for passing flow.")

        negative_validation = post_json(
            f"{VALIDATION_BASE}/validation/run",
            {
                "run_id": "run-val-e2e-002",
                "module_id": "module-e2e-002",
                "mode": "migration_ready",
                "total_cases": 8,
                "fail_count": 1,
                "strict_numeric_emulation_passed": False,
            },
        )
        negative_readiness = post_json(
            f"{ANALYSIS_BASE}/analysis/readiness-from-validation",
            {
                "module_id": "module-e2e-002",
                "readiness_score": 0.93,
                "threshold_profile": "standard",
                "high_assurance_recompute_passed": True,
                "required_approvals": {
                    "modernization_engineer": True,
                    "domain_sme": True,
                    "risk_controls_owner": True,
                },
                "validation_result": negative_validation,
            },
        )
        assert_true(
            negative_readiness["migration_ready"] is False,
            "Expected migration_ready=false when strict numeric fails.",
        )
        assert_true(
            "strict_numeric_emulation_required" in negative_readiness["blockers"],
            "Missing strict numeric blocker in negative flow.",
        )

        print("E2E flow passed.")
        return 0
    except (AssertionError, urllib.error.URLError, TimeoutError) as exc:
        print(f"E2E flow failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

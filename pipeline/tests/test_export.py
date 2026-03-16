"""Tests for export.py — CSV/JSON export."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from export import export_all


class TestExport:
    def test_exports_carddemo(self):
        carddemo = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
        if not carddemo.exists():
            return
        result = export_all(str(carddemo))
        assert result["programs"] > 20
        assert Path(result["csv"]).exists()
        assert Path(result["json"]).exists()

        # Verify CSV
        with open(result["csv"], "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) > 20
        assert "program" in rows[0]
        assert "effort_days" in rows[0]
        assert "readiness_score" in rows[0]

        # Verify JSON
        with open(result["json"], "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["summary"]["total_programs"] > 20
        assert data["effort_estimate"]["total_effort_days"] > 0
        assert len(data["programs"]) > 20
        assert "migration_waves" in data

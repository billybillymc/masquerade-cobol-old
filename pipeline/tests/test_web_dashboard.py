"""Tests for web_dashboard.py — Flask API and dashboard."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from web_dashboard import app, CODEBASES


class TestDashboardAPI:
    def setup_method(self):
        app.testing = True
        self.client = app.test_client()

    def test_index_returns_html(self):
        response = self.client.get("/")
        assert response.status_code == 200
        assert b"Masquerade" in response.data

    def test_codebases_api(self):
        response = self.client.get("/api/codebases")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
        if CODEBASES:
            assert len(data) > 0

    def test_codebase_detail_api(self):
        if not CODEBASES:
            return
        name = list(CODEBASES.keys())[0]
        response = self.client.get(f"/api/codebase/{name}")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "summary" in data
        assert "programs" in data
        assert len(data["programs"]) > 0

    def test_program_detail_api(self):
        if not CODEBASES:
            return
        name = list(CODEBASES.keys())[0]
        cb_response = self.client.get(f"/api/codebase/{name}")
        cb_data = json.loads(cb_response.data)
        programs_with_code = [p for p in cb_data["programs"] if p.get("code_lines", 0) > 0]
        if not programs_with_code:
            return
        pgm = programs_with_code[0]["program"]
        response = self.client.get(f"/api/codebase/{name}/program/{pgm}")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["program"] == pgm
        assert "paragraphs" in data
        assert "readiness_score" in data

    def test_unknown_codebase_404(self):
        response = self.client.get("/api/codebase/nonexistent")
        assert response.status_code == 404

    def test_unknown_program_404(self):
        if not CODEBASES:
            return
        name = list(CODEBASES.keys())[0]
        response = self.client.get(f"/api/codebase/{name}/program/NONEXISTENT")
        assert response.status_code == 404

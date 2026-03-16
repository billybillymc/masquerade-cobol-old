"""Tests for complexity.py — cyclomatic complexity measurement."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from complexity import compute_complexity, complexity_grade, compute_all


def _write_cbl(tmp_dir, name, content):
    p = Path(tmp_dir) / f"{name}.cbl"
    p.write_text(content, encoding="utf-8")
    return str(p)


class TestCyclomaticComplexity:
    def test_simple_linear_program(self, tmp_path):
        path = _write_cbl(tmp_path, "LINEAR", """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LINEAR.
       PROCEDURE DIVISION.
       MAIN-PARA.
           MOVE 1 TO WS-COUNT.
           DISPLAY WS-COUNT.
           STOP RUN.
""")
        r = compute_complexity(path)
        assert r is not None
        assert r.cyclomatic == 1
        assert r.decision_points == 0

    def test_single_if(self, tmp_path):
        path = _write_cbl(tmp_path, "ONEIF", """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONEIF.
       PROCEDURE DIVISION.
       MAIN-PARA.
           IF WS-FLAG = 'Y'
               DISPLAY 'YES'
           END-IF.
           STOP RUN.
""")
        r = compute_complexity(path)
        assert r.cyclomatic == 2
        assert r.decision_points == 1

    def test_evaluate_with_whens(self, tmp_path):
        path = _write_cbl(tmp_path, "EVAL", """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. EVAL.
       PROCEDURE DIVISION.
       MAIN-PARA.
           EVALUATE WS-CODE
               WHEN 'A'
                   DISPLAY 'ALPHA'
               WHEN 'B'
                   DISPLAY 'BRAVO'
               WHEN OTHER
                   DISPLAY 'OTHER'
           END-EVALUATE.
           STOP RUN.
""")
        r = compute_complexity(path)
        assert r.decision_points >= 3
        assert r.cyclomatic >= 4

    def test_nested_ifs_track_nesting(self, tmp_path):
        path = _write_cbl(tmp_path, "NESTED", """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. NESTED.
       PROCEDURE DIVISION.
       MAIN-PARA.
           IF WS-A = 1
               IF WS-B = 2
                   IF WS-C = 3
                       DISPLAY 'DEEP'
                   END-IF
               END-IF
           END-IF.
           STOP RUN.
""")
        r = compute_complexity(path)
        assert r.max_nesting >= 3
        assert r.decision_points == 3

    def test_perform_until_counted(self, tmp_path):
        path = _write_cbl(tmp_path, "LOOP", """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LOOP.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM PROCESS-RECORD UNTIL WS-EOF = 'Y'.
           STOP RUN.
       PROCESS-RECORD.
           READ INPUT-FILE
               AT END
                   MOVE 'Y' TO WS-EOF
               NOT AT END
                   ADD 1 TO WS-COUNT
           END-READ.
""")
        r = compute_complexity(path)
        assert r.decision_points >= 3

    def test_paragraph_hotspots(self, tmp_path):
        path = _write_cbl(tmp_path, "HOTSPOT", """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. HOTSPOT.
       PROCEDURE DIVISION.
       SIMPLE-PARA.
           DISPLAY 'HELLO'.
       COMPLEX-PARA.
           IF WS-A = 1
               DISPLAY 'A'
           END-IF.
           IF WS-B = 2
               DISPLAY 'B'
           END-IF.
           IF WS-C = 3
               DISPLAY 'C'
           END-IF.
""")
        r = compute_complexity(path)
        assert len(r.hotspot_paragraphs) >= 1
        assert r.hotspot_paragraphs[0]["paragraph"] == "COMPLEX-PARA"


class TestComplexityGrade:
    def test_low(self):
        assert complexity_grade(5, 100) == "LOW"

    def test_moderate(self):
        assert complexity_grade(20, 300) == "MODERATE"

    def test_high(self):
        assert complexity_grade(45, 500) == "HIGH"

    def test_very_high(self):
        assert complexity_grade(80, 1000) == "VERY HIGH"


class TestComputeAll:
    def test_real_carddemo(self):
        carddemo = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "carddemo"
        if not carddemo.exists():
            return
        results = compute_all(str(carddemo))
        assert len(results) > 20
        total_cyclo = sum(r.cyclomatic for r in results)
        assert total_cyclo > 50

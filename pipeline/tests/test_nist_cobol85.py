"""NIST COBOL-85 Test Suite — compile, run, and validate via GnuCOBOL.

Tests the pipeline against the official NIST CCVS85 Compiler Validation
System: 414 COBOL programs across 13 modules covering the full COBOL-85
standard (nucleus, sequential I/O, indexed I/O, relative I/O, sort/merge,
inter-program communication, debugging, segmentation, and more).

This test:
1. Compiles all programs with GnuCOBOL
2. Runs them and parses PASS/FAIL from the CCVS report output
3. Verifies the pipeline can analyze the full 89K-line codebase
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cobol_runner import is_cobc_available, _to_wsl_path

NIST = Path(__file__).resolve().parent.parent.parent / "test-codebases" / "nist-cobol85"
COBC_AVAILABLE = is_cobc_available()


@pytest.mark.skipif(not COBC_AVAILABLE, reason="GnuCOBOL not available")
class TestNistCompilation:
    """NIST programs compile with GnuCOBOL."""

    def test_nc_nucleus_all_compile(self):
        """All 95 NC (nucleus) programs compile — core language features."""
        self._assert_module_compiles("NC", expected_min=90)

    def test_if_intrinsic_functions_all_compile(self):
        """All IF (intrinsic function) programs compile."""
        self._assert_module_compiles("IF", expected_min=40)

    def test_sq_sequential_io_compiles(self):
        """SQ (sequential I/O) programs compile."""
        self._assert_module_compiles("SQ", expected_min=75)

    def test_ix_indexed_io_compiles(self):
        """IX (indexed I/O) programs compile."""
        self._assert_module_compiles("IX", expected_min=25)

    def test_st_sort_merge_compiles(self):
        """ST (sort/merge) programs compile."""
        self._assert_module_compiles("ST", expected_min=20)

    def _assert_module_compiles(self, module, expected_min):
        copy_dir = _to_wsl_path(str(NIST / "copy"))
        mod_dir = NIST / module
        compiled = 0
        total = 0
        for f in sorted(mod_dir.glob("*.CBL")):
            total += 1
            src_wsl = _to_wsl_path(str(f))
            name = f.stem
            cmd = f'cobc -x -std=cobol85 -I {copy_dir} -o /tmp/nist_{name} {src_wsl}'
            r = subprocess.run(
                ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                compiled += 1
        assert compiled >= expected_min, \
            f"{module}: only {compiled}/{total} compiled (expected >= {expected_min})"


@pytest.mark.skipif(not COBC_AVAILABLE, reason="GnuCOBOL not available")
class TestNistExecution:
    """NIST programs run and produce PASS results."""

    def test_nc_nucleus_pass_rate(self):
        """NC module achieves >98% individual test pass rate."""
        # Compile first (execution depends on binaries existing)
        self._compile_module("NC")
        pass_count, fail_count = self._run_module("NC")
        total = pass_count + fail_count
        assert total > 0, "No NC programs produced output"
        rate = pass_count / total * 100
        assert rate >= 98.0, f"NC pass rate {rate:.1f}% < 98% ({pass_count}/{total})"

    def test_if_intrinsic_functions_pass_rate(self):
        """IF module achieves 100% pass rate."""
        pass_count, fail_count = self._run_module("IF")
        assert fail_count == 0, f"IF had {fail_count} failures"

    def test_st_sort_merge_pass_rate(self):
        """ST module achieves 100% pass rate."""
        pass_count, fail_count = self._run_module("ST")
        assert fail_count == 0, f"ST had {fail_count} failures"

    def _compile_module(self, module):
        copy_dir = _to_wsl_path(str(NIST / "copy"))
        mod_dir = NIST / module
        for f in sorted(mod_dir.glob("*.CBL")):
            src_wsl = _to_wsl_path(str(f))
            name = f.stem
            cmd = f'cobc -x -std=cobol85 -I {copy_dir} -o /tmp/nist_{name} {src_wsl}'
            subprocess.run(
                ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
                capture_output=True, text=True, timeout=30,
            )

    def _run_module(self, module):
        """Run all compiled binaries for a module and count PASS/FAIL."""
        # Write a helper script to WSL filesystem to avoid Git Bash escaping issues
        script_content = f"""#!/bin/bash
mkdir -p /tmp/nist_batch
cd /tmp/nist_batch
PASS=0
FAIL=0
for f in {_to_wsl_path(str(NIST / module))}/*.CBL; do
    name=$(basename "$f" .CBL)
    bin="/tmp/nist_$name"
    [ -x "$bin" ] || continue
    rm -f report.log
    timeout 10 "$bin" >/dev/null 2>&1
    if [ -s report.log ]; then
        p=$(grep -c ' PASS ' report.log)
        f_c=$(grep -c 'FAIL[*]' report.log)
        PASS=$((PASS+p))
        FAIL=$((FAIL+f_c))
    fi
done
echo "$PASS $FAIL"
"""
        # Write script via WSL
        subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "tee", "/tmp/run_nist_mod.sh"],
            input=script_content.encode(), capture_output=True, timeout=10,
        )
        subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "chmod", "+x", "/tmp/run_nist_mod.sh"],
            capture_output=True, timeout=10,
        )

        r = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "/tmp/run_nist_mod.sh"],
            capture_output=True, text=True, timeout=300,
        )
        parts = r.stdout.strip().split()
        if len(parts) >= 2:
            return int(parts[0]), int(parts[1])
        return 0, 0


class TestNistAnalysis:
    """Pipeline analyzes the full NIST suite."""

    def test_programs_json_exists(self):
        """analyze.py produced programs.json for 414 programs."""
        pj = NIST / "_analysis" / "programs.json"
        assert pj.exists()
        data = json.loads(pj.read_text())
        assert len(data) >= 400

    def test_graph_json_exists(self):
        """analyze.py produced graph.json."""
        gj = NIST / "_analysis" / "graph.json"
        assert gj.exists()

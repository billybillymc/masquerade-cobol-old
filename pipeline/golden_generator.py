"""
Golden vector generator — automate mock data → COBOL compile+run → capture output
→ save as golden test vectors for the differential harness (IQ-09).

Orchestrates:
1. Write a COBOL seed program to create indexed/sequential input files
2. Compile the target program + any stubs (e.g., COBDATFT)
3. Run with file assignments
4. Parse stdout for DISPLAY output (field-by-field values)
5. Save as golden vectors in _analysis/golden_vectors/{program}.json
"""

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cobol_runner import compile_cobol, run_cobol, _to_wsl_path
from differential_harness import DiffVector, save_golden_vectors


@dataclass
class GoldenRunConfig:
    """Configuration for a golden vector generation run."""
    program: str                   # e.g., "CBACT01C"
    source_file: str               # path to .cbl
    copybook_dirs: list[str]       # paths to copybook directories
    stub_files: list[str] = field(default_factory=list)  # compiled stubs to link
    input_records: list[dict] = field(default_factory=list)  # mock input data
    file_assignments: dict = field(default_factory=dict)  # COBOL name → WSL path
    output_file_names: list[str] = field(default_factory=list)  # output file COBOL names


def parse_display_output(stdout: str, program: str) -> list[dict]:
    """Parse COBOL DISPLAY output into field-value dicts.

    CBACT01C outputs lines like:
        ACCT-ID                 :12345678901
        ACCT-CURR-BAL           :000000500000+

    Each block separated by a '---' line is one record.
    """
    records = []
    current = {}

    for line in stdout.splitlines():
        line = line.strip()

        if line.startswith("---------") and current:
            records.append(current)
            current = {}
            continue

        # Match "FIELD-NAME     :VALUE" pattern
        m = re.match(r'^([A-Z0-9][\w-]+)\s*:\s*(.*)$', line)
        if m:
            field_name = m.group(1).strip()
            value = m.group(2).strip()
            current[field_name] = value

    # Capture last record if no trailing separator
    if current:
        records.append(current)

    return records


def generate_golden_vectors(
    config: GoldenRunConfig,
    work_dir: str = "/tmp/golden_test",
) -> list[DiffVector]:
    """Run a COBOL program and capture output as golden test vectors.

    Args:
        config: Program configuration with source, stubs, file assignments
        work_dir: WSL working directory for temp files

    Returns:
        List of DiffVector objects with expected_outputs populated from
        the COBOL program's DISPLAY output.
    """
    import subprocess

    # Ensure work dir exists
    subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "mkdir", "-p", work_dir],
        capture_output=True, timeout=10,
    )

    # Compile stubs
    stub_objects = []
    for stub_file in config.stub_files:
        stub_wsl = _to_wsl_path(stub_file)
        stem = Path(stub_file).stem
        obj_path = f"{work_dir}/{stem}.o"

        cpy_args = []
        for cpd in config.copybook_dirs:
            cpy_args.extend(["-I", _to_wsl_path(cpd)])

        cmd = f'cobc -std=ibm {" ".join(cpy_args)} -c -o {obj_path} {stub_wsl}'
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Stub compilation failed for {stub_file}: {result.stderr}")
        stub_objects.append(obj_path)

    # Compile main program with stubs
    src_wsl = _to_wsl_path(config.source_file)
    binary_path = f"{work_dir}/{config.program.lower()}"

    cpy_args = []
    for cpd in config.copybook_dirs:
        cpy_args.extend(["-I", _to_wsl_path(cpd)])

    obj_args = " ".join(stub_objects)
    cmd = f'cobc -x -std=ibm {" ".join(cpy_args)} -o {binary_path} {src_wsl} {obj_args}'
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Compilation failed for {config.program}: {result.stderr}")

    # Build environment and run
    env_lines = []
    for cobol_name, file_path in config.file_assignments.items():
        env_lines.append(f'export {cobol_name}="{file_path}"')

    # Touch output files
    for name in config.output_file_names:
        path = config.file_assignments.get(name, f"{work_dir}/{name.lower()}.dat")
        env_lines.append(f'touch "{path}"')

    env_block = "\n".join(env_lines)
    run_cmd = f"{env_block}\n{binary_path}"

    result = subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-c", run_cmd],
        capture_output=True, text=True, timeout=30,
    )

    if result.returncode != 0 and "END OF EXECUTION" not in result.stdout:
        raise RuntimeError(
            f"Execution failed for {config.program} (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    # Parse DISPLAY output into records
    output_records = parse_display_output(result.stdout, config.program)

    # Build test vectors
    vectors = []
    for i, (inp, out) in enumerate(zip(config.input_records, output_records)):
        vectors.append(DiffVector(
            vector_id=f"{config.program}-V{i+1:03d}",
            program=config.program,
            inputs=inp,
            expected_outputs=out,
            actual_outputs={},
            field_types={k: "str" for k in out},  # default to string comparison
        ))

    return vectors

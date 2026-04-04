"""
COBOL compiler wrapper — compile and execute COBOL programs via GnuCOBOL (cobc)
running in WSL Ubuntu.

Handles:
- Compilation with copybook include paths
- File assignment via environment variables
- Execution with timeout
- Output file capture
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Optional


@dataclass
class CompileResult:
    """Result of a COBOL compilation."""
    success: bool
    binary_path: str = ""
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0


@dataclass
class RunResult:
    """Result of executing a compiled COBOL program."""
    success: bool
    return_code: int = 0
    stdout: str = ""
    stderr: str = ""
    output_files: dict[str, str] = field(default_factory=dict)  # name → path


def _to_wsl_path(windows_path: str) -> str:
    """Convert a Windows path to WSL /mnt/c/... path."""
    p = str(windows_path).replace('\\', '/')
    if len(p) >= 2 and p[1] == ':':
        drive = p[0].lower()
        return f"/mnt/{drive}{p[2:]}"
    return p


def _build_cmd(parts: list[str]) -> str:
    """Join command parts into a shell-safe command string."""
    return " ".join(shlex.quote(p) for p in parts)


def _safe_export(name: str, value: str) -> str:
    """Generate a safe 'export NAME=VALUE' shell line.

    Validates that name is a legal shell identifier and quotes the value.
    """
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name):
        raise ValueError(f"Invalid environment variable name: {name!r}")
    return f"export {name}={shlex.quote(value)}"


def compile_cobol(
    source_file: str,
    copybook_dirs: list[str] = None,
    output_binary: str = None,
    std: str = "ibm",
) -> CompileResult:
    """Compile a COBOL source file using GnuCOBOL in WSL.

    Args:
        source_file: Path to .cbl file (Windows or WSL path)
        copybook_dirs: Directories to search for COPY statements
        output_binary: Path for compiled binary (default: /tmp/<stem>)
        std: COBOL standard (default: ibm)

    Returns:
        CompileResult with success status and paths
    """
    src_wsl = _to_wsl_path(source_file)
    stem = Path(source_file).stem.lower()

    if output_binary:
        out_wsl = _to_wsl_path(output_binary)
    else:
        out_wsl = f"/tmp/{stem}"

    cmd_parts = ["cobc", "-x", f"-std={std}"]

    for cpd in (copybook_dirs or []):
        cmd_parts.append(f"-I")
        cmd_parts.append(_to_wsl_path(cpd))

    cmd_parts.extend(["-o", out_wsl, src_wsl])

    cmd = " ".join(f'"{p}"' if " " in p else p for p in cmd_parts)

    try:
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=60,
        )
        success = result.returncode == 0
        return CompileResult(
            success=success,
            binary_path=out_wsl if success else "",
            stdout=result.stdout,
            stderr=result.stderr,
            return_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return CompileResult(
            success=False,
            stderr="Compilation timed out after 60 seconds",
            return_code=-1,
        )
    except FileNotFoundError:
        return CompileResult(
            success=False,
            stderr="WSL or cobc not found. Install WSL Ubuntu and gnucobol.",
            return_code=-1,
        )


def run_cobol(
    binary_path: str,
    input_files: dict[str, str] = None,
    output_files: dict[str, str] = None,
    timeout: int = 30,
    env_vars: dict[str, str] = None,
) -> RunResult:
    """Execute a compiled COBOL program in WSL.

    Args:
        binary_path: WSL path to compiled binary
        input_files: Mapping of COBOL file name → WSL file path
                     (e.g., {"ACCTFILE": "/tmp/acct_input.dat"})
        output_files: Mapping of COBOL file name → WSL file path for outputs
        timeout: Max execution time in seconds
        env_vars: Additional environment variables

    Returns:
        RunResult with output and file contents
    """
    # Build environment variable exports for file assignments
    # GnuCOBOL uses dd_<FILENAME> or the ASSIGN TO name
    env_lines = []
    all_files = {}
    all_files.update(input_files or {})
    all_files.update(output_files or {})

    for cobol_name, file_path in all_files.items():
        # GnuCOBOL file assignment: export dd_FILENAME=path
        env_lines.append(f'export dd_{cobol_name}="{file_path}"')
        # Also set the ASSIGN TO name directly
        env_lines.append(f'export {cobol_name}="{file_path}"')

    for k, v in (env_vars or {}).items():
        env_lines.append(f'export {k}="{v}"')

    # Create output files (touch them so they exist)
    for name, path in (output_files or {}).items():
        env_lines.append(f'touch "{path}"')

    env_block = "\n".join(env_lines)
    cmd = f"{env_block}\n{binary_path}"

    try:
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Read output files back
        read_outputs = {}
        for name, path in (output_files or {}).items():
            read_result = subprocess.run(
                ["wsl", "-d", "Ubuntu", "--", "cat", path],
                capture_output=True,
                timeout=10,
            )
            if read_result.returncode == 0:
                read_outputs[name] = path

        return RunResult(
            success=result.returncode == 0,
            return_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            output_files=read_outputs,
        )
    except subprocess.TimeoutExpired:
        return RunResult(
            success=False,
            return_code=-1,
            stderr=f"Execution timed out after {timeout} seconds",
        )
    except FileNotFoundError:
        return RunResult(
            success=False,
            return_code=-1,
            stderr="WSL not found",
        )


def compile_and_run(
    source_file: str,
    copybook_dirs: list[str] = None,
    input_files: dict[str, str] = None,
    output_files: dict[str, str] = None,
    timeout: int = 30,
) -> RunResult:
    """Compile a COBOL program and execute it in one step.

    Convenience function that chains compile_cobol() and run_cobol().
    """
    compile_result = compile_cobol(source_file, copybook_dirs)
    if not compile_result.success:
        return RunResult(
            success=False,
            return_code=compile_result.return_code,
            stdout=compile_result.stdout,
            stderr=f"Compilation failed:\n{compile_result.stderr}",
        )

    return run_cobol(
        compile_result.binary_path,
        input_files=input_files,
        output_files=output_files,
        timeout=timeout,
    )


def is_cobc_available() -> bool:
    """Check if GnuCOBOL is available via WSL."""
    try:
        result = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "cobc", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

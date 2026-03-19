"""
Reimplementation of COBSWAIT — CardDemo wait utility.

COBOL source summary:
  ACCEPT PARM-VALUE FROM SYSIN       (PIC X(8))
  MOVE PARM-VALUE TO MVSWAIT-TIME    (PIC 9(8) COMP)
  CALL 'MVSWAIT' USING MVSWAIT-TIME
  STOP RUN

MVSWAIT is an IBM batch utility that suspends execution for a given number
of centiseconds (hundredths of a second).

PIC 9(8) COMP: unsigned binary, max value 99_999_999 (~28 hours).
Non-numeric or blank PARM-VALUE maps to 0 centiseconds (no wait), matching
COBOL numeric MOVE behaviour when the source is non-numeric.
"""

from __future__ import annotations
import sys
import time
from dataclasses import dataclass

_MAX_CENTISECONDS = 99_999_999  # PIC 9(8) COMP ceiling


@dataclass
class WaitResult:
    requested_cs: int       # centiseconds requested (after coercion)
    actual_seconds: float   # wall-clock sleep duration


def coerce_parm(parm_value: str) -> int:
    """Convert PIC X(8) PARM-VALUE to PIC 9(8) COMP centiseconds.

    COBOL MOVE of non-numeric data to a numeric item fills with zeros;
    out-of-range positive values are left-truncated (COMP overflow).
    """
    try:
        cs = int(parm_value.strip())
    except (ValueError, AttributeError):
        return 0
    if cs < 0:
        return 0
    return cs % (10 ** 8)  # silent left-truncation for > 8 digits


def wait_centiseconds(centiseconds: int) -> WaitResult:
    """Sleep for centiseconds/100 seconds.  Mirrors CALL 'MVSWAIT' USING MVSWAIT-TIME."""
    cs = max(0, min(centiseconds, _MAX_CENTISECONDS))
    seconds = cs / 100.0
    time.sleep(seconds)
    return WaitResult(requested_cs=cs, actual_seconds=seconds)


def run(parm_value: str) -> WaitResult:
    """Entry point mirroring COBSWAIT PROCEDURE DIVISION.

    Accepts the SYSIN string, coerces it to centiseconds, and waits.
    """
    cs = coerce_parm(parm_value)
    return wait_centiseconds(cs)


def main(argv: list[str] | None = None) -> None:
    """CLI shim: reads one line from stdin (SYSIN), runs wait, exits."""
    line = sys.stdin.readline() if argv is None else (argv[0] if argv else "")
    run(line[:8])

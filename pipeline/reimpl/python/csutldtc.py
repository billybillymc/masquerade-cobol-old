"""
Reimplementation of CSUTLDTC — CardDemo date validation utility.

Called as a sub-program:  CALL 'CSUTLDTC' USING LS-DATE, LS-DATE-FORMAT, LS-RESULT
It validates a date string against a format mask using the logic equivalent to
the IBM Language Environment CEEDAYS API, which converts a Gregorian date to a
Lilian day-number (count of days since October 14, 1582).

Supported format masks (subset used by CardDemo):
  YYYY-MM-DD   (ISO)
  MM/DD/YYYY   (US)
  YYYYMMDD     (compact)

Returns an 80-character result message in LS-RESULT, severity 0 on success.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date


# ── Result codes mirroring CEEDAYS feedback tokens ───────────────────────────

class DateValidationResult:
    VALID              = "Date is valid  "  # 15 chars like COBOL WS-RESULT
    INSUFFICIENT       = "Insufficient   "
    BAD_DATE_VALUE     = "Datevalue error"
    INVALID_ERA        = "Invalid Era    "
    UNSUPPORTED_RANGE  = "Unsupp. Range  "
    INVALID_MONTH      = "Invalid month  "
    BAD_PIC_STRING     = "Bad Pic String "
    NON_NUMERIC        = "Nonnumeric data"
    YEAR_IN_ERA_ZERO   = "YearInEra is 0 "
    INVALID            = "Date is invalid"


@dataclass
class DateCheckResult:
    severity: int        # 0 = ok, non-zero = error
    msg_no: int          # CEEDAYS message number
    result_text: str     # 15-char result classification
    lillian: int         # Lilian day number (0 if invalid)
    raw_message: str     # Full 80-char message like WS-MESSAGE


_LILIAN_EPOCH = date(1582, 10, 14)


def _to_lilian(d: date) -> int:
    """Convert a date to its Lilian number (days since 1582-10-14)."""
    return (d - _LILIAN_EPOCH).days + 1


_FORMATS = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "MM/DD/YYYY": "%m/%d/%Y",
    "YYYYMMDD":   "%Y%m%d",
    "MM/DD/YY":   "%m/%d/%y",
    "DD/MM/YYYY": "%d/%m/%Y",
    "YYYY/MM/DD": "%Y/%m/%d",
}


def validate_date(ls_date: str, ls_date_format: str) -> DateCheckResult:
    """Validate a date string against a format mask.

    Mirrors CSUTLDTC's A000-MAIN paragraph which calls CEEDAYS.

    Returns DateCheckResult with severity=0 on success, >0 on error.
    """
    date_str = (ls_date or "").strip()
    fmt_str = (ls_date_format or "").strip().upper()

    if not date_str:
        return _make_result(3, DateValidationResult.INSUFFICIENT, 0, date_str, fmt_str)

    if fmt_str not in _FORMATS:
        return _make_result(3, DateValidationResult.BAD_PIC_STRING, 0, date_str, fmt_str)

    try:
        parsed = datetime.strptime(date_str, _FORMATS[fmt_str]).date()
    except ValueError:
        # Distinguish month vs. general value errors
        parts = _split_parts(date_str, fmt_str)
        if parts and _has_bad_month(parts, fmt_str):
            return _make_result(3, DateValidationResult.INVALID_MONTH, 0, date_str, fmt_str)
        return _make_result(3, DateValidationResult.BAD_DATE_VALUE, 0, date_str, fmt_str)
    except Exception:
        return _make_result(3, DateValidationResult.INVALID, 0, date_str, fmt_str)

    # Check year is not zero (Lilian calendars require year >= 1)
    if parsed.year == 0:
        return _make_result(3, DateValidationResult.YEAR_IN_ERA_ZERO, 0, date_str, fmt_str)

    # Check supported range: 1582-10-15 to 9999-12-31
    if parsed < date(1582, 10, 15) or parsed > date(9999, 12, 31):
        return _make_result(3, DateValidationResult.UNSUPPORTED_RANGE, 0, date_str, fmt_str)

    lillian = _to_lilian(parsed)
    return _make_result(0, DateValidationResult.VALID, lillian, date_str, fmt_str)


def _split_parts(date_str: str, fmt_str: str) -> list[str] | None:
    try:
        sep = "-" if "-" in date_str else "/" if "/" in date_str else None
        if sep:
            return date_str.split(sep)
        return None
    except Exception:
        return None


def _has_bad_month(parts: list[str], fmt_str: str) -> bool:
    try:
        if "MM" in fmt_str and len(parts) >= 2:
            if fmt_str.startswith("YYYY"):
                month_idx = 1
            else:
                month_idx = 0
            month = int(parts[month_idx])
            return month < 1 or month > 12
    except (ValueError, IndexError):
        pass
    return False


def _make_result(
    severity: int,
    result_text: str,
    lillian: int,
    date_str: str,
    fmt_str: str,
) -> DateCheckResult:
    msg_no = 0 if severity == 0 else 777
    msg = (
        f"{severity:04d}Mesg Code:{msg_no:04d} "
        f"{result_text:<15} "
        f"TstDate:{date_str:<10} "
        f"Mask used:{fmt_str:<10}   "
    )
    return DateCheckResult(
        severity=severity,
        msg_no=msg_no,
        result_text=result_text,
        lillian=lillian,
        raw_message=msg[:80].ljust(80),
    )


def call_csutldtc(ls_date: str, ls_date_format: str) -> tuple[int, str]:
    """Entry point matching COBOL CALL interface.

    Returns (return_code, ls_result_80chars)
    """
    result = validate_date(ls_date, ls_date_format)
    return result.severity, result.raw_message


# ── Differential harness runner adapter (W2 contract) ──────────────────────
#
# `run_vector` is the canonical entry point used by the language-agnostic
# vector runner in `pipeline/vector_runner.py`. Java's Csutldtc reimplementation
# (registered in pipeline/reimpl/java/runner ProgramRegistry) speaks the same
# JSON contract so the differential harness can drive both targets with the
# same vectors.
#
# Inputs accepted:
#   LS_DATE         — required, the date string to validate
#   LS_DATE_FORMAT  — required, the format mask (e.g., "YYYY-MM-DD")
#
# Outputs produced:
#   SEVERITY     — "0" on success, "3" on any validation error
#   RESULT_TEXT  — 15-char classification (e.g., "Date is valid  ")
#   LILLIAN      — Lilian day count as string ("0" if invalid)
#   RAW_MESSAGE  — full 80-char message identical to LS-RESULT in COBOL


def run_vector(inputs: dict) -> dict:
    """Canonical runner entry point for the differential harness."""
    ls_date = str(inputs.get("LS_DATE", ""))
    ls_date_format = str(inputs.get("LS_DATE_FORMAT", ""))

    result = validate_date(ls_date, ls_date_format)

    return {
        "SEVERITY": str(result.severity),
        "RESULT_TEXT": result.result_text,
        "LILLIAN": str(result.lillian),
        "RAW_MESSAGE": result.raw_message,
    }

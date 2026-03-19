"""
Reimplementation of CORPT00C — CardDemo Report Submission Screen.

CICS online program. Allows users to submit a transaction report job
(monthly, yearly, or custom date range). The COBOL original submits
JCL to an internal reader TDQ; this reimplementation captures the
parameters and returns a JobRequest descriptor that the caller can
use to invoke cbtrn03c or a similar batch report function.

Report types:
  Monthly → current month start → end of month
  Yearly  → current year Jan 1 → Dec 31
  Custom  → user-supplied start/end date (YYYY-MM-DD)

Navigation:
  ENTER → validate and submit job
  PF3   → return to COMEN01C
"""

from __future__ import annotations
import calendar
from dataclasses import dataclass
from datetime import date
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3,
)
from .csutldtc import validate_date


WS_PGMNAME  = "CORPT00C"
WS_TRANID   = "CR00"
DATE_FORMAT = "YYYY-MM-DD"


@dataclass
class JobRequest:
    report_name: str = ""
    start_date: str = ""
    end_date: str = ""


@dataclass
class ReportResult:
    job_request: Optional[JobRequest] = None
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    xctl_program: str = ""
    return_to_prev: bool = False


def process_report_screen(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    report_type: str,
    start_mm: str = "",
    start_dd: str = "",
    start_yyyy: str = "",
    end_mm: str = "",
    end_dd: str = "",
    end_yyyy: str = "",
    today: Optional[date] = None,
) -> ReportResult:
    """Process report submission screen — mirrors CORPT00C PROCEDURE DIVISION."""
    result = ReportResult()

    if eibcalen == 0:
        result.return_to_prev = True
        result.xctl_program = "COSGN00C"
        return result

    result.commarea = commarea
    if today is None:
        today = date.today()

    if commarea.cdemo_pgm_context == 0:
        commarea.cdemo_pgm_context = 1
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.commarea = commarea
        return result

    if eibaid in (DFHPF3, "PF3"):
        result.xctl_program = "COMEN01C"
        result.return_to_prev = True
        result.commarea = commarea
        return result

    if eibaid not in (DFHENTER, "ENTER"):
        result.error = True
        result.message = CCDA_MSG_INVALID_KEY
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    rt = report_type.strip().lower() if report_type else ""

    if rt == "monthly":
        yr = today.year
        mo = today.month
        start = f"{yr:04d}-{mo:02d}-01"
        last_day = calendar.monthrange(yr, mo)[1]
        end = f"{yr:04d}-{mo:02d}-{last_day:02d}"
        return _submit_job("Monthly", start, end, commarea, result)

    elif rt == "yearly":
        yr = today.year
        start = f"{yr:04d}-01-01"
        end   = f"{yr:04d}-12-31"
        return _submit_job("Yearly", start, end, commarea, result)

    elif rt == "custom":
        errors = []
        if not start_mm or not start_mm.strip():
            errors.append("Start Date - Month can NOT be empty...")
        if not start_dd or not start_dd.strip():
            errors.append("Start Date - Day can NOT be empty...")
        if not start_yyyy or not start_yyyy.strip():
            errors.append("Start Date - Year can NOT be empty...")
        if not end_mm or not end_mm.strip():
            errors.append("End Date - Month can NOT be empty...")
        if not end_dd or not end_dd.strip():
            errors.append("End Date - Day can NOT be empty...")
        if not end_yyyy or not end_yyyy.strip():
            errors.append("End Date - Year can NOT be empty...")

        if errors:
            result.error = True
            result.message = errors[0]
            result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
            result.screen.errmsg = result.message
            result.commarea = commarea
            return result

        start = f"{start_yyyy.strip()}-{start_mm.strip().zfill(2)}-{start_dd.strip().zfill(2)}"
        end   = f"{end_yyyy.strip()}-{end_mm.strip().zfill(2)}-{end_dd.strip().zfill(2)}"

        start_check = validate_date(start, DATE_FORMAT)
        if start_check.severity != 0:
            result.error = True
            result.message = "Start Date - Not a valid date..."
            result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
            result.screen.errmsg = result.message
            result.commarea = commarea
            return result

        end_check = validate_date(end, DATE_FORMAT)
        if end_check.severity != 0:
            result.error = True
            result.message = "End Date - Not a valid date..."
            result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
            result.screen.errmsg = result.message
            result.commarea = commarea
            return result

        return _submit_job("Custom", start, end, commarea, result)

    else:
        result.error = True
        result.message = "Select a report type to print report..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result


def _submit_job(report_name, start_date, end_date, commarea, result):
    result.job_request = JobRequest(
        report_name=report_name,
        start_date=start_date,
        end_date=end_date,
    )
    result.message = f"{report_name} report job submitted"
    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    result.commarea = commarea
    return result

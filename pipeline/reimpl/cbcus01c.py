"""
Reimplementation of CBCUS01C — CardDemo Batch Customer File Reader.

Function: Read the customer VSAM KSDS sequentially and display each record.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable

from .carddemo_data import CustomerRecord


@dataclass
class ProcessResult:
    records_read: int = 0
    display_lines: list[str] = field(default_factory=list)


def process_customer_file(
    customers: list[CustomerRecord],
    logger: Callable[[str], None] = print,
) -> ProcessResult:
    """Process all customer records — mirrors CBCUS01C PROCEDURE DIVISION."""
    result = ProcessResult()
    logger("START OF EXECUTION OF PROGRAM CBCUS01C")

    for cust in customers:
        result.records_read += 1
        line = _format_customer_record(cust)
        logger(line)
        result.display_lines.append(line)

    logger("END OF EXECUTION OF PROGRAM CBCUS01C")
    return result


def _format_customer_record(cust: CustomerRecord) -> str:
    """DISPLAY CUSTOMER-RECORD — all fields formatted."""
    return (
        f"CUST-ID:{cust.cust_id:09d} "
        f"NAME:{cust.cust_first_name.strip()} {cust.cust_middle_name.strip()} "
        f"{cust.cust_last_name.strip()} "
        f"SSN:{cust.cust_ssn:09d} "
        f"DOB:{cust.cust_dob_yyyy_mm_dd} "
        f"FICO:{cust.cust_fico_credit_score:03d} "
        f"ZIP:{cust.cust_addr_zip}"
    )

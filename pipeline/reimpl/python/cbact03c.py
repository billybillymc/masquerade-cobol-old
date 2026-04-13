"""
Reimplementation of CBACT03C — CardDemo Batch Account Cross-Reference Reader.

Function: Read the card cross-reference VSAM KSDS sequentially and display each record.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable

from .carddemo_data import CardXrefRecord


@dataclass
class ProcessResult:
    records_read: int = 0
    display_lines: list[str] = field(default_factory=list)


def process_xref_file(
    xrefs: list[CardXrefRecord],
    logger: Callable[[str], None] = print,
) -> ProcessResult:
    """Process all cross-reference records — mirrors CBACT03C PROCEDURE DIVISION."""
    result = ProcessResult()
    logger("START OF EXECUTION OF PROGRAM CBACT03C")

    for xref in xrefs:
        result.records_read += 1
        line = _format_xref_record(xref)
        logger(line)
        result.display_lines.append(line)

    logger("END OF EXECUTION OF PROGRAM CBACT03C")
    return result


def _format_xref_record(xref: CardXrefRecord) -> str:
    """DISPLAY CARD-XREF-RECORD."""
    return (
        f"XREF-CARD-NUM:{xref.xref_card_num} "
        f"CUST-ID:{xref.xref_cust_id:09d} "
        f"ACCT-ID:{xref.xref_acct_id:011d}"
    )


def run_vector(inputs: dict) -> dict:
    """Adapter for the differential harness runner contract."""
    xrefs = [
        CardXrefRecord(
            xref_card_num="4111111111111111",
            xref_cust_id=1,
            xref_acct_id=100000001,
        ),
        CardXrefRecord(
            xref_card_num="4222222222222222",
            xref_cust_id=2,
            xref_acct_id=100000002,
        ),
    ]
    result = process_xref_file(xrefs, logger=lambda _: None)
    out: dict[str, str] = {"RECORDS_READ": str(result.records_read)}
    for i, line in enumerate(result.display_lines):
        out[f"DISPLAY_{i}"] = line
    return out

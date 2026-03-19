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

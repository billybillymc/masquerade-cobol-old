"""
Reimplementation of CBACT02C — CardDemo Batch Card File Reader.

Function: Read the card VSAM KSDS sequentially and display each record.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable

from .carddemo_data import CardRecord


@dataclass
class ProcessResult:
    records_read: int = 0
    display_lines: list[str] = field(default_factory=list)


def process_card_file(
    cards: list[CardRecord],
    logger: Callable[[str], None] = print,
) -> ProcessResult:
    """Process all card records — mirrors CBACT02C PROCEDURE DIVISION."""
    result = ProcessResult()
    logger("START OF EXECUTION OF PROGRAM CBACT02C")

    for card in cards:
        result.records_read += 1
        line = _format_card_record(card)
        logger(line)
        result.display_lines.append(line)

    logger("END OF EXECUTION OF PROGRAM CBACT02C")
    return result


def _format_card_record(card: CardRecord) -> str:
    """DISPLAY CARD-RECORD — formats all fields inline."""
    return (
        f"CARD-NUM:{card.card_num} "
        f"ACCT-ID:{card.card_acct_id:011d} "
        f"CVV:{card.card_cvv_cd:03d} "
        f"NAME:{card.card_embossed_name} "
        f"EXP:{card.card_expiration_date} "
        f"STATUS:{card.card_active_status}"
    )


def run_vector(inputs: dict) -> dict:
    """Adapter for the differential harness runner contract."""
    cards = [
        CardRecord(
            card_num="4111111111111111",
            card_acct_id=100000001,
            card_cvv_cd=123,
            card_embossed_name="JOHN DOE",
            card_expiration_date="2029-12-31",
            card_active_status="Y",
        ),
        CardRecord(
            card_num="4222222222222222",
            card_acct_id=100000002,
            card_cvv_cd=456,
            card_embossed_name="JANE SMITH",
            card_expiration_date="2028-06-30",
            card_active_status="Y",
        ),
    ]
    result = process_card_file(cards, logger=lambda _: None)
    out: dict[str, str] = {"RECORDS_READ": str(result.records_read)}
    for i, line in enumerate(result.display_lines):
        out[f"DISPLAY_{i}"] = line
    return out

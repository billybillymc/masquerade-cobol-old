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

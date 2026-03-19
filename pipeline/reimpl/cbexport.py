"""
Reimplementation of CBEXPORT — CardDemo Batch Data Export.

Reads normalized CardDemo files (Customer, Account, Xref, Transaction, Card)
and creates a multi-record export bundle for branch migration.

Each record in the export bundle is tagged with a type character:
  'C' → customer record
  'A' → account record
  'X' → xref record
  'T' → transaction record
  'D' → card (debit/credit) record

Returns an ExportResult with all records, a statistics summary, and a log.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from .carddemo_data import (
    CustomerRecord, AccountRecord, CardXrefRecord, TranRecord, CardRecord,
)


# ─── Export record types ─────────────────────────────────────────────────────

@dataclass
class ExportRecord:
    seq_num: int = 0
    rec_type: str = ""          # C/A/X/T/D
    timestamp: str = ""
    branch_id: str = "0001"
    region_code: str = "NORTH"
    data: Any = None            # the original dataclass instance


@dataclass
class ExportStats:
    customers: int = 0
    accounts: int = 0
    xrefs: int = 0
    transactions: int = 0
    cards: int = 0

    @property
    def total(self) -> int:
        return self.customers + self.accounts + self.xrefs + self.transactions + self.cards


@dataclass
class ExportResult:
    records: list[ExportRecord] = field(default_factory=list)
    stats: ExportStats = field(default_factory=ExportStats)
    log: list[str] = field(default_factory=list)
    abended: bool = False
    abend_reason: str = ""


# ─── Main entry ──────────────────────────────────────────────────────────────

def run_export(
    customers: list[CustomerRecord],
    accounts: list[AccountRecord],
    xrefs: list[CardXrefRecord],
    transactions: list[TranRecord],
    cards: list[CardRecord],
    export_timestamp: Optional[str] = None,
) -> ExportResult:
    """Run data export — mirrors CBEXPORT PROCEDURE DIVISION."""
    result = ExportResult()
    ts = export_timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S.00")
    result.log.append(f"CBEXPORT: Starting Customer Data Export")
    result.log.append(f"CBEXPORT: Export Timestamp: {ts}")

    seq = 0

    def _make(rec_type, data):
        nonlocal seq
        seq += 1
        return ExportRecord(seq_num=seq, rec_type=rec_type, timestamp=ts, data=data)

    for cust in customers:
        result.records.append(_make("C", cust))
        result.stats.customers += 1
    result.log.append(f"CBEXPORT: Customers exported: {result.stats.customers}")

    for acct in accounts:
        result.records.append(_make("A", acct))
        result.stats.accounts += 1
    result.log.append(f"CBEXPORT: Accounts exported: {result.stats.accounts}")

    for xref in xrefs:
        result.records.append(_make("X", xref))
        result.stats.xrefs += 1
    result.log.append(f"CBEXPORT: Xrefs exported: {result.stats.xrefs}")

    for tran in transactions:
        result.records.append(_make("T", tran))
        result.stats.transactions += 1
    result.log.append(f"CBEXPORT: Transactions exported: {result.stats.transactions}")

    for card in cards:
        result.records.append(_make("D", card))
        result.stats.cards += 1
    result.log.append(f"CBEXPORT: Cards exported: {result.stats.cards}")

    result.log.append(
        f"CBEXPORT: Total records exported: {result.stats.total}"
    )
    result.log.append("CBEXPORT: Export complete.")
    return result

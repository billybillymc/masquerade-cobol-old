"""
Reimplementation of CBIMPORT — CardDemo Batch Data Import.

Reads a multi-record export bundle produced by CBEXPORT and splits it into
separate normalized target collections (Customer, Account, Xref, Transaction,
Card).  Records with unknown type characters are logged to the error list.

Returns an ImportResult with separated lists, statistics, and an error log.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from .carddemo_data import (
    CustomerRecord, AccountRecord, CardXrefRecord, TranRecord, CardRecord,
)
from .cbexport import ExportRecord


@dataclass
class ImportStats:
    customers: int = 0
    accounts: int = 0
    xrefs: int = 0
    transactions: int = 0
    cards: int = 0
    errors: int = 0

    @property
    def total_imported(self) -> int:
        return self.customers + self.accounts + self.xrefs + self.transactions + self.cards


@dataclass
class ImportResult:
    customers: list[CustomerRecord] = field(default_factory=list)
    accounts: list[AccountRecord] = field(default_factory=list)
    xrefs: list[CardXrefRecord] = field(default_factory=list)
    transactions: list[TranRecord] = field(default_factory=list)
    cards: list[CardRecord] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    stats: ImportStats = field(default_factory=ImportStats)
    log: list[str] = field(default_factory=list)


def run_import(export_records: list[ExportRecord]) -> ImportResult:
    """Run data import — mirrors CBIMPORT PROCEDURE DIVISION."""
    result = ImportResult()
    result.log.append("CBIMPORT: Starting Customer Data Import")
    result.log.append(f"CBIMPORT: Records to process: {len(export_records)}")

    _HANDLERS = {
        "C": (_handle_customer, result.customers),
        "A": (_handle_account, result.accounts),
        "X": (_handle_xref, result.xrefs),
        "T": (_handle_tran, result.transactions),
        "D": (_handle_card, result.cards),
    }

    for rec in export_records:
        if rec.rec_type not in _HANDLERS:
            result.errors.append(
                f"CBIMPORT: Unknown record type '{rec.rec_type}' at seq {rec.seq_num}"
            )
            result.stats.errors += 1
            continue

        handler, target_list = _HANDLERS[rec.rec_type]
        parsed, err = handler(rec)
        if err:
            result.errors.append(f"CBIMPORT: Error at seq {rec.seq_num}: {err}")
            result.stats.errors += 1
        else:
            target_list.append(parsed)

    result.stats.customers = len(result.customers)
    result.stats.accounts = len(result.accounts)
    result.stats.xrefs = len(result.xrefs)
    result.stats.transactions = len(result.transactions)
    result.stats.cards = len(result.cards)

    result.log.append(f"CBIMPORT: Customers imported:     {result.stats.customers}")
    result.log.append(f"CBIMPORT: Accounts imported:      {result.stats.accounts}")
    result.log.append(f"CBIMPORT: Xrefs imported:         {result.stats.xrefs}")
    result.log.append(f"CBIMPORT: Transactions imported:  {result.stats.transactions}")
    result.log.append(f"CBIMPORT: Cards imported:         {result.stats.cards}")
    result.log.append(f"CBIMPORT: Errors:                 {result.stats.errors}")
    result.log.append("CBIMPORT: Import complete.")
    return result


# ─── Record handlers ─────────────────────────────────────────────────────────

def _handle_customer(rec: ExportRecord):
    if isinstance(rec.data, CustomerRecord):
        return rec.data, None
    return None, "data is not a CustomerRecord"


def _handle_account(rec: ExportRecord):
    if isinstance(rec.data, AccountRecord):
        return rec.data, None
    return None, "data is not an AccountRecord"


def _handle_xref(rec: ExportRecord):
    if isinstance(rec.data, CardXrefRecord):
        return rec.data, None
    return None, "data is not a CardXrefRecord"


def _handle_tran(rec: ExportRecord):
    if isinstance(rec.data, TranRecord):
        return rec.data, None
    return None, "data is not a TranRecord"


def _handle_card(rec: ExportRecord):
    if isinstance(rec.data, CardRecord):
        return rec.data, None
    return None, "data is not a CardRecord"

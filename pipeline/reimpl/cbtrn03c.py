"""
Reimplementation of CBTRN03C — CardDemo Transaction Detail Report Generator.

Function: Read transaction file sequentially, filter by date range, look up
cross-reference / transaction type / category, and produce a paginated report.

Report is broken by card number with page totals, account totals, and grand total.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from .carddemo_data import TranRecord, CardXrefRecord


# ── Supporting reference structures ───────────────────────────────────────────

@dataclass
class TranTypeRecord:
    tran_type: str = ""    # PIC X(02)
    tran_type_desc: str = ""  # PIC X(58)


@dataclass
class TranCatgRecord:
    tran_type_cd: str = ""
    tran_cat_cd: int = 0
    tran_catg_desc: str = ""  # PIC X(54)


# ── Report line structures ─────────────────────────────────────────────────────

@dataclass
class ReportLine:
    content: str
    is_header: bool = False
    is_total: bool = False
    is_page_break: bool = False


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class ReportResult:
    report_lines: list[ReportLine] = field(default_factory=list)
    records_read: int = 0
    records_reported: int = 0
    grand_total: Decimal = Decimal("0.00")
    page_count: int = 0


PAGE_SIZE = 20


# ── Repository interfaces ──────────────────────────────────────────────────────

class XrefRepository:
    def __init__(self, xrefs: dict[str, CardXrefRecord]):
        self._by_card = xrefs

    def find(self, card_num: str) -> CardXrefRecord | None:
        return self._by_card.get(card_num)


class TranTypeRepository:
    def __init__(self, types: dict[str, TranTypeRecord]):
        self._types = types

    def find(self, type_cd: str) -> TranTypeRecord | None:
        return self._types.get(type_cd)


class TranCatgRepository:
    def __init__(self, catgs: dict[tuple[str, int], TranCatgRecord]):
        self._catgs = catgs

    def find(self, type_cd: str, cat_cd: int) -> TranCatgRecord | None:
        return self._catgs.get((type_cd, cat_cd))


# ── Core processing ───────────────────────────────────────────────────────────

def generate_transaction_report(
    transactions: list[TranRecord],
    xref_repo: XrefRepository,
    trantype_repo: TranTypeRepository,
    trancatg_repo: TranCatgRepository,
    start_date: str,
    end_date: str,
    logger: Callable[[str], None] = print,
) -> ReportResult:
    """Generate transaction detail report — mirrors CBTRN03C PROCEDURE DIVISION."""
    result = ReportResult()
    logger("START OF EXECUTION OF PROGRAM CBTRN03C")

    line_counter = 0
    page_total = Decimal("0.00")
    account_total = Decimal("0.00")
    grand_total = Decimal("0.00")
    curr_card_num = ""
    first_time = True

    def emit(line: str, is_header=False, is_total=False):
        result.report_lines.append(ReportLine(line, is_header, is_total))

    def write_page_header(page_num: int):
        emit("=" * 133, is_header=True)
        emit(f"  CARDEMO TRANSACTION DETAIL REPORT               PAGE: {page_num:05d}", is_header=True)
        emit(f"  DATE RANGE: {start_date} TO {end_date}", is_header=True)
        emit("=" * 133, is_header=True)
        emit(f"{'TRAN ID':<16} {'TRAN DETAILS':<51} {'TRAN AMOUNT':>13}", is_header=True)
        emit("-" * 133, is_header=True)
        result.page_count += 1

    def write_account_totals(card_num: str, acc_total: Decimal):
        emit("-" * 133, is_total=True)
        emit(f"  ACCOUNT TOTAL FOR CARD {card_num}: ${acc_total:>14.2f}", is_total=True)
        emit("", is_total=True)

    write_page_header(1)

    for tran in transactions:
        result.records_read += 1

        # Date filter
        proc_date = tran.tran_proc_ts[:10] if tran.tran_proc_ts else ""
        if proc_date < start_date or proc_date > end_date:
            continue

        result.records_reported += 1

        # Account break
        if tran.tran_card_num != curr_card_num:
            if not first_time:
                write_account_totals(curr_card_num, account_total)
                account_total = Decimal("0.00")
            else:
                first_time = False
            curr_card_num = tran.tran_card_num

        # Look up references
        xref = xref_repo.find(tran.tran_card_num)
        tran_type = trantype_repo.find(tran.tran_type_cd)
        tran_catg = trancatg_repo.find(tran.tran_type_cd, tran.tran_cat_cd)

        type_desc = tran_type.tran_type_desc.strip() if tran_type else tran.tran_type_cd
        catg_desc = tran_catg.tran_catg_desc.strip() if tran_catg else str(tran.tran_cat_cd)
        detail = f"{type_desc}/{catg_desc} {tran.tran_desc[:30]}"

        line = f"{tran.tran_id:<16} {detail:<51} ${tran.tran_amt:>12.2f}"
        emit(line)
        logger(str(tran))

        page_total += tran.tran_amt
        account_total += tran.tran_amt
        grand_total += tran.tran_amt
        line_counter += 1

        # Page break
        if line_counter >= PAGE_SIZE:
            emit(f"  PAGE TOTAL: ${page_total:>14.2f}", is_total=True)
            grand_total_running = grand_total
            emit(f"  GRAND TOTAL SO FAR: ${grand_total_running:>14.2f}", is_total=True)
            page_total = Decimal("0.00")
            line_counter = 0
            write_page_header(result.page_count + 1)

    # Final account total
    if not first_time:
        write_account_totals(curr_card_num, account_total)

    # Grand total
    emit("=" * 133, is_total=True)
    emit(f"  GRAND TOTAL: ${grand_total:>14.2f}", is_total=True)
    emit("=" * 133, is_total=True)

    result.grand_total = grand_total
    logger(f"TRAN-AMT {grand_total}")
    logger(f"WS-PAGE-TOTAL {page_total}")
    logger("END OF EXECUTION OF PROGRAM CBTRN03C")
    return result

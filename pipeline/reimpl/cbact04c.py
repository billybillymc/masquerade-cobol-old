"""
Reimplementation of CBACT04C — CardDemo Interest Calculator.

Function: For each account's transaction category balances, compute monthly
interest charges, write interest transactions, and update account balances.

Files consumed:
  TCATBAL-FILE  — transaction category balance (sequential KSDS by acct+type+cat)
  XREF-FILE     — card cross-reference (random by acct-id)
  DISCGRP-FILE  — disclosure group / interest rates (random by group+type+cat)
  ACCOUNT-FILE  — account master (random I-O)
  TRANSACT-FILE — output interest transactions (sequential output)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from typing import Callable

from .carddemo_data import (
    AccountRecord, CardXrefRecord, TranCatBalRecord, DisGroupRecord, TranRecord,
    get_db2_timestamp,
)

DEFAULT_GROUP = "DEFAULT"


# ── Repository interfaces ──────────────────────────────────────────────────────

class AccountRepository:
    def __init__(self, accounts: dict[int, AccountRecord]):
        self._accounts = accounts

    def find(self, acct_id: int) -> AccountRecord | None:
        return self._accounts.get(acct_id)

    def update(self, acct: AccountRecord) -> None:
        self._accounts[acct.acct_id] = acct


class XrefRepository:
    def __init__(self, xrefs: dict[int, CardXrefRecord]):
        """Keyed by acct_id for random-by-alternate-key reads."""
        self._by_acct = xrefs

    def find_by_acct(self, acct_id: int) -> CardXrefRecord | None:
        return self._by_acct.get(acct_id)


class DiscGrpRepository:
    def __init__(self, rates: dict[tuple[str, str, int], DisGroupRecord]):
        """Key: (group_id, type_cd, cat_cd)."""
        self._rates = rates

    def find(self, group_id: str, type_cd: str, cat_cd: int) -> DisGroupRecord | None:
        rec = self._rates.get((group_id, type_cd, cat_cd))
        if rec is None:
            # Fallback to DEFAULT group
            rec = self._rates.get((DEFAULT_GROUP, type_cd, cat_cd))
        return rec


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class InterestResult:
    transactions_written: list[TranRecord] = field(default_factory=list)
    accounts_updated: list[AccountRecord] = field(default_factory=list)
    records_processed: int = 0
    total_interest: Decimal = Decimal("0.00")
    display_lines: list[str] = field(default_factory=list)


# ── Core processing ────────────────────────────────────────────────────────────

def compute_interest(
    tran_cat_bals: list[TranCatBalRecord],
    account_repo: AccountRepository,
    xref_repo: XrefRepository,
    discgrp_repo: DiscGrpRepository,
    parm_date: str = "",
    logger: Callable[[str], None] = print,
) -> InterestResult:
    """Main interest calculation loop — mirrors CBACT04C PROCEDURE DIVISION."""
    result = InterestResult()
    logger("START OF EXECUTION OF PROGRAM CBACT04C")

    last_acct_num: int = -1
    first_time = True
    ws_total_int = Decimal("0.00")
    ws_tranid_suffix = 0
    current_acct: AccountRecord | None = None
    current_xref: CardXrefRecord | None = None

    for cat_bal in tran_cat_bals:
        result.records_processed += 1
        logger(str(cat_bal))

        if cat_bal.trancat_acct_id != last_acct_num:
            if not first_time and current_acct is not None:
                # 1050-UPDATE-ACCOUNT for previous account
                current_acct = _update_account(current_acct, ws_total_int, account_repo)
                result.accounts_updated.append(current_acct)
            else:
                first_time = False

            ws_total_int = Decimal("0.00")
            last_acct_num = cat_bal.trancat_acct_id

            current_acct = account_repo.find(cat_bal.trancat_acct_id)
            current_xref = xref_repo.find_by_acct(cat_bal.trancat_acct_id)

        # Look up interest rate
        dis_rec = None
        if current_acct:
            dis_rec = discgrp_repo.find(
                current_acct.acct_group_id,
                cat_bal.trancat_type_cd,
                cat_bal.trancat_cd,
            )

        if dis_rec and dis_rec.dis_int_rate != 0:
            # 1300-COMPUTE-INTEREST
            monthly_int = (cat_bal.tran_cat_bal * dis_rec.dis_int_rate / Decimal("1200")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            ws_total_int += monthly_int
            result.total_interest += monthly_int

            # 1300-B-WRITE-TX
            ws_tranid_suffix += 1
            tran = _build_interest_transaction(
                cat_bal, current_xref, current_acct,
                monthly_int, parm_date, ws_tranid_suffix,
            )
            result.transactions_written.append(tran)

    # Final account update
    if not first_time and current_acct is not None:
        current_acct = _update_account(current_acct, ws_total_int, account_repo)
        result.accounts_updated.append(current_acct)

    logger("END OF EXECUTION OF PROGRAM CBACT04C")
    return result


def _update_account(
    acct: AccountRecord,
    total_int: Decimal,
    repo: AccountRepository,
) -> AccountRecord:
    """1050-UPDATE-ACCOUNT: add interest to balance, zero cyclic amounts."""
    acct.acct_curr_bal += total_int
    acct.acct_curr_cyc_credit = Decimal("0.00")
    acct.acct_curr_cyc_debit = Decimal("0.00")
    repo.update(acct)
    return acct


def _build_interest_transaction(
    cat_bal: TranCatBalRecord,
    xref: CardXrefRecord | None,
    acct: AccountRecord | None,
    amount: Decimal,
    parm_date: str,
    suffix: int,
) -> TranRecord:
    """1300-B-WRITE-TX: build interest transaction record."""
    tran_id = f"{parm_date}{suffix:06d}"[:16]
    acct_id_str = str(acct.acct_id) if acct else "00000000000"
    card_num = xref.xref_card_num if xref else ""
    ts = get_db2_timestamp()

    return TranRecord(
        tran_id=tran_id,
        tran_type_cd="01",
        tran_cat_cd=5,
        tran_source="System",
        tran_desc=f"Int. for a/c {acct_id_str}"[:100],
        tran_amt=amount,
        tran_merchant_id=0,
        tran_merchant_name="",
        tran_merchant_city="",
        tran_merchant_zip="",
        tran_card_num=card_num,
        tran_orig_ts=ts,
        tran_proc_ts=ts,
    )

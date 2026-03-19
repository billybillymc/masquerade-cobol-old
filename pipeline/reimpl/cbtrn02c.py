"""
Reimplementation of CBTRN02C — CardDemo Daily Transaction Posting.

Function: Read daily transactions sequentially, validate each one, then either:
  - POST: write to TRANSACT-FILE, update TCATBAL, update ACCOUNT
  - REJECT: write to DALYREJS with failure reason code

Validation rules:
  100: Invalid card number (not found in XREF)
  101: Account record not found
  102: Over credit limit
  103: Transaction received after account expiration date
"""

from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable

from .carddemo_data import (
    AccountRecord, CardXrefRecord, TranCatBalRecord, TranRecord,
    get_db2_timestamp,
)
from .cbtrn01c import DalyTranRecord


# ── Reject record ─────────────────────────────────────────────────────────────

@dataclass
class RejectRecord:
    tran_data: DalyTranRecord
    fail_reason: int
    fail_reason_desc: str


# ── Repository interfaces ──────────────────────────────────────────────────────

class XrefRepository:
    def __init__(self, xrefs: dict[str, CardXrefRecord]):
        self._by_card = xrefs

    def find_by_card(self, card_num: str) -> CardXrefRecord | None:
        return self._by_card.get(card_num)


class AccountRepository:
    def __init__(self, accounts: dict[int, AccountRecord]):
        self._accounts = accounts

    def find(self, acct_id: int) -> AccountRecord | None:
        return self._accounts.get(acct_id)

    def update(self, acct: AccountRecord) -> None:
        self._accounts[acct.acct_id] = acct


class TcatbalRepository:
    """Transaction category balance store — keyed by (acct_id, type_cd, cat_cd)."""

    def __init__(self, records: dict[tuple, TranCatBalRecord] = None):
        self._records = records or {}

    def find(self, acct_id: int, type_cd: str, cat_cd: int) -> TranCatBalRecord | None:
        return self._records.get((acct_id, type_cd, cat_cd))

    def upsert(self, rec: TranCatBalRecord) -> None:
        key = (rec.trancat_acct_id, rec.trancat_type_cd, rec.trancat_cd)
        self._records[key] = rec


# ── Validation codes ──────────────────────────────────────────────────────────

FAIL_INVALID_CARD   = 100
FAIL_ACCOUNT_NF     = 101
FAIL_OVERLIMIT      = 102
FAIL_EXPIRED        = 103


# ── Result ─────────────────────────────────────────────────────────────────────

@dataclass
class PostResult:
    transaction_count: int = 0
    reject_count: int = 0
    posted_transactions: list[TranRecord] = field(default_factory=list)
    rejected_records: list[RejectRecord] = field(default_factory=list)
    return_code: int = 0
    display_lines: list[str] = field(default_factory=list)


# ── Core processing ───────────────────────────────────────────────────────────

def post_daily_transactions(
    transactions: list[DalyTranRecord],
    xref_repo: XrefRepository,
    account_repo: AccountRepository,
    tcatbal_repo: TcatbalRepository,
    logger: Callable[[str], None] = print,
) -> PostResult:
    """Post daily transactions — mirrors CBTRN02C PROCEDURE DIVISION."""
    result = PostResult()
    logger("START OF EXECUTION OF PROGRAM CBTRN02C")

    for tran in transactions:
        result.transaction_count += 1

        fail_reason = 0
        fail_desc = ""
        xref = None
        acct = None

        # 1500-VALIDATE-TRAN → 1500-A-LOOKUP-XREF
        xref = xref_repo.find_by_card(tran.tran_card_num)
        if xref is None:
            fail_reason = FAIL_INVALID_CARD
            fail_desc = "INVALID CARD NUMBER FOUND"
        else:
            # 1500-B-LOOKUP-ACCT
            acct = account_repo.find(xref.xref_acct_id)
            if acct is None:
                fail_reason = FAIL_ACCOUNT_NF
                fail_desc = "ACCOUNT RECORD NOT FOUND"
            else:
                # Check credit limit
                temp_bal = (
                    acct.acct_curr_cyc_credit
                    - acct.acct_curr_cyc_debit
                    + Decimal(str(tran.tran_amt))
                )
                if acct.acct_credit_limit < temp_bal:
                    fail_reason = FAIL_OVERLIMIT
                    fail_desc = "OVERLIMIT TRANSACTION"
                # Check expiration (only set if not already failed)
                if fail_reason == 0:
                    tran_date = tran.tran_orig_ts[:10] if tran.tran_orig_ts else ""
                    if acct.acct_expiration_date < tran_date:
                        fail_reason = FAIL_EXPIRED
                        fail_desc = "TRANSACTION RECEIVED AFTER ACCT EXPIRATION"

        if fail_reason == 0 and xref is not None and acct is not None:
            # 2000-POST-TRANSACTION
            posted = _post_transaction(tran, xref, acct, tcatbal_repo, account_repo)
            result.posted_transactions.append(posted)
        else:
            # 2500-WRITE-REJECT-REC
            result.reject_count += 1
            result.rejected_records.append(
                RejectRecord(tran, fail_reason, fail_desc)
            )

    logger(f"TRANSACTIONS PROCESSED :{result.transaction_count:09d}")
    logger(f"TRANSACTIONS REJECTED  :{result.reject_count:09d}")

    if result.reject_count > 0:
        result.return_code = 4

    logger("END OF EXECUTION OF PROGRAM CBTRN02C")
    return result


def _post_transaction(
    tran: DalyTranRecord,
    xref: CardXrefRecord,
    acct: AccountRecord,
    tcatbal_repo: TcatbalRepository,
    account_repo: AccountRepository,
) -> TranRecord:
    """2000-POST-TRANSACTION: update tcatbal, update account, write transaction."""
    amt = Decimal(str(tran.tran_amt))
    ts = get_db2_timestamp()

    # 2700-UPDATE-TCATBAL
    cat_key = (xref.xref_acct_id, tran.tran_type_cd, tran.tran_cat_cd)
    existing = tcatbal_repo.find(xref.xref_acct_id, tran.tran_type_cd, tran.tran_cat_cd)
    if existing is None:
        new_cat = TranCatBalRecord(
            trancat_acct_id=xref.xref_acct_id,
            trancat_type_cd=tran.tran_type_cd,
            trancat_cd=tran.tran_cat_cd,
            tran_cat_bal=amt,
        )
        tcatbal_repo.upsert(new_cat)
    else:
        existing.tran_cat_bal += amt
        tcatbal_repo.upsert(existing)

    # 2800-UPDATE-ACCOUNT-REC
    acct.acct_curr_bal += amt
    if amt >= 0:
        acct.acct_curr_cyc_credit += amt
    else:
        acct.acct_curr_cyc_debit += amt
    account_repo.update(acct)

    # 2900-WRITE-TRANSACTION-FILE
    return TranRecord(
        tran_id=tran.tran_id,
        tran_type_cd=tran.tran_type_cd,
        tran_cat_cd=tran.tran_cat_cd,
        tran_source=tran.tran_source,
        tran_desc=tran.tran_desc,
        tran_amt=amt,
        tran_merchant_id=tran.tran_merchant_id,
        tran_merchant_name=tran.tran_merchant_name,
        tran_merchant_city=tran.tran_merchant_city,
        tran_merchant_zip=tran.tran_merchant_zip,
        tran_card_num=tran.tran_card_num,
        tran_orig_ts=tran.tran_orig_ts,
        tran_proc_ts=ts,
    )

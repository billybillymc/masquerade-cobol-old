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


def _format_bal(d: Decimal) -> str:
    return f"{d.quantize(Decimal('0.01')):.2f}"


# ── Differential harness runner adapter ────────────────────────────────────
#
# Hardcoded scenarios dispatched by the SCENARIO input key. Each scenario
# builds its own repos + transaction list so parity tests are fully
# deterministic (no datetime, no accumulated state).
#
# Inputs:
#   SCENARIO — one of "HAPPY_GOLDEN_VECTOR", "INVALID_CARD", "ACCT_NOT_FOUND",
#              "OVERLIMIT", "EXPIRED", "MIXED_BATCH"
#
# Outputs:
#   TRANSACTION_COUNT — total transactions processed
#   REJECT_COUNT      — number rejected
#   POSTED_COUNT      — number successfully posted
#   RETURN_CODE       — 4 if any rejected, 0 otherwise
#   FAIL_CODES        — comma-separated fail codes, one per transaction
#                       ("0" means posted, "100"-"103" are reject reasons)
#   FINAL_BAL_<acct>  — final curr_bal for each account touched (for success path)


def _scenario_happy_golden_vector():
    """The W1 CobolDecimal golden vector embedded in a full CBTRN02C run.

    acct.curr_cyc_credit = 5000.00, curr_cyc_debit = 3500.75, tran_amt = 150.25
    → temp_bal = 5000.00 - 3500.75 + 150.25 = 1649.50
    credit_limit (10000.00) < 1649.50  →  False  →  NOT overlimit, transaction posts.

    After posting:
      curr_bal 1000.00 + 150.25 = 1150.25
      cyc_credit 5000.00 + 150.25 = 5150.25 (amt > 0 → credit path)
    """
    xrefs = {"4111000000001111": CardXrefRecord(
        xref_card_num="4111000000001111", xref_cust_id=1, xref_acct_id=100000001
    )}
    accounts = {100000001: AccountRecord(
        acct_id=100000001,
        acct_active_status="Y",
        acct_curr_bal=Decimal("1000.00"),
        acct_credit_limit=Decimal("10000.00"),
        acct_curr_cyc_credit=Decimal("5000.00"),
        acct_curr_cyc_debit=Decimal("3500.75"),
        acct_expiration_date="2099-12-31",
    )}
    trans = [DalyTranRecord(
        tran_id="TRN0000000000001",
        tran_type_cd="01",
        tran_cat_cd=1,
        tran_source="POS",
        tran_desc="Golden vector test",
        tran_amt=float("150.25"),
        tran_card_num="4111000000001111",
        tran_orig_ts="2026-04-09-12.00.00.000000",
    )]
    return xrefs, accounts, {}, trans


def _scenario_invalid_card():
    xrefs = {"4111000000001111": CardXrefRecord(
        xref_card_num="4111000000001111", xref_cust_id=1, xref_acct_id=100000001
    )}
    accounts = {100000001: AccountRecord(
        acct_id=100000001,
        acct_curr_bal=Decimal("1000.00"),
        acct_credit_limit=Decimal("10000.00"),
        acct_curr_cyc_credit=Decimal("0.00"),
        acct_curr_cyc_debit=Decimal("0.00"),
        acct_expiration_date="2099-12-31",
    )}
    trans = [DalyTranRecord(
        tran_id="TRN0000000000002",
        tran_type_cd="01",
        tran_cat_cd=1,
        tran_source="POS",
        tran_amt=50.00,
        tran_card_num="9999999999999999",  # not in xref
        tran_orig_ts="2026-04-09-12.00.00.000000",
    )]
    return xrefs, accounts, {}, trans


def _scenario_acct_not_found():
    """Dangling xref: card maps to an account that doesn't exist."""
    xrefs = {"4111000000002222": CardXrefRecord(
        xref_card_num="4111000000002222", xref_cust_id=2, xref_acct_id=100000002
    )}
    accounts = {}  # 100000002 missing
    trans = [DalyTranRecord(
        tran_id="TRN0000000000003",
        tran_type_cd="01",
        tran_cat_cd=1,
        tran_source="POS",
        tran_amt=25.00,
        tran_card_num="4111000000002222",
        tran_orig_ts="2026-04-09-12.00.00.000000",
    )]
    return xrefs, accounts, {}, trans


def _scenario_overlimit():
    """Credit limit 100.00, temp_bal after txn would be 250.00 → reject 102."""
    xrefs = {"4111000000003333": CardXrefRecord(
        xref_card_num="4111000000003333", xref_cust_id=3, xref_acct_id=100000003
    )}
    accounts = {100000003: AccountRecord(
        acct_id=100000003,
        acct_curr_bal=Decimal("50.00"),
        acct_credit_limit=Decimal("100.00"),
        acct_curr_cyc_credit=Decimal("50.00"),
        acct_curr_cyc_debit=Decimal("0.00"),
        acct_expiration_date="2099-12-31",
    )}
    trans = [DalyTranRecord(
        tran_id="TRN0000000000004",
        tran_type_cd="01",
        tran_cat_cd=1,
        tran_source="POS",
        tran_amt=200.00,  # 50 - 0 + 200 = 250, exceeds 100 limit
        tran_card_num="4111000000003333",
        tran_orig_ts="2026-04-09-12.00.00.000000",
    )]
    return xrefs, accounts, {}, trans


def _scenario_expired():
    """Transaction date after account expiration → reject 103."""
    xrefs = {"4111000000004444": CardXrefRecord(
        xref_card_num="4111000000004444", xref_cust_id=4, xref_acct_id=100000004
    )}
    accounts = {100000004: AccountRecord(
        acct_id=100000004,
        acct_curr_bal=Decimal("0.00"),
        acct_credit_limit=Decimal("10000.00"),
        acct_curr_cyc_credit=Decimal("0.00"),
        acct_curr_cyc_debit=Decimal("0.00"),
        acct_expiration_date="2020-01-01",  # long expired
    )}
    trans = [DalyTranRecord(
        tran_id="TRN0000000000005",
        tran_type_cd="01",
        tran_cat_cd=1,
        tran_source="POS",
        tran_amt=10.00,
        tran_card_num="4111000000004444",
        tran_orig_ts="2026-04-09-12.00.00.000000",
    )]
    return xrefs, accounts, {}, trans


def _scenario_mixed_batch():
    """Three transactions: one posts, one invalid card, one overlimit."""
    xrefs = {
        "4111000000001111": CardXrefRecord(xref_card_num="4111000000001111", xref_cust_id=1, xref_acct_id=100000001),
        "4111000000003333": CardXrefRecord(xref_card_num="4111000000003333", xref_cust_id=3, xref_acct_id=100000003),
    }
    accounts = {
        100000001: AccountRecord(
            acct_id=100000001,
            acct_curr_bal=Decimal("1000.00"),
            acct_credit_limit=Decimal("10000.00"),
            acct_curr_cyc_credit=Decimal("0.00"),
            acct_curr_cyc_debit=Decimal("0.00"),
            acct_expiration_date="2099-12-31",
        ),
        100000003: AccountRecord(
            acct_id=100000003,
            acct_curr_bal=Decimal("50.00"),
            acct_credit_limit=Decimal("100.00"),
            acct_curr_cyc_credit=Decimal("50.00"),
            acct_curr_cyc_debit=Decimal("0.00"),
            acct_expiration_date="2099-12-31",
        ),
    }
    trans = [
        DalyTranRecord(
            tran_id="TRN0000000000006",
            tran_type_cd="01", tran_cat_cd=1,
            tran_amt=75.00,
            tran_card_num="4111000000001111",
            tran_orig_ts="2026-04-09-12.00.00.000000",
        ),
        DalyTranRecord(
            tran_id="TRN0000000000007",
            tran_type_cd="01", tran_cat_cd=1,
            tran_amt=40.00,
            tran_card_num="9999999999999999",  # invalid
            tran_orig_ts="2026-04-09-12.00.00.000000",
        ),
        DalyTranRecord(
            tran_id="TRN0000000000008",
            tran_type_cd="01", tran_cat_cd=1,
            tran_amt=500.00,  # overlimit on acct 3
            tran_card_num="4111000000003333",
            tran_orig_ts="2026-04-09-12.00.00.000000",
        ),
    ]
    return xrefs, accounts, {}, trans


_CBTRN02C_SCENARIOS = {
    "HAPPY_GOLDEN_VECTOR": _scenario_happy_golden_vector,
    "INVALID_CARD": _scenario_invalid_card,
    "ACCT_NOT_FOUND": _scenario_acct_not_found,
    "OVERLIMIT": _scenario_overlimit,
    "EXPIRED": _scenario_expired,
    "MIXED_BATCH": _scenario_mixed_batch,
}


def run_vector(inputs: dict) -> dict:
    """Canonical runner entry point for the differential harness."""
    scenario_name = str(inputs.get("SCENARIO", "")).upper()
    if scenario_name not in _CBTRN02C_SCENARIOS:
        return {"error": f"unknown scenario: {scenario_name!r}"}

    xrefs, accounts, _tcatbal, trans = _CBTRN02C_SCENARIOS[scenario_name]()
    xref_repo = XrefRepository(xrefs)
    account_repo = AccountRepository(dict(accounts))
    tcatbal_repo = TcatbalRepository({})

    # Snapshot the original account ids so we can report final balances
    # even when the original accounts dict is mutated in place.
    acct_ids = sorted(accounts.keys())

    result = post_daily_transactions(
        trans, xref_repo, account_repo, tcatbal_repo, logger=lambda _: None,
    )

    # Build per-transaction fail code list
    fail_codes = []
    posted_idx = 0
    rejected_idx = 0
    for _ in trans:
        # We need to figure out for each tran whether it was posted or rejected.
        # post_daily_transactions preserves input order, so we walk both lists.
        # Simpler: compare the total posted + rejected to input count; for
        # ordering, rebuild by matching tran_id.
        pass
    # Walk the posted and rejected collections in order — they were appended
    # in the same order as the input transactions
    posted_ids = [t.tran_id for t in result.posted_transactions]
    rejected_ids = [r.tran_data.tran_id for r in result.rejected_records]
    rejected_by_id = {r.tran_data.tran_id: r.fail_reason for r in result.rejected_records}
    for t in trans:
        if t.tran_id in posted_ids:
            fail_codes.append("0")
        else:
            fail_codes.append(str(rejected_by_id.get(t.tran_id, 0)))

    out = {
        "TRANSACTION_COUNT": str(result.transaction_count),
        "REJECT_COUNT": str(result.reject_count),
        "POSTED_COUNT": str(len(result.posted_transactions)),
        "RETURN_CODE": str(result.return_code),
        "FAIL_CODES": ",".join(fail_codes),
    }
    for aid in acct_ids:
        out[f"FINAL_BAL_{aid}"] = _format_bal(accounts[aid].acct_curr_bal)

    return out


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

"""
Reimplementation of CBTRN01C — CardDemo Daily Transaction Validation/Lookup.

Function: Read daily transactions sequentially, look up the card cross-reference,
then look up the corresponding account. Reports any unresolvable card numbers
or missing accounts.

Note: CBTRN01C does NOT post/write transactions — it is a read-and-verify pass.
Actual posting is done by CBTRN02C.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable

from .carddemo_data import TranRecord, CardXrefRecord, AccountRecord, CustomerRecord


# ── Daily transaction record (CVTRA06Y) ──────────────────────────────────────

@dataclass
class DalyTranRecord:
    """Daily transaction input record (RECLN 350)."""
    tran_id: str = ""
    tran_type_cd: str = ""
    tran_cat_cd: int = 0
    tran_source: str = ""
    tran_desc: str = ""
    tran_amt: float = 0.0
    tran_merchant_id: int = 0
    tran_merchant_name: str = ""
    tran_merchant_city: str = ""
    tran_merchant_zip: str = ""
    tran_card_num: str = ""
    tran_orig_ts: str = ""
    tran_proc_ts: str = ""


# ── Result ────────────────────────────────────────────────────────────────────

@dataclass
class LookupResult:
    """Result for a single transaction lookup."""
    tran: DalyTranRecord
    xref: CardXrefRecord | None = None
    account: AccountRecord | None = None
    xref_found: bool = False
    account_found: bool = False
    error_msg: str = ""


@dataclass
class ProcessResult:
    records_read: int = 0
    successful_lookups: int = 0
    failed_xref: int = 0
    failed_account: int = 0
    results: list[LookupResult] = field(default_factory=list)
    display_lines: list[str] = field(default_factory=list)


# ── Repository interfaces ──────────────────────────────────────────────────────

class XrefRepository:
    def __init__(self, xrefs: dict[str, CardXrefRecord]):
        """Keyed by card_num."""
        self._by_card = xrefs

    def find_by_card(self, card_num: str) -> CardXrefRecord | None:
        return self._by_card.get(card_num)


class AccountRepository:
    def __init__(self, accounts: dict[int, AccountRecord]):
        self._accounts = accounts

    def find(self, acct_id: int) -> AccountRecord | None:
        return self._accounts.get(acct_id)


# ── Core processing ───────────────────────────────────────────────────────────

def process_daily_transactions(
    transactions: list[DalyTranRecord],
    xref_repo: XrefRepository,
    account_repo: AccountRepository,
    logger: Callable[[str], None] = print,
) -> ProcessResult:
    """Validate daily transactions — mirrors CBTRN01C PROCEDURE DIVISION."""
    result = ProcessResult()
    logger("START OF EXECUTION OF PROGRAM CBTRN01C")

    for tran in transactions:
        result.records_read += 1
        line = str(tran)
        logger(line)
        result.display_lines.append(line)

        lookup = LookupResult(tran=tran)

        # 2000-LOOKUP-XREF
        xref = xref_repo.find_by_card(tran.tran_card_num)
        if xref is None:
            msg = (
                f"CARD NUMBER {tran.tran_card_num} COULD NOT BE VERIFIED. "
                f"SKIPPING TRANSACTION ID-{tran.tran_id}"
            )
            logger(msg)
            result.display_lines.append(msg)
            lookup.error_msg = msg
            result.failed_xref += 1
        else:
            lookup.xref = xref
            lookup.xref_found = True
            logger(f"SUCCESSFUL READ OF XREF")
            logger(f"CARD NUMBER: {xref.xref_card_num}")
            logger(f"ACCOUNT ID : {xref.xref_acct_id}")
            logger(f"CUSTOMER ID: {xref.xref_cust_id}")
            result.display_lines.extend([
                "SUCCESSFUL READ OF XREF",
                f"CARD NUMBER: {xref.xref_card_num}",
                f"ACCOUNT ID : {xref.xref_acct_id}",
                f"CUSTOMER ID: {xref.xref_cust_id}",
            ])

            # 3000-READ-ACCOUNT
            account = account_repo.find(xref.xref_acct_id)
            if account is None:
                msg = f"ACCOUNT {xref.xref_acct_id} NOT FOUND"
                logger(msg)
                result.display_lines.append(msg)
                lookup.error_msg = msg
                result.failed_account += 1
            else:
                lookup.account = account
                lookup.account_found = True
                logger("SUCCESSFUL READ OF ACCOUNT FILE")
                result.display_lines.append("SUCCESSFUL READ OF ACCOUNT FILE")
                result.successful_lookups += 1

        result.results.append(lookup)

    logger("END OF EXECUTION OF PROGRAM CBTRN01C")
    return result


# ── run_vector adapter ───────────────────────────────────────────────────────

def _scenario_process_records():
    xrefs = {
        "4111000000001111": CardXrefRecord(
            xref_card_num="4111000000001111", xref_cust_id=1, xref_acct_id=100000001,
        ),
    }
    accounts = {
        100000001: AccountRecord(acct_id=100000001, acct_active_status="Y"),
    }
    trans = [
        DalyTranRecord(tran_id="TRN0000000000001", tran_card_num="4111000000001111",
                        tran_type_cd="01", tran_cat_cd=1, tran_amt=150.25),
        DalyTranRecord(tran_id="TRN0000000000002", tran_card_num="9999999999999999",
                        tran_type_cd="01", tran_cat_cd=1, tran_amt=50.00),
    ]
    return trans, xrefs, accounts


def _scenario_empty_input():
    return [], {}, {}


_CBTRN01C_SCENARIOS = {
    "PROCESS_RECORDS": _scenario_process_records,
    "EMPTY_INPUT": _scenario_empty_input,
}


def run_vector(inputs: dict) -> dict:
    """Adapter for the differential harness runner contract."""
    scenario_name = str(inputs.get("SCENARIO", "PROCESS_RECORDS")).upper()
    if scenario_name not in _CBTRN01C_SCENARIOS:
        return {"error": f"unknown scenario: {scenario_name!r}"}

    trans, xrefs, accounts = _CBTRN01C_SCENARIOS[scenario_name]()
    xref_repo = XrefRepository(xrefs)
    account_repo = AccountRepository(accounts)

    result = process_daily_transactions(trans, xref_repo, account_repo, logger=lambda _: None)

    out: dict[str, str] = {
        "RECORDS_READ": str(result.records_read),
        "SUCCESSFUL_LOOKUPS": str(result.successful_lookups),
        "FAILED_XREF": str(result.failed_xref),
        "FAILED_ACCOUNT": str(result.failed_account),
    }
    for i, line in enumerate(result.display_lines):
        out[f"DISPLAY_{i}"] = line
    return out

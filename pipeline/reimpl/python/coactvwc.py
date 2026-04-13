"""
Reimplementation of COACTVWC — CardDemo Account View Screen.

CICS online program. Accepts an account ID, reads account and customer
data, and displays the full account detail view.

Navigation:
  ENTER → look up account by ID and display
  PF3   → return to calling program / main menu
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader, AccountRecord, CustomerRecord, CardXrefRecord,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3,
)


WS_PGMNAME   = "COACTVWC"
WS_TRANID    = "CAVW"
LIT_MENUPGM  = "COMEN01C"


# ── Screen output ─────────────────────────────────────────────────────────────

@dataclass
class AccountViewData:
    """Screen fields for account detail display."""
    acct_id: int = 0
    acct_active_status: str = ""
    acct_curr_bal: str = ""
    acct_credit_limit: str = ""
    acct_cash_credit_limit: str = ""
    acct_curr_cyc_credit: str = ""
    acct_curr_cyc_debit: str = ""
    acct_open_date: str = ""
    acct_expiration_date: str = ""
    acct_reissue_date: str = ""
    acct_group_id: str = ""
    cust_id: int = 0
    cust_ssn_masked: str = ""
    cust_name: str = ""
    cust_dob: str = ""
    cust_fico_score: int = 0
    cust_addr_zip: str = ""
    cust_phone_1: str = ""
    cust_phone_2: str = ""


@dataclass
class AccountViewResult:
    account_data: Optional[AccountViewData] = None
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    xctl_program: str = ""
    return_to_prev: bool = False


# ── Repository interfaces ──────────────────────────────────────────────────────

class AccountRepository:
    def __init__(self, accounts: dict[int, AccountRecord]):
        self._accounts = accounts

    def find(self, acct_id: int) -> Optional[AccountRecord]:
        return self._accounts.get(acct_id)


class XrefRepository:
    def __init__(self, xrefs_by_acct: dict[int, CardXrefRecord]):
        self._by_acct = xrefs_by_acct

    def find_by_acct(self, acct_id: int) -> Optional[CardXrefRecord]:
        return self._by_acct.get(acct_id)


class CustomerRepository:
    def __init__(self, customers: dict[int, CustomerRecord]):
        self._customers = customers

    def find(self, cust_id: int) -> Optional[CustomerRecord]:
        return self._customers.get(cust_id)


# ── Core logic ────────────────────────────────────────────────────────────────

def process_account_view(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    acct_id_input: str,
    account_repo: AccountRepository,
    xref_repo: XrefRepository,
    customer_repo: CustomerRepository,
) -> AccountViewResult:
    """Process account view screen — mirrors COACTVWC PROCEDURE DIVISION."""
    result = AccountViewResult()

    # Always set up commarea context
    if eibcalen == 0 or (
        commarea.cdemo_from_program == LIT_MENUPGM
        and commarea.cdemo_pgm_context == 0
    ):
        commarea = CarddemoCommarea()

    result.commarea = commarea

    if eibaid in (DFHPF3, "PF3"):
        # Return to calling program
        back_pgm = commarea.cdemo_from_program or LIT_MENUPGM
        back_tranid = commarea.cdemo_from_tranid or "CM00"
        commarea.cdemo_to_program = back_pgm
        commarea.cdemo_to_tranid = back_tranid
        commarea.cdemo_from_tranid = WS_TRANID
        commarea.cdemo_from_program = WS_PGMNAME
        commarea.cdemo_pgm_context = 0
        result.xctl_program = back_pgm
        result.return_to_prev = True
        result.commarea = commarea
        return result

    # ENTER or any other key → process input and display
    if commarea.cdemo_pgm_context == 0:
        # First entry — show blank search form
        commarea.cdemo_pgm_context = 1
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.message = "Enter or update id of account to display"
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    # Re-entry with account ID
    return _process_account_lookup(
        acct_id_input, account_repo, xref_repo, customer_repo, commarea, result
    )


def _process_account_lookup(
    acct_id_input: str,
    account_repo: AccountRepository,
    xref_repo: XrefRepository,
    customer_repo: CustomerRepository,
    commarea: CarddemoCommarea,
    result: AccountViewResult,
) -> AccountViewResult:
    """2000-PROCESS-INPUTS + 9000-READ-ACCT."""
    # Validate input
    if not acct_id_input or acct_id_input.strip() == "":
        result.error = True
        result.message = "Account number not provided"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    try:
        acct_id = int(acct_id_input.strip())
    except ValueError:
        result.error = True
        result.message = "Account number must be a non zero 11 digit number"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    if acct_id == 0:
        result.error = True
        result.message = "Account number must be a non zero 11 digit number"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    # Look up account
    acct = account_repo.find(acct_id)
    if acct is None:
        result.error = True
        result.message = "Did not find this account in account master file"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    # Look up customer via xref
    xref = xref_repo.find_by_acct(acct_id)
    cust = None
    if xref:
        cust = customer_repo.find(xref.xref_cust_id)
    if cust is None:
        result.error = True
        result.message = "Did not find associated customer in master file"

    view_data = _build_view_data(acct, cust)
    result.account_data = view_data
    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message if result.error else "Displaying details of given Account"
    result.commarea = commarea
    return result


def _build_view_data(acct: AccountRecord, cust: Optional[CustomerRecord]) -> AccountViewData:
    vd = AccountViewData(
        acct_id=acct.acct_id,
        acct_active_status=acct.acct_active_status,
        acct_curr_bal=f"{float(acct.acct_curr_bal):,.2f}",
        acct_credit_limit=f"{float(acct.acct_credit_limit):,.2f}",
        acct_cash_credit_limit=f"{float(acct.acct_cash_credit_limit):,.2f}",
        acct_curr_cyc_credit=f"{float(acct.acct_curr_cyc_credit):,.2f}",
        acct_curr_cyc_debit=f"{float(acct.acct_curr_cyc_debit):,.2f}",
        acct_open_date=acct.acct_open_date,
        acct_expiration_date=acct.acct_expiration_date,
        acct_reissue_date=acct.acct_reissue_date,
        acct_group_id=acct.acct_group_id,
    )
    if cust:
        ssn = str(cust.cust_ssn).zfill(9)
        vd.cust_id = cust.cust_id
        vd.cust_ssn_masked = f"{ssn[:3]}-{ssn[3:5]}-{ssn[5:]}"
        vd.cust_name = f"{cust.cust_first_name.strip()} {cust.cust_last_name.strip()}"
        vd.cust_dob = cust.cust_dob_yyyy_mm_dd
        vd.cust_fico_score = cust.cust_fico_credit_score
        vd.cust_addr_zip = cust.cust_addr_zip
        vd.cust_phone_1 = cust.cust_phone_num_1
        vd.cust_phone_2 = cust.cust_phone_num_2
    return vd


# ── Differential harness runner adapter ──────────────────────────────────────

from decimal import Decimal as _Decimal

_SEED_ACCOUNTS: dict[int, AccountRecord] = {
    10000001: AccountRecord(
        acct_id=10000001, acct_active_status="Y",
        acct_curr_bal=_Decimal("1500.00"), acct_credit_limit=_Decimal("5000.00"),
        acct_cash_credit_limit=_Decimal("1000.00"),
        acct_open_date="2020-01-15", acct_expiration_date="2028-01-15",
        acct_reissue_date="2025-01-15",
        acct_curr_cyc_credit=_Decimal("200.00"), acct_curr_cyc_debit=_Decimal("50.00"),
        acct_group_id="GOLD",
    ),
}

_SEED_XREFS_BY_ACCT: dict[int, CardXrefRecord] = {
    10000001: CardXrefRecord(xref_card_num="4111111111110001", xref_cust_id=100001, xref_acct_id=10000001),
}

_SEED_CUSTOMERS: dict[int, CustomerRecord] = {
    100001: CustomerRecord(
        cust_id=100001, cust_first_name="Jane", cust_last_name="User",
        cust_ssn=123456789, cust_dob_yyyy_mm_dd="1985-03-15",
        cust_fico_credit_score=750, cust_addr_zip="10001",
        cust_phone_num_1="212-555-0100", cust_phone_num_2="212-555-0101",
    ),
}


def run_vector(inputs: dict) -> dict:
    """Canonical runner entry point for the differential harness.

    SCENARIO selects a hardcoded test path:
      FIRST_ENTRY    — context=0, first entry → show blank form
      VALID_INPUT    — ENTER with valid account ID → display account
      ACCT_NOT_FOUND — ENTER with bad account ID → error
      PF3_RETURN     — press PF3 → return to menu
    """
    scenario = inputs.get("SCENARIO", "FIRST_ENTRY")

    account_repo = AccountRepository(dict(_SEED_ACCOUNTS))
    xref_repo = XrefRepository(dict(_SEED_XREFS_BY_ACCT))
    customer_repo = CustomerRepository(dict(_SEED_CUSTOMERS))

    commarea = CarddemoCommarea(
        cdemo_from_tranid="CM00",
        cdemo_from_program="COMEN01C",
        cdemo_user_id="USER0001",
        cdemo_user_type="U",
        cdemo_pgm_context=1,
    )

    if scenario == "FIRST_ENTRY":
        commarea.cdemo_pgm_context = 0
        result = process_account_view(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            acct_id_input="",
            account_repo=account_repo, xref_repo=xref_repo,
            customer_repo=customer_repo,
        )
    elif scenario == "VALID_INPUT":
        result = process_account_view(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            acct_id_input="10000001",
            account_repo=account_repo, xref_repo=xref_repo,
            customer_repo=customer_repo,
        )
    elif scenario == "ACCT_NOT_FOUND":
        result = process_account_view(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            acct_id_input="99999999",
            account_repo=account_repo, xref_repo=xref_repo,
            customer_repo=customer_repo,
        )
    elif scenario == "PF3_RETURN":
        result = process_account_view(
            eibcalen=100, eibaid="PF3", commarea=commarea,
            acct_id_input="",
            account_repo=account_repo, xref_repo=xref_repo,
            customer_repo=customer_repo,
        )
    else:
        commarea.cdemo_pgm_context = 0
        result = process_account_view(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            acct_id_input="",
            account_repo=account_repo, xref_repo=xref_repo,
            customer_repo=customer_repo,
        )

    acct_id_out = ""
    acct_status_out = ""
    acct_bal_out = ""
    cust_name_out = ""
    cust_ssn_out = ""
    if result.account_data:
        acct_id_out = str(result.account_data.acct_id)
        acct_status_out = result.account_data.acct_active_status
        acct_bal_out = result.account_data.acct_curr_bal
        cust_name_out = result.account_data.cust_name
        cust_ssn_out = result.account_data.cust_ssn_masked

    return {
        "ERROR": "Y" if result.error else "N",
        "MESSAGE": result.message,
        "XCTL_PROGRAM": result.xctl_program or "",
        "RETURN_TO_PREV": "Y" if result.return_to_prev else "N",
        "ACCT_ID": acct_id_out,
        "ACCT_STATUS": acct_status_out,
        "ACCT_BAL": acct_bal_out,
        "CUST_NAME": cust_name_out,
        "CUST_SSN": cust_ssn_out,
    }

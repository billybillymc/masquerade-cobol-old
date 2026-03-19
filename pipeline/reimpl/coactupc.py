"""
Reimplementation of COACTUPC — CardDemo Account Update Screen.

CICS online program. Provides a full account + customer update facility.

State machine (mirroring ACUP-CHANGE-ACTION flag):
  '' / ' '   → initial: prompt for account ID
  'S'        → account details fetched; ready for editing
  'E'        → validation errors; screen re-displayed
  'N'        → changes OK; awaiting PF5 confirmation
  'C'        → changes committed
  'L'/'F'    → lock/write error

Navigation:
  ENTER  → fetch account (initial) or validate edits
  PF3    → return to menu
  PF5    → save after confirmation (action='N')
  PF12   → go to card list for this account
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader,
    AccountRecord, CustomerRecord, CardXrefRecord,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3, DFHPF5, DFHPF12,
)


WS_PGMNAME = "COACTUPC"
WS_TRANID  = "CAUP"


# ─── Input dataclass ────────────────────────────────────────────────────────

@dataclass
class AccountUpdateInput:
    acct_id: str = ""
    active_status: str = ""
    credit_limit: str = ""
    cash_credit_limit: str = ""
    curr_bal: str = ""
    curr_cyc_credit: str = ""
    curr_cyc_debit: str = ""
    open_date: str = ""
    expiry_date: str = ""
    reissue_date: str = ""
    group_id: str = ""
    # customer fields
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    addr_line1: str = ""
    addr_line2: str = ""
    addr_line3: str = ""
    addr_state: str = ""
    addr_country: str = ""
    addr_zip: str = ""
    phone1: str = ""
    phone2: str = ""
    eft_account_id: str = ""
    pri_card_holder: str = ""
    fico_score: str = ""
    dob: str = ""
    govt_issued_id: str = ""


@dataclass
class AccountUpdateResult:
    acct_record: Optional[AccountRecord] = None
    cust_record: Optional[CustomerRecord] = None
    xref_record: Optional[CardXrefRecord] = None
    action: str = ""          # S, E, N, C, L, F
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    success: bool = False
    xctl_program: str = ""
    return_to_prev: bool = False


# ─── Repositories ───────────────────────────────────────────────────────────

class AccountRepository:
    def __init__(self, accounts: dict[int, AccountRecord]):
        self._accounts = accounts

    def find(self, acct_id: int) -> Optional[AccountRecord]:
        return self._accounts.get(acct_id)

    def rewrite(self, acct: AccountRecord) -> bool:
        if acct.acct_id not in self._accounts:
            return False
        self._accounts[acct.acct_id] = acct
        return True


class CustomerRepository:
    def __init__(self, customers: dict[int, CustomerRecord]):
        self._customers = customers

    def find(self, cust_id: int) -> Optional[CustomerRecord]:
        return self._customers.get(cust_id)

    def rewrite(self, cust: CustomerRecord) -> bool:
        if cust.cust_id not in self._customers:
            return False
        self._customers[cust.cust_id] = cust
        return True


class XrefRepository:
    def __init__(self, xrefs: list[CardXrefRecord]):
        self._by_acct: dict[int, CardXrefRecord] = {x.xref_acct_id: x for x in xrefs}

    def find_by_acct(self, acct_id: int) -> Optional[CardXrefRecord]:
        return self._by_acct.get(acct_id)


# ─── Main entry ─────────────────────────────────────────────────────────────

def process_account_update(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    inp: AccountUpdateInput,
    acct_repo: AccountRepository,
    cust_repo: CustomerRepository,
    xref_repo: XrefRepository,
    current_action: str = "",
    old_acct: Optional[AccountRecord] = None,
    old_cust: Optional[CustomerRecord] = None,
) -> AccountUpdateResult:
    """Process account update screen — mirrors COACTUPC PROCEDURE DIVISION."""
    result = AccountUpdateResult()

    if eibcalen == 0:
        result.return_to_prev = True
        result.xctl_program = "COSGN00C"
        return result

    result.commarea = commarea

    if eibaid in (DFHPF3, "PF3"):
        back = commarea.cdemo_from_program or "COMEN01C"
        result.xctl_program = back
        result.return_to_prev = True
        result.commarea = commarea
        return result

    if current_action in ("C", "L", "F", ""):
        return _initial_display(inp.acct_id, acct_repo, cust_repo, xref_repo, commarea, result)

    if current_action == "S":
        return _validate_and_preview(inp, old_acct, old_cust, acct_repo, cust_repo, xref_repo, commarea, result)

    if current_action in ("N", "E"):
        if eibaid in (DFHPF5, "PF5") and current_action == "N":
            return _commit_changes(inp, old_acct, old_cust, acct_repo, cust_repo, commarea, result)
        if eibaid in (DFHPF12, "PF12"):
            result.xctl_program = "COCRDLIC"
            result.return_to_prev = True
            result.commarea = commarea
            return result
        return _validate_and_preview(inp, old_acct, old_cust, acct_repo, cust_repo, xref_repo, commarea, result)

    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.commarea = commarea
    return result


# ─── Internal helpers ────────────────────────────────────────────────────────

def _initial_display(acct_id_str, acct_repo, cust_repo, xref_repo, commarea, result):
    result.action = ""
    if not acct_id_str or not acct_id_str.strip():
        result.message = "Enter or update id of account to update"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.commarea = commarea
        return result

    if not acct_id_str.strip().isdigit():
        result.error = True
        result.message = "Account number must be a non zero 11 digit number"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    acct_id = int(acct_id_str.strip())
    if acct_id == 0:
        result.error = True
        result.message = "Account number must be a non zero 11 digit number"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    acct = acct_repo.find(acct_id)
    if acct is None:
        result.error = True
        result.message = "Did not find this account in account master file"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    xref = xref_repo.find_by_acct(acct_id)
    if xref is None:
        result.error = True
        result.message = "Did not find this account in account card xref file"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    cust = cust_repo.find(xref.xref_cust_id)
    if cust is None:
        result.error = True
        result.message = "Did not find associated customer in master file"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    result.action = "S"
    result.acct_record = acct
    result.cust_record = cust
    result.xref_record = xref
    result.message = "Details of selected account shown above"
    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    result.commarea = commarea
    return result


def _validate_and_preview(inp, old_acct, old_cust, acct_repo, cust_repo, xref_repo, commarea, result):
    errors = _validate_inputs(inp)
    if errors:
        result.action = "E"
        result.error = True
        result.message = errors[0]
        result.acct_record = old_acct
        result.cust_record = old_cust
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    # Build proposed records from input
    new_acct = _apply_acct_input(inp, old_acct)
    new_cust = _apply_cust_input(inp, old_cust)

    result.action = "N"
    result.acct_record = new_acct
    result.cust_record = new_cust
    result.message = "Changes validated.Press F5 to save"
    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    result.commarea = commarea
    return result


def _commit_changes(inp, old_acct, old_cust, acct_repo, cust_repo, commarea, result):
    new_acct = _apply_acct_input(inp, old_acct)
    new_cust = _apply_cust_input(inp, old_cust)

    if not acct_repo.rewrite(new_acct):
        result.action = "L"
        result.error = True
        result.message = "Could not lock account record for update"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    if not cust_repo.rewrite(new_cust):
        result.action = "F"
        result.error = True
        result.message = "Update of record failed"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    result.action = "C"
    result.success = True
    result.acct_record = new_acct
    result.cust_record = new_cust
    result.message = "Changes committed to database"
    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    result.commarea = commarea
    return result


# ─── Validation ─────────────────────────────────────────────────────────────

def _validate_inputs(inp: AccountUpdateInput) -> list[str]:
    errors: list[str] = []

    status = inp.active_status.strip().upper() if inp.active_status else ""
    if status not in ("Y", "N"):
        errors.append("Account Active Status must be Y or N")
        return errors

    for label, val in [
        ("Credit Limit", inp.credit_limit),
        ("Cash Credit Limit", inp.cash_credit_limit),
    ]:
        v = val.strip() if val else ""
        if not v:
            errors.append(f"{label} must be supplied")
            return errors
        try:
            Decimal(v)
        except InvalidOperation:
            errors.append(f"{label} is not valid")
            return errors

    last = inp.last_name.strip() if inp.last_name else ""
    if not last:
        errors.append("Last name not provided")
        return errors

    return errors


# ─── Record construction ─────────────────────────────────────────────────────

def _apply_acct_input(inp, old: Optional[AccountRecord]) -> AccountRecord:
    from copy import deepcopy
    acct = deepcopy(old) if old else AccountRecord()

    if inp.active_status.strip():
        acct.acct_active_status = inp.active_status.strip().upper()[0]
    if inp.credit_limit.strip():
        try:
            acct.acct_credit_limit = Decimal(inp.credit_limit.strip())
        except InvalidOperation:
            pass
    if inp.cash_credit_limit.strip():
        try:
            acct.acct_cash_credit_limit = Decimal(inp.cash_credit_limit.strip())
        except InvalidOperation:
            pass
    if inp.curr_bal.strip():
        try:
            acct.acct_curr_bal = Decimal(inp.curr_bal.strip())
        except InvalidOperation:
            pass
    if inp.open_date.strip():
        acct.acct_open_date = inp.open_date.strip()
    if inp.expiry_date.strip():
        acct.acct_expiration_date = inp.expiry_date.strip()
    if inp.reissue_date.strip():
        acct.acct_reissue_date = inp.reissue_date.strip()
    if inp.group_id.strip():
        acct.acct_group_id = inp.group_id.strip()
    return acct


def _apply_cust_input(inp, old: Optional[CustomerRecord]) -> CustomerRecord:
    from copy import deepcopy
    cust = deepcopy(old) if old else CustomerRecord()

    def _set(attr, val):
        if val and val.strip():
            setattr(cust, attr, val.strip())

    _set("cust_first_name", inp.first_name)
    _set("cust_middle_name", inp.middle_name)
    _set("cust_last_name", inp.last_name)
    _set("cust_addr_line_1", inp.addr_line1)
    _set("cust_addr_line_2", inp.addr_line2)
    _set("cust_addr_line_3", inp.addr_line3)
    _set("cust_addr_state_cd", inp.addr_state)
    _set("cust_addr_country_cd", inp.addr_country)
    _set("cust_addr_zip", inp.addr_zip)
    _set("cust_phone_num_1", inp.phone1)
    _set("cust_phone_num_2", inp.phone2)
    _set("cust_eft_account_id", inp.eft_account_id)
    _set("cust_pri_card_holder_ind", inp.pri_card_holder)
    _set("cust_govt_issued_id", inp.govt_issued_id)
    _set("cust_dob_yyyy_mm_dd", inp.dob)
    if inp.fico_score.strip():
        try:
            cust.cust_fico_credit_score = int(inp.fico_score.strip())
        except ValueError:
            pass
    return cust

"""
Reimplementation of COTRN02C — CardDemo Add Transaction Screen.

CICS online program. Allows entry of a new transaction record.
Validates all fields (account/card lookup, date formats, amount format)
and writes a new record to the TRANSACT file upon confirmation (Y).

Navigation:
  ENTER → validate and confirm/add transaction
  PF3   → return to calling program
  PF4   → clear screen
  PF5   → copy last transaction's data into fields
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader, TranRecord, CardXrefRecord,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3, DFHPF4, DFHPF5,
    get_db2_timestamp,
)
from .csutldtc import validate_date


WS_PGMNAME = "COTRN02C"
WS_TRANID  = "CT02"
DATE_FORMAT = "YYYY-MM-DD"
DATE_RE     = re.compile(r"^\d{4}-\d{2}-\d{2}$")
AMT_RE      = re.compile(r"^[+-]\d{8}\.\d{2}$")


@dataclass
class TranAddInput:
    acct_id: str = ""
    card_num: str = ""
    type_cd: str = ""
    cat_cd: str = ""
    source: str = ""
    desc: str = ""
    amount: str = ""
    orig_date: str = ""
    proc_date: str = ""
    merchant_id: str = ""
    merchant_name: str = ""
    merchant_city: str = ""
    merchant_zip: str = ""
    confirm: str = ""


@dataclass
class TranAddResult:
    tran_record: Optional[TranRecord] = None
    resolved_acct_id: str = ""
    resolved_card_num: str = ""
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    success: bool = False
    xctl_program: str = ""
    return_to_prev: bool = False
    cleared: bool = False
    last_tran_copied: bool = False


class TranRepository:
    def __init__(self, transactions: list[TranRecord]):
        self._trans = sorted(transactions, key=lambda t: t.tran_id)

    def find_last(self) -> Optional[TranRecord]:
        return self._trans[-1] if self._trans else None

    def write(self, tran: TranRecord) -> str:
        """Write new transaction; returns '' on success or error message."""
        if any(t.tran_id == tran.tran_id for t in self._trans):
            return "Tran ID already exist..."
        self._trans.append(tran)
        self._trans.sort(key=lambda t: t.tran_id)
        return ""

    def next_id(self) -> str:
        if not self._trans:
            return "0000000000000001"
        last_id = self._trans[-1].tran_id.strip()
        try:
            return str(int(last_id) + 1).zfill(16)
        except ValueError:
            return "0000000000000001"


class XrefRepository:
    def __init__(self, xrefs: list[CardXrefRecord]):
        self._by_card: dict[str, CardXrefRecord] = {x.xref_card_num.strip(): x for x in xrefs}
        self._by_acct: dict[int, CardXrefRecord] = {x.xref_acct_id: x for x in xrefs}

    def find_by_card(self, card_num: str) -> Optional[CardXrefRecord]:
        return self._by_card.get(card_num.strip())

    def find_by_acct(self, acct_id: int) -> Optional[CardXrefRecord]:
        return self._by_acct.get(acct_id)


def process_tran_add(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    inp: TranAddInput,
    tran_repo: TranRepository,
    xref_repo: XrefRepository,
) -> TranAddResult:
    """Process add transaction screen — mirrors COTRN02C PROCEDURE DIVISION."""
    result = TranAddResult()

    if eibcalen == 0:
        result.return_to_prev = True
        result.xctl_program = "COSGN00C"
        return result

    result.commarea = commarea

    if commarea.cdemo_pgm_context == 0:
        commarea.cdemo_pgm_context = 1
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.commarea = commarea
        return result

    if eibaid in (DFHENTER, "ENTER"):
        return _process_enter(inp, tran_repo, xref_repo, commarea, result)
    elif eibaid in (DFHPF3, "PF3"):
        back = commarea.cdemo_from_program or "COMEN01C"
        result.xctl_program = back
        result.return_to_prev = True
        result.commarea = commarea
        return result
    elif eibaid in (DFHPF4, "PF4"):
        result.cleared = True
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.commarea = commarea
        return result
    elif eibaid in (DFHPF5, "PF5"):
        return _copy_last_tran(inp, tran_repo, xref_repo, commarea, result)
    else:
        result.error = True
        result.message = CCDA_MSG_INVALID_KEY
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result


def _process_enter(inp, tran_repo, xref_repo, commarea, result):
    xref = _validate_key_fields(inp, xref_repo, result)
    if result.error:
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    _validate_data_fields(inp, result)
    if result.error:
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    confirm = inp.confirm.strip().upper() if inp.confirm else ""
    if confirm == "Y":
        _add_transaction(inp, xref, tran_repo, result)
    elif confirm in ("N", "", "\x00"):
        result.error = True
        result.message = "Confirm to add this transaction..."
    else:
        result.error = True
        result.message = "Invalid value. Valid values are (Y/N)..."

    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    result.commarea = commarea
    return result


def _validate_key_fields(inp, xref_repo, result) -> Optional[CardXrefRecord]:
    acct_s = inp.acct_id.strip() if inp.acct_id else ""
    card_s = inp.card_num.strip() if inp.card_num else ""

    if acct_s:
        if not acct_s.isdigit():
            result.error = True
            result.message = "Account ID must be Numeric..."
            return None
        xref = xref_repo.find_by_acct(int(acct_s))
        if xref is None:
            result.error = True
            result.message = "Account ID NOT found..."
            return None
        result.resolved_acct_id = acct_s
        result.resolved_card_num = xref.xref_card_num.strip()
        return xref
    elif card_s:
        if not card_s.isdigit():
            result.error = True
            result.message = "Card Number must be Numeric..."
            return None
        xref = xref_repo.find_by_card(card_s)
        if xref is None:
            result.error = True
            result.message = "Card Number NOT found..."
            return None
        result.resolved_card_num = card_s
        result.resolved_acct_id = str(xref.xref_acct_id)
        return xref
    else:
        result.error = True
        result.message = "Account or Card Number must be entered..."
        return None


def _validate_data_fields(inp, result):
    checks = [
        (inp.type_cd, "Type CD can NOT be empty..."),
        (inp.cat_cd, "Category CD can NOT be empty..."),
        (inp.source, "Source can NOT be empty..."),
        (inp.desc, "Description can NOT be empty..."),
        (inp.amount, "Amount can NOT be empty..."),
        (inp.orig_date, "Orig Date can NOT be empty..."),
        (inp.proc_date, "Proc Date can NOT be empty..."),
        (inp.merchant_id, "Merchant ID can NOT be empty..."),
        (inp.merchant_name, "Merchant Name can NOT be empty..."),
        (inp.merchant_city, "Merchant City can NOT be empty..."),
        (inp.merchant_zip, "Merchant Zip can NOT be empty..."),
    ]
    for val, msg in checks:
        if not val or not val.strip():
            result.error = True
            result.message = msg
            return

    type_s = inp.type_cd.strip()
    cat_s = inp.cat_cd.strip()
    if not type_s.isdigit():
        result.error = True
        result.message = "Type CD must be Numeric..."
        return
    if not cat_s.isdigit():
        result.error = True
        result.message = "Category CD must be Numeric..."
        return

    if not AMT_RE.match(inp.amount.strip() if inp.amount else ""):
        result.error = True
        result.message = "Amount should be in format -99999999.99"
        return

    if not DATE_RE.match(inp.orig_date.strip() if inp.orig_date else ""):
        result.error = True
        result.message = "Orig Date should be in format YYYY-MM-DD"
        return

    if not DATE_RE.match(inp.proc_date.strip() if inp.proc_date else ""):
        result.error = True
        result.message = "Proc Date should be in format YYYY-MM-DD"
        return

    orig_check = validate_date(inp.orig_date.strip(), DATE_FORMAT)
    if orig_check.severity != 0:
        result.error = True
        result.message = "Orig Date - Not a valid date..."
        return

    proc_check = validate_date(inp.proc_date.strip(), DATE_FORMAT)
    if proc_check.severity != 0:
        result.error = True
        result.message = "Proc Date - Not a valid date..."
        return

    if not inp.merchant_id.strip().isdigit():
        result.error = True
        result.message = "Merchant ID must be Numeric..."
        return


def _add_transaction(inp, xref, tran_repo, result):
    try:
        amt = Decimal(inp.amount.strip())
    except InvalidOperation:
        result.error = True
        result.message = "Invalid amount value"
        return

    tran = TranRecord(
        tran_id=tran_repo.next_id(),
        tran_type_cd=inp.type_cd.strip(),
        tran_cat_cd=int(inp.cat_cd.strip()),
        tran_source=inp.source.strip(),
        tran_desc=inp.desc.strip(),
        tran_amt=amt,
        tran_card_num=result.resolved_card_num or (inp.card_num.strip() if inp.card_num else ""),
        tran_merchant_id=int(inp.merchant_id.strip()),
        tran_merchant_name=inp.merchant_name.strip(),
        tran_merchant_city=inp.merchant_city.strip(),
        tran_merchant_zip=inp.merchant_zip.strip(),
        tran_orig_ts=inp.orig_date.strip(),
        tran_proc_ts=inp.proc_date.strip(),
    )

    err = tran_repo.write(tran)
    if err:
        result.error = True
        result.message = err
    else:
        result.success = True
        result.tran_record = tran
        result.message = (
            f"Transaction added successfully.  Your Tran ID is {tran.tran_id.strip()}."
        )


def _copy_last_tran(inp, tran_repo, xref_repo, commarea, result):
    _validate_key_fields(inp, xref_repo, result)
    if result.error:
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    last = tran_repo.find_last()
    if last:
        inp.type_cd = last.tran_type_cd
        inp.cat_cd = str(last.tran_cat_cd)
        inp.source = last.tran_source
        inp.amount = f"{float(last.tran_amt):+011.2f}"
        inp.desc = last.tran_desc
        inp.orig_date = last.tran_orig_ts[:10]
        inp.proc_date = last.tran_proc_ts[:10]
        inp.merchant_id = str(last.tran_merchant_id)
        inp.merchant_name = last.tran_merchant_name
        inp.merchant_city = last.tran_merchant_city
        inp.merchant_zip = last.tran_merchant_zip
        result.last_tran_copied = True

    return _process_enter(inp, tran_repo, xref_repo, commarea, result)


# ── Differential harness runner adapter ──────────────────────────────────────

_SEED_XREFS = [
    CardXrefRecord(xref_card_num="4111111111111111", xref_cust_id=1, xref_acct_id=10000001),
    CardXrefRecord(xref_card_num="4222222222222222", xref_cust_id=2, xref_acct_id=10000002),
]

_SEED_TRANS = [
    TranRecord(tran_id="0000000000000001", tran_type_cd="01", tran_cat_cd=1,
               tran_source="ONLINE", tran_desc="SEED PURCHASE",
               tran_amt=Decimal("50.00"), tran_card_num="4111111111111111",
               tran_merchant_id=100001, tran_merchant_name="ACME STORE",
               tran_merchant_city="NEW YORK", tran_merchant_zip="10001",
               tran_orig_ts="2025-01-10", tran_proc_ts="2025-01-10"),
]


def run_vector(inputs: dict) -> dict:
    """Canonical runner entry point for the differential harness.

    SCENARIO selects a hardcoded test path:
      ADD_SUCCESS       — valid input, confirm Y → transaction added
      ACCT_NOT_FOUND    — non-existent account → error
      MISSING_FIELDS    — empty description → validation error
      INVALID_AMOUNT    — bad amount format → error
      INVALID_DATE      — bad date → error
      CONFIRM_PENDING   — no confirm → "Confirm to add..."
    """
    scenario = inputs.get("SCENARIO", "ADD_SUCCESS")

    import copy
    tran_repo = TranRepository(copy.deepcopy(_SEED_TRANS))
    xref_repo = XrefRepository(list(_SEED_XREFS))

    commarea = CarddemoCommarea(
        cdemo_from_tranid="CM00",
        cdemo_from_program="COMEN01C",
        cdemo_user_id="USER0001",
        cdemo_user_type="U",
        cdemo_pgm_context=1,
    )

    if scenario == "ADD_SUCCESS":
        inp = TranAddInput(
            acct_id="10000001", card_num="", type_cd="01", cat_cd="1",
            source="ONLINE", desc="NEW PURCHASE", amount="+00000100.00",
            orig_date="2025-03-15", proc_date="2025-03-15",
            merchant_id="100001", merchant_name="TEST MERCHANT",
            merchant_city="BOSTON", merchant_zip="02101", confirm="Y",
        )
        result = process_tran_add(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            inp=inp, tran_repo=tran_repo, xref_repo=xref_repo,
        )
    elif scenario == "ACCT_NOT_FOUND":
        inp = TranAddInput(
            acct_id="99999999", card_num="", type_cd="01", cat_cd="1",
            source="ONLINE", desc="TEST", amount="+00000050.00",
            orig_date="2025-03-15", proc_date="2025-03-15",
            merchant_id="100001", merchant_name="TEST",
            merchant_city="NYC", merchant_zip="10001", confirm="Y",
        )
        result = process_tran_add(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            inp=inp, tran_repo=tran_repo, xref_repo=xref_repo,
        )
    elif scenario == "MISSING_FIELDS":
        inp = TranAddInput(
            acct_id="10000001", card_num="", type_cd="01", cat_cd="1",
            source="ONLINE", desc="", amount="+00000050.00",
            orig_date="2025-03-15", proc_date="2025-03-15",
            merchant_id="100001", merchant_name="TEST",
            merchant_city="NYC", merchant_zip="10001", confirm="Y",
        )
        result = process_tran_add(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            inp=inp, tran_repo=tran_repo, xref_repo=xref_repo,
        )
    elif scenario == "INVALID_AMOUNT":
        inp = TranAddInput(
            acct_id="10000001", card_num="", type_cd="01", cat_cd="1",
            source="ONLINE", desc="TEST", amount="BADAMT",
            orig_date="2025-03-15", proc_date="2025-03-15",
            merchant_id="100001", merchant_name="TEST",
            merchant_city="NYC", merchant_zip="10001", confirm="Y",
        )
        result = process_tran_add(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            inp=inp, tran_repo=tran_repo, xref_repo=xref_repo,
        )
    elif scenario == "INVALID_DATE":
        inp = TranAddInput(
            acct_id="10000001", card_num="", type_cd="01", cat_cd="1",
            source="ONLINE", desc="TEST", amount="+00000050.00",
            orig_date="2025-13-45", proc_date="2025-03-15",
            merchant_id="100001", merchant_name="TEST",
            merchant_city="NYC", merchant_zip="10001", confirm="Y",
        )
        result = process_tran_add(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            inp=inp, tran_repo=tran_repo, xref_repo=xref_repo,
        )
    elif scenario == "CONFIRM_PENDING":
        inp = TranAddInput(
            acct_id="10000001", card_num="", type_cd="01", cat_cd="1",
            source="ONLINE", desc="TEST", amount="+00000050.00",
            orig_date="2025-03-15", proc_date="2025-03-15",
            merchant_id="100001", merchant_name="TEST",
            merchant_city="NYC", merchant_zip="10001", confirm="",
        )
        result = process_tran_add(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            inp=inp, tran_repo=tran_repo, xref_repo=xref_repo,
        )
    else:
        inp = TranAddInput(
            acct_id="10000001", card_num="", type_cd="01", cat_cd="1",
            source="ONLINE", desc="NEW PURCHASE", amount="+00000100.00",
            orig_date="2025-03-15", proc_date="2025-03-15",
            merchant_id="100001", merchant_name="TEST MERCHANT",
            merchant_city="BOSTON", merchant_zip="02101", confirm="Y",
        )
        result = process_tran_add(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            inp=inp, tran_repo=tran_repo, xref_repo=xref_repo,
        )

    tran_id = ""
    if result.tran_record:
        tran_id = result.tran_record.tran_id

    return {
        "SUCCESS": "Y" if result.success else "N",
        "ERROR": "Y" if result.error else "N",
        "MESSAGE": result.message,
        "TRAN_ID": tran_id,
        "XCTL_PROGRAM": result.xctl_program or "",
    }

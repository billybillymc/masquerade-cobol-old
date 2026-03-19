"""
Reimplementation of COBIL00C — CardDemo Bill Payment Screen.

CICS online program. Allows a user to pay their full account balance.
Steps:
  1. Enter account ID → displays current balance
  2. Confirm with 'Y' → creates payment transaction, zeroes balance

Navigation:
  ENTER → process (lookup then confirm)
  PF3   → return to calling program
  PF4   → clear screen
"""

from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader, AccountRecord, TranRecord,
    CardXrefRecord, CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3, DFHPF4,
    get_db2_timestamp,
)


WS_PGMNAME = "COBIL00C"
WS_TRANID  = "CB00"
BILL_PAY_TYPE_CD   = "02"
BILL_PAY_CAT_CD    = 2
BILL_PAY_SOURCE    = "POS TERM"
BILL_PAY_DESC      = "BILL PAYMENT - ONLINE"
BILL_PAY_MERCHANT_ID   = 999999999
BILL_PAY_MERCHANT_NAME = "BILL PAYMENT"
BILL_PAY_MERCHANT_CITY = "N/A"
BILL_PAY_MERCHANT_ZIP  = "N/A"


@dataclass
class BillPayResult:
    acct_record: Optional[AccountRecord] = None
    tran_record: Optional[TranRecord] = None
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    success: bool = False
    xctl_program: str = ""
    return_to_prev: bool = False
    cleared: bool = False


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


class XrefRepository:
    def __init__(self, xrefs: dict[int, CardXrefRecord]):
        self._by_acct = xrefs

    def find_by_acct(self, acct_id: int) -> Optional[CardXrefRecord]:
        return self._by_acct.get(acct_id)


class TranRepository:
    def __init__(self, transactions: list[TranRecord]):
        self._trans = sorted(transactions, key=lambda t: t.tran_id)

    def next_id(self) -> str:
        if not self._trans:
            return "0000000000000001"
        last_id = self._trans[-1].tran_id.strip()
        try:
            return str(int(last_id) + 1).zfill(16)
        except ValueError:
            return "0000000000000001"

    def write(self, tran: TranRecord) -> bool:
        self._trans.append(tran)
        self._trans.sort(key=lambda t: t.tran_id)
        return True


def process_bill_pay(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    acct_id_input: str,
    confirm: str,
    acct_repo: AccountRepository,
    xref_repo: XrefRepository,
    tran_repo: TranRepository,
) -> BillPayResult:
    """Process bill payment screen — mirrors COBIL00C PROCEDURE DIVISION."""
    result = BillPayResult()

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
        return _process_enter(acct_id_input, confirm, acct_repo, xref_repo, tran_repo, commarea, result)
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
    else:
        result.error = True
        result.message = CCDA_MSG_INVALID_KEY
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result


def _process_enter(acct_id_input, confirm, acct_repo, xref_repo, tran_repo, commarea, result):
    if not acct_id_input or acct_id_input.strip() == "":
        result.error = True
        result.message = "Acct ID can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    try:
        acct_id = int(acct_id_input.strip())
    except ValueError:
        result.error = True
        result.message = "Acct ID must be numeric..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    conf = confirm.strip().upper() if confirm else ""

    if conf in ("N",):
        result.cleared = True
        result.error = True
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.commarea = commarea
        return result
    elif conf not in ("Y", "", "\x00"):
        result.error = True
        result.message = "Invalid value. Valid values are (Y/N)..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    acct = acct_repo.find(acct_id)
    if acct is None:
        result.error = True
        result.message = f"Account {acct_id} not found..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    result.acct_record = acct

    if acct.acct_curr_bal <= Decimal("0.00"):
        result.error = True
        result.message = "You have nothing to pay..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    if conf == "Y":
        xref = xref_repo.find_by_acct(acct_id)
        card_num = xref.xref_card_num.strip() if xref else ""
        ts = get_db2_timestamp()

        tran = TranRecord(
            tran_id=tran_repo.next_id(),
            tran_type_cd=BILL_PAY_TYPE_CD,
            tran_cat_cd=BILL_PAY_CAT_CD,
            tran_source=BILL_PAY_SOURCE,
            tran_desc=BILL_PAY_DESC,
            tran_amt=acct.acct_curr_bal,
            tran_card_num=card_num,
            tran_merchant_id=BILL_PAY_MERCHANT_ID,
            tran_merchant_name=BILL_PAY_MERCHANT_NAME,
            tran_merchant_city=BILL_PAY_MERCHANT_CITY,
            tran_merchant_zip=BILL_PAY_MERCHANT_ZIP,
            tran_orig_ts=ts,
            tran_proc_ts=ts,
        )
        tran_repo.write(tran)
        acct.acct_curr_bal = acct.acct_curr_bal - tran.tran_amt
        acct_repo.rewrite(acct)

        result.success = True
        result.tran_record = tran
        result.message = "Bill payment successful."
    else:
        result.message = "Confirm to make a bill payment..."

    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    result.commarea = commarea
    return result

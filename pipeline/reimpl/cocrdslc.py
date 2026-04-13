"""
Reimplementation of COCRDSLC — CardDemo Credit Card View/Select Screen.

CICS online program. Displays full detail of a credit card by card number.
Also shows the associated account and customer information.

Navigation:
  ENTER → look up card by number
  PF3   → return to calling program
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader, CardRecord, AccountRecord,
    CustomerRecord, CardXrefRecord,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3,
)


WS_PGMNAME = "COCRDSLC"
WS_TRANID  = "CCDL"


@dataclass
class CardDetailData:
    card_num: str = ""
    card_acct_id: int = 0
    card_cvv: int = 0
    card_embossed_name: str = ""
    card_expiration_date: str = ""
    card_active_status: str = ""
    acct_curr_bal: str = ""
    acct_credit_limit: str = ""
    cust_name: str = ""
    cust_id: int = 0


@dataclass
class CardViewResult:
    card_data: Optional[CardDetailData] = None
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    xctl_program: str = ""
    return_to_prev: bool = False


class CardRepository:
    def __init__(self, cards: dict[str, CardRecord]):
        self._cards = cards  # keyed by card_num

    def find(self, card_num: str) -> Optional[CardRecord]:
        return self._cards.get(card_num.strip())


class AccountRepository:
    def __init__(self, accounts: dict[int, AccountRecord]):
        self._accounts = accounts

    def find(self, acct_id: int) -> Optional[AccountRecord]:
        return self._accounts.get(acct_id)


class XrefRepository:
    def __init__(self, xrefs: dict[str, CardXrefRecord]):
        self._by_card = xrefs

    def find_by_card(self, card_num: str) -> Optional[CardXrefRecord]:
        return self._by_card.get(card_num.strip())


class CustomerRepository:
    def __init__(self, customers: dict[int, CustomerRecord]):
        self._customers = customers

    def find(self, cust_id: int) -> Optional[CustomerRecord]:
        return self._customers.get(cust_id)


def process_card_view(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    card_num_input: str,
    card_repo: CardRepository,
    account_repo: AccountRepository,
    xref_repo: XrefRepository,
    customer_repo: CustomerRepository,
    preloaded_card_num: str = "",
) -> CardViewResult:
    """Process card view screen — mirrors COCRDSLC PROCEDURE DIVISION."""
    result = CardViewResult()

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

    if commarea.cdemo_pgm_context == 0:
        commarea.cdemo_pgm_context = 1
        search_num = preloaded_card_num or card_num_input
        if search_num.strip():
            _lookup_card(search_num, card_repo, account_repo, xref_repo, customer_repo, result)
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.commarea = commarea
        return result

    return _process_enter(
        card_num_input, card_repo, account_repo, xref_repo, customer_repo, commarea, result
    )


def _process_enter(card_num_input, card_repo, account_repo, xref_repo, customer_repo, commarea, result):
    if not card_num_input or card_num_input.strip() == "":
        result.error = True
        result.message = "Card number not provided"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    _lookup_card(card_num_input, card_repo, account_repo, xref_repo, customer_repo, result)
    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    result.commarea = commarea
    return result


def _lookup_card(card_num, card_repo, account_repo, xref_repo, customer_repo, result):
    card = card_repo.find(card_num)
    if card is None:
        result.error = True
        result.message = f"Card {card_num.strip()} not found"
        return

    acct = account_repo.find(card.card_acct_id)
    xref = xref_repo.find_by_card(card.card_num)
    cust = None
    if xref:
        cust = customer_repo.find(xref.xref_cust_id)

    result.card_data = CardDetailData(
        card_num=card.card_num,
        card_acct_id=card.card_acct_id,
        card_cvv=card.card_cvv_cd,
        card_embossed_name=card.card_embossed_name.strip(),
        card_expiration_date=card.card_expiration_date,
        card_active_status=card.card_active_status,
        acct_curr_bal=f"{float(acct.acct_curr_bal):,.2f}" if acct else "",
        acct_credit_limit=f"{float(acct.acct_credit_limit):,.2f}" if acct else "",
        cust_name=(f"{cust.cust_first_name.strip()} {cust.cust_last_name.strip()}" if cust else ""),
        cust_id=cust.cust_id if cust else 0,
    )
    result.message = "Card record found"


# ── Differential harness runner adapter ──────────────────────────────────────

_SEED_CARDS: dict[str, CardRecord] = {
    "4111111111110001": CardRecord(card_num="4111111111110001", card_acct_id=10000001, card_cvv_cd=123,
                                   card_embossed_name="JANE USER", card_expiration_date="2028-12-31",
                                   card_active_status="Y"),
    "4111111111110002": CardRecord(card_num="4111111111110002", card_acct_id=10000001, card_cvv_cd=456,
                                   card_embossed_name="BOB SMITH", card_expiration_date="2027-06-30",
                                   card_active_status="Y"),
}

_SEED_ACCOUNTS: dict[int, AccountRecord] = {
    10000001: AccountRecord(acct_id=10000001, acct_active_status="Y",
                            acct_curr_bal=1500.00, acct_credit_limit=5000.00),
}

_SEED_XREFS: dict[str, CardXrefRecord] = {
    "4111111111110001": CardXrefRecord(xref_card_num="4111111111110001", xref_cust_id=100001, xref_acct_id=10000001),
    "4111111111110002": CardXrefRecord(xref_card_num="4111111111110002", xref_cust_id=100001, xref_acct_id=10000001),
}

_SEED_CUSTOMERS: dict[int, CustomerRecord] = {
    100001: CustomerRecord(cust_id=100001, cust_first_name="Jane", cust_last_name="User",
                           cust_ssn=123456789, cust_dob_yyyy_mm_dd="1985-03-15",
                           cust_fico_credit_score=750, cust_addr_zip="10001",
                           cust_phone_num_1="212-555-0100", cust_phone_num_2="212-555-0101"),
}


def run_vector(inputs: dict) -> dict:
    """Canonical runner entry point for the differential harness.

    SCENARIO selects a hardcoded test path:
      FIRST_ENTRY    — context=0, preloaded card → display detail
      LOOKUP_CARD    — ENTER with card number → display detail
      CARD_NOT_FOUND — ENTER with bad card number → error
      PF3_RETURN     — press PF3 → return to menu
    """
    scenario = inputs.get("SCENARIO", "FIRST_ENTRY")

    card_repo = CardRepository(dict(_SEED_CARDS))
    account_repo = AccountRepository(dict(_SEED_ACCOUNTS))
    xref_repo = XrefRepository(dict(_SEED_XREFS))
    customer_repo = CustomerRepository(dict(_SEED_CUSTOMERS))

    commarea = CarddemoCommarea(
        cdemo_from_tranid="CCLI",
        cdemo_from_program="COCRDLIC",
        cdemo_user_id="USER0001",
        cdemo_user_type="U",
        cdemo_pgm_context=1,
    )

    if scenario == "FIRST_ENTRY":
        commarea.cdemo_pgm_context = 0
        result = process_card_view(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            card_num_input="", card_repo=card_repo,
            account_repo=account_repo, xref_repo=xref_repo,
            customer_repo=customer_repo,
            preloaded_card_num="4111111111110001",
        )
    elif scenario == "LOOKUP_CARD":
        result = process_card_view(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            card_num_input="4111111111110002", card_repo=card_repo,
            account_repo=account_repo, xref_repo=xref_repo,
            customer_repo=customer_repo,
        )
    elif scenario == "CARD_NOT_FOUND":
        result = process_card_view(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            card_num_input="9999999999999999", card_repo=card_repo,
            account_repo=account_repo, xref_repo=xref_repo,
            customer_repo=customer_repo,
        )
    elif scenario == "PF3_RETURN":
        result = process_card_view(
            eibcalen=100, eibaid="PF3", commarea=commarea,
            card_num_input="", card_repo=card_repo,
            account_repo=account_repo, xref_repo=xref_repo,
            customer_repo=customer_repo,
        )
    else:
        commarea.cdemo_pgm_context = 0
        result = process_card_view(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            card_num_input="", card_repo=card_repo,
            account_repo=account_repo, xref_repo=xref_repo,
            customer_repo=customer_repo,
            preloaded_card_num="4111111111110001",
        )

    card_num_out = ""
    acct_id_out = ""
    embossed_name_out = ""
    cust_name_out = ""
    acct_curr_bal_out = ""
    if result.card_data:
        card_num_out = result.card_data.card_num
        acct_id_out = str(result.card_data.card_acct_id)
        embossed_name_out = result.card_data.card_embossed_name
        cust_name_out = result.card_data.cust_name
        acct_curr_bal_out = result.card_data.acct_curr_bal

    return {
        "ERROR": "Y" if result.error else "N",
        "MESSAGE": result.message,
        "XCTL_PROGRAM": result.xctl_program or "",
        "RETURN_TO_PREV": "Y" if result.return_to_prev else "N",
        "CARD_NUM": card_num_out,
        "ACCT_ID": acct_id_out,
        "EMBOSSED_NAME": embossed_name_out,
        "CUST_NAME": cust_name_out,
        "ACCT_CURR_BAL": acct_curr_bal_out,
    }

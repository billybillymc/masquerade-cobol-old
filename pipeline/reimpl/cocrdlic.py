"""
Reimplementation of COCRDLIC — CardDemo Credit Card List Screen.

CICS online program. Lists credit cards (7 per page) with filtering options:
  - Admin users: can see all cards or filter by account/card number
  - Regular users: see only cards for their own account

Selection codes:
  S = View card detail → COCRDSLC
  U = Update card       → COCRDUPC

Navigation: PF3=exit, PF7=prev page, PF8=next page
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader, CardRecord,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3, DFHPF7, DFHPF8,
)


WS_PGMNAME = "COCRDLIC"
WS_TRANID  = "CCLI"
PAGE_SIZE  = 7


@dataclass
class CardListRow:
    card_num: str = ""
    acct_id: int = 0
    embossed_name: str = ""
    expiration_date: str = ""
    active_status: str = ""
    sel_flag: str = ""


@dataclass
class CardListResult:
    rows: list[CardListRow] = field(default_factory=list)
    page_num: int = 1
    has_next_page: bool = False
    has_prev_page: bool = False
    xctl_program: str = ""
    selected_card_num: str = ""
    selected_action: str = ""
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    return_to_prev: bool = False


class CardRepository:
    def __init__(self, cards: list[CardRecord]):
        self._all = sorted(cards, key=lambda c: c.card_num)

    def get_page(
        self,
        page_num: int,
        acct_filter: int = 0,
        card_filter: str = "",
    ) -> tuple[list[CardRecord], bool]:
        cards = self._all
        if acct_filter:
            cards = [c for c in cards if c.card_acct_id == acct_filter]
        if card_filter.strip():
            cards = [c for c in cards if c.card_num.startswith(card_filter.strip())]
        start = (page_num - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        return cards[start:end], len(cards) > end


def process_card_list(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    card_repo: CardRepository,
    page_num: int = 1,
    acct_filter: int = 0,
    card_filter: str = "",
    selected_rows: list[tuple[str, str]] = None,
) -> CardListResult:
    """Process credit card list — mirrors COCRDLIC PROCEDURE DIVISION."""
    result = CardListResult()

    if eibcalen == 0:
        result.return_to_prev = True
        result.xctl_program = "COSGN00C"
        return result

    result.commarea = commarea

    if commarea.cdemo_pgm_context == 0:
        commarea.cdemo_pgm_context = 1
        return _load_page(page_num, acct_filter, card_filter, card_repo, commarea, result)

    if eibaid in (DFHENTER, "ENTER"):
        return _process_enter(
            selected_rows or [], page_num, acct_filter, card_filter,
            card_repo, commarea, result,
        )
    elif eibaid in (DFHPF3, "PF3"):
        back = commarea.cdemo_from_program or "COMEN01C"
        result.xctl_program = back
        result.return_to_prev = True
        result.commarea = commarea
        return result
    elif eibaid in (DFHPF7, "PF7"):
        return _load_page(max(1, page_num - 1), acct_filter, card_filter, card_repo, commarea, result)
    elif eibaid in (DFHPF8, "PF8"):
        return _load_page(page_num + 1, acct_filter, card_filter, card_repo, commarea, result)
    else:
        result.error = True
        result.message = CCDA_MSG_INVALID_KEY
        return _load_page(page_num, acct_filter, card_filter, card_repo, commarea, result)


def _load_page(page_num, acct_filter, card_filter, repo, commarea, result):
    cards, has_next = repo.get_page(page_num, acct_filter, card_filter)
    result.page_num = page_num
    result.has_next_page = has_next
    result.has_prev_page = page_num > 1
    result.rows = [
        CardListRow(
            card_num=c.card_num,
            acct_id=c.card_acct_id,
            embossed_name=c.card_embossed_name.strip(),
            expiration_date=c.card_expiration_date,
            active_status=c.card_active_status,
        )
        for c in cards
    ]
    if not cards:
        result.error = True
        result.message = "NO RECORDS FOUND FOR THIS SEARCH CONDITION."
    else:
        result.message = "TYPE S FOR DETAIL, U TO UPDATE ANY RECORD"
    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    result.commarea = commarea
    return result


def _process_enter(selected_rows, page_num, acct_filter, card_filter, repo, commarea, result):
    selections = [(f, c) for f, c in selected_rows if f and f.strip() not in ("", "\x00") and c.strip()]
    if len(selections) > 1:
        result.error = True
        result.message = "PLEASE SELECT ONLY ONE RECORD TO VIEW OR UPDATE"
        return _load_page(page_num, acct_filter, card_filter, repo, commarea, result)

    if selections:
        action, card_num = selections[0]
        a = action.strip().upper()
        if a not in ("S", "U"):
            result.error = True
            result.message = "INVALID ACTION CODE"
            return _load_page(page_num, acct_filter, card_filter, repo, commarea, result)

        result.selected_card_num = card_num.strip()
        result.selected_action = a
        commarea.cdemo_pgm_context = 0

        if a == "S":
            result.xctl_program = "COCRDSLC"
        else:
            result.xctl_program = "COCRDUPC"
        result.commarea = commarea
        return result

    return _load_page(page_num, acct_filter, card_filter, repo, commarea, result)

"""
Reimplementation of COCRDUPC — CardDemo Credit Card Update Screen.

CICS online program. Reads an existing credit card for display,
then allows updating specific fields (embossed name, expiration date,
active status, CVV).

Navigation:
  ENTER  → look up card by number
  PF3    → return to calling program
  PF5    → save changes
  PF12   → return to card list without saving
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader, CardRecord,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3, DFHPF5, DFHPF12,
)


WS_PGMNAME = "COCRDUPC"
WS_TRANID  = "CCUP"

DFHRESP_NORMAL = 0
DFHRESP_NOTFND = 13


@dataclass
class CardUpdateInput:
    card_num: str = ""
    embossed_name: str = ""
    expiration_date: str = ""
    active_status: str = ""
    cvv_cd: str = ""


@dataclass
class CardUpdateResult:
    card_found: Optional[CardRecord] = None
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    success: bool = False
    xctl_program: str = ""
    return_to_prev: bool = False


class CardRepository:
    def __init__(self, cards: dict[str, CardRecord]):
        self._cards = cards

    def find(self, card_num: str) -> Optional[CardRecord]:
        return self._cards.get(card_num.strip())

    def rewrite(self, card: CardRecord) -> int:
        key = card.card_num.strip()
        if key not in self._cards:
            return DFHRESP_NOTFND
        self._cards[key] = card
        return DFHRESP_NORMAL


def process_card_update(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    card_input: CardUpdateInput,
    card_repo: CardRepository,
    preloaded_card_num: str = "",
) -> CardUpdateResult:
    """Process card update screen — mirrors COCRDUPC PROCEDURE DIVISION."""
    result = CardUpdateResult()

    if eibcalen == 0:
        result.return_to_prev = True
        result.xctl_program = "COSGN00C"
        return result

    result.commarea = commarea

    if commarea.cdemo_pgm_context == 0:
        commarea.cdemo_pgm_context = 1
        if preloaded_card_num:
            card = card_repo.find(preloaded_card_num)
            result.card_found = card
            if card is None:
                result.error = True
                result.message = f"Card {preloaded_card_num.strip()} not found"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.commarea = commarea
        return result

    if eibaid in (DFHENTER, "ENTER"):
        return _lookup_card(card_input.card_num, card_repo, commarea, result)
    elif eibaid in (DFHPF3, "PF3"):
        back = commarea.cdemo_from_program or "COMEN01C"
        result.xctl_program = back
        result.return_to_prev = True
        result.commarea = commarea
        return result
    elif eibaid in (DFHPF5, "PF5"):
        return _save_card(card_input, card_repo, commarea, result)
    elif eibaid in (DFHPF12, "PF12"):
        result.xctl_program = "COCRDLIC"
        result.return_to_prev = True
        commarea.cdemo_to_program = "COCRDLIC"
        result.commarea = commarea
        return result
    else:
        result.error = True
        result.message = CCDA_MSG_INVALID_KEY
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result


def _lookup_card(card_num, repo, commarea, result):
    if not card_num or card_num.strip() == "":
        result.error = True
        result.message = "Card number can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    card = repo.find(card_num)
    if card is None:
        result.error = True
        result.message = f"Card {card_num.strip()} not found"
    else:
        result.card_found = card
        result.message = "Press PF5 to save changes"

    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    result.commarea = commarea
    return result


def _save_card(inp, repo, commarea, result):
    if not inp.card_num or inp.card_num.strip() == "":
        result.error = True
        result.message = "Card number can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    card = repo.find(inp.card_num)
    if card is None:
        result.error = True
        result.message = f"Card {inp.card_num.strip()} not found"
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    # Apply updates
    if inp.embossed_name.strip():
        card.card_embossed_name = inp.embossed_name[:50]
    if inp.expiration_date.strip():
        card.card_expiration_date = inp.expiration_date[:10]
    if inp.active_status.strip():
        card.card_active_status = inp.active_status.strip()[0]
    if inp.cvv_cd.strip():
        try:
            card.card_cvv_cd = int(inp.cvv_cd.strip())
        except ValueError:
            result.error = True
            result.message = "CVV must be numeric"
            result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
            result.screen.errmsg = result.message
            result.commarea = commarea
            return result

    resp = repo.rewrite(card)
    if resp == DFHRESP_NORMAL:
        result.success = True
        result.card_found = card
        result.message = f"Card {card.card_num.strip()} has been updated ..."
    else:
        result.error = True
        result.message = "Unable to update card..."

    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    result.commarea = commarea
    return result


# ── Differential harness runner adapter ──────────────────────────────────────

_SEED_CARDS: dict[str, CardRecord] = {
    "4111111111110001": CardRecord(card_num="4111111111110001", card_acct_id=10000001, card_cvv_cd=123,
                                   card_embossed_name="JANE USER", card_expiration_date="2028-12-31",
                                   card_active_status="Y"),
    "4111111111110002": CardRecord(card_num="4111111111110002", card_acct_id=10000001, card_cvv_cd=456,
                                   card_embossed_name="BOB SMITH", card_expiration_date="2027-06-30",
                                   card_active_status="Y"),
}


def run_vector(inputs: dict) -> dict:
    """Canonical runner entry point for the differential harness.

    SCENARIO selects a hardcoded test path:
      FIRST_ENTRY    — context=0, preloaded card → display card
      LOOKUP_CARD    — ENTER with card number → find card
      UPDATE_CARD    — PF5 with updated fields → save
      CARD_NOT_FOUND — ENTER with bad card number → error
      PF3_RETURN     — press PF3 → return to previous
    """
    scenario = inputs.get("SCENARIO", "FIRST_ENTRY")

    import copy
    repo = CardRepository(copy.deepcopy(_SEED_CARDS))

    commarea = CarddemoCommarea(
        cdemo_from_tranid="CCLI",
        cdemo_from_program="COCRDLIC",
        cdemo_user_id="USER0001",
        cdemo_user_type="U",
        cdemo_pgm_context=1,
    )

    if scenario == "FIRST_ENTRY":
        commarea.cdemo_pgm_context = 0
        result = process_card_update(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            card_input=CardUpdateInput(), card_repo=repo,
            preloaded_card_num="4111111111110001",
        )
    elif scenario == "LOOKUP_CARD":
        result = process_card_update(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            card_input=CardUpdateInput(card_num="4111111111110001"),
            card_repo=repo,
        )
    elif scenario == "UPDATE_CARD":
        result = process_card_update(
            eibcalen=100, eibaid="PF5", commarea=commarea,
            card_input=CardUpdateInput(
                card_num="4111111111110001", embossed_name="JANE UPDATED",
                expiration_date="2029-12-31", active_status="Y", cvv_cd="999",
            ),
            card_repo=repo,
        )
    elif scenario == "CARD_NOT_FOUND":
        result = process_card_update(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            card_input=CardUpdateInput(card_num="9999999999999999"),
            card_repo=repo,
        )
    elif scenario == "PF3_RETURN":
        result = process_card_update(
            eibcalen=100, eibaid="PF3", commarea=commarea,
            card_input=CardUpdateInput(), card_repo=repo,
        )
    else:
        commarea.cdemo_pgm_context = 0
        result = process_card_update(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            card_input=CardUpdateInput(), card_repo=repo,
            preloaded_card_num="4111111111110001",
        )

    card_num_out = ""
    embossed_name_out = ""
    if result.card_found:
        card_num_out = result.card_found.card_num
        embossed_name_out = result.card_found.card_embossed_name

    return {
        "ERROR": "Y" if result.error else "N",
        "SUCCESS": "Y" if result.success else "N",
        "MESSAGE": result.message,
        "XCTL_PROGRAM": result.xctl_program or "",
        "RETURN_TO_PREV": "Y" if result.return_to_prev else "N",
        "CARD_NUM": card_num_out,
        "EMBOSSED_NAME": embossed_name_out,
    }

"""
Reimplementation of COTRN00C — CardDemo Transaction List Screen.

CICS online program. Lists transactions (10 per page) from the TRANSACT file,
with PF7/PF8 navigation and selection to view a transaction detail.

Selection: Enter 'S' in a row's selector to view that transaction → COTRN01C
"""

from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader, TranRecord,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3, DFHPF7, DFHPF8,
)


WS_PGMNAME = "COTRN00C"
WS_TRANID  = "CT00"
PAGE_SIZE  = 10


@dataclass
class TranListRow:
    tran_id: str = ""
    tran_type_cd: str = ""
    tran_cat_cd: int = 0
    tran_source: str = ""
    tran_desc: str = ""
    tran_amt: Decimal = Decimal("0.00")
    tran_card_num: str = ""
    tran_proc_ts: str = ""
    sel_flag: str = ""


@dataclass
class TranListResult:
    rows: list[TranListRow] = field(default_factory=list)
    page_num: int = 1
    has_next_page: bool = False
    has_prev_page: bool = False
    xctl_program: str = ""
    selected_tran_id: str = ""
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    return_to_prev: bool = False


class TranRepository:
    def __init__(self, transactions: list[TranRecord]):
        self._trans = sorted(transactions, key=lambda t: t.tran_id)

    def get_page(self, page_num: int) -> tuple[list[TranRecord], bool]:
        start = (page_num - 1) * PAGE_SIZE
        end = start + PAGE_SIZE
        return self._trans[start:end], len(self._trans) > end


def process_tran_list(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    tran_repo: TranRepository,
    page_num: int = 1,
    selected_rows: list[tuple[str, str]] = None,
) -> TranListResult:
    """Process transaction list screen — mirrors COTRN00C PROCEDURE DIVISION."""
    result = TranListResult()

    if eibcalen == 0:
        result.return_to_prev = True
        result.xctl_program = "COSGN00C"
        return result

    result.commarea = commarea

    if commarea.cdemo_pgm_context == 0:
        commarea.cdemo_pgm_context = 1
        return _load_page(1, tran_repo, commarea, result)

    if eibaid in (DFHENTER, "ENTER"):
        return _process_enter(selected_rows or [], page_num, tran_repo, commarea, result)
    elif eibaid in (DFHPF3, "PF3"):
        back = commarea.cdemo_from_program or "COMEN01C"
        result.xctl_program = back
        result.return_to_prev = True
        result.commarea = commarea
        return result
    elif eibaid in (DFHPF7, "PF7"):
        return _load_page(max(1, page_num - 1), tran_repo, commarea, result)
    elif eibaid in (DFHPF8, "PF8"):
        return _load_page(page_num + 1, tran_repo, commarea, result)
    else:
        result.error = True
        result.message = CCDA_MSG_INVALID_KEY
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return _load_page(page_num, tran_repo, commarea, result)


def _load_page(page_num, repo, commarea, result):
    trans, has_next = repo.get_page(page_num)
    result.page_num = page_num
    result.has_next_page = has_next
    result.has_prev_page = page_num > 1
    result.rows = [
        TranListRow(
            tran_id=t.tran_id,
            tran_type_cd=t.tran_type_cd,
            tran_cat_cd=t.tran_cat_cd,
            tran_source=t.tran_source,
            tran_desc=t.tran_desc[:40],
            tran_amt=t.tran_amt,
            tran_card_num=t.tran_card_num,
            tran_proc_ts=t.tran_proc_ts[:10],
        )
        for t in trans
    ]
    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.commarea = commarea
    return result


def _process_enter(selected_rows, page_num, repo, commarea, result):
    for sel_flag, tran_id in selected_rows:
        if sel_flag and sel_flag.strip() not in ("", "\x00") and tran_id.strip():
            result.selected_tran_id = tran_id.strip()
            commarea.cdemo_pgm_context = 0
            result.xctl_program = "COTRN01C"
            result.commarea = commarea
            return result
    return _load_page(page_num, repo, commarea, result)

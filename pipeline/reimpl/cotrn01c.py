"""
Reimplementation of COTRN01C — CardDemo Transaction View Screen.

CICS online program. Displays details of a single transaction by ID.
Transaction ID may be passed via commarea (from list screen selection)
or typed by the user.

Navigation:
  ENTER  → look up transaction by ID
  PF3    → return to calling program
  PF4    → clear screen
  PF5    → return to transaction list (COTRN00C)
"""

from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from .carddemo_data import (
    CarddemoCommarea, ScreenHeader, TranRecord,
    CCDA_MSG_INVALID_KEY, DFHENTER, DFHPF3, DFHPF4, DFHPF5,
)


WS_PGMNAME = "COTRN01C"
WS_TRANID  = "CT01"


@dataclass
class TranViewResult:
    tran_record: Optional[TranRecord] = None
    commarea: Optional[CarddemoCommarea] = None
    screen: Optional[ScreenHeader] = None
    message: str = ""
    error: bool = False
    xctl_program: str = ""
    return_to_prev: bool = False
    cleared: bool = False


class TranRepository:
    def __init__(self, transactions: dict[str, TranRecord]):
        self._trans = transactions  # keyed by tran_id

    def find(self, tran_id: str) -> Optional[TranRecord]:
        return self._trans.get(tran_id.strip())


def process_tran_view(
    eibcalen: int,
    eibaid: str,
    commarea: CarddemoCommarea,
    tran_id_input: str,
    tran_repo: TranRepository,
    preloaded_tran_id: str = "",
) -> TranViewResult:
    """Process transaction view screen — mirrors COTRN01C PROCEDURE DIVISION."""
    result = TranViewResult()

    if eibcalen == 0:
        result.return_to_prev = True
        result.xctl_program = "COSGN00C"
        return result

    result.commarea = commarea

    if commarea.cdemo_pgm_context == 0:
        commarea.cdemo_pgm_context = 1
        if preloaded_tran_id and preloaded_tran_id.strip():
            _lookup_tran(preloaded_tran_id, tran_repo, result)
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    if eibaid in (DFHENTER, "ENTER"):
        return _process_enter(tran_id_input, tran_repo, commarea, result)
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
        result.xctl_program = "COTRN00C"
        result.return_to_prev = True
        result.commarea = commarea
        return result
    else:
        result.error = True
        result.message = CCDA_MSG_INVALID_KEY
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result


def _process_enter(tran_id_input, repo, commarea, result):
    if not tran_id_input or tran_id_input.strip() == "":
        result.error = True
        result.message = "Tran ID can NOT be empty..."
        result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
        result.screen.errmsg = result.message
        result.commarea = commarea
        return result

    _lookup_tran(tran_id_input, repo, result)
    result.screen = ScreenHeader.now(WS_TRANID, WS_PGMNAME)
    result.screen.errmsg = result.message
    result.commarea = commarea
    return result


def _lookup_tran(tran_id, repo, result):
    tran = repo.find(tran_id)
    if tran is None:
        result.error = True
        result.message = "Transaction ID NOT found..."
    else:
        result.tran_record = tran
        result.message = ""

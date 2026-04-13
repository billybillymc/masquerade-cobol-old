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


# ── Differential harness runner adapter ──────────────────────────────────────

_SEED_TRANS = {
    "0000000000000001": TranRecord(
        tran_id="0000000000000001", tran_type_cd="01", tran_cat_cd=1,
        tran_source="ONLINE", tran_desc="PURCHASE AT STORE",
        tran_amt=Decimal("125.50"), tran_card_num="4111111111111111",
        tran_merchant_id=100001, tran_merchant_name="ACME STORE",
        tran_merchant_city="NEW YORK", tran_merchant_zip="10001",
        tran_orig_ts="2025-01-10-09.00.00.000000",
        tran_proc_ts="2025-01-10-09.05.00.000000",
    ),
    "0000000000000002": TranRecord(
        tran_id="0000000000000002", tran_type_cd="02", tran_cat_cd=2,
        tran_source="POS TERM", tran_desc="BILL PAYMENT",
        tran_amt=Decimal("500.00"), tran_card_num="4222222222222222",
        tran_merchant_id=100002, tran_merchant_name="UTILITY CO",
        tran_merchant_city="CHICAGO", tran_merchant_zip="60601",
        tran_orig_ts="2025-01-12-14.30.00.000000",
        tran_proc_ts="2025-01-12-14.35.00.000000",
    ),
}


def run_vector(inputs: dict) -> dict:
    """Canonical runner entry point for the differential harness.

    SCENARIO selects a hardcoded test path:
      VIEW_FOUND      — look up existing transaction → display details
      VIEW_NOT_FOUND  — look up non-existent transaction → error
      EMPTY_TRAN_ID   — empty transaction ID → error
      INVALID_KEY     — press PF9 → invalid key error
      PF3_RETURN      — press PF3 → return to calling program
    """
    scenario = inputs.get("SCENARIO", "VIEW_FOUND")

    repo = TranRepository(dict(_SEED_TRANS))

    commarea = CarddemoCommarea(
        cdemo_from_tranid="CM00",
        cdemo_from_program="COMEN01C",
        cdemo_user_id="USER0001",
        cdemo_user_type="U",
        cdemo_pgm_context=1,
    )

    if scenario == "VIEW_FOUND":
        result = process_tran_view(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            tran_id_input="0000000000000001", tran_repo=repo,
        )
    elif scenario == "VIEW_NOT_FOUND":
        result = process_tran_view(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            tran_id_input="9999999999999999", tran_repo=repo,
        )
    elif scenario == "EMPTY_TRAN_ID":
        result = process_tran_view(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            tran_id_input="", tran_repo=repo,
        )
    elif scenario == "INVALID_KEY":
        result = process_tran_view(
            eibcalen=100, eibaid="PF9", commarea=commarea,
            tran_id_input="", tran_repo=repo,
        )
    elif scenario == "PF3_RETURN":
        result = process_tran_view(
            eibcalen=100, eibaid="PF3", commarea=commarea,
            tran_id_input="", tran_repo=repo,
        )
    else:
        result = process_tran_view(
            eibcalen=100, eibaid="ENTER", commarea=commarea,
            tran_id_input="0000000000000001", tran_repo=repo,
        )

    tran_id = ""
    tran_type = ""
    tran_amt = ""
    tran_desc = ""
    tran_card = ""
    tran_merchant = ""
    if result.tran_record:
        tran_id = result.tran_record.tran_id
        tran_type = result.tran_record.tran_type_cd
        tran_amt = f"{result.tran_record.tran_amt:.2f}"
        tran_desc = result.tran_record.tran_desc
        tran_card = result.tran_record.tran_card_num
        tran_merchant = result.tran_record.tran_merchant_name

    return {
        "ERROR": "Y" if result.error else "N",
        "MESSAGE": result.message,
        "XCTL_PROGRAM": result.xctl_program or "",
        "TRAN_ID": tran_id,
        "TRAN_TYPE": tran_type,
        "TRAN_AMT": tran_amt,
        "TRAN_DESC": tran_desc,
        "TRAN_CARD": tran_card,
        "TRAN_MERCHANT": tran_merchant,
    }
